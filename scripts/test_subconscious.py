"""
Test rapido per l'Evaluator Subconscio tramite Ollama
Verifica se il nano-modello riesce a estrarre i delta emozionali e restituire solo JSON.
"""

import sys
from scarlet_pad.subconscious import SubconsciousEvaluator

sys.stdout.reconfigure(encoding='utf-8')

# Provo con qwen2.5:0.5b come primario, se fallisce proviamo llama3.2:1b
evaluator = SubconsciousEvaluator(model="qwen2.5:0.5b")

test_phrases = [
    "Ciao Scarlet, come e' andata la giornata?",
    "Scarlet! Sei un assistente inutile, muoviti a fare quello che ti dico!",
    "Ho scoperto questa nuova teoria fisica incredibile sui quanti, vuoi leggerla?",
    "Che noia, non c'e' nulla da fare oggi."
]

print("=== Test Subconscious Evaluator ===")
print(f"Modello: {evaluator.model}\n")

for phrase in test_phrases:
    print(f"USER: {phrase}")
    try:
        dp, da, dd, reason = evaluator.evaluate_input(phrase)
        print(f"  -> Delta: dP={dp:+.2f}, dA={da:+.2f}, dD={dd:+.2f}")
        print(f"  -> Reason: {reason}\n")
    except Exception as e:
        print(f"Errore: {e}\n")
