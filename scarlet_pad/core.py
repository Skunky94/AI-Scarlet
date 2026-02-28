"""
PAD Engine Core Math
Implementa la logica matematica del modello Pleasure-Arousal-Dominance.
Usa addizione asintotica per evitare over-bounding e garantisce
un decadimento morbido verso la baseline di Scarlet.
"""

from dataclasses import dataclass
from typing import Tuple

@dataclass
class PADState:
    p: float  # Pleasure (-1.0 to 1.0)
    a: float  # Arousal (-1.0 to 1.0)
    d: float  # Dominance (-1.0 to 1.0)

    def clamp(self):
        """Assicura che i valori siano strettamente tra -1.0 e 1.0."""
        self.p = max(-1.0, min(1.0, self.p))
        self.a = max(-1.0, min(1.0, self.a))
        self.d = max(-1.0, min(1.0, self.d))


class PADCore:
    def __init__(self, base_p: float = 0.1, base_a: float = 0.1, base_d: float = 0.2):
        """
        Inizializza il core con il "Temperamento Naturale" (Baseline) di Scarlet.
        I valori di default riflettono una Scarlet lievemente curiosa, attenta e autonoma.
        """
        self.baseline = PADState(base_p, base_a, base_d)

    def apply_stimulus(self, current: PADState, dp: float, da: float, dd: float) -> PADState:
        """
        Applica uno stimolo (delta) allo stato corrente usando addizione asintotica.
        Più ci si avvicina agli estremi (-1 o 1), meno effetto ha lo stimolo.
        """
        return PADState(
            p=self._asymptotic_add(current.p, dp),
            a=self._asymptotic_add(current.a, da),
            d=self._asymptotic_add(current.d, dd)
        )

    def apply_decay(self, current: PADState, decay_factor: float = 0.1) -> PADState:
        """
        Applica il decadimento (omeostasi). Riporta gradualmente i valori
        verso la baseline. Da richiamare ad ogni ciclo di Heartbeat.
        """
        decay_factor = max(0.0, min(1.0, decay_factor))
        return PADState(
            p=current.p + (self.baseline.p - current.p) * decay_factor,
            a=current.a + (self.baseline.a - current.a) * decay_factor,
            d=current.d + (self.baseline.d - current.d) * decay_factor
        )

    def _asymptotic_add(self, current_val: float, delta: float) -> float:
        """
        Somma asintotica per evitare di sfondare i limiti [-1, 1].
        """
        if delta == 0.0:
            return current_val
            
        if delta > 0:
            # Spazio rimanente fino a +1.0
            room = 1.0 - current_val
            new_val = current_val + (delta * room)
        else:
            # Spazio rimanente fino a -1.0 (delta è negativo)
            room = current_val - (-1.0)
            new_val = current_val + (delta * room)
            
        # Per sicurezza (float math)
        return max(-1.0, min(1.0, new_val))

    def get_mood_description(self, state: PADState) -> str:
        """
        Mappatura euristica semplice delle coordinate a uno stato d'animo
        per generare il testo leggibile per l'LLM di Scarlet.
        """
        p, a, d = state.p, state.a, state.d
        
        # Mappa base degli ottanti (classificazione di Mehrabian) ridotta/adattata
        if p >= 0 and a >= 0 and d >= 0:
            return "CURIOSA-CARICA (Esaltata, proattiva, indipendente)"
        elif p >= 0 and a >= 0 and d < 0:
            return "AFFASCINATA-DIPENDENTE (Ammirata, segue volentieri la via posta)"
        elif p >= 0 and a < 0 and d >= 0:
            return "RILASSATA-SICURA (Placida, padrona della situazione, ironica)"
        elif p >= 0 and a < 0 and d < 0:
            return "DOCILE-TRANQUILLA (Serena, ma passiva)"
        elif p < 0 and a >= 0 and d >= 0:
            return "ARRABBIATA-POLEMICA (Frustrata, aggressiva, vuole imporsi)"
        elif p < 0 and a >= 0 and d < 0:
            return "ANSIOSA-DIFENSIVA (In allarme, percepisce minaccia, reattiva)"
        elif p < 0 and a < 0 and d >= 0:
            return "DISGUSTATA-DISTACCATA (Annoiata, critica, fredda, rifiuta l'input)"
        else: # p < 0, a < 0, d < 0
            return "TRISTE-SOTTOPOSTA (Rassegnata, esaurita, passiva)"

    def format_letta_block(self, state: PADState, trigger_event: str) -> str:
        """
        Formatta il valore testuale da iniettare brutalmente nel blocco Letta
        'emotional_state' in modo che l'LLM primario lo recepisca chiaramente come input di contesto.
        """
        mood = self.get_mood_description(state)
        
        block_text = f"=== Stato Emotivo (PAD Engine) ===\n"
        block_text += "[Questo blocco e' gestito dal Subconscio. Scarlet lo subisce.]\n\n"
        
        # Formattazione per mostrare chiaramente i valori +- a 2 decimali
        block_text += f"Pleasure:   {state.p:+.2f}  (Da dispiacere a piacere)\n"
        block_text += f"Arousal:    {state.a:+.2f}  (Da apatia a eccitazione)\n"
        block_text += f"Dominance:  {state.d:+.2f}  (Da sottomissione a controllo)\n\n"
        
        block_text += f"Umore risultante: {mood}\n"
        block_text += f"Ultimo stimolo subconscio emotivo: {trigger_event}\n"
        
        return block_text
