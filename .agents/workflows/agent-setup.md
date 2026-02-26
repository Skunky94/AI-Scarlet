---
description: Create or recreate the Scarlet agent on Letta with MiniMax M2.5 (create-then-patch approach)
---

# Setup Agente Scarlet

// turbo-all

1. Assicurati che lo stack Docker sia attivo (esegui `/deploy` se necessario).

2. Esegui lo script di creazione agente:
```
python scripts/create_agent.py
```

Lo script automaticamente:
- Attende che Letta sia pronto
- Elimina agenti esistenti
- Crea agente `scarlet-core` con `letta/letta-free`
- PATCH LLM config a `MiniMax-M2.5` (endpoint `https://api.minimax.io/v1`)
- Invia un messaggio di test e mostra la risposta
- Salva l'Agent ID in `.agent_id`

3. Verifica che il file `.agent_id` sia stato creato:
```
Get-Content .agent_id
```

**Note:**
- Il workaround create-then-patch e' necessario perche' MiniMax non espone `/v1/models` per auto-discovery.
- Se vuoi modificare i memory blocks (Persona/World State), edita `scripts/create_agent.py` e riesegui.
