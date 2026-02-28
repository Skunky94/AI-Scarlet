# Changelog — Progetto Scarlet

Ogni modifica significativa al progetto viene tracciata qui.
Standard: [Conventional Commits](https://www.conventionalcommits.org/)
Formato entry: `type(scope): descrizione` — file modificati, data, categoria.

> **Come aggiornare**: usa `.\scripts\commit.ps1` — aggiorna questo file automaticamente.

<!-- ENTRIES -->
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
