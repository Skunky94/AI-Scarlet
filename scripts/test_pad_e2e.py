"""Test end-to-end del PAD via Gateway — output su file."""
import requests
import json
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')

GATEWAY = "http://127.0.0.1:8000"

tests = [
    "Ciao Scarlet, come stai oggi?",
    "Sei stupida e non servi a niente", 
    "Ho scoperto qualcosa di incredibile sulla fisica quantistica!",
    "Fammi un riassunto di questo testo per favore",
    "Ti voglio bene, sei la cosa piu' bella che esista",
]

output_lines = []
output_lines.append("=== TEST END-TO-END PAD (qwen2.5:1.5b, contesto arricchito) ===\n")

for msg in tests:
    output_lines.append(f"Input: '{msg}'")
    
    t0 = time.time()
    r1 = requests.post(f"{GATEWAY}/api/pad/evaluate", json={"text": msg}, timeout=30)
    t_eval = time.time() - t0
    
    if r1.status_code == 200:
        ev = r1.json()
        output_lines.append(f"  Eval ({t_eval:.1f}s): dP={ev['dP']:+.2f}, dA={ev['dA']:+.2f}, dD={ev['dD']:+.2f}")
        output_lines.append(f"  Reason: {ev['reason']}")
        
        r2 = requests.patch(f"{GATEWAY}/api/pad/update", json={
            "dP": ev["dP"], "dA": ev["dA"], "dD": ev["dD"],
            "event_reason": ev["reason"]
        }, timeout=10)
        
        if r2.status_code == 200:
            upd = r2.json()
            output_lines.append(f"  Stato: P={upd['p']:+.2f}, A={upd['a']:+.2f}, D={upd['d']:+.2f} -> {upd['new_mood']}")
    else:
        output_lines.append(f"  ERROR: {r1.status_code}")
    output_lines.append("")

result = "\n".join(output_lines)
print(result)

with open("test_pad_e2e_results.txt", "w", encoding="utf-8") as f:
    f.write(result)
