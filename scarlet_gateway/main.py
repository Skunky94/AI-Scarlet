"""
Main FastAPI app for Scarlet Gateway.
Funge da hub (Heartbeat/API) e proxy OpenAI-compatibile.

Lifecycle:
  Startup  → verifica connessione Letta, log stato servizi
  Shutdown → graceful drain richieste in corso (gestito da uvicorn su SIGTERM)
"""

import os
import time
import asyncio
import requests
import cognee
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scarlet_memory.consolidator import start_heartbeat

# Sistema di osservabilita' centralizzato — inizializzato al primo import
from scarlet_observability import get_logger
log = get_logger("gateway.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestisce startup e shutdown ordinato del gateway.
    Startup: verifica dipendenze esterne (Letta), logga stato.
    Shutdown: segnala la fine prima che uvicorn dreni le connessioni.
    """
    # === STARTUP ===
    letta_url  = os.getenv("LETTA_URL",     "http://localhost:8283")
    letta_key  = os.getenv("LETTA_API_KEY",  "scarlet_dev")
    ollama_url = os.getenv("OLLAMA_URL",    "http://localhost:11434")
    agent_id   = os.getenv("AGENT_ID", "")

    log.info("======== Scarlet Gateway STARTUP ========")
    log.info(f"LETTA_URL={letta_url}")
    log.info(f"OLLAMA_URL={ollama_url}")
    log.info(f"AGENT_ID={(agent_id if agent_id else '(da file .agent_id)')}")
    log.debug(f"LETTA_API_KEY={'***' if letta_key else '(vuota)'}")

    # Verifica connessione Letta (non bloccante: solo warning se non disponibile)
    t0 = time.time()
    try:
        r = requests.get(
            f"{letta_url}/v1/health",
            headers={"Authorization": f"Bearer {letta_key}"},
            timeout=5,
        )
        r.raise_for_status()
        elapsed_ms = (time.time() - t0) * 1000
        log.info(f"Letta health OK | status={r.status_code} elapsed_ms={elapsed_ms:.0f}")
        log.debug(f"Letta health body: {r.text[:200]}")
    except Exception as exc:
        elapsed_ms = (time.time() - t0) * 1000
        log.warning(f"Letta non raggiungibile al boot | url={letta_url} elapsed_ms={elapsed_ms:.0f} error={exc}")

    # Verifica Ollama e lista modelli disponibili
    t0 = time.time()
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=5)
        elapsed_ms = (time.time() - t0) * 1000
        models = [m["name"] for m in r.json().get("models", [])]
        log.info(f"Ollama health OK | models={models} elapsed_ms={elapsed_ms:.0f}")
    except Exception as exc:
        elapsed_ms = (time.time() - t0) * 1000
        log.warning(f"Ollama non raggiungibile al boot | url={ollama_url} elapsed_ms={elapsed_ms:.0f} error={exc}")

    # I router sono importati sotto — SubconsciousEvaluator (DistilBERT) si carica
    # in background tramite il thread warmup di pad.py (impegna GPU ~30s al primo avvio).
    # === COGNEE INIT ===
    # Cognee si auto-configura dagli env vars impostati in docker-compose.yml
    # (LLM_PROVIDER, OPENAI_BASE_URL, LLM_MODEL, EMBEDDING_*, GRAPH_DATABASE_*, ecc.)
    # Non è necessaria configurazione esplicita: solo verifichiamo che il modulo
    # sia importato correttamente e avviamo il consolidatore.
    log.info("Cognee init | configurazione da env vars (kuzu+lancedb+sqlite)")
    log.debug(f"Cognee graph_db={os.getenv('GRAPH_DATABASE_PROVIDER','(def)')} "
              f"vector_db={os.getenv('VECTOR_DB_PROVIDER','(def)')} "
              f"llm={os.getenv('LLM_MODEL','(def)')}")

    # Avvia il consolidatore heartbeat come task asyncio
    # (gira per tutta la vita del processo, primo sleep = HEARTBEAT_SECONDS)
    asyncio.create_task(start_heartbeat())
    log.info("Consolidatore Cognee avviato (asyncio task)")

    log.info("======== Scarlet Gateway PRONTO ========")

    yield  # L'app gira qui

    # === SHUTDOWN ===
    # uvicorn drena le richieste in corso su SIGTERM (--timeout-graceful-shutdown)
    log.info("======== Scarlet Gateway SHUTDOWN ========")


# Importazione router DOPO la definizione del lifespan
# (evita che DistilBERT parta prima che il logger sia configurato)
from scarlet_gateway.routes import pad, letta, openai  # noqa: E402

app = FastAPI(
    title="Scarlet Gateway (Lego Blocks API)",
    description="Microservizi atomici per il motore cognitivo e PAD subconscio.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS per eventuali interfacce web custom future
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montaggio Router (I Mattoncini) ---

# Layer 1: Atomic Endpoints (Lego Blocks)
app.include_router(pad.router, prefix="/api/pad", tags=["PAD Subconscio"])
app.include_router(letta.router, prefix="/api/letta", tags=["Letta Core"])

# Layer 2: Composite Proxy (OpenAI Drop-in)
app.include_router(openai.router, prefix="/v1", tags=["OpenAI Proxy"])


@app.get("/")
def health_check():
    return {"status": "ok", "agent": "Scarlet", "subconscious": "active"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("scarlet_gateway.main:app", host="0.0.0.0", port=8000, reload=True)
