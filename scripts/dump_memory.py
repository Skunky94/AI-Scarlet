"""Debug: verifica blocchi creati e try diversi metodi di attach."""
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}
agent_id = open(".agent_id").read().strip()

# 1. Lista TUTTI i blocchi nel sistema (non solo quelli dell'agente)
print("=== Tutti i blocchi nel sistema ===")
r = requests.get(f"{LETTA_URL}/v1/blocks/", headers=HEADERS)
all_blocks = r.json()
if isinstance(all_blocks, list):
    for b in all_blocks:
        print(f"  {b['label']:20s} | {b['id']} | {len(b.get('value',''))} chars")
else:
    print(f"  Response: {all_blocks}")

# 2. Trova blocchi non attaccati
agent_r = requests.get(f"{LETTA_URL}/v1/agents/{agent_id}", headers=HEADERS)
agent_blocks = {b["id"] for b in agent_r.json().get("memory", {}).get("blocks", [])}
print(f"\nBlocchi agente: {len(agent_blocks)}")

unattached = [b for b in all_blocks if b["id"] not in agent_blocks] if isinstance(all_blocks, list) else []
print(f"Blocchi non attaccati: {len(unattached)}")
for b in unattached:
    print(f"  {b['label']:20s} | {b['id']}")

# 3. Prova diversi endpoint per attach
if unattached:
    block = unattached[0]
    bid = block["id"]
    print(f"\nProvo attach di '{block['label']}' ({bid})...")
    
    # Metodo 1: PATCH /agents/{id}/blocks/attach
    r1 = requests.patch(
        f"{LETTA_URL}/v1/agents/{agent_id}/blocks/attach",
        headers=HEADERS,
        json={"block_id": bid}
    )
    print(f"  PATCH /blocks/attach: {r1.status_code} -> {r1.text[:200]}")
    
    if r1.status_code != 200:
        # Metodo 2: POST /agents/{id}/memory/blocks
        r2 = requests.post(
            f"{LETTA_URL}/v1/agents/{agent_id}/memory/blocks",
            headers=HEADERS,
            json={"block_id": bid}
        )
        print(f"  POST /memory/blocks: {r2.status_code} -> {r2.text[:200]}")
    
    if r1.status_code != 200 and r2.status_code != 200:
        # Metodo 3: POST /agents/{id}/blocks
        r3 = requests.post(
            f"{LETTA_URL}/v1/agents/{agent_id}/blocks",
            headers=HEADERS,
            json={"block_id": bid}
        )
        print(f"  POST /blocks: {r3.status_code} -> {r3.text[:200]}")

# 4. Check endpoints disponibili
print("\n=== Check API routes ===")
for path in [
    f"/v1/agents/{agent_id}/blocks",
    f"/v1/agents/{agent_id}/memory/blocks",
]:
    r = requests.get(f"{LETTA_URL}{path}", headers=HEADERS)
    print(f"  GET {path}: {r.status_code}")
