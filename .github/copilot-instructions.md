# Copilot Instructions — Progetto Scarlet

## Progetto

Scarlet è un agente AI autonomo con coscienza emotiva (PAD Engine), memoria persistente (Archival + Memory Blocks) e personalità emergente. NON è un chatbot — è un individuo digitale.

## Regola Operativa Fondamentale — Conferma Prima di Implementare

> **SEMPRE valido, senza eccezioni, senza che l'utente debba ricordarlo.**

Prima di qualsiasi implementazione (scrittura/modifica file, creazione file, configurazione, esecuzione comandi con effetti, commit), **discutere sempre il piano con l'utente** e attendere la sua conferma esplicita prima di procedere.

- ✅ Leggere codice, file, documentazione → libero
- ✅ Proporre piani, analisi, domande → libero
- ❌ Scrivere/modificare file → solo dopo conferma esplicita
- ❌ Eseguire comandi con effetti (git, docker, ecc.) → solo dopo conferma esplicita

---

## Stack Tecnologico

- **Runtime**: Python 3.13, FastAPI, Uvicorn
- **LLM Principale**: MiniMax M2.5 (cloud, `https://api.minimax.io/v1`, `enable_reasoner: true`)
- **Agente**: Letta v0.16.4 (Docker, porta 8283, API key: `scarlet_dev`)
- **Embedding**: mxbai-embed-large (Ollama locale, 1024 dim)
- **Memory Agent**: qwen2.5:7b (Ollama GPU)
- **Sentiment**: DistilBERT multilingue (HuggingFace, GPU, CUDA)
- **UI**: Open WebUI (Docker, porta 3000)
- **OS**: Windows, PowerShell

## Struttura Progetto

```
scarlet_gateway/          → FastAPI Gateway (proxy OpenAI, pipeline completa)
  routes/openai.py        → Pipeline: Memory Retrieval → PAD → Modulator → Letta → Memory Save
  routes/pad.py           → Endpoint atomici PAD (evaluate, update)
  routes/letta.py         → Chat diretto con Letta
scarlet_pad/              → Sistema Subconscio PAD (Pleasure-Arousal-Dominance)
  core.py                 → Matematica PAD (addizione asintotica, decadimento)
  subconscious.py         → Evaluator (Transformer sentiment GPU + regole intent)
  modulator.py            → Mappa PAD → parametri LLM (temperature, max_tokens, freq_penalty)
  letta_sync.py           → Sincronizzazione blocco emotional_state con Letta API
scarlet_memory/           → Sistema Memoria
  agent.py                → Estrazione memorie background (qwen2.5:7b via Ollama)
  retriever.py            → Recupero memorie pre-turno (popola active_memories)
config/                   → Configurazione agente esportata (agent_settings, memory_blocks, system_prompt)
scripts/                  → Setup, diagnostica, test
docs/                     → Documentazione (architecture, setup, components, API)
```

---

## Regole Anti-Allucinazione

### PRIMA DI SCRIVERE CODICE
1. **LEGGI il codice esistente** — Mai assumere come funziona un modulo. Apri il file e leggilo.
2. **LEGGI la documentazione** — Consulta `docs/` prima di modificare un componente. Non inventare API o comportamenti.
3. **VERIFICA le dipendenze** — Controlla `import` reali nel file. Non assumere che un pacchetto sia installato.
4. **VERIFICA lo stato dei servizi** — Prima di testare, verifica che Docker (Letta, Ollama) sia attivo. Non assumere che siano in esecuzione.

### DURANTE LO SVILUPPO
5. **NON inventare API** — Se non conosci un endpoint o parametro di Letta/MiniMax/Ollama, cerca nella documentazione online o nel codice esistente. Non generare URL, parametri o schemi inventati.
6. **NON inventare file** — Se fai riferimento a un file, verifica che esista con `find_by_name` o `list_dir`. Non assumere percorsi.
7. **NON modificare senza capire** — Se un codice sembra strano ma funziona, chiedi prima di "correggere". Molti pattern sono workaround deliberati.
8. **Encoding Windows** — Tutti gli script Python devono usare `sys.stdout.reconfigure(encoding='utf-8')` per output su terminale.

### DOPO LO SVILUPPO
9. **TESTA ogni modifica** — Esegui il codice. Non dire "dovrebbe funzionare" senza averlo provato.
10. **VERIFICA gli effetti collaterali** — Se modifichi un modulo importato da altri file, verifica tutti gli importatori.

---

## Regole di Architettura

