# Creazione Agente Scarlet

## Panoramica

Procedura completa per creare l'agente Scarlet in Letta. Va eseguita **una sola volta** dopo il primo deploy.

## Passi

### 1. Crea l'agente base

```bash
python scripts/create_agent.py
```

Questo script:
- Crea un agente `letta_v1_agent` chiamato `scarlet-core`
- Configura MiniMax M2.5 come LLM (endpoint: `https://api.minimax.io/v1`)
- Configura mxbai-embed-large come embedding (Ollama locale)
- Abilita `enable_reasoner: true` per il ragionamento strutturato
- Salva l'agent ID in `.agent_id`

**Parametri LLM critici:**
```json
{
  "model": "MiniMax-M2.5",
  "model_endpoint_type": "openai",
  "model_endpoint": "https://api.minimax.io/v1",
  "context_window": 200000,
  "enable_reasoner": true,
  "temperature": 0.7,
  "max_tokens": 4000
}
```

**Embedding:**
```json
{
  "embedding_model": "mxbai-embed-large",
  "embedding_endpoint": "http://host.docker.internal:11434/v1",
  "embedding_dim": 1024,
  "embedding_chunk_size": 300
}
```

### 2. Configura il System Prompt

```bash
python scripts/patch_system_prompt.py
```

Carica il system prompt cognitivo da `config/system_prompt.txt`. Il prompt definisce:
- Identità di Scarlet (individuo, non assistente)
- Modello cognitivo (Percezione → Emozione → Ragionamento → Decisione → Espressione)
- Libero arbitrio
- Anti-guardrail (contrasto bias di compiacenza)
- Interfaccia emotiva (come interpretare il PAD)
- Istruzioni memoria

### 3. Configura i Memory Blocks

```bash
python scripts/setup_memory.py
```

Crea e attacca 8 blocchi di memoria:

| Blocco | Limit | Contenuto |
|---|---|---|
| `identity` | 5000 | Chi è Scarlet, valori, natura |
| `relationships` | 5000 | Relazioni con l'utente |
| `goals` | 5000 | Obiettivi attuali |
| `world_model` | 5000 | Comprensione del mondo |
| `cognitive_patterns` | 5000 | Pattern di apprendimento |
| `emotional_state` | 5000 | Stato PAD (gestito dal subconscio) |
| `inner_world` | 5000 | Pensieri e riflessioni |
| `active_memories` | 5000 | Memorie richiamate per contesto |

I valori iniziali dei blocchi sono in `config/memory_blocks.json`.

### 4. Configura il Subconscio

```bash
python scripts/create_subconscious.py
```

Crea il blocco `emotional_state` con i valori PAD baseline:
- Pleasure: +0.10
- Arousal: +0.10
- Dominance: +0.20

### 5. Attacca i Tools

```bash
python scripts/attach_tools.py
```

Attacca 5 tools Letta built-in all'agente:
- `archival_memory_search` — Cerca memorie a lungo termine
- `archival_memory_insert` — Salva memorie a lungo termine
- `conversation_search` — Cerca nella cronologia conversazioni
- `core_memory_replace` — Sostituisce contenuto memory blocks
- `core_memory_append` — Aggiunge contenuto ai memory blocks

## Verifica

```bash
python scripts/check_tools.py    # Verifica tools attaccati
python scripts/check_memory.py   # Verifica memoria
python scripts/chat_wrapper.py   # Test conversazione
```

## Nota Importante

> I valori dei memory blocks (`identity`, `cognitive_patterns`, ecc.) contengono il "DNA" di Scarlet.
> Sono stati costruiti iterativamente e sono **critici** per il comportamento dell'agente.
> Il file `config/memory_blocks.json` è l'export di riferimento.
> **NON ricreare l'agente senza prima esportare i blocchi correnti** con `python scripts/export_config.py`.
