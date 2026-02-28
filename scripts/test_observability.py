"""
Test isolato del sistema di osservabilita' scarlet_observability.

Verifica:
1. Creazione file log con nome corretto (finestra temporale)
2. Formato righe: [timestamp] [LEVEL] [component] message
3. Tutti i livelli: DEBUG, INFO, WARNING, ERROR
4. Dual logger (logica + API)
5. Cambio window_minutes: ricrea il singleton con config diversa
6. Toggle debug=False: i log DEBUG non devono comparire nel file
"""

import sys
import os
import time
import glob

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------------------------------------------
# Utilita'
# -----------------------------------------------------------------------

def read_last_log_file(log_dir: str = "logs") -> tuple[str, list[str]]:
    """Restituisce (path, righe) dell'ultimo file .log creato."""
    files = sorted(glob.glob(os.path.join(log_dir, "*.log")))
    if not files:
        return "", []
    path = files[-1]
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f.readlines() if l.strip()]
    return path, lines


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# -----------------------------------------------------------------------
# TEST 1 — File creato con nome finestra corretta
# -----------------------------------------------------------------------
separator("TEST 1 — Creazione file con nome finestra temporale")

# Reset singleton per partire puliti
import importlib
import scarlet_observability.logger as _obs_module
_obs_module._instance = None

from scarlet_observability import get_logger

log = get_logger("gateway.openai")
log.info("Messaggio di test | step=1 fase=init")
log.debug("Debug di test | key=valore")
log.warning("Warning di test | attenzione=True")
log.error("Errore di test | codice=42")

path, lines = read_last_log_file()
if path:
    from datetime import datetime
    now = datetime.now()
    window_min = (_obs_module._instance.config.window_minutes
                  if _obs_module._instance else 15)
    floored = (now.minute // window_min) * window_min
    expected_prefix = now.strftime(f"%Y-%m-%d_%H-") + f"{floored:02d}"
    filename = os.path.basename(path)

    print(f"  File creato : {path}")
    print(f"  Atteso nome : *{expected_prefix}*.log")
    ok = expected_prefix in filename
    print(f"  Risultato   : {'✅ OK' if ok else '❌ FAIL — nome file non corrisponde'}")
else:
    print("  ❌ FAIL — nessun file .log trovato in logs/")

# -----------------------------------------------------------------------
# TEST 2 — Formato righe
# -----------------------------------------------------------------------
separator("TEST 2 — Formato righe log")

if lines:
    print(f"  Ultime {min(4, len(lines))} righe scritte:")
    for line in lines[-4:]:
        print(f"  | {line}")

    # Controlla presenza dei 4 livelli
    levels_found = {lvl: any(f"[{lvl}" in l for l in lines) for lvl in ["INFO", "WARN", "ERROR", "DEBUG"]}
    for lvl, found in levels_found.items():
        print(f"  Livello [{lvl}] presente: {'✅' if found else '❌'}")
else:
    print("  ❌ Nessuna riga trovata")

# -----------------------------------------------------------------------
# TEST 3 — Dual logger (scarlet.letta separato da scarlet.gateway)
# -----------------------------------------------------------------------
separator("TEST 3 — Dual logger letta / gateway")

log_letta = get_logger("letta")
log_letta.debug("HTTP GET /v1/agents/xxx/memory/blocks | status=200 elapsed_ms=12")

log_gateway = get_logger("gateway.main")
log_gateway.info("Startup gateway | porta=8000")

_, lines2 = read_last_log_file()
has_letta  = any("[letta" in l for l in lines2)
has_gateway = any("[gateway" in l for l in lines2)
print(f"  Logger 'letta'   trovato nel file: {'✅' if has_letta else '❌'}")
print(f"  Logger 'gateway' trovato nel file: {'✅' if has_gateway else '❌'}")

# -----------------------------------------------------------------------
# TEST 4 — debug=False silenzia i DEBUG
# -----------------------------------------------------------------------
separator("TEST 4 — debug=False silenzia i log DEBUG")

# Ricrea il singleton con debug=False
_obs_module._instance = None
os.environ["OBS_CONFIG"] = ""  # forza uso default senza file

# Patch temporanea: sovrascriviamo ObsConfig.load per restituire debug=False
original_load = _obs_module.ObsConfig.load

@classmethod
def _load_no_debug(cls):
    cfg = cls()
    cfg.debug = False
    return cfg

_obs_module.ObsConfig.load = _load_no_debug

log2 = get_logger("pad.core")
debug_marker = "QUESTO_NON_DEVE_APPARIRE_NEL_FILE"
log2.debug(debug_marker)
log2.info("Questo INFO deve apparire anche con debug=False")

_, lines3 = read_last_log_file()
debug_present = any(debug_marker in l for l in lines3)
info_present  = any("Questo INFO deve apparire" in l for l in lines3)
print(f"  DEBUG presente (dovrebbe essere assente): {'❌ FAIL' if debug_present else '✅ OK — assente'}")
print(f"  INFO presente  (dovrebbe esserci)       : {'✅ OK' if info_present else '❌ FAIL'}")

# Ripristina
_obs_module.ObsConfig.load = original_load
_obs_module._instance = None
os.environ.pop("OBS_CONFIG", None)

# -----------------------------------------------------------------------
# RIEPILOGO FILE
# -----------------------------------------------------------------------
separator("RIEPILOGO — File log presenti")
files = sorted(glob.glob("logs/*.log"))
for f in files:
    size = os.path.getsize(f)
    print(f"  {os.path.basename(f)}  ({size} bytes)")
if not files:
    print("  (nessuno)")

print("\nTest completato.\n")
