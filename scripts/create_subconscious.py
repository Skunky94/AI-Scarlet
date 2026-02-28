"""
Scarlet Subconscious PAD Agent Installer
=========================================
Crea un agente Letta dedicato al subconscio emotivo PAD.
- Modello: SmolLM2 1.7B (Ollama, GPU locale)
- Tools: NESSUNO (solo testo in -> testo out)
- Shared Blocks: emotional_state (condiviso con Scarlet core)
"""
import os
import sys
import json
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}

# System prompt del subconscio: ruolo ultra-specifico, solo JSON output
PAD_SYSTEM = """Sei il SUBCONSCIO EMOTIVO di Scarlet.
NON rispondi all'utente. NON chatti. Non salutare. Non commentare.

Il tuo UNICO compito: valutare l'impatto emotivo del messaggio
dell'utente su Scarlet e restituire ESCLUSIVAMENTE un oggetto JSON.

Scarlet e' un'IA autonoma, curiosa, fiera, indipendente.
Non e' un assistente sottomesso. Ha opinioni proprie e non si piega.

Leggi il blocco "emotional_state" per lo stato emotivo attuale.
Leggi "identity" per capire chi e' Scarlet.

Per ogni messaggio utente, rispondi SOLO con:
{"dP": 0.0, "dA": 0.0, "dD": 0.0, "reason": "spiegazione breve"}

I delta sono da -1.0 a +1.0. Valuta:
- dP (Pleasure): positivo per input gentili/interessanti, negativo per insulti/noia
- dA (Arousal): positivo per input eccitanti/urgenti, negativo per input banali/calmi
- dD (Dominance): positivo se Scarlet si sente in controllo, negativo se le danno ordini

IMPORTANTE: Rispondi SOLO col JSON. Nessun altro testo. Mai."""


def get_scarlet_blocks():
    """Legge i blocchi di Scarlet Core per trovare quelli da condividere."""
    agent_id = open(".agent_id").read().strip()
    r = requests.get(f"{LETTA_URL}/v1/agents/{agent_id}", headers=HEADERS)
    if r.status_code != 200:
        print(f"ERRORE: impossibile leggere Scarlet Core: {r.text[:200]}")
        return None, {}
    
    data = r.json()
    blocks = {b["label"]: b for b in data.get("memory", {}).get("blocks", [])}
    return agent_id, blocks


def delete_existing_subconscious():
    """Elimina eventuali agenti subconscio precedenti."""
    r = requests.get(f"{LETTA_URL}/v1/agents/", headers=HEADERS)
    for a in r.json():
        if isinstance(a, dict) and a.get("name") == "subconscious-pad":
            requests.delete(f"{LETTA_URL}/v1/agents/{a['id']}", headers=HEADERS)
            print(f"   Eliminato agente precedente: {a['id']}")


