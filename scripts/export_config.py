"""Esporta stato completo dell'agente Scarlet da Letta per preservazione."""
import sys, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import requests, json

h = {'Authorization': 'Bearer scarlet_dev', 'Content-Type': 'application/json'}
aid = open('.agent_id').read().strip()
LETTA = 'http://localhost:8283'
OUT = 'config'
os.makedirs(OUT, exist_ok=True)

# 1. Agent completo
print("1. Esportazione agent settings...")
r = requests.get(f'{LETTA}/v1/agents/{aid}', headers=h, timeout=10)
agent = r.json()

# Estrai solo le parti importanti
settings = {
    "agent_id": aid,
    "name": agent.get("name", ""),
    "agent_type": agent.get("agent_type", ""),
    "description": agent.get("description", ""),
    "llm_config": agent.get("llm_config", {}),
    "embedding_config": agent.get("embedding_config", {}),
    "tool_ids": agent.get("tool_ids", []),
    "tool_names": agent.get("tool_names", []),
    "tags": agent.get("tags", []),
    "metadata": agent.get("metadata", {}),
}
with open(f'{OUT}/agent_settings.json', 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
print(f"   Salvato: {OUT}/agent_settings.json")
print(f"   Nome: {settings['name']}")
print(f"   Modello: {settings['llm_config'].get('model', '?')}")

# 2. System Prompt
print("\n2. Esportazione system prompt...")
system_prompt = agent.get("system", "")
with open(f'{OUT}/system_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(system_prompt)
print(f"   Salvato: {OUT}/system_prompt.txt ({len(system_prompt)} chars)")

# 3. Memory Blocks
print("\n3. Esportazione memory blocks...")
blocks = agent.get("memory", {}).get("blocks", [])
blocks_export = []
for b in blocks:
    block_data = {
        "label": b.get("label", ""),
        "value": b.get("value", ""),
        "limit": b.get("limit", 5000),
        "description": b.get("description", ""),
    }
    blocks_export.append(block_data)
    print(f"   - {block_data['label']}: {len(block_data['value'])} chars")

with open(f'{OUT}/memory_blocks.json', 'w', encoding='utf-8') as f:
    json.dump(blocks_export, f, indent=2, ensure_ascii=False)
print(f"   Salvato: {OUT}/memory_blocks.json ({len(blocks_export)} blocks)")

# 4. Tools
print("\n4. Esportazione tools attaccati...")
tool_ids = agent.get("tool_ids", [])
tools_export = []
for tid in tool_ids:
    r_tool = requests.get(f'{LETTA}/v1/tools/{tid}', headers=h, timeout=5)
    if r_tool.status_code == 200:
        t = r_tool.json()
        tools_export.append({
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "id": tid,
        })
        print(f"   - {t.get('name', '?')}")

with open(f'{OUT}/tools.json', 'w', encoding='utf-8') as f:
    json.dump(tools_export, f, indent=2, ensure_ascii=False)
print(f"   Salvato: {OUT}/tools.json ({len(tools_export)} tools)")

# 5. Archival Memory (tutte le memorie)
print("\n5. Esportazione archival memory...")
r_arch = requests.get(f'{LETTA}/v1/agents/{aid}/archival-memory', headers=h, params={'limit': 200}, timeout=10)
arch_data = r_arch.json() if r_arch.status_code == 200 else []
with open(f'{OUT}/archival_memory.json', 'w', encoding='utf-8') as f:
    json.dump(arch_data, f, indent=2, ensure_ascii=False)
print(f"   Salvato: {OUT}/archival_memory.json ({len(arch_data)} memorie)")

print("\n=== EXPORT COMPLETATO ===")
print(f"File in {OUT}/:")
for fname in os.listdir(OUT):
    fpath = os.path.join(OUT, fname)
    size = os.path.getsize(fpath)
    print(f"  {fname}: {size:,} bytes")
