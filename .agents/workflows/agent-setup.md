---
description: Create or recreate the Scarlet agent on Letta with MiniMax M2.5 (create-then-patch approach)
---

## 🧠 Workflow: Configurazione e Creazione Agente

Lo script `create_agent.py` è uno strumento *stateless* che legge "l'identità" di Scarlet da un file di configurazione `YAML` e la instrada nell'API di Letta. Non contiene più i prompt o i blocchi hardcoded.

### Step 1: Modifica Identità (Single Source of Truth)
Se vuoi cambiare la personalità di Scarlet, i pattern cognitivi, i prompt di sistema o aggiungere informazioni al suo "mondo interiore" fisso iniziale, modificalo nell'unico file designato:
- **`h:/AI-Scarlet/.agents/config/cognitive_v2.yaml`**

### Step 2: Deployment
Una volta configurata l'identità nel file YAML, esegui il setup (eliminerà l'agente precedente e ne forgerà uno nuovo col medesimo modello, ma memoria fresca):

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
