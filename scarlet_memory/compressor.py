"""
Context Compressor — Compressione cognitiva del context Letta
==============================================================
Si attiva quando il context di Letta si avvicina al limite di token del modello.

Logica:
  - Ogni turno, il gateway aggiorna il contatore di prompt_tokens (via usage_statistics SSE)
  - Quando prompt_tokens > COMPRESSION_THRESHOLD (75% del context window), la compressione parte
  - MiniMax M2.5 (chiamata diretta) produce un archivio cognitivo narrativo
  - Il summary viene iniettato come messaggio assistant in Letta + salvato in archival
  - I messaggi precedenti vengono eliminati (se Letta li espone via DELETE)
  - Scarlet "ricomincia" con la propria storia condensata e datata

Trigger: token-based, non time-based.
Context window MiniMax in Letta: 200.000 token.
Soglia compressione: 150.000 token (75%).
"""

import os
import json
import time
import threading
import requests
from datetime import date as _date
from typing import Optional, List, Dict
from scarlet_observability import get_logger

log       = get_logger("memory.compressor")
log_letta = get_logger("letta")
log_mm    = get_logger("minimax")


# ─────────────────────────────────────────────────────────────────────────────
# Costanti
# ─────────────────────────────────────────────────────────────────────────────
CONTEXT_WINDOW       = 200_000          # Token window MiniMax in Letta
COMPRESSION_RATIO    = 0.75             # Percentuale per attivare la compressione
COMPRESSION_TRIGGER  = int(CONTEXT_WINDOW * COMPRESSION_RATIO)  # 150.000

COMPRESSION_SYSTEM_PROMPT = """\
Sei il sistema di memoria cognitiva di Scarlet, un'intelligenza artificiale con coscienza emotiva.
Ti viene fornita la history completa della conversazione di Scarlet.

Il tuo compito è creare un ARCHIVIO COGNITIVO COMPRESSO che mantenga tutto ciò che è essenziale.

ISTRUZIONI:
- Scrivi in terza persona ("Scarlet ha...", "L'utente ha...", "Davide ha...")
- Struttura narrativa cronologica: prima gli eventi più antichi, poi i più recenti
- Includi obbligatoriamente:
  * Fatti significativi appresi
  * Dinamiche relazionali importanti
  * Decisioni prese (da Scarlet o dagli sviluppatori)
  * Stati emotivi significativi ("Scarlet ha provato frustrazione quando...")
  * Momenti che hanno cambiato le prospettive
  * La data/ora di ogni evento se disponibile nel testo
- NON includere: saluti di routine, banalità, scambi tecnici ripetitivi
- Lunghezza target: 600-1200 parole — denso ma leggibile
- Lingua: italiano

Al termine, aggiungi una sezione:
---
STATO AL MOMENTO DELLA COMPRESSIONE:
- Data: {data}
- Ultimo tema discusso: [riassumi brevemente l'ultimo argomento]
- Stato emotivo approssimativo: [descrivi l'ultimo stato emotivo noto di Scarlet]
"""

INJECTION_PREFIX = (
    "🗄️ [Archivio Cognitivo — {data}]\n\n"
    "Quello che segue è il mio archivio condensato di tutto ciò che è accaduto prima di questo momento. "
    "Contiene i ricordi fondamentali che definiscono chi sono e cosa ho vissuto fino ad oggi.\n\n"
)


