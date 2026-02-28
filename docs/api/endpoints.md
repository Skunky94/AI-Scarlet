# API Reference

## Base URL

```
http://127.0.0.1:8000
```

---

## OpenAI-Compatible Proxy

### GET /v1/models
Lista modelli disponibili (per compatibilità Open WebUI).

**Response:**
```json
{"data": [{"id": "scarlet-core", "object": "model", "owned_by": "scarlet"}]}
```

### POST /v1/chat/completions
Endpoint principale. Pipeline completa: memoria → subconscio → Letta → streaming.

**Request:**
```json
{
  "model": "scarlet-core",
  "messages": [{"role": "user", "content": "Ciao Scarlet"}],
  "stream": true,
  "temperature": 0.7
}
```

**Response (stream):** SSE in formato OpenAI standard.

> Nota: `temperature` e `max_tokens` nel request vengono **sovrascritti** dal PAD Modulator.

---

## PAD Endpoints

### POST /api/pad/evaluate
Analizza il sentiment di un testo senza side effects.

**Request:**
```json
{"text": "Che bella giornata!"}
```

**Response:**
```json
{"dP": 0.32, "dA": 0.08, "dD": 0.12, "reason": "COMPLIMENTO | Positive (0.40, 0.50)"}
```

### PATCH /api/pad/update
Aggiorna lo stato emotivo PAD con decadimento + stimolo.

**Request:**
```json
{"dP": 0.3, "dA": 0.1, "dD": 0.1, "event_reason": "Complimento ricevuto"}
```

**Response:**
```json
{"success": true, "new_mood": "CURIOSA-CARICA", "p": 0.28, "a": 0.18, "d": 0.22, "error": ""}
```

---

## Letta Direct

### POST /api/letta/chat
Chat diretto con Letta (bypass subconscio PAD).

**Request:**
```json
{"message": "Ciao", "stream": false}
```

**Response:**
```json
{"response": "Ciao. Cos'hai in mente?", "raw_messages": [...]}
```

---

## Health

### GET /
Health check base.

**Response:**
```json
{"status": "ok", "agent": "Scarlet", "subconscious": "active"}
```
