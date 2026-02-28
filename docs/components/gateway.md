# Gateway — Scarlet API Hub

## Panoramica

Il Gateway è un'applicazione FastAPI che funge da proxy OpenAI-compatibile e orchestratore della pipeline completa.

## File

| File | Ruolo |
|---|---|
| `main.py` | Entry point FastAPI, monta i router |
| `routes/openai.py` | Pipeline completa (memoria + PAD + Letta + streaming) |
| `routes/pad.py` | Endpoint atomici PAD (evaluate, update) |
| `routes/letta.py` | Chat diretto con Letta (bypass subconscio) |

## Pipeline OpenAI (`routes/openai.py`)

Questo è il cuore del sistema. Ogni chiamata a `/v1/chat/completions` esegue:

1. **STEP 0.5** — `MemoryRetriever.feed_context()`: cerca memorie rilevanti, popola `active_memories`
2. **STEP 1** — `SubconsciousEvaluator.evaluate_input()`: sentiment (GPU) + intent → delta PAD
3. **STEP 2** — `LettaPADSync`: legge stato attuale, applica decadimento + stimolo, scrive `emotional_state`
4. **STEP 2.5** — `PADModulator.apply_to_agent()`: mappa PAD → temperature, max_tokens, frequency_penalty
5. **STEP 3** — Letta streaming: POST a `/v1/agents/{id}/messages/stream`, parse SSE, re-stream in formato OpenAI
6. **STEP 4** — `MemoryAgent.process_turn()` (background thread): estrae e salva memorie dal turno

### Singletons

```python
_pad_modulator = PADModulator()    # Sempre in RAM
_memory_agent = MemoryAgent()      # Pre-warm qwen2.5:7b in VRAM
_memory_retriever = MemoryRetriever()  # Sempre in RAM
```

## Avvio

```bash
python -m uvicorn scarlet_gateway.main:app --host 127.0.0.1 --port 8000
# oppure
python scarlet_gateway/main.py  # porta 8000, reload attivo
```
