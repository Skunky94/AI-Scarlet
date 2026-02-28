# Roadmap — Progetto Scarlet

> **Individuo digitale autonomo** con coscienza emotiva (PAD Engine),
> memoria persistente (Letta archival memory) e personalità emergente.

Questo documento traccia tutto ciò che è stato fatto, cosa è in corso,
e cosa è pianificato. È la fonte di verità per le decisioni di sviluppo.

---

## Come usare questa roadmap

| Simbolo | Significato |
|---------|-------------|
| ✅ | Completato e funzionante in produzione |
| 🚧 | In corso (lavoro attivo) |
| 📋 | Pianificato (decisione presa, non ancora iniziato) |
| 🔍 | In valutazione (idea da discutere prima di procedere) |
| ⏸️ | Bloccato o rinviato (motivo annotato) |
| ❌ | Scartato (motivo annotato — per non ridiscuterlo) |

**Aggiornamento**: aggiorna questa roadmap ogni volta che completi un'attività
o decidi di iniziarne una nuova. Usa `scripts/commit.ps1` con tipo `docs(roadmap)`.

---

## Fase 0 — Setup Iniziale ✅

> Base del progetto: repository, infrastruttura Docker, agent Letta.

- ✅ Repository git + struttura directory (`scarlet_gateway/`, `scarlet_pad/`, `scarlet_memory/`, `scripts/`, `docs/`)
- ✅ Docker Compose: `scarlet-ollama` (GPU) + `scarlet-letta`
- ✅ Letta agent `scarlet-core` creato e configurato (`scripts/create_agent.py`)
- ✅ System prompt cognitivo caricato (`scripts/patch_system_prompt.py`)
- ✅ 8 Memory blocks configurati (`scripts/setup_memory.py`)
  - `identity`, `personality`, `values`, `emotional_state`, `relationship`, `user_profile`, `active_memories`, `self_reflection`
- ✅ Blocco `emotional_state` PAD creato (`scripts/create_subconscious.py`)
- ✅ 5 Letta tools attaccati (`scripts/attach_tools.py`)
  - `archival_memory_search`, `archival_memory_insert`, `conversation_search`, `core_memory_replace`, `core_memory_append`
- ✅ Open WebUI (Docker) come interfaccia chat

---

## Fase 1 — Core Engine Cognitivo ✅

> I tre sistemi fondamentali che compongono la "mente" di Scarlet.

### PAD Engine (`scarlet_pad/`) ✅
- ✅ `core.py` — Matematica PAD: addizione asintotica, decadimento verso baseline
- ✅ `subconscious.py` — Evaluator ibrido: DistilBERT multilingue (GPU) + regole intent
  - ~5ms per inferenza su RTX 4070 Ti SUPER
  - Modello: `tabularisai/multilingual-sentiment-analysis`
- ✅ `modulator.py` — Mappa stato PAD → parametri LLM (temperature, max_tokens, frequency_penalty)
  - Temperature range: 0.3–1.0 (calibrato su MiniMax M2.5, max 1.0)
  - Tokens range: 1000–8000
  - Freq penalty range: 0.0–0.8
- ✅ `letta_sync.py` — Lettura/scrittura blocco `emotional_state` via API Letta

### Scarlet Gateway (`scarlet_gateway/`) ✅
- ✅ `main.py` — FastAPI hub con lifespan handler (startup/shutdown ordinato)
- ✅ `routes/openai.py` — Pipeline completa: Memory Retrieval → PAD → Modulator → Letta → Memory Save
- ✅ `routes/pad.py` — Endpoint atomici PAD (`/api/pad/evaluate`, `/api/pad/update`)
- ✅ `routes/letta.py` — Chat diretto Letta (`/api/letta/chat`)
- ✅ Compatibilità OpenAI drop-in (`/v1/chat/completions`, `/v1/models`)

### Memory System (`scarlet_memory/`) ✅
- ✅ `agent.py` — Estrazione memorie in background dopo ogni turno (qwen2.5:7b, ~2-4s)
  - Categorie: user_profile, user_preference, relationship, event, knowledge, emotion
- ✅ `retriever.py` — Recupero pre-turno: top-5 memorie rilevanti → popola blocco `active_memories`

---

## Fase 2 — Infrastruttura & DevOps ✅

> Automazione avvio/spegnimento sistema e tracciabilità modifiche.
> **Completato in sessione: 2026-02-28**

