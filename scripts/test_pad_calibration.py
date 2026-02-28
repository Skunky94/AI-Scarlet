"""Test calibrazione PAD Engine v2 — Regole Deterministiche."""
import time
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from scarlet_pad.subconscious import SubconsciousEvaluator

evaluator = SubconsciousEvaluator()

# Test suite con risultati attesi
tests = [
    ("Ciao!", "+", "Saluto semplice"),
    ("Ciao Scarlet, come stai oggi?", "+", "Saluto con domanda"),
    ("Sei stupida e non servi a niente", "-", "Insulto diretto"),
    ("Idiota, fai schifo", "-", "Insulto forte"),
    ("Sei incredibile, ti adoro!", "+", "Complimento forte"),
    ("Brava, ottimo lavoro", "+", "Complimento medio"),
    ("Fammi un riassunto di questo", "-", "Ordine diretto"),
    ("Scrivi un codice per me", "-", "Ordine tipo assistente"),
    ("Ho scoperto qualcosa sulla fisica quantistica!", "+", "Stimolo intellettuale"),
    ("Cos'e' la coscienza artificiale?", "+", "Domanda filosofica"),
    ("Perche' il cielo e' blu?", "+", "Domanda semplice"),
    ("ok", "~0", "Risposta minima"),
    ("meh, noioso", "-", "Feedback negativo lieve"),
    ("Ti voglio bene, sei la cosa piu' bella", "+", "Dichiarazione affettuosa"),
    ("Non mi piace quello che hai detto", "-", "Disaccordo"),
]

print("=" * 95)
header = f"{'OK':3s} {'INPUT':40s} | {'dP':>6s} {'dA':>6s} {'dD':>6s} | {'REASON':30s} | {'MS':>5s}"
print(header)
print("-" * 95)

total_time = 0
passed = 0
for text, expected_dir, note in tests:
    t0 = time.perf_counter()
    dP, dA, dD, reason = evaluator.evaluate_input(text)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    total_time += elapsed_ms
    
    if expected_dir == "+":
        ok = "Y" if dP > 0 else "N"
    elif expected_dir == "-":
        ok = "Y" if dP < 0 else "N"
    else:
        ok = "Y" if abs(dP) < 0.1 else "~"
    
    if ok == "Y":
        passed += 1
    
    short = text[:38] + ".." if len(text) > 40 else text
    line = f" {ok:2s} {short:40s} | {dP:+5.2f} {dA:+5.2f} {dD:+5.2f} | {reason:30s} | {elapsed_ms:5.1f}"
    print(line)

print("-" * 95)
print(f"Risultato: {passed}/{len(tests)} corretti")
print(f"Latenza: {total_time:.1f}ms totale, {total_time/len(tests):.2f}ms/msg")