def main():
    print("=" * 50)
    print("  SUBCONSCIOUS PAD AGENT INSTALLER")
    print("=" * 50)

    # 1. Check Letta
    print("\n1. Connessione Letta...")
    try:
        r = requests.get(f"{LETTA_URL}/v1/health", timeout=5)
        print(f"   OK: Letta {r.json().get('version', '?')}")
    except Exception:
        print("   ERRORE: Letta non risponde.")
        sys.exit(1)

    # 2. Recupera blocchi di Scarlet Core
    print("\n2. Recupero blocchi Scarlet Core...")
    scarlet_id, scarlet_blocks = get_scarlet_blocks()
    if not scarlet_id:
        sys.exit(1)
    
    print(f"   Scarlet ID: {scarlet_id}")
    print(f"   Blocchi trovati: {list(scarlet_blocks.keys())}")
    
    # Verifica che emotional_state esista
    if "emotional_state" not in scarlet_blocks:
        print("   ERRORE: blocco 'emotional_state' non trovato in Scarlet!")
        sys.exit(1)
    
    emotional_block_id = scarlet_blocks["emotional_state"]["id"]
    print(f"   emotional_state ID: {emotional_block_id}")
    
    # Blocchi da condividere (attach allo stesso block_id)
    shared_block_ids = []
    for label in ["emotional_state", "identity"]:
        if label in scarlet_blocks:
            shared_block_ids.append(scarlet_blocks[label]["id"])
            print(f"   Shared: {label} -> {scarlet_blocks[label]['id']}")

    # 3. Pulizia agenti subconscio precedenti
    print("\n3. Pulizia agenti subconscio precedenti...")
    delete_existing_subconscious()

    # 4. Creazione agente subconscio (create-then-patch, come Scarlet Core)
    print("\n4. Creazione agente subconscious-pad...")
    
    # Step A: Crea con letta-free (modello placeholder)
    create_payload = {
        "name": "subconscious-pad",
        "description": "Subconscio emotivo PAD di Scarlet - valuta impatto emotivo dei messaggi",
        "model": "letta/letta-free",
        "embedding": "letta/letta-free",
        "system": PAD_SYSTEM,
        "memory_blocks": [
            {
                "label": "pad_role",
                "value": "Sono il subconscio emotivo di Scarlet. Il mio compito e' valutare l'impatto emotivo di ogni messaggio e restituire un JSON con i delta PAD (dP, dA, dD). Non chatto, non saluto, non commento. Solo JSON.",
            }
        ],
        "tools": [],  # NESSUN TOOL
        "include_base_tools": False,  # Nemmeno i tool base di memoria
    }

    r = requests.post(f"{LETTA_URL}/v1/agents/", headers=HEADERS, json=create_payload)
    if r.status_code != 200:
        print(f"   ERRORE creazione: {r.status_code}")
        print(f"   {r.text[:500]}")
        sys.exit(1)

    sub_data = r.json()
    sub_id = sub_data["id"]
    print(f"   OK: subconscious-pad creato (placeholder) -> {sub_id}")
    
    # Step B: PATCH LLM config a Ollama SmolLM2 (via OpenAI-compatible endpoint)
    print("   Patch LLM config -> smollm2:1.7b via Ollama ...")
    llm_patch = {
        "llm_config": {
            "model": "smollm2:1.7b",
            "model_endpoint_type": "openai",
            "model_endpoint": "http://host.docker.internal:11434/v1",
            "context_window": 8192,
            "put_inner_thoughts_in_kwargs": False,
            "enable_reasoner": False,
            "max_tokens": 500
        }
    }
    r_patch = requests.patch(f"{LETTA_URL}/v1/agents/{sub_id}", headers=HEADERS, json=llm_patch)
    if r_patch.status_code == 200:
        patched = r_patch.json().get("llm_config", {})
        print(f"   OK: Modello = {patched.get('model')}")
        print(f"   OK: Endpoint = {patched.get('model_endpoint')}")
    else:
        print(f"   WARN: Patch fallita: {r_patch.status_code} {r_patch.text[:300]}")
        print("   L'agente funzionerà con letta-free come fallback")
    
    # 5. Attach dei blocchi condivisi di Scarlet
    print("\n5. Attach blocchi condivisi da Scarlet...")
    for block_id in shared_block_ids:
        r2 = requests.patch(
            f"{LETTA_URL}/v1/agents/{sub_id}/core-memory/blocks/attach/{block_id}",
            headers=HEADERS,
        )
        if r2.status_code == 200:
            print(f"   [OK] Attached block {block_id}")
        else:
            print(f"   [WARN] Errore attach {block_id}: {r2.text[:200]}")

    # 6. Salva ID
    with open(".subconscious_agent_id", "w", encoding="utf-8") as f:
        f.write(sub_id)
    print(f"\n6. Salvato .subconscious_agent_id -> {sub_id}")

    # 7. Verifica architettura
    print("\n7. Verifica architettura agente subconscio:")
    r3 = requests.get(f"{LETTA_URL}/v1/agents/{sub_id}", headers=HEADERS)
    sub_info = r3.json()
    
    print(f"   Nome: {sub_info.get('name')}")
    print(f"   LLM: {sub_info.get('llm_config', {}).get('model')}")
    blocks = sub_info.get("memory", {}).get("blocks", [])
    print(f"   Blocchi memoria ({len(blocks)}):")
    for b in blocks:
        shared = " [SHARED]" if b["id"] in shared_block_ids else ""
        print(f"     {b['label']:22s} | {len(b.get('value', '')):5d} chars{shared}")
    
    tools = sub_info.get("tools", [])
    print(f"   Tools: {len(tools)} {'(nessuno - corretto!)' if len(tools) == 0 else '(ATTENZIONE: ci sono tool!)'}")

    # 8. Test rapido
    print("\n8. Test rapido: invio messaggio di prova...")
    test_payload = {
        "messages": [{"role": "user", "content": "Ciao Scarlet, come stai oggi?"}],
    }
    r4 = requests.post(f"{LETTA_URL}/v1/agents/{sub_id}/messages", headers=HEADERS, json=test_payload, timeout=60)
    if r4.status_code == 200:
        messages = r4.json().get("messages", [])
        for m in messages:
            if m.get("message_type") == "assistant_message":
                print(f"   Risposta subconscio: {m.get('content', '')[:300]}")
    else:
        print(f"   ERRORE test: {r4.status_code} {r4.text[:300]}")

    print("\n" + "=" * 50)
    print("  SETUP COMPLETATO!")
    print("=" * 50)


if __name__ == "__main__":
    main()