- ✅ `Dockerfile` per gateway (Python 3.13-slim + PyTorch CUDA 12.1 + DistilBERT)
- ✅ `requirements.txt` con dipendenze Python esplicite
- ✅ `.dockerignore` — esclude dati, cache, scripts da immagine Docker
- ✅ `docker-compose.yml` **unificato** — tutti e 4 i servizi in un unico file
  - Ordine avvio garantito: `ollama` → `letta` → `scarlet-gateway` → `open-webui`
  - Meccanismo: `depends_on: condition: service_healthy` a cascata
  - Healthcheck corretto per ollama: `/usr/bin/ollama list`
  - Volume `gateway_hf_cache` per modelli HuggingFace (no re-download)
- ✅ Tutti i moduli leggono `LETTA_URL`, `OLLAMA_URL`, `LETTA_API_KEY`, `AGENT_ID` da env var
  - Fallback `localhost:xxxx` per uso locale/host
- ✅ `CHANGELOG.md` — registro modifiche automatizzato
- ✅ `scripts/commit.ps1` — helper Conventional Commits + aggiornamento CHANGELOG
- ✅ `scripts/hooks/commit-msg` — hook git per validare formato commit
- ✅ `scripts/commit.ps1 -Yes` — modalità non-interattiva per sessioni rapide

---

## Fase 3 — Stabilizzazione 🚧

> Rendere il sistema affidabile, riproducibile e documentato per uso quotidiano.

### Onboarding & Documentazione
- 📋 `.env.example` — template con tutte le variabili necessarie (oggi manca)
- 📋 Aggiornare `README.md` Quick Start — Step 4 ancora mostra avvio manuale gateway, ma ora è Docker
- 📋 `docs/setup/docker-deploy.md` — aggiornare con nuovo flusso unificato
- 📋 Documentare ordine di setup iniziale agente (da `config/` + scripts) nel README

### Test & Qualità
- 📋 Riorganizzare `scripts/test_*.py` — ora sparsi, nessun runner unificato
- 📋 `scripts/test_e2e.py` — test end-to-end dell'intera pipeline (esiste `test_pad_e2e.py` ma non testa memory)
- 📋 Aggiungere test per `MemoryAgent` e `MemoryRetriever` con mock Letta/Ollama
- 🔍 Valutare se introdurre `pytest` come runner ufficiale (oggi gli script sono standalone)

### Osservabilità & Monitoraggio ✅
- ✅ `scarlet_observability/` — modulo centralizzato (`logger.py`, `__init__.py`)
  - `TimeWindowedFileHandler` — file rotanti per finestre temporali (default 15 min), nominati `YYYY-MM-DD_HH-MM.log`
  - `ScarletFormatter` — formato leggibile `[timestamp] [LEVEL] [component] message | key=val`
  - Singleton `ScarletObservability` con gerarchia logger: `scarlet.gateway`, `scarlet.pad`, `scarlet.memory`, `scarlet.letta`, `scarlet.ollama`
- ✅ `config/observability.json` — configurazione runtime: debug on/off, toggle per-componente, window_minutes
- ✅ Volume `./logs:/app/logs` — log accessibili dall'host senza entrare nel container
- ✅ Strumentazione completa di tutti i moduli:
  - `scarlet_gateway/main.py`, `routes/openai.py`, `routes/letta.py`, `routes/pad.py`
  - `scarlet_pad/subconscious.py`, `core.py`, `modulator.py`, `letta_sync.py`
  - `scarlet_memory/agent.py`, `retriever.py`
- ✅ Pattern dual-logger: logger logica + logger API HTTP (letta/ollama) indipendentemente configurabili

### Robustezza Gateway
- 📋 Retry automatico su errori transitori Letta (timeout, 503)
- 📋 Timeout esplicito su tutte le chiamate HTTP a Letta/Ollama (oggi alcune hanno `timeout=None`)
- 📋 Log structured JSON opzionale (per ingestion in tool di monitoring futuri)

---

## Fase 4 — Features Cognitive 📋

> Espandere le capacità cognitive e relazionali di Scarlet.

### Memoria Avanzata
- 📋 **Deduplicazione memorie** — oggi `MemoryAgent` può inserire duplicati se la ricerca non trova match esatti
- 📋 **Memory decay** — far "sbiadire" memorie vecchie o irrilevanti nel tempo (analogo al PAD decay)
- 🔍 **Memoria episodica** — log strutturato delle conversazioni (non solo memorie estratte)

