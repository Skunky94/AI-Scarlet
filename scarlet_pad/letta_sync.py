"""
PAD Letta Synchronizer
Legge e Scrive il blocco 'emotional_state' via API Letta.
Il blocco Letta e' la Single Source of Truth.
"""

import os
import re
import time
import requests
from typing import Optional, Tuple
from scarlet_pad.core import PADState, PADCore
from scarlet_observability import get_logger

log     = get_logger("pad.sync")
log_api = get_logger("letta")

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
            log.debug(f"get_agent_id | source=env_var id={agent_id[:20]}...")
            return agent_id
        try:
            with open(".agent_id", "r", encoding="utf-8") as f:
                agent_id = f.read().strip()
            log.debug(f"get_agent_id | source=file id={agent_id[:20]}...")
            return agent_id
        except FileNotFoundError:
            log.warning("get_agent_id | AGENT_ID non trovato (env var o file .agent_id mancante)")
            return None

    def read_current_state(self, agent_id: str) -> Tuple[PADState, str]:
        """
        Interroga Letta, estrae il blocco 'emotional_state' via regex.
        Ritorna il PADState attuale e l'ID del blocco per futuri aggiornamenti.
        Se non trova valori, ritorna il Baseline (0.1, 0.1, 0.2).
        """
        url = f"{self.base_url}/v1/agents/{agent_id}"
        log_api.debug(f"GET agent state | url={url}")
        t0 = time.time()
        resp = requests.get(url, headers=self.headers, timeout=10)
        elapsed_ms = (time.time() - t0) * 1000

        if resp.status_code != 200:
            log_api.error(f"read_current_state API error | status={resp.status_code} body={resp.text[:300]!r} elapsed_ms={elapsed_ms:.0f}")
            raise RuntimeError(f"Errore API Letta: {resp.text}")

        log_api.debug(f"GET agent state OK | status=200 elapsed_ms={elapsed_ms:.0f}")

        data = resp.json()
        blocks = data.get("memory", {}).get("blocks", [])
        log.debug(f"Blocchi memoria agente | count={len(blocks)} labels={[b.get('label') for b in blocks]}")

        target_block = None
        for b in blocks:
            if b.get("label") == "emotional_state":
                target_block = b
                break

        if not target_block:
            log.error(f"Blocco 'emotional_state' NON TROVATO | agent_id={agent_id[:20]}... labels={[b.get('label') for b in blocks]}")
            raise ValueError(f"Blocco 'emotional_state' non trovato nell'agente {agent_id}")

        block_val = target_block.get("value", "")
        block_id  = target_block.get("id")
        log.debug(f"emotional_state block | id={block_id} value_len={len(block_val)}")

        # Regex per trovare i numeric values (es: "Pleasure:   +0.20")
        p_match = re.search(r"Pleasure:\s*([+-]?\d+\.\d+)", block_val)
        a_match = re.search(r"Arousal:\s*([+-]?\d+\.\d+)", block_val)
        d_match = re.search(r"Dominance:\s*([+-]?\d+\.\d+)", block_val)

        # Default baseline
        p = 0.1
        a = 0.1
        d = 0.2

        if p_match:
            p = float(p_match.group(1))
        else:
            log.warning("read_current_state | regex Pleasure non trovata in emotional_state -> uso baseline 0.1")
        if a_match:
            a = float(a_match.group(1))
        else:
            log.warning("read_current_state | regex Arousal non trovata in emotional_state -> uso baseline 0.1")
        if d_match:
            d = float(d_match.group(1))
        else:
            log.warning("read_current_state | regex Dominance non trovata in emotional_state -> uso baseline 0.2")

        state = PADState(p, a, d)
        state.clamp()
        log.info(f"read_current_state | P={state.p:+.3f} A={state.a:+.3f} D={state.d:+.3f} block_id={block_id}")
        return state, block_id

    def update_state(self, agent_id: str, block_id: str, new_state: PADState, event_trigger: str) -> bool:
        """
        Sovrascrive il blocco 'emotional_state' in Letta col nuovo testo descrittivo.
        """
        core = PADCore()
        new_text = core.format_letta_block(new_state, event_trigger)

        url = f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/emotional_state"
        payload = {"value": new_text}

        log.debug(
            f"update_state | agent_id={agent_id[:20]}... block_id={block_id}"
            f" P={new_state.p:+.3f} A={new_state.a:+.3f} D={new_state.d:+.3f}"
            f" trigger={event_trigger!r}"
        )
        log_api.debug(f"PATCH emotional_state | url={url} content_len={len(new_text)}")

        t0 = time.time()
        resp = requests.patch(url, headers=self.headers, json=payload, timeout=10)
        elapsed_ms = (time.time() - t0) * 1000

        if resp.status_code == 200:
            log.info(
                f"update_state OK | P={new_state.p:+.3f} A={new_state.a:+.3f} D={new_state.d:+.3f}"
                f" elapsed_ms={elapsed_ms:.0f}"
            )
            return True

        log.warning(
            f"update_state FALLITO | status={resp.status_code}"
            f" body={resp.text[:200]!r} elapsed_ms={elapsed_ms:.0f}"
        )
        return False
