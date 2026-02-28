"""
PAD → LLM Parameter Modulator
==============================
Mappa lo stato emotivo PAD di Scarlet a parametri reali di inferenza LLM.
Modifica la temperature, max_tokens e frequency_penalty dell'agente Letta
prima di ogni messaggio, creando un effetto subconscio REALE sul comportamento.

=== PARAMETRI MiniMax M2.5 (Documentazione Ufficiale) ===

Temperature:
  - Range: (0.0, 1.0]  -- ATTENZIONE: max 1.0, valori >1.0 danno errore!
  - Default raccomandato: 1.0
  - 0.0-0.3: Deterministico, fattuale
  - 0.4-0.7: Bilanciato creatività/consistenza
  - 0.8-1.0: Creativo, vario

Max Tokens:
  - Output massimo: ~131K token
  - Nessun limite inferiore documentato
  - Valori ragionevoli per chat: 500-8000

Frequency Penalty:
  - Range: 0.0-2.0
  - 0.0: Nessuna penalità (può ripetere)
  - 0.5-1.0: Moderata variazione
  - 1.0-2.0: Forte penalità ripetizioni

=== MAPPING PAD → PARAMETRI ===

Arousal → Temperature:
  - Arousal BASSO (-1.0): Scarlet è apatica, calma → temp BASSA (0.3) = risposte misurate
  - Arousal NEUTRO (0.0): Stato normale → temp MEDIA (0.7) = default bilanciato  
  - Arousal ALTO (+1.0): Scarlet è eccitata/agitata → temp ALTA (1.0) = risposte più vivaci

Pleasure → Max Tokens:
  - Pleasure BASSO (-1.0): Scarlet è irritata/triste → pochi token (1000) = risposte secche, lapidarie
  - Pleasure NEUTRO (0.0): Stato normale → token medi (4000) = risposte standard
  - Pleasure ALTO (+1.0): Scarlet è felice/appagata → molti token (8000) = risposte elaborate, generose

Dominance → Frequency Penalty:
  - Dominance ALTA (+1.0): Scarlet è assertiva, in controllo → penalty BASSA (0.0) = ripete le sue posizioni
  - Dominance NEUTRA (0.0): Stato normale → penalty MEDIA (0.3) = moderata
  - Dominance BASSA (-1.0): Scarlet è sottomessa → penalty ALTA (0.8) = cerca parole diverse, meno assertiva
"""

import requests
from typing import Optional


class PADModulator:
    """Modula i parametri LLM di Scarlet basandosi sullo stato PAD corrente."""
    
    def __init__(self, letta_url: str = "http://localhost:8283",
                 letta_token: str = "scarlet_dev"):
        self.letta_url = letta_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json"
        }
        
        # Range calibrati su MiniMax M2.5
        #                    (min,  default, max)
        self.temp_range =     (0.3,  0.7,    1.0)    # Arousal → Temperature
        self.tokens_range =   (1000, 4000,   8000)   # Pleasure → Max Tokens
        self.freq_pen_range = (0.0,  0.3,    0.8)    # -Dominance → Frequency Penalty
    
    def _map_value(self, pad_value: float, range_tuple: tuple) -> float:
        """
        Mappa un valore PAD [-1, +1] a un range di parametri LLM.
        -1 → range[0] (min)
         0 → range[1] (default)
        +1 → range[2] (max)
        """
        low, mid, high = range_tuple
        if pad_value >= 0:
            return mid + (high - mid) * pad_value
        else:
            return mid + (mid - low) * pad_value  # pad_value è negativo
    
    def compute_params(self, p: float, a: float, d: float) -> dict:
        """
        Calcola i parametri LLM dallo stato PAD.
        
        Args:
            p: Pleasure [-1, +1]
            a: Arousal [-1, +1]  
            d: Dominance [-1, +1]
        
        Returns dict con:
            temperature: [0.3, 1.0] — da Arousal
            max_tokens: [1000, 8000] — da Pleasure
            frequency_penalty: [0.0, 0.8] — da Dominance (invertita)
        """
        temperature = round(self._map_value(a, self.temp_range), 2)
        max_tokens = int(self._map_value(p, self.tokens_range))
        frequency_penalty = round(self._map_value(-d, self.freq_pen_range), 2)
        # Nota: -d perché alta Dominance = bassa frequency_penalty (assertiva, ripete)
        
        # Safety clamp per rispettare limiti MiniMax M2.5
        temperature = max(0.01, min(1.0, temperature))
        max_tokens = max(500, min(16000, max_tokens))
        frequency_penalty = max(0.0, min(2.0, frequency_penalty))
        
        return {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "frequency_penalty": frequency_penalty
        }
    
    def apply_to_agent(self, agent_id: str, p: float, a: float, d: float) -> Optional[dict]:
        """
        Applica i parametri PAD-modulati all'agente Letta via PATCH.
        Legge la config corrente, modifica solo i 3 campi, PATCH completo.
        """
        params = self.compute_params(p, a, d)
        
        try:
            # 1. Leggi config corrente (Letta richiede tutti i campi nel PATCH)
            r_get = requests.get(
                f"{self.letta_url}/v1/agents/{agent_id}",
                headers=self.headers,
                timeout=5
            )
            if r_get.status_code != 200:
                print(f"[PADModulator] WARN: GET agent fallito ({r_get.status_code})")
                return None
            
            current_config = r_get.json().get("llm_config", {})
            
            # 2. Merge: aggiorna solo i 3 campi dinamici
            current_config["temperature"] = params["temperature"]
            current_config["max_tokens"] = params["max_tokens"]
            current_config["frequency_penalty"] = params["frequency_penalty"]
            
            # 3. PATCH con config completo
            r_patch = requests.patch(
                f"{self.letta_url}/v1/agents/{agent_id}",
                headers=self.headers,
                json={"llm_config": current_config},
                timeout=5
            )
            
            if r_patch.status_code == 200:
                return params
            else:
                print(f"[PADModulator] WARN: PATCH fallito ({r_patch.status_code}): {r_patch.text[:200]}")
                return None
                
        except Exception as e:
            print(f"[PADModulator] WARN: Errore: {e}")
            return None
