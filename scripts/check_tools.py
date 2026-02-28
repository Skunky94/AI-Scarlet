"""Verifica tools disponibili in Letta e quelli attaccati a Scarlet."""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import requests, json

aid = open('.agent_id').read().strip()
h = {'Authorization': 'Bearer scarlet_dev'}

# Tools dell'agente
r = requests.get(f'http://localhost:8283/v1/agents/{aid}', headers=h)
agent = r.json()
print(f"=== TOOLS ATTACCATI A SCARLET ===")
print(f"Tool IDs: {agent.get('tool_ids', [])}")
print(f"Tool Names: {agent.get('tool_names', [])}")
print()

# Tools disponibili nel server
r2 = requests.get('http://localhost:8283/v1/tools', headers=h, params={'limit': 100})
tools = r2.json()
print(f"=== TOOLS DISPONIBILI NEL SERVER ({len(tools)}) ===")
for t in tools:
    name = t.get('name', '?')
    desc = t.get('description', '')[:80]
    tid = t.get('id', '?')
    print(f"  {name:40s} | {desc}")
