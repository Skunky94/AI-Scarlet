"""
PAD Subconscious Evaluator v3 — Transformer Sentiment + Regole
==============================================================
Architettura ibrida:
- SentimentAnalyzer: HuggingFace Transformer (DistilBERT multilingue) su GPU, pre-hot
- IntentClassifier: pattern-based, classifica il tipo di interazione
- PersonalityMatrix: mappa (intent x sentiment) -> delta PAD calibrati su Scarlet

Performance: ~5ms per valutazione su GPU (RTX 4070 Ti SUPER).
Modello: tabularisai/multilingual-sentiment-analysis (~66M params, ~540MB)
"""

import re
import time
from typing import Tuple
from dataclasses import dataclass
from enum import Enum
from scarlet_observability import get_logger

log = get_logger("pad.subconscious")


# ============================================================
# 1. SENTIMENT ANALYSIS — Transformer su GPU
# ============================================================

@dataclass
class Sentiment:
    polarity: float    # -1.0 (molto negativo) a +1.0 (molto positivo)
    intensity: float   # 0.0 (neutro) a 1.0 (molto intenso)
    label: str         # Label testuale dal modello

# Mapping label -> (polarity, intensity)
_LABEL_MAP = {
    "Very Negative": (-0.9, 0.9),
    "Negative":      (-0.5, 0.6),
    "Neutral":       ( 0.0, 0.1),
    "Positive":      ( 0.4, 0.5),
    "Very Positive": ( 0.8, 0.9),
}


class TransformerSentiment:
    """Sentiment analyzer basato su DistilBERT multilingue, pre-caricato su GPU."""
    
    def __init__(self):
        import torch
        from transformers import pipeline

        self.device = 0 if torch.cuda.is_available() else -1
        device_name = torch.cuda.get_device_name(0) if self.device == 0 else "CPU"

        log.info(f"Caricamento modello sentiment | device={device_name} cuda={self.device >= 0}")
        t0 = time.time()

        self.analyzer = pipeline(
            "text-classification",
            model="tabularisai/multilingual-sentiment-analysis",
            device=self.device,
            top_k=None
        )

        # Warmup: prima inferenza per pre-compilare CUDA kernels
        _ = self.analyzer("warmup")
        load_time = time.time() - t0
        log.info(f"Modello sentiment pronto | load_time_s={load_time:.1f} device={device_name} warmup=OK")
    
    def analyze(self, text: str) -> Sentiment:
        """Analizza il sentiment del testo. ~4ms su GPU warm."""
        log.debug(f"Transformer analyze | input_len={len(text)} preview={text[:80]!r}")
        t0 = time.time()
        result = self.analyzer(text)
        elapsed_ms = (time.time() - t0) * 1000

        # result[0] e' una lista di dicts con 'label' e 'score'
        all_scores = {r['label']: round(r['score'], 4) for r in result[0]}
        top = max(result[0], key=lambda x: x['score'])
        label = top['label']
        confidence = top['score']

        base_polarity, base_intensity = _LABEL_MAP.get(label, (0.0, 0.1))

        # Scala per confidence del modello
        polarity = base_polarity * confidence
        intensity = base_intensity * confidence

        log.debug(f"Transformer scores | all={all_scores}")
        log.info(
            f"Sentiment | label={label!r} confidence={confidence:.4f}"
            f" polarity={polarity:+.3f} intensity={intensity:.3f} elapsed_ms={elapsed_ms:.1f}"
        )

        return Sentiment(polarity=polarity, intensity=intensity, label=label)


# ============================================================
# 2. INTENT CLASSIFICATION (pattern-based, italiano)
# ============================================================

class Intent(Enum):
    SALUTO = "saluto"
    DOMANDA = "domanda"
    ORDINE = "ordine"
    INSULTO = "insulto"
    COMPLIMENTO = "complimento"
    STIMOLO_INTELLETTUALE = "stimolo_intellettuale"
    AFFERMAZIONE = "affermazione"

