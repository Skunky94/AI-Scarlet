# Memory System — Estrazione e Recupero Memorie

## Panoramica

Il sistema di memoria opera in due fasi complementari:
- **Pre-turno** (Retriever): recupera memorie rilevanti e le mette in contesto
- **Post-turno** (Agent): estrae nuove memorie dalla conversazione e le salva

## File

| File | Ruolo |
|---|---|
| `agent.py` | Estrazione memorie (background, usa qwen2.5:7b via Ollama) |
| `retriever.py` | Recupero pre-turno, aggiorna blocco `active_memories` |

## Memory Agent (`agent.py`)

### Flusso
1. Riceve il turno completo (user_msg + think + response)
2. Invia a qwen2.5:7b (Ollama) con prompt di estrazione
3. LLM restituisce JSON con memorie categorizzate
4. Python engine cerca duplicati nell'archival memory
5. Inserisce/aggiorna memorie

### Categorie Memorie
- `user_profile` — Chi è l'utente
- `user_preference` — Preferenze specifiche
- `relationship` — Dinamica relazionale
- `event` — Evento significativo
- `self_reflection` — Insight di Scarlet su sé stessa

### Limite: max 5 memorie per categoria

### Deduplicazione
- **Duplicato**: un testo contiene l'altro → skip
- **Simile**: >60% parole in comune → update (elimina vecchio, inserisce nuovo)

### Warmup
All'avvio, pre-carica qwen2.5:7b in VRAM con `keep_alive: "30m"` per evitare cold start.

## Memory Retriever (`retriever.py`)

### Flusso Pre-turno
1. Riceve il messaggio utente
2. Cerca nell'archival memory (ricerca semantica, top-5)
3. Formatta le memorie trovate
4. Aggiorna il blocco `active_memories` in Letta

### Blocco `active_memories`
```
=== Memorie Attive (richiamate per contesto) ===
1. [user_profile] L'utente è uno sviluppatore italiano...
2. [relationship] Relazione collaborativa, l'utente apprezza...
3. [event] Nella sessione del 26/02, abbiamo configurato...
```

### Auto-creazione blocchi
Se il blocco `active_memories` non esiste, lo crea automaticamente e lo attacca all'agente.
