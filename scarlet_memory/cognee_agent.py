"""
Cognee Memory Agent — Estrazione e salvataggio memorie (Background)
===================================================================
Sostituisce agent.py come layer di archival memory.

Invece di LLM Ollama + Letta archival flat, usa Cognee per costruire
un knowledge graph semantico-temporale (KuzuDB embedded).

Processo:
1. Riceve il turno completo post-risposta (chiamata async, non-blocking per UI)
2. Formatta testo con metadati PAD + timestamp (leggibili da MiniMax)
3. cognee.add() — ingestisce il testo nel dataset isolato per user_id
4. cognee.cognify() — pipeline LLM (MiniMax): estrae entità/relazioni,
   aggiorna grafo Kuzu + indice vettoriale LanceDB

Modello LLM: MiniMax-M2.5 via env var OPENAI_BASE_URL
Graph DB:    Kuzu embedded → /data/cognee/graph
Vector DB:   LanceDB embedded → /data/cognee/vectors
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import cognee
from scarlet_observability import get_logger

log = get_logger("memory.cognee_agent")


class CogneeMemoryAgent:
    """
    Agente di memoria che usa Cognee per costruire un KG semantico-temporale.
    Interfaccia drop-in per scarlet_memory.agent.MemoryAgent (metodi async).

    Thread-safety: Cognee usa connessioni async — chiamare SOLO tramite
    asyncio.create_task() da contesto asincrono FastAPI (mai threading.Thread).
    """

    def __init__(self):
        # Cognee è configurato centralmente nel lifespan di main.py via env vars.
        # Questo __init__ è sync e non fa chiamate async/I/O.
        log.debug("CogneeMemoryAgent init | backend=cognee/kuzu/lancedb")

    async def process_turn_async(
        self,
        user_msg: str,
        think: str,
        response: str,
        user_id: str = "default",
        pad_state: Optional[Tuple[float, float, float]] = None,
    ) -> dict:
        """
        Aggiunge il turno al grafo Cognee e avvia cognify() per aggiornarlo.

        Design: un dataset Cognee per user_id — node_set=["scarlet_{user_id}"]
        garantisce isolamento multi-utente sullo stesso backend KuzuDB.

        Il testo del turno include metadati strutturati leggibili da MiniMax
        (timestamp ISO, stato PAD, user_id) per facilitare l'estrazione di
        relazioni temporali nel grafo.

        Args:
            user_msg:   Testo dell'utente
            think:      Chain-of-thought interna di Scarlet (tag <think>)
            response:   Risposta visibile di Scarlet
            user_id:    Utente corrente (default="default")
            pad_state:  Stato PAD attuale (P, A, D) per annotare il turno

        Returns:
            dict con {"created": int, "updated": int, "skipped": int}
        """
        t0 = time.time()
        dataset = f"scarlet_{user_id}"

        # Metadati PAD leggibili nel testo (MiniMax le estrarrà come relazioni)
        pad_str = ""
        if pad_state:
            P, A, D = pad_state
            pad_str = f"[PAD: P={P:+.2f} A={A:+.2f} D={D:+.2f}] "

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        turn_text = (
            f"[Turno — {ts}] {pad_str}user_id={user_id}\n\n"
            f"UTENTE:\n{user_msg}\n\n"
            f"PENSIERO SCARLET:\n{think if think else '(nessuno)'}\n\n"
            f"RISPOSTA SCARLET:\n{response}"
        )

        try:
            log.debug(
                f"process_turn_async | dataset={dataset!r}"
                f" turn_len={len(turn_text)} pad={pad_str.strip()!r}"
            )

            # Fase 1: ingestione testo nel dataset
            await cognee.add(turn_text, node_set=[dataset])

            # Fase 2: pipeline LLM — estrae entità/relazioni e aggiorna il grafo
            # cognify è la chiamata più costosa (~5-15s con MiniMax M2.5)
            await cognee.cognify(node_sets=[dataset])

            elapsed_ms = (time.time() - t0) * 1000
            log.info(
                f"process_turn_async OK | dataset={dataset!r}"
                f" turn_len={len(turn_text)} elapsed_ms={elapsed_ms:.0f}"
            )
            return {"created": 1, "updated": 0, "skipped": 0}

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            log.error(
                f"process_turn_async ERRORE | dataset={dataset!r}"
                f" error={e} elapsed_ms={elapsed_ms:.0f}"
            )
            return {"created": 0, "updated": 0, "skipped": 1}
