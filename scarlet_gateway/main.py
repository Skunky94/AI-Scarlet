"""
Main FastAPI app for Scarlet Gateway.
Funge da hub (Heartbeat/API) e proxy OpenAI-compatibile.

Lifecycle:
  Startup  → verifica connessione Letta, log stato servizi
  Shutdown → graceful drain richieste in corso (gestito da uvicorn su SIGTERM)
"""

import os
import logging
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configura logging strutturato
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("scarlet.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestisce startup e shutdown ordinato del gateway.
    Startup: verifica dipendenze esterne (Letta), logga stato.
    Shutdown: segnala la fine prima che uvicorn dreni le connessioni.
    """
    # === STARTUP ===
    letta_url  = os.getenv("LETTA_URL",    "http://localhost:8283")
    letta_key  = os.getenv("LETTA_API_KEY", "scarlet_dev")
    ollama_url = os.getenv("OLLAMA_URL",   "http://localhost:11434")

    logger.info("Avvio Scarlet Gateway...")
    logger.info(f"  LETTA_URL  = {letta_url}")
    logger.info(f"  OLLAMA_URL = {ollama_url}")
    logger.info(f"  AGENT_ID   = {os.getenv('AGENT_ID', '(da file .agent_id)')}")

    # Verifica connessione Letta (non bloccante: solo warning se non disponibile)
    try:
        r = requests.get(
            f"{letta_url}/v1/health",
            headers={"Authorization": f"Bearer {letta_key}"},
            timeout=5,
        )
        r.raise_for_status()
        logger.info("Letta: OK")
    except Exception as exc:
        logger.warning(f"Letta non raggiungibile all'avvio: {exc}")

    # Verifica Ollama
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        logger.info(f"Ollama: OK — modelli: {models}")
    except Exception as exc:
        logger.warning(f"Ollama non raggiungibile all'avvio: {exc}")

    # I router (pad, letta, openai) sono già stati importati — SubconsciousEvaluator
    # (DistilBERT) si sta caricando in background tramite il thread warmup di pad.py.
    logger.info("Scarlet Gateway pronto — in ascolto sulla porta 8000.")

    yield  # L'app gira qui

    # === SHUTDOWN ===
    logger.info("Scarlet Gateway: shutdown ordinato avviato.")
    logger.info("Shutdown completato.")


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
