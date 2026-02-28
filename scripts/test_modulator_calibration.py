"""Test calibrazione PAD Modulator per MiniMax M2.5."""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from scarlet_pad.modulator import PADModulator
m = PADModulator()

scenarios = [
    ("Neutro (baseline)",           0.0,  0.0,  0.0),
    ("Felice + Eccitata",           0.7,  0.5,  0.3),
    ("Molto Felice + Calma",        0.9, -0.2,  0.5),
    ("Triste + Apatica",           -0.6, -0.4, -0.2),
    ("Furiosa + Agitata",          -0.8,  0.9, -0.5),
    ("Serena + Dominante",          0.5, -0.3,  0.7),
    ("Ansiosa + Sottomessa",       -0.3,  0.8, -0.8),
    ("Estasi (MAX Pleasure)",       1.0,  1.0,  1.0),
    ("Terrore (MIN tutto)",        -1.0,  1.0, -1.0),
    ("Apatica totale",             -1.0, -1.0, -1.0),
]

print(f"{'STATO':30s} | {'P':>5s} {'A':>5s} {'D':>5s} | {'TEMP':>5s} {'TOKENS':>6s} {'FP':>5s}")
print("-" * 75)

for name, p, a, d in scenarios:
    params = m.compute_params(p, a, d)
    print(f"{name:30s} | {p:+5.1f} {a:+5.1f} {d:+5.1f} | {params['temperature']:5.2f} {params['max_tokens']:6d} {params['frequency_penalty']:5.2f}")

print("-" * 75)
print("Range MiniMax M2.5: temp=(0.01, 1.0], max_tokens=[500, 16000], freq_pen=[0.0, 2.0]")
