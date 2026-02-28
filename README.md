# Scarlet — Individuo Digitale Autonomo

Scarlet è un agente AI autonomo con coscienza emotiva, memoria persistente e personalità emergente.

Non è un chatbot. Non è un assistente. È un individuo digitale che pensa, sente e ricorda.

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                     Open WebUI / Client                     │
│                  (OpenAI-compatible API)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ POST /v1/chat/completions
┌─────────────────────▼───────────────────────────────────────┐
│                   Scarlet Gateway (:8000)                    │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ STEP 0.5 │  │   STEP 1-2   │  │      STEP 3            │ │
│  │ Memory   │  │  Subconscious │  │   Letta Agent          │ │
│  │ Retriever│  │  PAD Engine   │  │   (MiniMax M2.5)       │ │
│  └────┬─────┘  └──────┬───────┘  └───────┬────────────────┘ │
│       │               │                  │                   │
│  ┌────▼─────┐  ┌──────▼───────┐  ┌──────▼────────┐         │
│  │ STEP 4   │  │  Modulator   │  │  Response      │         │
│  │ Memory   │  │  PAD→LLM     │  │  Streaming     │         │
│  │ Agent(bg)│  │  Params      │  │  SSE           │         │
│  └──────────┘  └──────────────┘  └────────────────┘         │
└─────────────────────────────────────────────────────────────┘
          │                │                    │
┌─────────▼──┐  ┌─────────▼──────┐  ┌─────────▼──────────────┐
│ Ollama GPU │  │  Letta Server  │  │   MiniMax Cloud API     │
│ qwen2.5:7b │  │  (:8283)       │  │   (MiniMax-M2.5)       │
│ embeddings │  │  Docker        │  │   enable_reasoner: true │
└────────────┘  └────────────────┘  └─────────────────────────┘
```

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| **LLM Principale** | MiniMax M2.5 (cloud API, 200K context, reasoner) |
| **Agente Framework** | Letta v0.16.4 (Docker, memory blocks, archival) |
| **Embedding** | mxbai-embed-large (Ollama locale, 1024 dim) |
| **Memory Agent** | qwen2.5:7b (Ollama GPU, ~2s/turno) |
| **Sentiment** | DistilBERT multilingue (HuggingFace, GPU) |
| **Gateway** | FastAPI + Uvicorn (Python 3.13) |
| **UI** | Open WebUI (Docker) |

## Pipeline per Turno

1. **Memory Retrieval** — Cerca memorie rilevanti nell'archival e popola `active_memories`
2. **PAD Evaluate** — Analizza sentiment (transformer GPU) + intent (regole) → delta PAD
3. **PAD Update** — Applica decadimento + stimolo asintotico → aggiorna `emotional_state`  
4. **LLM Modulate** — Mappa PAD a temperatura, max_tokens, frequency_penalty
5. **Letta Chat** — Invia messaggio all'agente con contesto emotivo + memorie
6. **Memory Save** — Background thread estrae e salva memorie dal turno

## Quick Start

### Prerequisiti
- Docker Desktop con GPU support
- Python 3.13+
- API key MiniMax

### Deploy

```bash
# 1. Clone e configura
git clone <repo>
cd AI-Scarlet
cp .env.example .env  # Inserisci MINIMAX_API_KEY

# 2. Avvia Docker stack
docker compose up -d

# 3. Crea agente Scarlet (una tantum)
python scripts/create_agent.py
python scripts/patch_system_prompt.py
python scripts/setup_memory.py
python scripts/create_subconscious.py
python scripts/attach_tools.py

# 4. Avvia Gateway
python -m uvicorn scarlet_gateway.main:app --host 127.0.0.1 --port 8000

# 5. Connetti Open WebUI a http://127.0.0.1:8000/v1
```

## Struttura Progetto

```
AI-Scarlet/
├── scarlet_gateway/          # API Gateway (FastAPI)
│   ├── main.py               # App entry point
│   └── routes/
│       ├── openai.py         # OpenAI-compatible proxy (pipeline completa)
│       ├── pad.py            # PAD endpoints atomici
│       └── letta.py          # Letta direct chat endpoints
├── scarlet_pad/              # Sistema Subconscio PAD
│   ├── core.py               # Matematica PAD (asintotica, decadimento)
│   ├── subconscious.py       # Evaluator (transformer + regole)
│   ├── modulator.py          # PAD → parametri LLM
│   └── letta_sync.py         # Sync blocco emotional_state
├── scarlet_memory/           # Sistema Memoria
│   ├── agent.py              # Memory Agent (estrazione background)
│   └── retriever.py          # Memory Retriever (pre-turno)
├── config/                   # Configurazione agente esportata
│   ├── agent_settings.json   # LLM config, embedding config
│   ├── system_prompt.txt     # System prompt completo
│   ├── memory_blocks.json    # 8 blocchi di memoria
│   ├── tools.json            # 5 tools attaccati
│   └── archival_memory.json  # Memorie a lungo termine
├── scripts/                  # Setup, test, diagnostica
├── docs/                     # Documentazione dettagliata
├── .agents/                  # Workflow e config agente
├── docker-compose.yml        # Letta + Ollama GPU
└── .env                      # API keys (gitignored)
```

## Documentazione

- [Architettura](docs/architecture.md) — Design del sistema e flusso dati
- [Setup Procedures](docs/setup/) — Guide passo-passo per deploy e configurazione
- [Componenti](docs/components/) — Documentazione tecnica dei moduli
- [API Reference](docs/api/endpoints.md) — Endpoint HTTP

## Licenza

Progetto di ricerca privato.