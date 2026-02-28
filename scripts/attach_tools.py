"""Attacca i 5 tools a Scarlet uno per uno."""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import requests, json

aid = open('.agent_id').read().strip()
h = {'Authorization': 'Bearer scarlet_dev', 'Content-Type': 'application/json'}

TOOLS = [
    'archival_memory_search',
    'archival_memory_insert',
    'conversation_search',
    'core_memory_replace',
    'core_memory_append',
]

# Trova tool IDs
r = requests.get('http://localhost:8283/v1/tools', headers=h, params={'limit': 100})
all_tools = r.json()
tool_map = {t['name']: t['id'] for t in all_tools if t['name'] in TOOLS}

# Cerca endpoint di attach
r_api = requests.get('http://localhost:8283/openapi.json', headers=h)
paths = r_api.json()['paths']
tool_paths = [p for p in paths if 'tool' in p.lower()]
print("Endpoints tool:")
for p in tool_paths:
    methods = list(paths[p].keys())
    print(f"  {p} -> {methods}")

# Prova attach via PATCH con tool_ids
print(f"\nAttaching {len(tool_map)} tools...")
for name, tid in tool_map.items():
    # Prova endpoint attach
    url = f'http://localhost:8283/v1/agents/{aid}/tools/attach/{tid}'
    r = requests.patch(url, headers=h)
    if r.status_code == 200:
        print(f"  OK: {name}")
    else:
        # Prova POST
        url2 = f'http://localhost:8283/v1/agents/{aid}/tools/{tid}'
        r2 = requests.post(url2, headers=h)
        if r2.status_code == 200:
            print(f"  OK (POST): {name}")
        else:
            print(f"  FAIL: {name} -> PATCH {r.status_code}, POST {r2.status_code}")

# Verifica
r_check = requests.get(f'http://localhost:8283/v1/agents/{aid}', headers=h)
print(f"\nTools attaccati: {r_check.json().get('tool_names', [])}")
