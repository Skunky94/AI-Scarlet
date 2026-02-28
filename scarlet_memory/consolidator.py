"""
Cognee Consolidator — Heartbeat di consolidamento memorie
=========================================================
Ogni 10 minuti, esegue cognee.memify() sul dataset globale per:

- Pruning: rimuove entità/relazioni obsolete o ridondanti
- Strengthening: rafforza connessioni frequentemente accedute
- Reweighting: ricalibra i pesi degli archi del grafo
- Derived facts: crea nuovi nodi da pattern emergenti

Design:
- Loop async infinito — avviato come asyncio.Task nel lifespan FastAPI
- Il task dorme HEARTBEAT_SECONDS prima della prima esecuzione
  (evita conflitti con cognify() dei primi turni al boot)
- Se memify() fallisce, logga l'errore e riprova al ciclo successivo
- Non è necessario specificare node_sets: memify() consolida tutti i dataset

Avvio: asyncio.create_task(start_heartbeat()) in scarlet_gateway/main.py
"""

import asyncio
import time

import cognee
from scarlet_observability import get_logger

log = get_logger("memory.consolidator")

# Intervallo tra consolidamenti (secondi)
HEARTBEAT_SECONDS: int = 600  # 10 minuti


async def start_heartbeat() -> None:
    """
    Loop di consolidamento asincrono.
    Progettato per girare per tutta la vita del processo FastAPI.

    Il primo sleep evita che memify() parta mentre cognify() del
    primo turno è ancora in esecuzione (race condition su KuzuDB).
    """
    log.info(
        f"Consolidatore avviato | intervallo={HEARTBEAT_SECONDS}s"
        f" ({HEARTBEAT_SECONDS // 60} minuti)"
    )

    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)

        t0 = time.time()
        log.info("Heartbeat consolidamento | avvio cognee.memify()")
        try:
            await cognee.memify()
            elapsed_ms = (time.time() - t0) * 1000
            log.info(f"Heartbeat consolidamento OK | elapsed_ms={elapsed_ms:.0f}")
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            log.error(
                f"Heartbeat consolidamento ERRORE | error={e}"
                f" elapsed_ms={elapsed_ms:.0f}"
            )
            # Non rilanciare l'eccezione: il loop continua al prossimo ciclo
