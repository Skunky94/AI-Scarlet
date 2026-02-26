---
description: Verifica veloce stato di tutti i componenti del sistema Scarlet
---

# Status Check

// turbo-all

1. Verifica container Docker:
```
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

2. Verifica health Letta:
```
python -c "import requests,json; r=requests.get('http://localhost:8283/v1/health'); print(json.dumps(r.json(), indent=2))"
```

3. Verifica agente attivo:
```
python -c "import requests,json,sys; sys.stdout.reconfigure(encoding='utf-8'); r=requests.get('http://localhost:8283/v1/agents/', headers={'Authorization':'Bearer scarlet_dev'}); agents=r.json(); [print(f'{a[\"name\"]:20s} | {a[\"id\"]}') for a in agents] if agents else print('Nessun agente')"
```

4. Verifica modelli Ollama:
```
docker exec scarlet-ollama ollama list
```

5. Verifica spazio disco volumi:
```
docker system df -v 2>$null | Select-String "VOLUME" -Context 0,5
```
