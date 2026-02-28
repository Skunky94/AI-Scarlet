# Changelog — Progetto Scarlet

Ogni modifica significativa al progetto viene tracciata qui.
Standard: [Conventional Commits](https://www.conventionalcommits.org/)
Formato entry: `type(scope): descrizione` — file modificati, data, categoria.

> **Come aggiornare**: usa `.\scripts\commit.ps1` — aggiorna questo file automaticamente.

<!-- ENTRIES -->
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
