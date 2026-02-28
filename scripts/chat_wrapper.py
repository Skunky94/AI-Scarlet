"""
Scarlet Chat Wrapper (Interceptor Pattern)
Dimostra l'integrazione del livello Subconscio:
1. Intercetta il messagio utente.
2. Calcola l'impatto emotivo veloce (Ollama).
3. Aggiorna il blocco Letta (SSOT) via PATCH.
4. Passa il messaggio all'Agente Letta (Scarlet) per la risposta.
"""

import os
import sys
import json
import time
import requests
from scarlet_pad.core import PADCore
from scarlet_pad.letta_sync import LettaPADSync
from scarlet_pad.subconscious import SubconsciousEvaluator

sys.stdout.reconfigure(encoding='utf-8')

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}

def send_letta_message(agent_id: str, message: str) -> str:
    """Invia un messaggio all'agente Letta e recupera la risposta dell'assistant."""
    url = f"{LETTA_URL}/v1/agents/{agent_id}/messages"
    payload = {
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ],
        "stream": False
    }
    
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code != 200:
        return f"[Errore Letta API: {resp.text}]"
        
    data = resp.json()
    # Letta response can be complex, looking for "assistant_message"
    messages = data.get("messages", [])
    reply = ""
    for msg in messages:
        if msg.get("message_type") == "assistant_message":
            # Letta messages content are either in 'message', 'text' or 'content' sometimes based on models
            reply += msg.get("message", "") + msg.get("content", "") + "\n"
    
    return reply.strip() if reply else "[Nessuna risposta 'assistant_message' visibile]"

def main():
    print("=" * 60)
    print("  SCARLET CONSOLE (con Subconscious Interceptor attivo)")
    print("=" * 60)
    print("[Inizializzazione moduli...]")
    
    sync = LettaPADSync(base_url=LETTA_URL)
    core = PADCore()
    # Fast model per il subconscio
    evaluator = SubconsciousEvaluator(ollama_url="http://127.0.0.1:11434", model="qwen2.5:0.5b")
    
    agent_id = sync.get_agent_id()
    if not agent_id:
        print("Operazione fallita: nessun .agent_id trovato.")
        return
        
    print(f"[Agent ID: {agent_id}]")
    print("Scrivi 'exit' o 'quit' per uscire.\n")
    
    while True:
        try:
            user_input = input("Tu: ").strip()
        except EOFError:
            break
            
        if user_input.lower() in ['exit', 'quit']:
            break
            
        if not user_input:
            continue
            
        # -- FASE 1: SUBCONSCIOSO (Fast Evaluation) --
        start_eval = time.time()
        dp, da, dd, reason = evaluator.evaluate_input(user_input)
        
        # -- FASE 2: AGGIORNAMENTO STATO (Memory SSOT) --
        state, block_id = sync.read_current_state(agent_id)
        
        # Decadimento prima dello stimolo
        state = core.apply_decay(state, decay_factor=0.05) 
        # Applicazione stimolo
        new_state = core.apply_stimulus(state, dp, da, dd)
        
        # Aggiorna Letta (SSOT)
        sync.update_state(agent_id, block_id, new_state, f"Input: '{user_input}'. Reason: {reason}")
        eval_time = time.time() - start_eval
        
        mood = core.get_mood_description(new_state)
        print(f"\n[Subconscio] -> L'umore è mutato in: {mood} (in {eval_time:.2f}s)")
        print(f"[Subconscio] -> P={new_state.p:+.2f}, A={new_state.a:+.2f}, D={new_state.d:+.2f} | Reason: {reason}\n")
        
        # -- FASE 3: COSCIENZA (Generazione Responso Scarlet) --
        print("Scarlet sta pensando...")
        reply = send_letta_message(agent_id, user_input)
        
        print("\nSCARLET:")
        print(reply)
        print("-" * 60)

if __name__ == "__main__":
    main()
