"""
Scarlet Observability — Logger centralizzato con rotazione a finestre temporali
===============================================================================
Architettura:
- ObsConfig: legge config/observability.json (debug, window_minutes, per-component)
- TimeWindowedFileHandler: scrive su file rotanti ogni N minuti
- ScarletFormatter: formato testo leggibile con timestamp, livello, componente
- ScarletObservability: singleton che configura tutta la gerarchia di logger

Naming convention logger:
  scarlet.gateway.main       routes/openai.py, main.py
  scarlet.gateway.openai     pipeline principale
  scarlet.gateway.letta      routes/letta.py
  scarlet.gateway.pad        routes/pad.py
  scarlet.pad.subconscious   PAD evaluator (transformer + intent)
  scarlet.pad.core           PAD matematica
  scarlet.pad.modulator      PAD -> LLM params
  scarlet.pad.sync           PAD <-> Letta sync
  scarlet.memory.agent       Memory extractor (Ollama)
  scarlet.memory.retriever   Memory retriever (Letta archival)
  scarlet.letta              Chiamate HTTP a Letta API
  scarlet.ollama             Chiamate HTTP a Ollama API

Il componente top-level (gateway, pad, memory, letta, ollama) determina
il livello di log tramite config.components.
"""

import os
import sys
import json
import logging
from datetime import datetime
from threading import Lock
from typing import Optional
from dataclasses import dataclass, field


# ============================================================
# 1. CONFIGURAZIONE
# ============================================================

@dataclass
class ObsConfig:
    """
    Configurazione del sistema di osservabilita'.
    Caricata da config/observability.json all'avvio.
    """
    debug: bool = True
    log_dir: str = "logs"
    window_minutes: int = 15
    stdout: bool = True
    components: dict = field(default_factory=lambda: {
        "gateway": True,
        "pad": True,
        "memory": True,
        "letta": True,
        "ollama": True,
    })

    @classmethod
    def load(cls) -> "ObsConfig":
        """
        Carica la configurazione dal file JSON.
        Cerca in ordine: env OBS_CONFIG -> config/observability.json
        -> /app/config/observability.json (Docker) -> default.
        """
        candidates = [
            os.environ.get("OBS_CONFIG", ""),
            "config/observability.json",
            "/app/config/observability.json",
        ]

        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Merge components con i default (evita KeyError su nuovi componenti)
                    default_comp = cls().components.copy()
                    default_comp.update(data.get("components", {}))

                    return cls(
                        debug=data.get("debug", True),
                        log_dir=data.get("log_dir", "logs"),
                        window_minutes=data.get("window_minutes", 15),
                        stdout=data.get("stdout", True),
                        components=default_comp,
                    )
                except Exception as e:
                    print(f"[ObsConfig] Errore lettura {path}: {e} — uso default", file=sys.stderr)

        return cls()  # Default


# ============================================================
# 2. TIME-WINDOWED FILE HANDLER
# ============================================================

