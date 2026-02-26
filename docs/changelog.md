# Changelog

Tutte le modifiche importanti a questo progetto saranno documentate in questo file.
Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/).

## [2026-02-25] — Infrastruttura e Primo Agente

### Added
- **Infrastruttura Docker:** `docker-compose.yml` con Letta Server v0.16.4 + Ollama GPU (RTX 4070 Ti).
- **Primo agente `scarlet-core`** su Letta con MiniMax M2.5 e memory blocks Persona + World State.
- **Sicurezza:** `.env` per API keys, `.gitignore` per escludere dati sensibili e persistenti.
- **Script:** `scripts/create_agent.py` — setup automatizzato agente con workaround create-then-patch.

### Changed
- **MiniMax:** Modello corretto da M2-HER a **M2.5** (M2-HER non disponibile con Code Plan).
- **Billing:** Code Plan è **abbonamento fisso** (non pay-per-token come inizialmente documentato).

### Documentation
- `docs/letta/riferimento_letta.md` — Riferimento tecnico Letta completo.
- `docs/modelli/minimax.md` — API MiniMax, integrazione Letta, workaround discovery.
- `docs/modelli/ollama_docker_gpu.md` — Setup Ollama Docker con GPU CUDA.

## [Unreleased] — Design Architetturale
### Added
- Creazione della documentazione ufficiale del progetto (Index, Visione Architetturale, Roadmap, AI Rules).
- Definizione dell'architettura ibrida Letta + PAD + Intelligent Heartbeat.
