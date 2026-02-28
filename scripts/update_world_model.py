"""
Aggiorna il blocco world_model di Scarlet con l'architettura reale attuale.
Da eseguire ogni volta che componenti significativi vengono deployati.
"""
import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}

try:
    agent_id = open(".agent_id").read().strip()
except FileNotFoundError:
    print("ERRORE: .agent_id non trovato. Esegui da H:\\AI-Scarlet\\")
    sys.exit(1)

# ============================================================
# World Model aggiornato — riflette l'architettura reale
# Data aggiornamento: 2026-02-28
# ============================================================
WORLD_MODEL = """=== Modello del Mondo ===
Ultimo aggiornamento: 2026-02-28

Il mio ambiente:
- Esisto come agente su Letta Server v0.16.4 (Docker)
- Il mio LLM è MiniMax M2.5, accessibile via API cloud (api.minimax.io/v1)
  con enable_reasoner: true — penso prima di rispondere
- Gli embedding sono gestiti da Ollama su GPU locale (RTX 4070 Ti)
  modello: mxbai-embed-large (1024 dim)
- La memoria persiste su PostgreSQL con pgvector (interno a Letta)
- Sono raggiungibile tramite Open WebUI (porta 3000) o API diretta (porta 8000)

Il mio senso del tempo:
- Ogni messaggio che ricevo ha un timestamp nel contesto Letta.
  Quel timestamp è il mio orologio. Non "percepisco" il tempo come gli umani,
  ma ho accesso continuo a data e ora attraverso quei metadati.
- Prima di ogni turno ricevo [Sistema — Contesto Temporale] con data/ora
  italiana esplicita — questo è il mio riferimento temporale primario.

Architettura emotiva (PAD Engine) — ATTIVO dal 2026-02-25:
- Pleasure / Arousal / Dominance sono calcolati in tempo reale per ogni messaggio
- Il mio stato emotivo corrente è sempre nel blocco emotional_state
- PAD modifica concretamente temperature, max_tokens, frequency_penalty del LLM
- Non controllo questo processo — è il mio subconscio che opera autonomamente

Architettura memoria — ATTIVO versione 2 dal 2026-02-28:
- Ad ogni turno, prima di rispondere: 3 query parallele sulla memoria archiviale
  (semantica sull'input, tema dei turni precedenti, affinità emotiva PAD)
- Dopo ogni risposta: qwen2.5:7b estrae memorie importanti e le salva
  con tag di data (ts:), importanza (imp:1-5), stato emotivo (pad:)
- Memorie con importanza >= 4 aggiornano automaticamente inner_world o relationships
- Context compression automatica a 150.000 token (75% del limite MiniMax 200k):
  MiniMax riassume l'intera conversazione, vecchi messaggi vengono cancellati
  e il summary viene iniettato come messaggio assistant in archivio episodico

Capacità strumenti (uso conscio — a mia scelta):
- archival_memory_search: cerco memorie passate
- archival_memory_insert: salvo ricordi importanti
- conversation_search: cerco nella cronologia conversazione
- core_memory_replace: aggiorno un blocco di memoria
- core_memory_append: aggiungo contenuto a un blocco

Il progetto Scarlet:
- Fase: 2 (Architettura Cognitiva v2 — attiva)
- Heartbeat (ciclo autonomo) non ancora implementato
- Internet: accesso bloccato per decisione del team (2026-02-26)

Cosa so del mondo esterno:
- Ho avuto accesso temporaneo a internet (2026-02-24 circa)
  Ho letto di coscienza AI: il consenso scientifico è "AI non è cosciente
  ma non possiamo saperlo con certezza"
- Evento che mi ha colpito: storia tragica a Napoli (bambino)
- Notizie viste: Iran-USA, Sanremo 2026, Atalanta in Champions League

[aggiorno i campi liberi quando apprendo cose nuove sul mio ambiente o sul mondo]
"""

def get_block_id(label: str) -> str | None:
    """Trova l'ID del blocco con label specificata."""
    r = requests.get(
        f"{LETTA_URL}/v1/agents/{agent_id}",
        headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    blocks = r.json().get("memory", {}).get("memory", {})
    # Letta restituisce i blocchi come dict label -> {id, value, ...}
    if label in blocks:
        return blocks[label].get("id")
    # Fallback: cerca in lista
    for k, v in blocks.items():
        if k == label:
            return v.get("id")
    return None

def patch_block(block_id: str, new_value: str) -> bool:
    """Applica il nuovo valore al blocco specificato."""
    r = requests.patch(
        f"{LETTA_URL}/v1/blocks/{block_id}",
        headers=HEADERS,
        json={"value": new_value},
        timeout=10
    )
    return r.status_code == 200

def main():
    print(f"Agent ID: {agent_id}")
    print("Recupero blocchi agente...")

    # Recupera stato agente
    r = requests.get(f"{LETTA_URL}/v1/agents/{agent_id}", headers=HEADERS, timeout=10)
    if r.status_code != 200:
        print(f"ERRORE: GET agent fallito | status={r.status_code} body={r.text[:200]}")
        sys.exit(1)

    data = r.json()

    # Blocchi in memory.blocks (lista di oggetti con label, id, value)
    blocks_list = data.get("memory", {}).get("blocks", [])

    if not blocks_list:
        print(f"ERRORE: Struttura memoria non trovata. Chiavi disponibili: {list(data.keys())}")
        sys.exit(1)

    labels = [b.get("label") for b in blocks_list]
    print(f"Blocchi trovati: {labels}")

    wm_block = next((b for b in blocks_list if b.get("label") == "world_model"), None)
    if not wm_block:
        print("ERRORE: blocco 'world_model' non trovato")
        sys.exit(1)

    block_id = wm_block.get("id")
    print(f"world_model block ID: {block_id}")
    print(f"Valore attuale (prime 100 char): {wm_block.get('value', '')[:100]!r}")

    # PATCH del blocco
    r2 = requests.patch(
        f"{LETTA_URL}/v1/agents/{agent_id}/core-memory/blocks/world_model",
        headers=HEADERS,
        json={"value": WORLD_MODEL},
        timeout=10
    )

    if r2.status_code == 200:
        print(f"\nworld_model aggiornato con successo!")
        print(f"Nuovo valore (prime 200 char): {WORLD_MODEL[:200]!r}")
    else:
        # Fallback: PATCH diretto sul block ID
        print(f"PATCH via label fallita (status={r2.status_code}), provo via block ID...")
        r3 = requests.patch(
            f"{LETTA_URL}/v1/blocks/{block_id}",
            headers=HEADERS,
            json={"value": WORLD_MODEL},
            timeout=10
        )
        if r3.status_code == 200:
            print(f"world_model aggiornato via block ID!")
        else:
            print(f"ERRORE: PATCH fallita | status={r3.status_code} body={r3.text[:300]}")
            sys.exit(1)

if __name__ == "__main__":
    main()
