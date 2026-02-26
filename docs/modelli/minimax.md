# Riferimento Tecnico: MiniMax API

> Documentazione di riferimento interno per il Progetto Scarlet.  
> Fonte: [minimax.io](https://www.minimax.io/) — Aggiornata: 2026-02-25

---

## 1. Panoramica MiniMax

MiniMax è un'azienda leader nello sviluppo di modelli multimodali (200M+ utenti). Piattaforma occidentale: **minimax.io** (distinta dalla versione cinese minimaxi.com).

### Modelli Disponibili

| Modello | Uso in Scarlet | Context | Note |
|---|---|---|---|
| **MiniMax-M2.5** | 🧠 **LLM Principale** (core cognitivo Scarlet) | 200K | Coding, reasoning, interleaved thinking |
| MiniMax-M2.5-highspeed | Alternativa veloce | 200K | Velocità maggiore, stessa qualità |
| MiniMax-M2.1 | Backup | 200K | Versione precedente |
| ~~MiniMax-M2-HER~~ | ~~Roleplay~~ | — | **Non disponibile con Code Plan** |

> ⚠️ **Scoperta critica (2026-02-25):** Il modello `MiniMax-M2-HER` (roleplay) **non è accessibile** con la key Code Plan. L'API restituisce `unknown model`. Il modello corretto per Scarlet è **`MiniMax-M2.5`**.

---

## 2. Piano Corrente: Code Plan

| Parametro | Valore |
|---|---|
| **Piano** | Code Plan (abbonamento fisso) |
| **Billing** | **Abbonamento fisso** (~1/10 del prezzo Claude) — NON pay-per-token |
| **Modello Principale** | `MiniMax-M2.5` |
| **API Key** | In `.env` come `MINIMAX_API_KEY` |

---

## 3. API — Compatibilità OpenAI

MiniMax espone un'API **100% compatibile con OpenAI SDK**:
- `base_url`: `https://api.minimax.io/v1`
- Function calling e tool use supportati
- Streaming SSE supportato
- **No `/v1/models` endpoint** (discovery automatica non disponibile)

### Configurazione Base

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("MINIMAX_API_KEY"),  # da .env
    base_url="https://api.minimax.io/v1"
)

response = client.chat.completions.create(
    model="MiniMax-M2.5",  # CORRETTO — non usare "minimax-m2-her"
    messages=[
        {"role": "system", "content": "Sei Scarlet, un agente cognitivo autonomo."},
        {"role": "user", "content": "Come ti senti oggi?"}
    ],
    stream=True
)
```

---

## 4. Integrazione con Letta Docker (Operativa)

### Architettura Attuale

```
docker-compose.yml
│
├─ scarlet-ollama (:11434)
│   └─ GPU CUDA (RTX 4070 Ti)
│   └─ mxbai-embed-large (embedding)
│
└─ scarlet-letta (:8283)
    ├─ OPENAI_API_KEY → MiniMax Code Plan Key
    ├─ OPENAI_BASE_URL → https://api.minimax.io/v1
    ├─ OLLAMA_BASE_URL → http://ollama:11434/v1
    └─ Agent: scarlet-core (MiniMax-M2.5)
```

### Workaround Model Discovery

MiniMax **non espone** `/v1/models`. Letta non può auto-scoprire i modelli.

**Soluzione (create-then-patch):**
1. Creare agente con `model: letta/letta-free` (handle valido)
2. PATCH `llm_config` con `model: MiniMax-M2.5` e `model_endpoint: https://api.minimax.io/v1`

Lo script `scripts/create_agent.py` automatizza questo processo.

---

## 5. Caratteristiche M2.5 per Scarlet

| Feature | Dettaglio | Rilevanza |
|---|---|---|
| **Interleaved Thinking** | `<think>...</think>` tag per ragionamento | ✅ Debug + PAD analysis |
| **Function Calling** | Tool use compatibile OpenAI | ✅ Tools Letta |
| **200K Context** | Finestra enorme | ✅ Core Memory + conversazioni |
| **Streaming SSE** | Risposte in tempo reale | ✅ UI real-time |
| **Coding** | Ottimizzato per codice | ✅ Self-improvement |

---

## 6. Limiti e Considerazioni

| Aspetto | Dettaglio |
|---|---|
| **Billing** | Abbonamento fisso Code Plan (non per-token) |
| **Modello** | Solo `MiniMax-M2.5` (M2-HER non disponibile con Code Plan) |
| **Discovery** | No `/v1/models` → serve workaround create-then-patch in Letta |
| **Embedding** | Non fornito da MiniMax → usare Ollama `mxbai-embed-large` |

---

## 7. Risorse

- **Piattaforma:** [minimax.io](https://www.minimax.io/)
- **Code Plan Docs:** [minimax.io/docs/coding-plan/cursor](https://platform.minimax.io/docs/coding-plan/cursor)
- **API Docs:** [minimax.io/platform/document](https://www.minimax.io/platform/document/MiniMax-M2-HER)