class TimeWindowedFileHandler(logging.Handler):
    """
    Handler che scrive su file .log rotanti a finestre temporali fisse.

    Con window_minutes=15:
      logs/2026-02-28_13-00.log  →  eventi 13:00:00 - 13:14:59.999
      logs/2026-02-28_13-15.log  →  eventi 13:15:00 - 13:29:59.999
      ...

    Il file viene creato alla prima scrittura nella finestra, non all'avvio.
    Thread-safe tramite Lock interno.
    """

    def __init__(self, log_dir: str, window_minutes: int):
        super().__init__()
        self.log_dir = log_dir
        self.window_minutes = window_minutes
        self._lock = Lock()
        self._current_window: Optional[datetime] = None
        self._stream = None
        os.makedirs(log_dir, exist_ok=True)

    def _get_window_start(self) -> datetime:
        """Restituisce l'inizio della finestra temporale corrente (floor)."""
        now = datetime.now()
        floored = (now.minute // self.window_minutes) * self.window_minutes
        return now.replace(minute=floored, second=0, microsecond=0)

    def _get_filepath(self, window: datetime) -> str:
        """Percorso del file per questa finestra: logs/YYYY-MM-DD_HH-MM.log"""
        return os.path.join(self.log_dir, window.strftime("%Y-%m-%d_%H-%M") + ".log")

    def _rotate_if_needed(self):
        """
        Controlla se siamo in una nuova finestra temporale.
        Se si', chiude il file corrente e apre il nuovo.
        Chiamato sotto _lock.
        """
        window = self._get_window_start()
        if window != self._current_window:
            if self._stream:
                try:
                    self._stream.flush()
                    self._stream.close()
                except Exception:
                    pass
            filepath = self._get_filepath(window)
            # buffering=1 = line-buffered: ogni riga viene scritta subito
            self._stream = open(filepath, "a", encoding="utf-8", buffering=1)
            self._current_window = window

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            with self._lock:
                self._rotate_if_needed()
                self._stream.write(msg + "\n")
        except Exception:
            self.handleError(record)

    def close(self):
        with self._lock:
            if self._stream:
                try:
                    self._stream.flush()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
        super().close()


# ============================================================
# 3. FORMATTER
# ============================================================

class ScarletFormatter(logging.Formatter):
    """
    Formato leggibile: [YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [component.name    ] message

    Esempi:
      [2026-02-28 13:05:32.451] [INFO ] [gateway.openai      ] Step 1 PAD | dP=+0.150 elapsed_ms=4.8
      [2026-02-28 13:05:32.455] [DEBUG] [pad.subconscious     ] Transformer | label=Neutral confidence=0.48
      [2026-02-28 13:05:32.501] [WARN ] [memory.agent         ] JSON parse error | raw='{...}'
      [2026-02-28 13:05:32.510] [ERROR] [letta                ] API error | status=500 body='...'
    """

    _LEVEL_LABELS = {
        "DEBUG":    "DEBUG",
        "INFO":     "INFO ",
        "WARNING":  "WARN ",
        "ERROR":    "ERROR",
        "CRITICAL": "CRIT ",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = self._LEVEL_LABELS.get(record.levelname, record.levelname[:5])

        # Rimuove il prefisso "scarlet." per brevita' nel log
        name = record.name
        if name.startswith("scarlet."):
            name = name[len("scarlet."):]

        # Pad a 20 caratteri per allineamento colonne
        name_padded = name[:20].ljust(20)

        return f"[{ts}] [{level}] [{name_padded}] {record.getMessage()}"


# ============================================================
# 4. SCARLET OBSERVABILITY SINGLETON
# ============================================================

class ScarletObservability:
    """
    Singleton che configura e gestisce l'intero sistema di logging di Scarlet.

    Gerarchia logger Python:
      scarlet                  ← root osservabilita' (ha i 2 handler: file + stdout)
        scarlet.gateway        ← livello: DEBUG/INFO/CRITICAL da config
          scarlet.gateway.openai
          scarlet.gateway.letta
          ...
        scarlet.pad            ← livello: DEBUG/INFO/CRITICAL da config
          scarlet.pad.subconscious
          ...
        scarlet.memory         ← livello: DEBUG/INFO/CRITICAL da config
          ...
        scarlet.letta          ← livello per chiamate HTTP a Letta
        scarlet.ollama         ← livello per chiamate HTTP a Ollama

    I logger figli propagano a scarlet (propagate=True default).
    scarlet.propagate=False: nessun output al root Python logger.
    """

    # Mappa: prefisso logger → chiave in config.components
    _COMPONENT_MAP = {
        "gateway": "gateway",
        "pad":     "pad",
        "memory":  "memory",
        "letta":   "letta",
        "ollama":  "ollama",
    }

    def __init__(self, config: ObsConfig):
        self.config = config
        self._setup_root_logger()
        self._configure_component_levels()

    def _setup_root_logger(self):
        """Configura il logger radice 'scarlet' con handler file e stdout."""
        root = logging.getLogger("scarlet")
        root.setLevel(logging.DEBUG)   # Filtraggio a livello dei sub-logger
        root.propagate = False         # Non passa al root Python logger
        root.handlers.clear()          # Reset (utile in caso di reinizializzazione)

        formatter = ScarletFormatter()

        # Handler 1: File a finestre temporali
        file_h = TimeWindowedFileHandler(self.config.log_dir, self.config.window_minutes)
        file_h.setFormatter(formatter)
        file_h.setLevel(logging.DEBUG)
        root.addHandler(file_h)

        # Handler 2: stdout (opzionale)
        if self.config.stdout:
            stdout_h = logging.StreamHandler(sys.stdout)
            stdout_h.setFormatter(formatter)
            stdout_h.setLevel(logging.DEBUG)
            root.addHandler(stdout_h)

    def _get_component_level(self, component_key: str) -> int:
        """
        Determina il livello minimo di log per un componente.

        Logica:
          - Se il componente non e' nel config o e' False → CRITICAL (silenzioso)
          - Se debug=True globale E componente abilitato → DEBUG
          - Se debug=False globale E componente abilitato → INFO
          - Se il componente ha override {"debug": true} → DEBUG indipendentemente dal globale
        """
        comp_val = self.config.components.get(component_key, True)

        # Componente esplicitamente disabilitato
        if comp_val is False:
            return logging.CRITICAL

        # Override per-componente {"debug": true} ignora il flag globale
        per_component_debug = (
            isinstance(comp_val, dict) and comp_val.get("debug", False)
        )

        if self.config.debug or per_component_debug:
            return logging.DEBUG
        return logging.INFO

    def _configure_component_levels(self):
        """Imposta il livello su tutti i logger di componente top-level."""
        for prefix, key in self._COMPONENT_MAP.items():
            lg = logging.getLogger(f"scarlet.{prefix}")
            lg.setLevel(self._get_component_level(key))

    def get_logger(self, component_path: str) -> logging.Logger:
        """
        Restituisce un logger per il percorso di componente specificato.

        Args:
            component_path: es "gateway.openai", "pad.subconscious", "memory.agent"

        Il logger e' automaticamente configurato con il livello del suo antenato
        di componente (scarlet.gateway, scarlet.pad, ecc.).
        """
        return logging.getLogger(f"scarlet.{component_path}")

    def reload_config(self):
        """Ricarica la configurazione dal file e riconfigura i livelli."""
        self.config = ObsConfig.load()
        self._configure_component_levels()


# ============================================================
# 5. API PUBBLICA (SINGLETON THREAD-SAFE)
# ============================================================

_instance: Optional[ScarletObservability] = None
_init_lock = Lock()


def _get_instance() -> ScarletObservability:
    """Inizializza il singleton al primo accesso (lazy, thread-safe)."""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                config = ObsConfig.load()
                _instance = ScarletObservability(config)
    return _instance


def get_logger(component_path: str) -> logging.Logger:
    """
    Punto di accesso globale al sistema di logging di Scarlet.

    Ogni modulo chiama questa funzione UNA VOLTA a livello di modulo:
        log = get_logger("gateway.openai")

    Poi usa il logger standard Python:
        log.debug(f"Step 1 PAD | dP={dp:+.3f} dA={da:+.3f} elapsed_ms={t:.1f}")
        log.info(f"Turno completato | total_ms={elapsed:.0f}")
        log.warning(f"API Letta irraggiungibile | url={url} error={e}")
        log.error(f"Errore critico | traceback={tb}")

    Args:
        component_path: Percorso del componente, es:
            "gateway.main", "gateway.openai", "gateway.letta", "gateway.pad"
            "pad.subconscious", "pad.core", "pad.modulator", "pad.sync"
            "memory.agent", "memory.retriever"
            "letta"     ← per chiamate HTTP dirette a Letta API
            "ollama"    ← per chiamate HTTP dirette a Ollama API

    Returns:
        logging.Logger configurato e collegato al sistema Scarlet.
    """
    return _get_instance().get_logger(component_path)
