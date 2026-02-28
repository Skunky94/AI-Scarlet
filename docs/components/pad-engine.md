# PAD Engine — Sistema Subconscio

## Panoramica

Il PAD (Pleasure-Arousal-Dominance) Engine è il subconscio di Scarlet. Analizza ogni input utente, calcola una risposta emotiva e modifica i parametri LLM in tempo reale.

## File

| File | Ruolo |
|---|---|
| `core.py` | Matematica PAD (addizione asintotica, decadimento, mood mapping) |
| `subconscious.py` | Evaluator ibrido (Transformer sentiment + regole intent) |
| `modulator.py` | Mappa PAD → parametri LLM (temperature, max_tokens, freq_penalty) |
| `letta_sync.py` | Legge/scrive il blocco `emotional_state` in Letta |

## PAD Core (`core.py`)

### PADState
```python
@dataclass
class PADState:
    p: float  # Pleasure [-1.0, +1.0]
    a: float  # Arousal  [-1.0, +1.0]
    d: float  # Dominance [-1.0, +1.0]
```

### Baseline (Temperamento naturale)
- Pleasure: **+0.10** (lievemente positiva)
- Arousal: **+0.10** (attenta)
- Dominance: **+0.20** (autonoma)

### Addizione Asintotica
Garantisce che i valori non sfondino mai [-1, +1]. Più ci si avvicina al limite, meno effetto ha lo stimolo.

### Decadimento
Riporta gradualmente i valori verso la baseline (omeostasi emotiva). `decay_factor = 0.05` per turno.

### Mood Mapping (8 ottanti)
| P | A | D | Umore |
|---|---|---|---|
| + | + | + | Curiosa-Carica |
| + | + | - | Affascinata-Dipendente |
| + | - | + | Rilassata-Sicura |
| + | - | - | Docile-Tranquilla |
| - | + | + | Arrabbiata-Polemica |
| - | + | - | Ansiosa-Difensiva |
| - | - | + | Disgustata-Distaccata |
| - | - | - | Triste-Sottoposta |

## Subconscious Evaluator (`subconscious.py`)

Architettura ibrida a due livelli:

### Level 1: Sentiment Analysis (Transformer GPU)
- Modello: `lxyuan/distilbert-base-multilingual-cased-sentiments-student`
- Dispositivo: CUDA (GPU), pre-caricato al boot
- Velocità: ~4ms per analisi (GPU warm)
- Output: Sentiment (polarity, intensity, label)

### Level 2: Intent Classification (Pattern-based)
- 7 categorie: SALUTO, DOMANDA, ORDINE, INSULTO, COMPLIMENTO, STIMOLO_INTELLETTUALE, AFFERMAZIONE
- Regex patterns per italiano

### Personality Matrix
Combina intent e sentiment per calcolare delta PAD specifici della personalità di Scarlet.

## Modulator (`modulator.py`)

Mappa i valori PAD a parametri LLM concreti:

| PAD | Parametro LLM | Range |
|---|---|---|
| Arousal → | Temperature | 0.3 — 0.7 — 1.0 |
| Pleasure → | Max Tokens | 1000 — 4000 — 8000 |
| -Dominance → | Frequency Penalty | 0.0 — 0.3 — 0.8 |

Esempio: Scarlet arrabbiata (P-, A+, D+) → temperature alta, pochi token, bassa penalty = risposte brevi, vivaci, assertive.

## Letta Sync (`letta_sync.py`)

Legge e scrive il blocco `emotional_state` in Letta via API REST.
Il blocco contiene il testo formattato con valori PAD numericiy e mood description.
