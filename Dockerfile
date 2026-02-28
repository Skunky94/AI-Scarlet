# === Scarlet Gateway — Dockerfile ===
# Base: Python 3.13 slim (la NVIDIA Container Runtime espone la GPU host)
# PyTorch CUDA 12.1 per DistilBERT sentiment analysis
#
# Build: docker build -t scarlet-gateway .
# Run:   gestito da docker compose (vedi docker-compose.yml)

FROM python:3.13-slim

# Metadati
LABEL maintainer="Scarlet Project" \
      description="Scarlet Gateway — FastAPI proxy + PAD subconscious + memory"

# Evita dialog interattivi durante apt
ENV DEBIAN_FRONTEND=noninteractive

# --- System deps minimi ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Working directory ---
WORKDIR /app

# --- Installazione PyTorch CUDA prima (layer separato per cache Docker) ---
# NOTA: CUDA 12.1 wheels funzionano con CUDA 12.x grazie alla compat layer
RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cu121

# --- Installazione dipendenze Python (senza torch, già installato) ---
COPY requirements.txt .
RUN grep -v "^torch" requirements.txt | pip install --no-cache-dir -r /dev/stdin

# --- Copia sorgente ---
COPY scarlet_gateway/       ./scarlet_gateway/
COPY scarlet_pad/           ./scarlet_pad/
COPY scarlet_memory/        ./scarlet_memory/
COPY scarlet_observability/ ./scarlet_observability/
# Config osservabilita' (unico file di config necessario nell'immagine)
COPY config/observability.json ./config/observability.json

# --- Variabili d'ambiente con default per Docker (sovrascrivibili in compose) ---
# URL servizi (nome container Docker → risolto dalla rete interna)
ENV LETTA_URL="http://letta:8283"
ENV OLLAMA_URL="http://ollama:11434"
ENV LETTA_API_KEY="scarlet_dev"
# Agent ID — OBBLIGATORIO, impostato in docker-compose tramite .agent_id montato
ENV AGENT_ID=""
# Cache modelli HuggingFace (montata come volume per evitare re-download)
ENV HF_HOME="/app/.cache/huggingface"
# Encoding output terminale
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# --- Porta esposta ---
EXPOSE 8000

# --- Healthcheck (usato da docker compose depends_on) ---
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/ || exit 1

# --- Entrypoint ---
# --timeout-graceful-shutdown: uvicorn drena le richieste prima di uscire su SIGTERM
CMD ["python", "-m", "uvicorn", "scarlet_gateway.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--timeout-graceful-shutdown", "30"]
