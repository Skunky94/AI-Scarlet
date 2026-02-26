# Riferimento Tecnico: Ollama su Docker con GPU

> Documentazione di riferimento interno per il Progetto Scarlet.  
> Consultata: 2026-02-25

---

## 1. Panoramica

Per il Progetto Scarlet, Ollama gira su **Docker con accesso GPU CUDA** (RTX 4070 Ti, 12GB VRAM). Questo permette inferenza locale per:
- **Embeddings** (es. `mxbai-embed-large`)
- **Sentiment Analysis PAD** (modelli leggeri)
- **Riflessioni di background** (monologo subconscio)

---

## 2. Prerequisiti

| Requisito | Dettaglio |
|---|---|
| **NVIDIA Driver** | ≥ 452.39 (consigliato: ultimo disponibile) |
| **Docker Desktop** | Con backend WSL 2 (Windows) |
| **NVIDIA Container Toolkit** | Installato nel sistema |
| **GPU** | RTX 4070 Ti (12GB VRAM) |

### Installazione NVIDIA Container Toolkit (WSL 2 / Linux)

```bash
# Aggiungere repository NVIDIA
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Installare
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configurare Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

> **Windows con Docker Desktop:** Il supporto GPU è nativo via WSL 2 — assicurarsi che Docker Desktop usi il backend WSL 2 e che i driver NVIDIA siano installati in Windows.

---

## 3. Comando Docker Ollama con GPU

```bash
docker run -d \
  --gpus all \
  --name ollama \
  -v H:/AI-Scarlet/.ollama:/root/.ollama \
  -p 11434:11434 \
  ollama/ollama:latest
```

| Parametro | Significato |
|---|---|
| `--gpus all` | Abilita accesso a tutte le GPU NVIDIA |
| `-v ...:/root/.ollama` | Persistenza modelli scaricati |
| `-p 11434:11434` | Porta API Ollama |
| `ollama/ollama:latest` | Immagine ufficiale |

### Scaricare un Modello

```bash
# Eseguire dentro il container
docker exec -it ollama ollama pull mxbai-embed-large
docker exec -it ollama ollama pull llama3.1:8b-instruct-q6_K
```

> ⚠️ Usare **sempre tag espliciti** (es. `:8b-instruct-q6_K`). Mai usare compressione sotto Q5 — modelli instabili con Letta.

---

## 4. Docker Compose (Letta + Ollama)

```yaml
version: "3.8"

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - H:/AI-Scarlet/.ollama:/root/.ollama
    ports:
      - "11434:11434"
    restart: unless-stopped

  letta:
    image: letta/letta:latest
    container_name: letta
    depends_on:
      - ollama
    volumes:
      - H:/AI-Scarlet/.letta/pgdata:/var/lib/postgresql/data
    ports:
      - "8283:8283"
    environment:
      - OPENAI_API_KEY=${MINIMAX_API_KEY}
      - OPENAI_BASE_URL=https://api.minimax.io/v1
      - OLLAMA_BASE_URL=http://ollama:11434/v1
      - SECURE=true
      - LETTA_SERVER_PASSWORD=scarlet_dev
    restart: unless-stopped
```

> **Nota:** In Docker Compose, i servizi si raggiungono per nome (`ollama` invece di `host.docker.internal`).

### File `.env`

> Il file `.env` è già stato creato nella root del progetto (`h:\AI-Scarlet\.env`).
> Contiene `MINIMAX_API_KEY` e `LETTA_SERVER_PASSWORD`. Non va mai committato in git.

---

## 5. Modelli Consigliati per RTX 4070 Ti (12GB VRAM)

| Modello | Uso | VRAM | Comando |
|---|---|---|---|
| `mxbai-embed-large` | Embeddings (archival memory) | ~1GB | `ollama pull mxbai-embed-large` |
| `llama3.1:8b-instruct-q6_K` | Sentiment PAD / riflessioni | ~6GB | `ollama pull llama3.1:8b-instruct-q6_K` |
| `nomic-embed-text` | Embeddings (alternativa) | ~0.5GB | `ollama pull nomic-embed-text` |

> Con 12GB VRAM, puoi eseguire embedding + modello 8B contemporaneamente senza problemi.

---

## 6. Verifica Funzionamento

```bash
# Testare Ollama da host
curl http://localhost:11434/api/tags

# Testare da container Letta (se in docker compose)
# Ollama è raggiungibile su http://ollama:11434/v1

# Testare inferenza
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b-instruct-q6_K",
  "prompt": "Hello, how are you?",
  "stream": false
}'
```

---

## 7. Risorse

- **Ollama GitHub:** [github.com/ollama/ollama](https://github.com/ollama/ollama)
- **Ollama Docker Hub:** [hub.docker.com/r/ollama/ollama](https://hub.docker.com/r/ollama/ollama)
- **NVIDIA Container Toolkit:** [docs.nvidia.com/datacenter/cloud-native/container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- **Letta + Ollama:** [docs.letta.com/models/ollama](https://docs.letta.com/models/ollama)
