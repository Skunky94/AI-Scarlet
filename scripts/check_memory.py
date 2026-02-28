"""Verifica memorie salvate nell'archival memory di Scarlet."""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import requests, json

aid = open('.agent_id').read().strip()
h = {'Authorization': 'Bearer scarlet_dev'}

# Lista tutte le memorie
r = requests.get(
    f'http://localhost:8283/v1/agents/{aid}/archival-memory',
    headers=h, params={'limit': 50}
)
data = r.json()

print(f"═══ ARCHIVAL MEMORY DI SCARLET ═══")
print(f"Totale memorie: {len(data)}\n")

for i, e in enumerate(data):
    tags = e.get('tags', []) or ['no-tag']
    text = e.get('text', '')
    ts = e.get('created_at', '?')
    mid = e.get('id', '?')
    print(f"  {i+1}. [{', '.join(tags)}]")
    print(f"     {text}")
    print(f"     created: {ts}")
    print(f"     id: {mid}")
    print()

# Core memory blocks
print(f"═══ MEMORY BLOCKS ATTIVI ═══\n")
r2 = requests.get(
    f'http://localhost:8283/v1/agents/{aid}/core-memory/blocks',
    headers=h
)
blocks = r2.json()
for b in blocks:
    label = b.get('label', '?')
    value = b.get('value', '')
    print(f"  [{label}] ({len(value)} chars)")
    # Mostra solo le prime righe
    lines = value.split('\n')[:5]
    for line in lines:
        if line.strip():
            print(f"     {line.strip()[:120]}")
    print()
