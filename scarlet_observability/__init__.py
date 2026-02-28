"""
scarlet_observability — Sistema di osservabilita' centralizzato di Scarlet.

Uso:
    from scarlet_observability import get_logger

    log = get_logger("gateway.openai")
    log.debug("Step 1 PAD | dP=%+.3f elapsed_ms=%.1f", dp, elapsed)
    log.info("Turno completato | ms=%d", total_ms)
    log.warning("API timeout | url=%s", url)
    log.error("Errore critico | %s", str(e))

Configurazione: config/observability.json
Log files: logs/YYYY-MM-DD_HH-MM.log (rotazione ogni window_minutes)
"""

from scarlet_observability.logger import get_logger

__all__ = ["get_logger"]