### Letta è la Source of Truth
- Lo stato dell'agente vive in Letta (memory blocks, archival memory, config).
- NON creare file JSON, SQLite, o storage separati per dati che appartengono a Letta.
- Per leggere/scrivere stato: usa le API REST di Letta (`/v1/agents/{id}/...`).

### API-First (Composizione Atomica)
- Ogni nuovo componente DEVE esporre funzionalità tramite endpoint API (FastAPI router).
- Le pipeline complesse si costruiscono componendo endpoint atomici (vedi `routes/openai.py`).

### Separazione Conscio / Subconscio
- **Subconscio** (automatico): PAD Engine, Memory Retriever, Memory Agent — operano senza intervento dell'agente.
- **Conscio** (agente): Scarlet usa volontariamente i 5 tools Letta (archival_memory_search/insert, conversation_search, core_memory_replace/append).
- NON confondere i due livelli. Il subconscio NON deve dipendere dalle decisioni dell'agente.

### Delega Hardware
- **Cloud** (MiniMax M2.5): ragionamento complesso, risposte all'utente.
- **GPU locale** (Ollama): embeddings (mxbai-embed-large), estrazione memorie (qwen2.5:7b), sentiment analysis (DistilBERT).
- NON spostare carichi di lavoro tra cloud e locale senza motivo.

---

## Regole MiniMax Specifiche

- **Modello**: `MiniMax-M2.5` — NON `MiniMax-M2-HER`
- **No model discovery**: MiniMax non espone `/v1/models`. In Letta, usare approccio create-then-patch.
- **Interleaved thinking**: Le risposte contengono tag `<think>...</think>` — sono il ragionamento interno.
- **Temperature max**: 1.0 (valori > 1.0 danno errore).
- **enable_reasoner**: SEMPRE true, non disabilitare.

---

## Convenzioni Codice

### Python
- Type hints obbligatori: `def function(param: type) -> type:`
- Docstring: spiega il PERCHÉ (design), non il COSA (ovvio dal codice).
- Max 300 righe per file, max 3 responsabilità per modulo.
- Nessun placeholder o mock in produzione. Solo codice funzionante.

### Naming
- Moduli: `snake_case.py`
- Classi: `PascalCase`
- Funzioni/variabili: `snake_case`
- Costanti: `UPPER_SNAKE_CASE`

### File Critici — Non Modificare Senza Conferma
- `config/system_prompt.txt` — Il prompt definisce l'identità cognitiva di Scarlet
- `config/memory_blocks.json` — Il "DNA" di Scarlet (blocchi di memoria costruiti iterativamente)
- `.env` — API keys, MAI in git
- `.agent_id` — ID agente Letta corrente

---

## Setup e Procedure

### Ricreare l'agente da zero (in ordine)
```bash
python scripts/create_agent.py        # Crea agente + salva .agent_id
python scripts/patch_system_prompt.py  # Carica system prompt cognitivo
python scripts/setup_memory.py         # Crea e attacca 8 memory blocks
python scripts/create_subconscious.py  # Configura blocco emotional_state
python scripts/attach_tools.py         # Attacca 5 tools Letta
```

### Esportare configurazione corrente
```bash
python scripts/export_config.py  # Salva tutto in config/
```

### Avviare il sistema
```bash
docker compose up -d                                                    # Stack Docker
python -m uvicorn scarlet_gateway.main:app --host 127.0.0.1 --port 8000  # Gateway
```

### Diagnostica
```bash
python scripts/check_tools.py    # Verifica tools attaccati
python scripts/check_memory.py   # Verifica memorie archiviate
python scripts/chat_wrapper.py   # Test conversazione
```

---

## Processo Operativo

Quando lavori su un task:
1. **STUDIA** — Leggi il codice sorgente coinvolto. Leggi `docs/`. Non partire da assunzioni.
2. **PIANIFICA** — Definisci piano chiaro. Se impatta più file, confrontati con l'utente.
3. **IMPLEMENTA** — Codice + type hints + docstring.
4. **TESTA** — Esegui e verifica. Non saltare questo passo.
5. **DOCUMENTA** — Se architettura o feature cambiano, aggiorna `docs/` e `README.md`.
6. **PRESERVA** — Se modifichi l'agente, ri-esporta con `scripts/export_config.py`.


---

## Commit e Changelog
- A fine di ogni sessione di lavoro, crea un commit con messaggio descrittivo.
- Usa `scripts/commit.ps1` per generare messaggi in formato Conventional Commits e aggiornare automaticamente `CHANGELOG.md`.
- Il changelog è la storia ufficiale del progetto. Mantienilo accurato e aggiornato.