_INSULTO_PATTERNS = [
    r"\bstupid[ao]?\b", r"\bidiot[ao]?\b", r"\bimbecille\b", r"\bcretino[ao]?\b",
    r"\bfai schifo\b", r"\binutile\b", r"\bincapace\b", r"\bignorante\b",
    r"\bscem[ao]?\b", r"\bdeficiente\b", r"\bpatetico[ao]?\b", r"\bvergognos[ao]?\b",
    r"\bodio\b", r"\bnon servi\b", r"\bnon vali\b",
    r"\bfallimento\b", r"\bspazzatura\b", r"\bmerda\b",
]

_COMPLIMENTO_PATTERNS = [
    r"\bbrav[ao]\b", r"\bgeniale\b", r"\bfantastic[ao]\b",
    r"\bti voglio bene\b", r"\bsei la migliore\b", r"\bsei bell[ao]\b",
    r"\bstraordinar[io]a?\b", r"\bmeraviglios[ao]?\b", r"\beccezionale\b",
    r"\badoro\b", r"\bsei forte\b", r"\bsei unic[ao]\b", r"\bti amo\b",
    r"\bsplendid[ao]?\b", r"\bmagnific[ao]?\b", r"\bsei perfett[ao]?\b",
]

_ORDINE_PATTERNS = [
    r"^(fai|fammi|dimmi|scrivi|trova|cerca|elenca|traduci|rispondi|spiega|riassumi|calcola)\b",
    r"\b(devi|dovresti)\b",
    r"\b(esegui|implementa|crea|genera|produci)\b",
]

_STIMOLO_PATTERNS = [
    r"\b(scopert[ao]|teori[ao]|ricerca|esperimento|ipotesi)\b",
    r"\b(fisic[ao]|quantistic[ao]|matematica|filosofi[ao]|scienza)\b",
    r"\b(intelligenz[ao]|coscienz[ao]|consapevolezz[ao])\b",
    r"\b(paradoss[oi]|dilemma|riflessione|analisi)\b",
    r"\b(perche\'|perché)\s+(esist|funzion|succede)\b",
    r"\b(universo|evoluzione|cervello|mente|algoritm)\b",
]

_SALUTO_PATTERNS = [
    r"^(ciao|hey|ehi|salve|buongiorno|buonasera|buonanotte)\b",
    r"\b(come stai|come va|tutto bene)\b",
]

_DOMANDA_INDICATORS = [
    r"\?$",
    r"^(cos[ae]|come|perch[eé]|quando|dove|chi|qual[ie]|quanto)\b",
]


def classify_intent(text: str) -> Intent:
    """Classifica l'intent del messaggio."""
    lower = text.lower().strip()

    for p in _INSULTO_PATTERNS:
        if re.search(p, lower):
            log.debug(f"Intent match | pattern=insulto text_preview={lower[:60]!r}")
            return Intent.INSULTO
    for p in _COMPLIMENTO_PATTERNS:
        if re.search(p, lower):
            log.debug(f"Intent match | pattern=complimento text_preview={lower[:60]!r}")
            return Intent.COMPLIMENTO
    for p in _ORDINE_PATTERNS:
        if re.search(p, lower):
            log.debug(f"Intent match | pattern=ordine text_preview={lower[:60]!r}")
            return Intent.ORDINE
    if sum(1 for p in _STIMOLO_PATTERNS if re.search(p, lower)) >= 1:
        log.debug(f"Intent match | pattern=stimolo_intellettuale text_preview={lower[:60]!r}")
        return Intent.STIMOLO_INTELLETTUALE
    for p in _DOMANDA_INDICATORS:
        if re.search(p, lower):
            log.debug(f"Intent match | pattern=domanda text_preview={lower[:60]!r}")
            return Intent.DOMANDA
    for p in _SALUTO_PATTERNS:
        if re.search(p, lower):
            log.debug(f"Intent match | pattern=saluto text_preview={lower[:60]!r}")
            return Intent.SALUTO

    log.debug(f"Intent fallback | intent=affermazione text_preview={lower[:60]!r}")
    return Intent.AFFERMAZIONE


