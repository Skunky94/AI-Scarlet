"""
PAD Letta Synchronizer
Legge e Scrive il blocco 'emotional_state' via API Letta.
Il blocco Letta e' la Single Source of Truth.
"""

import os
import re
import requests
from typing import Optional, Tuple
from scarlet_pad.core import PADState, PADCore

class LettaPADSync:
    def __init__(self,
                 base_url: str = os.getenv("LETTA_URL", "http://localhost:8283"),
                 token: str = os.getenv("LETTA_API_KEY", "scarlet_dev")):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_agent_id(self) -> Optional[str]:
        """Legge AGENT_ID da env var (Docker) o da file .agent_id (host)."""
        agent_id = os.getenv("AGENT_ID", "").strip()
        if agent_id:
            return agent_id
        try:
            with open(".agent_id", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print("Nessun file .agent_id trovato.")
            return None

    def read_current_state(self, agent_id: str) -> Tuple[PADState, str]:
        """
        Interroga Letta, estrae il blocco 'emotional_state' via regex per trovare i valori PAD.
        Ritorna il PACState attuale e l'ID del blocco per futuri aggiornamenti.
        Se non trova valori, ritorna il Baseline (0.1, 0.1, 0.2).
        """
        url = f"{self.base_url}/v1/agents/{agent_id}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Errore API Letta: {resp.text}")
            
        data = resp.json()
        blocks = data.get("memory", {}).get("blocks", [])
        
        target_block = None
        for b in blocks:
            if b.get("label") == "emotional_state":
                target_block = b
                break
                
        if not target_block:
            raise ValueError(f"Blocco 'emotional_state' non trovato nell'agente {agent_id}")
            
        block_val = target_block.get("value", "")
        block_id = target_block.get("id")
        
        # Regex per trovare i numeric values (es: "Pleasure:   +0.20")
        p_match = re.search(r"Pleasure:\s*([+-]?\d+\.\d+)", block_val)
        a_match = re.search(r"Arousal:\s*([+-]?\d+\.\d+)", block_val)
        d_match = re.search(r"Dominance:\s*([+-]?\d+\.\d+)", block_val)
        
        # Default baseline
        p = 0.1
        a = 0.1
        d = 0.2
        
        if p_match: p = float(p_match.group(1))
        if a_match: a = float(a_match.group(1))
        if d_match: d = float(d_match.group(1))
        
        # clamp
        state = PADState(p, a, d)
        state.clamp()
        return state, block_id

    def update_state(self, agent_id: str, block_id: str, new_state: PADState, event_trigger: str) -> bool:
        """
        Sovrascrive il blocco 'emotional_state' in Letta col nuovo testo descrittivo.
        """
        core = PADCore()
        new_text = core.format_letta_block(new_state, event_trigger)
        
        url = f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/emotional_state"
        payload = {
            "value": new_text
        }
        resp = requests.patch(url, headers=self.headers, json=payload)
        
        if resp.status_code == 200:
            return True
            
        print(f"Errore aggiornamento blocco: {resp.text}")
        return False
