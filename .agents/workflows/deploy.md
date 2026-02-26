---
description: Deploy/restart the full Docker stack (Letta + Ollama GPU) and verify health
---

# Deploy Stack Docker

// turbo-all

1. Assicurati di essere nella directory del progetto `h:\AI-Scarlet`

2. Avvia lo stack Docker:
```
docker compose up -d
```

3. Attendi 15 secondi per l'inizializzazione di Letta:
```
Start-Sleep -Seconds 15
```

4. Verifica health Letta:
```
python -c "import requests; r = requests.get('http://localhost:8283/v1/health'); print(r.json())"
```

5. Verifica che Ollama sia raggiungibile e il modello embedding sia caricato:
```
docker exec scarlet-ollama ollama list
```

6. Se lo stack era gia' attivo e vuoi riavviare:
```
docker compose down; docker compose up -d
```
