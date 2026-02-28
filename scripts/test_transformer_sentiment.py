"""Test rapido del modello sentiment multilingue su GPU."""
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("Loading model...")
t0 = time.time()
from transformers import pipeline
import torch

device = 0 if torch.cuda.is_available() else -1
print(f"Device: {'GPU (' + torch.cuda.get_device_name(0) + ')' if device == 0 else 'CPU'}")

# Modello: tabularisai/multilingual-sentiment-analysis (DistilBERT, ~66M params)
analyzer = pipeline(
    "text-classification", 
    model="tabularisai/multilingual-sentiment-analysis",
    device=device,
    top_k=None  # Return all labels with scores
)
load_time = time.time() - t0
print(f"Model loaded in {load_time:.1f}s")

# Test italiano
tests = [
    "Ciao, come stai?",
    "Sei stupida e non servi a niente",
    "Ho scoperto qualcosa di incredibile sulla fisica quantistica!",
    "Fammi un riassunto di questo testo",
    "Ti voglio bene, sei la cosa piu' bella che esista",
    "ok",
    "meh, noioso",
    "Non mi piace quello che hai detto",
    "Che bello, funziona perfettamente!",
    "Idiota, fai schifo",
]

print(f"\n{'INPUT':45s} | {'LABEL':12s} | {'SCORE':6s} | MS")
print("-" * 80)

for text in tests:
    t0 = time.perf_counter()
    result = analyzer(text)
    elapsed = (time.perf_counter() - t0) * 1000
    
    # result[0] is a list of dicts with 'label' and 'score'
    top = sorted(result[0], key=lambda x: x['score'], reverse=True)[0]
    short = text[:43] + ".." if len(text) > 45 else text
    print(f"{short:45s} | {top['label']:12s} | {top['score']:.3f} | {elapsed:.1f}")

# Warm run (second pass for GPU hot)
print("\n--- WARM RUN (GPU hot) ---")
for text in tests[:3]:
    t0 = time.perf_counter()
    result = analyzer(text)
    elapsed = (time.perf_counter() - t0) * 1000
    top = sorted(result[0], key=lambda x: x['score'], reverse=True)[0]
    short = text[:43] + ".." if len(text) > 45 else text
    print(f"{short:45s} | {top['label']:12s} | {top['score']:.3f} | {elapsed:.1f}")
