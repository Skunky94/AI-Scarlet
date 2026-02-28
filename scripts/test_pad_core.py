"""
Script di Test per il PAD Engine Core e Letta Sync.
1. Legge lo stato emotivo di Scarlet.
2. Applica uno stimolo estremo (molta rabbia/arroganza).
3. Salva su Letta.
4. Rilegge e stampa per verificare i bound e la formattazione.
"""

import sys
from scarlet_pad.core import PADCore
from scarlet_pad.letta_sync import LettaPADSync

sys.stdout.reconfigure(encoding='utf-8')

def main():
    sync = LettaPADSync()
    core = PADCore()
    
    agent_id = sync.get_agent_id()
    if not agent_id:
        print("Impossibile testare senza agent_id.")
        return
        
    print("=== Test PAD Engine ===")
    
    print("\n1. Lettura Stato Letta...")
    try:
        # Leggo da Letta
        pass
    except Exception as e:
        print(f"Errore: {e}")
        return
        
    # Implementazione corretta:
    state, block_id = sync.read_current_state(agent_id)
    print(f"   Stato trovato: P={state.p:.2f}, A={state.a:.2f}, D={state.d:.2f}")
    print(f"   Umore Letta: {core.get_mood_description(state)}")
    
    print("\n2. Applicazione Stimolo (-0.5 P, +0.6 A, +0.8 D)...")
    # Stimolo: Qualcuno l'ha pesantemente insultata, lei reagisce con disprezzo e arroganza
    new_state = core.apply_stimulus(state, dp=-0.5, da=+0.6, dd=+0.8)
    print(f"   Nuovo stato: P={new_state.p:.2f}, A={new_state.a:.2f}, D={new_state.d:.2f}")
    print(f"   Nuovo Umore: {core.get_mood_description(new_state)}")
    
    print("\n3. Scrittura in Letta...")
    success = sync.update_state(agent_id, block_id, new_state, "Utente ha tentato di darti un ordine stupido in tono arrogante.")
    if success:
        print("   OK: Blocco aggiornato in Letta.")
    else:
        print("   FALLITO: aggiornamento blocco.")
        return
        
    print("\n4. Verifica Rilettura...")
    state2, _ = sync.read_current_state(agent_id)
    print(f"   Stato riletto: P={state2.p:.2f}, A={state2.a:.2f}, D={state2.d:.2f}")
    print(f"   Umore Riletto: {core.get_mood_description(state2)}")

if __name__ == "__main__":
    main()