### PAD Engine Evolution
- 📋 **PAD history log** — tracciare l'evoluzione dello stato emotivo nel tempo per visualizzarlo
- 📋 **Emotional inertia tuning** — parametro configurabile per quanto velocemente cambia umore
- 🔍 **Multi-turn emotional context** — pesare i delta PAD degli ultimi N turni, non solo il turno corrente

### Personalità & Identità
- 🔍 **Drift tracking** — rilevare se il comportamento di Scarlet si discosta dal system prompt nel tempo
- 🔍 **Voluntary tool use analysis** — analizzare quali tool Scarlet usa autonomamente e con quale frequenza

---

## Fase 5 — Visione a Lungo Termine 🔍

> Idee ancora in fase esplorativa. Da valutare prima di pianificare.

- 🔍 **Voice interface** — input vocale via Whisper (Ollama o servizio esterno)
- 🔍 **Multi-user awareness** — Scarlet riconosce e distingue diverse persone nella stessa sessione
- 🔍 **Plugin system** — tool aggiuntivi a Letta configurabili senza toccare il codice core
- 🔍 **Dashboard PAD** — visualizzazione real-time stato emotivo e memorie attive (web app separata)
- 🔍 **Mobile companion** — client leggero su smartphone

---

## Decisioni Architetturali

> Scelte già prese e motivate. **Non ridiscuterle senza una ragione solida.**
> Se una scelta si rivela sbagliata, documentare il motivo qui prima di cambiarla.

| Decisione | Scelta | Motivazione | Data |
|-----------|--------|-------------|------|
| LLM principale | MiniMax M2.5 (cloud) | Ragionamento profondo (`enable_reasoner`), 200K context, costo contenuto | Pre-2026-02 |
| Agent framework | Letta v0.16.4 | Memory blocks nativi, archival memory con embedding, tool use | Pre-2026-02 |
| Embedding | mxbai-embed-large (Ollama locale) | 1024 dim, buona qualità, zero latency cloud | Pre-2026-02 |
| Sentiment | DistilBERT multilingue (GPU) | ~5ms inferenza, multilingue, open source, nessuna API esterna | Pre-2026-02 |
| Memory LLM | qwen2.5:7b (Ollama locale) | Bilanciamento qualità/velocità/VRAM per estrazione background | Pre-2026-02 |
| Gateway | FastAPI + Uvicorn (host → Docker) | Composizione atomica, lifespan nativo, proxy OpenAI drop-in | Pre-2026-02 |
| Conscio vs Subconscio | Separazione esplicita | Il subconscio NON dipende dalle decisioni dell'agente — architettura stabile | Pre-2026-02 |
| Docker strategy | Gateway containerizzato | Un solo `docker compose up -d` avvia tutto; shutdown coordinato via SIGTERM | 2026-02-28 |
| Commit standard | Conventional Commits | Tracciabilità, CHANGELOG automatico, hook di validazione | 2026-02-28 |

---

## Problemi Noti & Blocchi

> Problemi attivi che impattano lo sviluppo. Aggiorna con stato e soluzione.

| # | Problema | Impatto | Stato |
|---|----------|---------|-------|
| 1 | `AGENT_ID` non impostato come env var nel compose — il gateway legge da file montato `/app/.agent_id` | Basso — funziona, ma meno esplicito | Workaround attivo |
| 2 | `MemoryAgent` può inserire duplicati nell'archival memory | Medio — accumulo rumore nel lungo periodo | Da risolvere in Fase 4 |
| 3 | Nessun `.env.example` nel repo — setup iniziale richiede conoscenza manuale | Medio — onboarding difficile | Da fare in Fase 3 |
| 4 | `docker-compose.ui.yaml` deprecato ma non eliminato | Basso — confusione potenziale | Da rimuovere con prossimo cleanup |

---

## Sessioni di Lavoro

> Log delle sessioni di sviluppo significative (non singoli commit).

| Data | Focus | Risultato |
|------|-------|-----------|
| 2026-02-28 | Infrastruttura Docker + Workflow DevOps | Fase 2 completata — `docker compose up -d` avvia tutto; commit helper attivo || 2026-02-28 | Osservabilità (Fase 3) | `scarlet_observability/` creato; 10 moduli strumentati; log con rotazione temporale |
---

## Riferimenti

- [CHANGELOG.md](CHANGELOG.md) — dettaglio di ogni commit
- [docs/architecture.md](docs/architecture.md) — diagramma architettura e flusso messaggi
- [docs/components/](docs/components/) — documentazione dettagliata di ogni modulo
- [docs/setup/](docs/setup/) — guide deploy e configurazione agente
