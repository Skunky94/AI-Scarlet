# Deploy Docker Stack

## Prerequisiti
- Docker Desktop con NVIDIA GPU support
- WSL2 configurato per Docker

## Componenti Docker

Il `docker-compose.yml` avvia 2 container:
- **scarlet-letta** (:8283) — Letta server
- **scarlet-ollama** (:11434) — Ollama con GPU passthrough

Il `docker-compose.ui.yaml` aggiunge:
- **scarlet-ui** (:3000) — Open WebUI

## Deploy

```bash
# Stack base (Letta + Ollama)
docker compose up -d

# Con UI
docker compose -f docker-compose.yml -f docker-compose.ui.yaml up -d
```

## Verifica Salute

```bash
# Letta
curl http://localhost:8283/v1/health
# Expected: {"version":"0.16.4","status":"ok"}

# Ollama
curl http://localhost:11434/api/tags
# Expected: lista modelli (qwen2.5:7b, mxbai-embed-large)
```

## Modelli Ollama Necessari

```bash
docker exec scarlet-ollama ollama pull qwen2.5:7b
docker exec scarlet-ollama ollama pull mxbai-embed-large
```

## Variabili d'Ambiente (.env)

```
MINIMAX_API_KEY=<chiave MiniMax>
LETTA_SERVER_PASSWORD=scarlet_dev
```

## Networking

Letta Docker accede a Ollama tramite `host.docker.internal:11434`.
Il Gateway Python (non in Docker) accede a Letta tramite `localhost:8283`.

## Troubleshooting

| Problema | Soluzione |
|---|---|
| Letta health: starting | Attendi 1-2 minuti (startup lento) |
| Ollama GPU non disponibile | Verifica `nvidia-smi` e Docker GPU runtime |
| Connection refused :8283 | `docker compose restart scarlet-letta` |
