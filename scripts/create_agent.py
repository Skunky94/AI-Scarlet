"""
Scarlet Cognitive Architecture Installer
========================================
Legge la configurazione da .agents/config/cognitive_v2.yaml
ed esegue la ricreazione dell'agente su Letta, applicando
le patch LLM specificate.
"""
import os
import sys
import json
import time
import subprocess

try:
    import requests
except ImportError:
    print("Manca 'requests'. Installazione in corso...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    import yaml
except ImportError:
    print("Manca 'pyyaml'. Installazione in corso...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

sys.stdout.reconfigure(encoding='utf-8')

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}
CONFIG_PATH = os.path.join(".agents", "config", "cognitive_v2.yaml")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERRORE: File di configurazione '{CONFIG_PATH}' non trovato.")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    print("=" * 50)
    print("  SCARLET AGENT INSTALLER (Config-Based)")
    print("=" * 50)

    # 1. Caricamento config
    print("\n1. Caricamento configurazione cognitiva...")
    config = load_config()
    agent_cfg = config.get("agent", {})
    llm_cfg = config.get("llm_config", {})
    system_prompt = config.get("system_prompt", "")
    memory_blocks = config.get("memory_blocks", [])

    print(f"   Nome Agente : {agent_cfg.get('name')}")
    print(f"   Modello Base: {agent_cfg.get('base_model')}")
    print(f"   Blocchi Mem : {len(memory_blocks)}")

    # 2. Check Letta
    print("\n2. Connessione Letta...")
    for i in range(10):
        try:
            r = requests.get(f"{LETTA_URL}/v1/health", timeout=5)
            if r.status_code == 200:
                print(f"   OK: Letta {r.json().get('version', 'Sconosciuta')}")
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        print("   ERRORE: Letta non risponde.")
        sys.exit(1)

    # 3. Pulizia agenti
    print("\n3. Pulizia agenti esistenti...")
    r = requests.get(f"{LETTA_URL}/v1/agents/", headers=HEADERS)
    for a in r.json():
        if isinstance(a, dict) and "id" in a:
            requests.delete(f"{LETTA_URL}/v1/agents/{a['id']}", headers=HEADERS)
            print(f"   Eliminato: {a['name']}")

    # 4. Creazione Agente
    print(f"\n4. Creazione agente '{agent_cfg.get('name')}'...")
    payload = {
        "name": agent_cfg.get("name", "scarlet-core"),
        "description": agent_cfg.get("description", "Scarlet - Individuo Digitale Autonomo"),
        "model": agent_cfg.get("base_model", "letta/letta-free"),
        "embedding": agent_cfg.get("base_embedding", "letta/letta-free"),
        "system": system_prompt,
        "memory_blocks": memory_blocks,
    }

    r = requests.post(f"{LETTA_URL}/v1/agents/", headers=HEADERS, json=payload)
    if r.status_code != 200:
        print(f"   ERRORE API: {r.text[:500]}")
        sys.exit(1)

    data = r.json()
    agent_id = data["id"]
    print(f"   OK: {data.get('name')} creato col l'ID ({agent_id})")

    # 5. Patch LLM
    if llm_cfg:
        print("\n5. Patch configurazione LLM...")
        patch_payload = {
            "llm_config": llm_cfg
        }
        r2 = requests.patch(f"{LETTA_URL}/v1/agents/{agent_id}", headers=HEADERS, json=patch_payload)
        patch_data = r2.json().get("llm_config", {})
        print(f"   Modello  : {patch_data.get('model')}")
        print(f"   Endpoint : {patch_data.get('model_endpoint')}")

    # 6. Salva .agent_id
    with open(".agent_id", "w", encoding="utf-8") as f:
        f.write(agent_id)

    # 7. Verifica Finale
    print("\n6. Verifica architettura memoria caricata:")
    r3 = requests.get(f"{LETTA_URL}/v1/agents/{agent_id}", headers=HEADERS)
    blocks = r3.json().get("memory", {}).get("blocks", [])
    total_chars = 0
    for b in blocks:
        chars = len(b.get("value", ""))
        total_chars += chars
        print(f"   {b['label']:22s} | {chars:5d} chars")
    print(f"   {'TOTALE':22s} | {total_chars:5d} chars")

    print("\nSetup completato con successo partendo dai file di configurazione!")

if __name__ == "__main__":
    main()