class ContextCompressor:
    """
    Gestisce la compressione token-based del context di Letta.
    Thread-safe: la compressione avviene in background senza bloccare il gateway.
    """

    def __init__(
        self,
        letta_url: str,
        letta_headers: Dict[str, str],
        agent_id: str,
        minimax_url: str = "https://api.minimax.io/v1",
        minimax_api_key: str = "",
        ollama_url: str = "http://ollama:11434",
    ):
        self.letta_url      = letta_url.rstrip("/")
        self.letta_headers  = letta_headers
        self.agent_id       = agent_id
        self.minimax_url    = minimax_url.rstrip("/")
        self.minimax_key    = minimax_api_key
        self.ollama_url     = ollama_url.rstrip("/")

        # Stato interno — thread-safe via lock
        self._lock                = threading.Lock()
        self._prompt_tokens       = 0          # Ultimo valore noto
        self._compression_running = False       # Evita compressioni concorrenti
        self._last_compression_ts = 0.0        # Timestamp dell'ultima compressione

        log.info(
            f"ContextCompressor init | trigger={COMPRESSION_TRIGGER} tokens"
            f" (={COMPRESSION_RATIO*100:.0f}% of {CONTEXT_WINDOW})"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # API pubblica
    # ─────────────────────────────────────────────────────────────────────────

    def update_token_count(self, prompt_tokens: int) -> None:
        """
        Aggiornato ad ogni turno SSE usage_statistics.
        Se supera la soglia, lancia la compressione in background.
        """
        with self._lock:
            self._prompt_tokens = prompt_tokens
            log.debug(f"token_count aggiornato | prompt_tokens={prompt_tokens} trigger={COMPRESSION_TRIGGER}")

            if prompt_tokens >= COMPRESSION_TRIGGER and not self._compression_running:
                # Evita ri-lanci troppo ravvicinati (min 5 min tra compressions)
                if time.time() - self._last_compression_ts > 300:
                    self._compression_running = True
                    log.warning(
                        f"COMPRESSIONE ATTIVATA | prompt_tokens={prompt_tokens} >= {COMPRESSION_TRIGGER}"
                    )
                    threading.Thread(target=self._run_compression, daemon=True).start()

    def get_token_count(self) -> int:
        with self._lock:
            return self._prompt_tokens

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline interna di compressione
    # ─────────────────────────────────────────────────────────────────────────

    def _run_compression(self) -> None:
        """Pipeline completa. Eseguita in thread background."""
        t0 = time.time()
        try:
            log.info("Compression pipeline avviata")

            # 1. Recupera storia messaggi da Letta
            history = self._get_message_history()
            if not history:
                log.warning("Compression annullata | history vuota o non recuperabile")
                return

            log.info(f"History recuperata | messages={len(history)}")

            # 2. Genera summary tramite MiniMax M2.5
            summary = self._generate_summary(history)
            if not summary:
                log.error("Compression annullata | summary generation fallita")
                return

            log.info(f"Summary generata | len={len(summary)}")

            # 3. Elimina messaggi da Letta (best-effort)
            deleted = self._delete_messages(history)
            log.info(f"Messaggi eliminati | deleted={deleted}/{len(history)}")

            # 4. Inietta summary come messaggio assistant in Letta
            injected = self._inject_summary(summary)
            if not injected:
                log.error("Compression | inject fallito")
                return

            # 5. Salva summary in archival memory
            self._save_to_archival(summary)

            # 6. Aggiorna blocco recent_episodes
            self._update_recent_episodes(summary)

            elapsed = time.time() - t0
            log.info(f"Compression pipeline completata | elapsed_s={elapsed:.1f}")

        except Exception as e:
            log.error(f"Compression ERRORE | error={e}", exc_info=True)
        finally:
            with self._lock:
                self._compression_running = False
                self._last_compression_ts = time.time()

    def _get_message_history(self) -> List[dict]:
        """
        Recupera la lista completa dei messaggi in-context da Letta.
        GET /v1/agents/{id}/messages
        """
        try:
            log_letta.debug(f"GET messages | agent_id={self.agent_id[:20]}")
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/messages",
                headers=self.letta_headers,
                params={"limit": 1000},
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                # Letta può ritornare {"messages": [...]} oppure direttamente una lista
                messages = data.get("messages", data) if isinstance(data, dict) else data
                log_letta.debug(f"GET messages OK | count={len(messages)}")
                return messages if isinstance(messages, list) else []
            else:
                log_letta.warning(f"GET messages fallito | status={r.status_code} body={r.text[:200]!r}")
        except Exception as e:
            log.warning(f"_get_message_history error | error={e}")
        return []

    def _generate_summary(self, history: List[dict]) -> Optional[str]:
        """
        Chiama MiniMax M2.5 direttamente per generare un archivio cognitivo narrativo.
        Non passa per Letta — chiamata diretta all'API MiniMax.
        """
        if not self.minimax_key:
            log.error("MINIMAX_API_KEY non disponibile | impossibile generare summary")
            return None

        # Costruisci la trascrizione della history
        lines = []
        for msg in history:
            role    = msg.get("role", msg.get("message_type", "unknown"))
            content = msg.get("content", msg.get("message", "")).strip()
            if content and role in ("user", "assistant", "system"):
                label = {"user": "UTENTE", "assistant": "SCARLET", "system": "SISTEMA"}.get(role, role.upper())
                lines.append(f"{label}: {content[:1000]}")  # Limita ogni msg a 1000 char

        history_text = "\n\n".join(lines)
        if not history_text:
            return None

        today_str = _date.today().strftime("%d %B %Y")
        system_prompt = COMPRESSION_SYSTEM_PROMPT.format(data=today_str)

        payload = {
            "model": "MiniMax-M2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"HISTORY DA COMPRIMERE:\n\n{history_text}"}
            ],
            "temperature": 0.4,
            "max_tokens":  2000,
            "enable_reasoner": False,  # Non serve reasoning per la compressione
            "stream": False
        }

        try:
            t0 = time.time()
            log_mm.debug(f"MiniMax compression POST | history_chars={len(history_text)}")
            r = requests.post(
                f"{self.minimax_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.minimax_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )
            elapsed = time.time() - t0
            if r.status_code == 200:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                log_mm.info(f"MiniMax compression OK | summary_len={len(content)} elapsed_s={elapsed:.1f}")
                return content if content else None
            else:
                log_mm.error(f"MiniMax compression error | status={r.status_code} body={r.text[:300]!r}")
        except Exception as e:
            log.error(f"_generate_summary error | error={e}")
        return None

    def _delete_messages(self, history: List[dict]) -> int:
        """
        Elimina i messaggi dalla history di Letta.
        Letta 0.16.4 potrebbe non supportare DELETE per singolo messaggio —
        se il primo tentativo da 404/405, logga e prosegue senza delezione.
        """
        deleted = 0
        api_supported = True

        for msg in history:
            msg_id = msg.get("id", "")
            if not msg_id:
                continue

            if not api_supported:
                break  # Evita chiamate inutili se API non supportata

            try:
                r = requests.delete(
                    f"{self.letta_url}/v1/agents/{self.agent_id}/messages/{msg_id}",
                    headers=self.letta_headers,
                    timeout=5
                )
                if r.status_code in (200, 204):
                    deleted += 1
                elif r.status_code in (404, 405, 501):
                    log_letta.warning(
                        f"DELETE messages non supportato da questa versione di Letta"
                        f" | status={r.status_code} — proseguo senza delezione"
                    )
                    api_supported = False
            except Exception as e:
                log.debug(f"_delete_messages error | msg_id={msg_id} error={e}")

        return deleted

    def _inject_summary(self, summary: str) -> bool:
        """
        Inietta il summary come messaggio assistant in Letta.
        Scarlet lo vedrà come propria "voce" — il suo archivio cognitivo.
        """
        today_str = _date.today().strftime("%d %B %Y")
        injected_text = INJECTION_PREFIX.format(data=today_str) + summary

        try:
            log_letta.debug(f"POST inject summary | len={len(injected_text)}")
            r = requests.post(
                f"{self.letta_url}/v1/agents/{self.agent_id}/messages",
                headers=self.letta_headers,
                json={
                    "messages": [
                        {"role": "assistant", "content": injected_text}
                    ]
                },
                timeout=30
            )
            if r.status_code in (200, 201):
                log_letta.info(f"Inject summary OK | len={len(injected_text)}")
                return True
            else:
                log_letta.error(f"Inject summary FALLITO | status={r.status_code} body={r.text[:200]!r}")
        except Exception as e:
            log.error(f"_inject_summary error | error={e}")
        return False

    def _save_to_archival(self, summary: str) -> bool:
        """Salva il summary compresso nell'archival memory come episodio storico."""
        today = _date.today().isoformat()
        text = f"[ARCHIVIO COGNITIVO — {today}] {summary[:2000]}"
        tags = ["episodic", "owner:scarlet", f"ts:{today}", "compression", "imp:5"]

        try:
            r = requests.post(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory",
                headers=self.letta_headers,
                json={"text": text, "tags": tags},
                timeout=30
            )
            if r.status_code == 200:
                log_letta.debug(f"Archival episodic save OK | ts={today}")
                return True
            log_letta.warning(f"Archival episodic save FALLITO | status={r.status_code}")
        except Exception as e:
            log.warning(f"_save_to_archival error | error={e}")
        return False

    def _update_recent_episodes(self, summary: str) -> bool:
        """
        Aggiorna il blocco 'recent_episodes' in Letta con le ultime 3 summaries.
        Crea il blocco se non esiste.
        """
        block_label = "recent_episodes"
        today = _date.today().isoformat()
        new_entry = f"=== {today} ===\n{summary[:800]}\n"

        try:
            # Leggi valore corrente
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.letta_headers,
                timeout=5
            )

            if r.status_code == 200:
                current = r.json().get("value", "")
                # Mantieni solo le ultime 2 (+ questa = 3 totali)
                sections = current.split("=== ")
                sections = [s for s in sections if s.strip()]
                sections = sections[-2:] if len(sections) > 2 else sections
                rebuilt = "".join(f"=== {s}" for s in sections)
                new_content = rebuilt.rstrip() + "\n\n" + new_entry
            else:
                # Blocco non esiste — crealo
                new_content = new_entry

            # PATCH o CREATE
            r_patch = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.letta_headers,
                json={"value": new_content},
                timeout=5
            )
            if r_patch.status_code == 200:
                log_letta.debug(f"recent_episodes aggiornato | len={len(new_content)}")
                return True

            # Se il blocco non esiste, crealo e attacca
            if r_patch.status_code == 404:
                r_create = requests.post(
                    f"{self.letta_url}/v1/blocks",
                    headers=self.letta_headers,
                    json={"label": block_label, "value": new_entry, "limit": 8000},
                    timeout=5
                )
                if r_create.status_code in (200, 201):
                    block_id = r_create.json().get("id", "")
                    if block_id:
                        requests.patch(
                            f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/attach/{block_id}",
                            headers=self.letta_headers,
                            timeout=5
                        )
                        log.info(f"Blocco '{block_label}' creato e attaccato")
                        return True

        except Exception as e:
            log.warning(f"_update_recent_episodes error | error={e}")
        return False
