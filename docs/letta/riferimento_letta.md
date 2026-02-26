# Riferimento Tecnico: Letta Framework

> Documentazione di riferimento interno per il Progetto Scarlet.
> Fonte: [docs.letta.com](https://docs.letta.com/) — Consultata: 2026-02-25

---

## 1. Cos'è Letta

Letta (ex MemGPT) è la piattaforma per costruire **agenti stateful** — AI con memoria avanzata che può apprendere e auto-migliorarsi nel tempo. Tutti gli stati (memorie, messaggi, tool calls, ragionamento) sono **persistiti** in un database e non vengono mai persi, nemmeno dopo eviction dal context window.

### Prodotti Letta

| Prodotto | Descrizione | Uso per Scarlet |
|---|---|---|
| **Letta API** | API cloud-hosted, richiede API key da `app.letta.com` | Possibile per prototipazione rapida |
| **Letta Code** | CLI locale, agente nel terminale | Non rilevante (è un coding agent) |
| **Letta Server (Docker)** | Server self-hosted via Docker | **✅ Raccomandato per Scarlet** |

---

## 2. Deployment Docker (Self-Hosted)

### Comando Base

```bash
docker run \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -p 8283:8283 \
  -e OPENAI_API_KEY="xxx" \
  letta/letta:latest
```

- **Immagine:** `letta/letta:latest`
- **Porta:** `8283` → API REST su `http://localhost:8283/v1`
- **Persistenza:** Volume montato per PostgreSQL (dati agente)
- **DB Interno:** PostgreSQL con estensione `pgvector` (vettori per archival memory)

### Multi-Provider (Cloud + Locale)

```bash
docker run \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -p 8283:8283 \
  -e OPENAI_API_KEY="xxx" \
  -e ANTHROPIC_API_KEY="xxx" \
  -e OLLAMA_BASE_URL="http://host.docker.internal:11434/v1" \
  letta/letta:latest
```

> **Windows/macOS:** usare `host.docker.internal` per raggiungere Ollama host.
> **Linux:** usare `--network host` e `localhost`.

### Password Protection (Produzione)

```bash
docker run \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -p 8283:8283 \
  --env-file .env \
  -e SECURE=true \
  -e LETTA_SERVER_PASSWORD=yourpassword \
  letta/letta:latest
```

Poi nel client SDK: `api_key="yourpassword"`.

### Postgres Esterno

Variabile `LETTA_PG_URI` per connettere una propria istanza PostgreSQL. Richiede estensione `pgvector`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Tool Sandboxing

Per sandbox sicuro dei custom tools: `E2B_API_KEY` e `E2B_SANDBOX_TEMPLATE_ID`.

---

## 3. Architettura degli Agenti

Un agente Letta è composto da:

| Componente | Descrizione |
|---|---|
| **System Prompt** | Include i memory blocks attaccati |
| **Memory Blocks** | Stringhe editabili (label + value) pinnate nel system prompt |
| **Messages** | In-context e out-of-context (persistiti dopo eviction) |
| **Tools** | JSON schema passato all'LLM + codice eseguibile |

### Creazione Agente (Python SDK)

```python
from letta_client import Letta

client = Letta(base_url="http://localhost:8283")

agent = client.agents.create(
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",  # obbligatorio in Docker
    memory_blocks=[
        {"label": "persona", "value": "Sono Scarlet, un agente cognitivo autonomo..."},
        {"label": "world_state", "value": "Stato corrente del mondo..."},
    ],
    tools=["web_search", "fetch_webpage"],
)
```

### Invio Messaggio

```python
response = client.agents.messages.create(
    agent_id=agent.id,
    input="Cosa sai di me?"
)
for msg in response.messages:
    print(msg)
```

---

## 4. Sistema di Memoria

### Memory Blocks (Core Memory)

- **Stringhe** con `label` (es. `persona`, `human`, `world_state`) e `value`
- **Pinnate** al system prompt → sempre nel contesto LLM
- **Editabili** dall'agente via memory tools (`core_memory_append`, `core_memory_replace`)
- **Condivisibili** tra agenti (shared blocks)
- **Attaccabili/Staccabili** via API

### Archival Memory

- Database vettoriale (PostgreSQL + `pgvector`)
- Ricerca semantica via embeddings
- Usata per: lessons learned, log storici, playbook RAG
- L'agente può fare insert/search tramite tool dedicati (`archival_memory_insert`, `archival_memory_search`)

### Recall Memory

- Tutti i messaggi sono persistiti nel DB
- Anche dopo eviction/compaction, i vecchi messaggi sono recuperabili
- Via API (per sviluppatori) e via retrieval tools (per agenti)

### Conversations

- Thread di messaggi indipendenti con lo stesso agente
- Permette messaging concorrente tra un agente e più utenti

---

## 5. Sistema di Tools

### Tools Built-in (Server-side)

| Tool | Funzione | Requisiti Docker |
|---|---|---|
| `web_search` | Ricerca web via Exa AI | `EXA_API_KEY` |
| `fetch_webpage` | Fetch + conversione HTML→markdown | Nessuno (opzionale `EXA_API_KEY`) |
| `run_code` | Esecuzione codice in sandbox (Python, JS, R, Java) | `E2B_API_KEY` |

### Tipi di Tools

| Tipo | Dove esegue | Schema | Codice |
|---|---|---|---|
| **Server tools** | Sul server Letta (sandbox) | ✅ | ✅ (Python/TS) |
| **Client tools** | Nell'ambiente locale del client | ✅ | ❌ (solo schema) |
| **MCP tools** | Sul server MCP esterno | ✅ | ❌ (solo schema) |
| **Memory tools** | Built-in nel server | Auto | Auto |

### Custom Server Tools

Si possono creare tools custom in Python o TypeScript, il cui codice viene eseguito server-side.

---

## 6. Integrazione Ollama (LLM Locale)

### Setup

1. Installare Ollama
2. `ollama pull <MODELLO>:<TAG>` (usare sempre tag Q6 o Q8, mai sotto Q5)
3. Configurare `OLLAMA_BASE_URL` nel docker run

### Creazione Agente con Modello Locale

```python
client = Letta(base_url="http://localhost:8283")

ollama_agent = client.agents.create(
    model="ollama/hermes-3-llama-3.1-8b:latest",
    embedding="ollama/mxbai-embed-large",  # embedding obbligatorio
    context_window_limit=16000,  # opzionale
)
```

> ⚠️ Letta è un framework "demanding" — modelli open weights piccoli possono essere instabili. Consigliati modelli frontier per il loop cognitivo principale.

---

## 7. Runs & Steps

- Una singola invocazione dell'agente = **Run**
- Un Run contiene multipli **Steps** (ogni step = un pass di inferenza LLM)
- Es: "fix this bug" → l'agente fa multipli steps (leggi file, scrivi file, testa)

---

## 8. ADE (Agent Development Environment)

- UI web per sviluppare e testare agenti
- Richiede connessione HTTPS per server remoti (eccezione per `localhost`)
- Opzioni per reverse proxy: ngrok, Caddy, Traefik, nginx + Let's Encrypt

---

## 9. Risorse

- **Documentazione:** [docs.letta.com](https://docs.letta.com/)
- **GitHub:** [github.com/letta-ai/letta](https://github.com/letta-ai/letta)
- **SDK Python:** `pip install letta-client`
- **SDK TypeScript:** `npm install @letta-ai/letta-client`
- **Docker Image:** `letta/letta:latest`
- **API Reference:** [docs.letta.com/api](https://docs.letta.com/api)
- **Ollama Models:** [docs.letta.com/models/ollama](https://docs.letta.com/models/ollama)
