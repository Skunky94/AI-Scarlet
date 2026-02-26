# Regole di Sviluppo per Agenti AI (LLM)

Questo file contiene le direttive fondamentali che **tutti gli agenti AI (LLM) devono seguire** quando lavorano sulla stesura di codice o documentazione per il Progetto Scarlet.

> **Ultimo aggiornamento:** 2026-02-25 — Infrastruttura operativa (Letta + MiniMax M2.5 + Ollama GPU).

---

## 0. Orientamento Rapido del Progetto

### Stato Attuale
| Componente | Tecnologia | Stato |
|---|---|---|
| **LLM Principale** | MiniMax M2.5 (via `https://api.minimax.io/v1`) | Operativo |
| **Framework Agente** | Letta v0.16.4 (Docker, porta 8283) | Operativo |
| **Embedding** | Ollama `mxbai-embed-large` (GPU, RTX 4070 Ti) | Operativo |
| **Motore Emotivo PAD** | — | Da implementare |
| **Heartbeat** | — | Da implementare |

### File Critici
| File | Scopo |
|---|---|
| `.env` | API keys (MINIMAX_API_KEY, LETTA_SERVER_PASSWORD) — **MAI in git** |
| `docker-compose.yml` | Stack Docker (Letta + Ollama GPU) |
| `scripts/create_agent.py` | Setup agente con workaround create-then-patch |
| `index.md` | Indice SSOT della documentazione |
| `docs/roadmap.md` | Stato avanzamento fasi sviluppo |
| `docs/changelog.md` | Registro modifiche datato |

---

## 1. Documentazione come Base Singola di Verita (SSOT)

- **Mantieni l'Indice:** Qualsiasi nuovo modulo, documento o servizio creato deve essere linkato in `index.md`. Non lasciare file orfani.
- **Aggiorna contestualmente:** MAI modificare la logica di sistema senza aggiornare *immediatamente* la documentazione in `docs/`. Codice e docs nello stesso commit logico.
- **Aggiorna il Changelog:** Usa `docs/changelog.md` con data per funzionalita principali. Evita logging di refactor minori.
- **Aggiorna la Roadmap:** Se un item della roadmap viene completato o cambia, aggiorna `docs/roadmap.md` con i checkbox `[x]`.

---

## 2. Principi di Architettura (Prevenire il Drift)

- **Nessuna Duplicazione:** Prima di creare utility o strumenti, verifica che non esistano gia con `grep_search`.
- **Letta e la Memoria:** Letta e il gestore della memoria. NON creare `.json`, SQLite separati, o file di stato per dati che appartengono alla Core/Archival Memory di Letta.
- **Sincronizzazione di Stato:** L'LLM locale NON deve mai scrivere direttamente nel DB Letta. Deve pubblicare "Memory Update Proposals" su un sistema di code (Redis/RabbitMQ) che il Core smalti serialmente.
- **Delega Hardware:** Cloud LLM (MiniMax M2.5) per ragionamento complesso. Ollama locale (RTX 4070 Ti) per embeddings, sentiment analysis PAD, riflessioni background.

### Architettura Corrente

```
Host Windows
  |
  +-- docker-compose.yml
       |
       +-- scarlet-ollama (:11434) -- GPU CUDA, mxbai-embed-large
       |
       +-- scarlet-letta (:8283)
            |-- OPENAI_API_KEY -> MiniMax Code Plan
            |-- OPENAI_BASE_URL -> https://api.minimax.io/v1
            |-- OLLAMA_BASE_URL -> http://ollama:11434/v1
            |-- PostgreSQL + pgvector (interno)
            |
            +-- Agent: scarlet-core
                 |-- LLM: MiniMax-M2.5 (via patch)
                 |-- Embedding: mxbai-embed-large (Ollama)
                 |-- Memory: Persona + World State blocks
```

---

## 3. Regole MiniMax Specifiche

- **Modello:** `MiniMax-M2.5` (NON `MiniMax-M2-HER` — non disponibile con Code Plan)
- **Billing:** Abbonamento fisso Code Plan (~1/10 prezzo Claude), non per-token
- **No model discovery:** MiniMax non espone `/v1/models`. In Letta, usare approccio **create-then-patch**
- **Interleaved thinking:** Le risposte contengono tag `<think>...</think>` — usarli per debug e PAD analysis

---

## 4. Pratiche di Scrittura Codice

- **Type Hints:** `def function(param: type) -> type:` per ogni funzione Python.
- **Docstring:** Spiegare il *perche* (design/business logic), non il *cosa*.
- **Modularity:** Niente file oltre 300 linee o 3 responsabilita. Separare Model (PAD), Controller (Heartbeat), Integrazioni (Letta Tools).
- **Encoding:** Script Python devono usare `sys.stdout.reconfigure(encoding='utf-8')` su Windows per evitare errori Unicode.

---

## 5. Metodologia di Testing

- **Test Reali:** Preferire test di integrazione con chiamate API/Ollama reali rispetto a mock.
- **Test PAD:** Iniettare valori estremi `[P, A, D]` per validare fallback.
- **Test Agente:** Usare `scripts/create_agent.py` per ricreazione pulita agente di test.

---

## 6. Processo Operativo

Quando lavori su un task:
1. **Leggi:** Verifica `docs/visione_architettura.md`, roadmap, e codebase rilevante.
2. **Pianifica:** Definisci piano chiaro. Se impattante, confrontati con utente.
3. **Esegui:** Codice + docstring + test.
4. **SSOT:** Aggiorna `index.md`, `roadmap.md`, `changelog.md` se architettura/features sono variate.
5. **Cleanup:** Elimina script temporanei/debug. Mantieni solo codice di produzione.
