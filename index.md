# Progetto Scarlet: Agente Cognitivo Autonomo

Benvenuto nella documentazione centrale del Progetto Scarlet.

Scarlet è un agente cognitivo di nuova concezione, progettato per essere un'entità digitale "pseudo-umana" autonoma, dotata di motivazione intrinseca, obiettivi propri e un sistema emotivo (Modello PAD) che ne influenza concretamente il comportamento logico. A differenza dei classici assistenti AI, Scarlet "vive" in background, studiando, riflettendo e agendo in base al suo strato aspirazionale (Aspirational Layer).

## Indice della Documentazione

- [Visione e Architettura](docs/visione_architettura.md): Concetti chiave, design del sistema (Letta + PAD + Heartbeat), criticità da evitare e punti di forza.
- [Roadmap di Sviluppo](docs/roadmap.md): Stati di avanzamento e pianificazione delle fasi di sviluppo.
- [Changelog](docs/changelog.md): Registro delle modifiche architetturali e di codice.
- [Regole per Sviluppo AI](AI_DEVELOPMENT_RULES.md): Linee guida fondamentali e best-practice per gli agenti LLM che lavorano sullo sviluppo di questo progetto.

### Riferimenti Tecnici
- [Riferimento Letta](docs/letta/riferimento_letta.md): Documentazione tecnica su Letta (architettura, Docker, memoria, tools, Ollama, SDK).
- [Riferimento MiniMax](docs/modelli/minimax.md): API MiniMax M2.5, integrazione con Letta Docker, workaround model discovery.
- [Ollama Docker GPU](docs/modelli/ollama_docker_gpu.md): Setup Ollama Docker con GPU CUDA, modelli per RTX 4070 Ti.

### Operazioni e Workflows
Comandi slash disponibili (`.agents/workflows/`):
- `/deploy` — Avvia/riavvia stack Docker (Letta + Ollama GPU)
- `/agent-setup` — Crea/ricrea agente Scarlet su Letta (create-then-patch)
- `/status-check` — Verifica stato di tutti i componenti
- `/docs-update` — Checklist aggiornamento documentazione post-modifica
- `/yolo` — Auto-run di tutti i comandi senza conferma

---
*Progetto Antigravity - AI-Scarlet*