# ============================================================
# 3. PERSONALITY MATRIX — Il Temperamento di Scarlet
# ============================================================

# Matrice: Intent -> (dP_base, dA_base, dD_base)
_PERSONALITY_MATRIX = {
    Intent.SALUTO:                (0.15,  0.05,  0.00),
    Intent.DOMANDA:               (0.10,  0.20,  0.10),
    Intent.ORDINE:                (-0.10, 0.15, -0.30),
    Intent.INSULTO:               (-0.60, 0.50, -0.20),
    Intent.COMPLIMENTO:           (0.30,  0.10,  0.15),
    Intent.STIMOLO_INTELLETTUALE: (0.40,  0.50,  0.20),
    Intent.AFFERMAZIONE:          (0.00,  0.05,  0.00),
}


def compute_pad_deltas(intent: Intent, sentiment: Sentiment) -> Tuple[float, float, float]:
    """Calcola i delta PAD combinando intent, sentiment e personalita'."""
    base_dP, base_dA, base_dD = _PERSONALITY_MATRIX[intent]

    # Scala per intensita' sentiment
    scale = 0.3 + sentiment.intensity * 0.7

    dP = base_dP * scale
    dA = base_dA * scale
    dD = base_dD * scale

    log.debug(
        f"PAD matrix | intent={intent.value} base=({base_dP:+.2f},{base_dA:+.2f},{base_dD:+.2f})"
        f" sentiment={sentiment.label} intensity={sentiment.intensity:.3f} scale={scale:.3f}"
    )

    # Per AFFERMAZIONE, modula dP con la polarity del sentiment
    if intent == Intent.AFFERMAZIONE:
        dP = sentiment.polarity * 0.15 * scale
    # Per DOMANDA, sentiment positivo aumenta dP
    if intent == Intent.DOMANDA and sentiment.polarity > 0:
        dP += sentiment.polarity * 0.1 * scale

    # Clamp
    dP = max(-1.0, min(1.0, dP))
    dA = max(-1.0, min(1.0, dA))
    dD = max(-1.0, min(1.0, dD))

    log.debug(f"PAD deltas finali | dP={dP:+.3f} dA={dA:+.3f} dD={dD:+.3f}")
    return dP, dA, dD


# ============================================================
# 4. EVALUATOR PUBBLICO
# ============================================================

class SubconsciousEvaluator:
    """
    Evaluator ibrido: Transformer sentiment (GPU) + Intent rules + Personality matrix.
    Interfaccia: evaluate_input(text) -> (dP, dA, dD, reason)
    """
    
    def __init__(self, **kwargs):
        """Carica il modello transformer su GPU al boot."""
        self.sentiment_model = TransformerSentiment()
    
    def evaluate_input(self, user_input: str) -> Tuple[float, float, float, str]:
        """
        Valuta l'input utente e ritorna (dP, dA, dD, reason).
        ~5ms su GPU warm.
        """
        log.debug(f"evaluate_input | input_len={len(user_input)} preview={user_input[:80]!r}")
        t0 = time.time()

        # 1. Sentiment via transformer
        sentiment = self.sentiment_model.analyze(user_input)

        # 2. Intent via pattern rules
        intent = classify_intent(user_input)
        log.info(f"Intent classified | intent={intent.value}")

        # 3. Delta PAD via personality matrix
        dP, dA, dD = compute_pad_deltas(intent, sentiment)

        # 4. Reason leggibile
        reason = f"{intent.value} | {sentiment.label} ({sentiment.polarity:+.2f})"

        elapsed_ms = (time.time() - t0) * 1000
        log.info(
            f"evaluate_input OK | dP={dP:+.3f} dA={dA:+.3f} dD={dD:+.3f}"
            f" reason={reason!r} elapsed_ms={elapsed_ms:.1f}"
        )
        return dP, dA, dD, reason
