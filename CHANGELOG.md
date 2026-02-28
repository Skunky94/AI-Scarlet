# Changelog — Progetto Scarlet

Ogni modifica significativa al progetto viene tracciata qui.
Standard: [Conventional Commits](https://www.conventionalcommits.org/)
Formato entry: `type(scope): descrizione` — file modificati, data, categoria.

> **Come aggiornare**: usa `.\scripts\commit.ps1` — aggiorna questo file automaticamente.

<!-- ENTRIES -->
---

## [2026-02-28] `feat(memory)` - migrazione archival memory → Cognee knowledge graph

**Categoria:** Feature

Sostituisce Letta archival flat + qwen2.5:7b Ollama con Cognee v0.5.3 (KuzuDB + LanceDB + SQLite, tutti embedded). `CogneeMemoryAgent.process_turn_async()` usa `cognee.add()+cognify()` per costruire un KG semantico-temporale per user. `CogneeRetriever.feed_context_async()` esegue 3 query parallele `GRAPH_COMPLETION_COT` (semantica, contesto conversazione, affinità PAD emotiva) e scrive su blocco Letta `active_memories` (meccanismo invariato). `consolidator.py` avvia un heartbeat asyncio ogni 10 min con `cognee.memify()` per pruning, strengthening e reweighting del grafo. LLM: MiniMax-M2.5 via `OPENAI_BASE_URL`. Embedding: mxbai-embed-large (Ollama locale). Thread `threading.Thread` sostituiti con `asyncio.create_task()` in openai.py per evitare conflitti event loop. Tutti i core memory blocks Letta e il PAD Engine rimangono invariati.

### File
- `requirements.txt` *(modified)* — `cognee>=0.5.3`
- `Dockerfile` *(modified)* — layer cognee separato per cache
- `docker-compose.yml` *(modified)* — volume cognee_data + 15 env vars Cognee
- `scarlet_gateway/main.py` *(modified)* — init Cognee + avvio heartbeat nel lifespan
- `scarlet_gateway/routes/openai.py` *(modified)* — swap import, async pattern
- `scarlet_memory/cognee_agent.py` *(new)*
- `scarlet_memory/cognee_retriever.py` *(new)*
- `scarlet_memory/consolidator.py` *(new)*
---

## [2026-02-28] `chore(config)` - esporta stato agente aggiornato

**Categoria:** Manutenzione

Snapshot configurazione agente post-sessione. `agent_settings.json`: parametri PAD modulati (temp=0.85, max_tokens=5017, freq_penalty=0.30). `tools.json`: `tool_ids=[]` confermato — archival gestita interamente da Cognee subconscio.

### File
- `config/agent_settings.json` *(modified)*
- `config/tools.json` *(modified)*
---

## [2026-02-28] `infra(observability)` - sistema di log centralizzato con finestre temporali

**Categoria:** Infrastruttura

Aggiunge scarlet_observability/ con TimeWindowedFileHandler, ScarletFormatter e singleton ScarletObservability. Config config/observability.json con debug/component toggle. Volume logs/ montato in docker-compose. Tutti i moduli di produzione strumentati (gateway x4, pad x4, memory x2) con log strutturati debug/info/warn/error. File log nominati YYYY-MM-DD_HH-MM.log rotanti ogni window_minutes.

### File
- `.dockerignore` *(modified)*
- `Dockerfile` *(modified)*
- `ROADMAP.md` *(modified)*
- `docker-compose.yml` *(modified)*
- `scarlet_gateway/main.py` *(modified)*
- `scarlet_gateway/routes/letta.py` *(modified)*
- `scarlet_gateway/routes/openai.py` *(modified)*
- `scarlet_gateway/routes/pad.py` *(modified)*
- `scarlet_memory/agent.py` *(modified)*
- `scarlet_memory/retriever.py` *(modified)*
- `scarlet_pad/core.py` *(modified)*
- `scarlet_pad/letta_sync.py` *(modified)*
- `scarlet_pad/modulator.py` *(modified)*
- `scarlet_pad/subconscious.py` *(modified)*
- `config/observability.json` *(new)*
- `logs/.gitkeep` *(new)*
- `scarlet_observability/__init__.py` *(new)*
- `scarlet_observability/logger.py` *(new)*
---

## [2026-02-28] `docs(roadmap)` - aggiunge ROADMAP.md con fasi, decisioni e problemi noti

**Categoria:** Documentazione

Roadmap strutturata in 5 fasi (Setup, Core Engine, Infrastruttura, Stabilizzazione, Visione). Include tabella decisioni architetturali, problemi noti, log sessioni. Fix script commit.ps1: gestione warning CRLF git con ErrorActionPreference.

### File
- `.github/copilot-instructions.md` *(modified)*
- `scripts/commit.ps1` *(modified)*
- `ROADMAP.md` *(new)*
---

## [2026-02-28] `chore(workflow)` - aggiunge commit helper e changelog automatizzato

**Categoria:** Manutenzione

scripts/commit.ps1: script PowerShell interattivo per Conventional Commits + aggiornamento CHANGELOG.md automatico. scripts/hooks/commit-msg: hook git per validare formato messaggi. .gitignore: aggiunge .cache/ e .memvid/.

### File
- `.gitignore` *(modified)*
- `scripts/commit.ps1` *(new)*
- `scripts/hooks/commit-msg` *(new)*
---

## [2026-02-28] `infra(docker)` - containerizza gateway e unifica stack di avvio

**Categoria:** Infrastruttura

Aggiunge Dockerfile, requirements.txt, .dockerignore. Unifica docker-compose.yml (depends_on+healthcheck a cascata). Lifespan handler FastAPI. Moduli leggono LETTA_URL/OLLAMA_URL/AGENT_ID da env var.

### File
- `.gitignore` *(modified)*
- `docker-compose.ui.yaml` *(modified)*
- `docker-compose.yml` *(modified)*
- `scarlet_gateway/main.py` *(modified)*
- `scarlet_gateway/routes/letta.py` *(modified)*
- `scarlet_memory/agent.py` *(modified)*
- `scarlet_memory/retriever.py` *(modified)*
- `scarlet_pad/letta_sync.py` *(modified)*
- `scarlet_pad/modulator.py` *(modified)*
- `.dockerignore` *(new)*
- `CHANGELOG.md` *(new)*
- `Dockerfile` *(new)*
- `requirements.txt` *(new)*
- `scripts/commit.ps1` *(new)*
- `scripts/hooks/commit-msg` *(new)*

---

## Storico pre-changelog (commit legacy)

I commit precedenti all'introduzione di questo workflow non seguono
il formato Conventional Commits.

| Hash      | Messaggio                    | Note                          |
|-----------|------------------------------|-------------------------------|
| `8985123` | migration antigravity -> vsc | Migrazione workspace in VS Code |
| `4c52e42` | fix                          | Fix generico                  |
| `a5dee2c` | Add files via upload         | Upload iniziale file progetto |
| `c455c1f` | Initial commit               | Setup repository              |
