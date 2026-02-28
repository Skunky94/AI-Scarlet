"""
Memory Agent — Estrazione e salvataggio memorie (Background)
=============================================================
Analizza ogni turno (user_msg + think + response) tramite un LLM Ollama
e salva le memorie estratte nell'Archival Memory di Letta.

Processo:
1. Riceve il turno completo dal Gateway (post-risposta, async)
2. Invia al LLM (qwen2.5:7b) con prompt di estrazione
3. Il LLM ritorna JSON con memorie estratte
4. Il Python engine cerca duplicati e inserisce/aggiorna

Modello: qwen2.5:7b su Ollama Docker (~4GB VRAM, ~2-4s)
"""

import os
import json
import time
import threading
import requests
from typing import List, Optional
from dataclasses import dataclass, field
from scarlet_observability import get_logger

log     = get_logger("memory.agent")
log_api = get_logger("ollama")
log_letta = get_logger("letta")


@dataclass
class MemoryItem:
    """Una singola memoria estratta."""
    action: str       # "create" o "update"
    category: str     # user_profile, user_preference, relationship, event, knowledge, emotion
    content: str      # Testo della memoria
    old_id: Optional[str] = None  # ID memoria da aggiornare (per update)


MEMORY_CATEGORIES = [
    "user_profile",      # Chi è l'utente
    "user_preference",   # Preferenze specifiche
    "relationship",      # Dinamica relazionale
    "event",             # Evento significativo
    "knowledge",         # Fatto/conoscenza appresa
    "emotion",           # Momento emotivo importante
]

EXTRACTION_PROMPT = """Sei il sistema di memoria di Scarlet, un'intelligenza artificiale. 
Il tuo compito è analizzare la conversazione e identificare informazioni da memorizzare.

REGOLE:
- Estrai SOLO informazioni utili e significative, non banalità
- Ogni memoria deve essere un fatto concreto, una preferenza, o un evento importante
- Usa categorie: user_profile, user_preference, relationship, event, knowledge, emotion
- Rispondi SOLO con JSON valido, nessun altro testo
- Se non c'è nulla da memorizzare, rispondi con {"memories": []}

FORMATO OUTPUT:
{"memories": [{"action": "create", "category": "categoria", "content": "testo memoria"}]}

Se una memoria AGGIORNA una esistente, usa action "update" e includi la vecchia memoria in "old_content":
{"memories": [{"action": "update", "category": "categoria", "content": "nuovo testo", "old_content": "vecchio testo simile"}]}
"""


class MemoryAgent:
    """Agente di memoria che estrae e salva memorie in background."""
    
    def __init__(
        self,
        ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model: str = "qwen2.5:7b",
        letta_url: str = os.getenv("LETTA_URL", "http://localhost:8283"),
        letta_token: str = os.getenv("LETTA_API_KEY", "scarlet_dev"),
        agent_id_file: str = ".agent_id",
    ):
        self.ollama_url = ollama_url.rstrip('/')
        self.ollama_model = ollama_model
        self.letta_url = letta_url.rstrip('/')
        self.letta_headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json"
        }
        
        # Leggi agent_id: env var (Docker) -> file (host)
        self.agent_id = os.getenv("AGENT_ID", "").strip() or None
        if not self.agent_id:
            try:
                with open(agent_id_file) as f:
                    self.agent_id = f.read().strip()
            except Exception:
                self.agent_id = None
                log.warning("AGENT_ID non trovato | controllare env var AGENT_ID o file .agent_id")

        log.debug(f"MemoryAgent init | ollama={self.ollama_url} letta={self.letta_url} agent_id={str(self.agent_id)[:20] if self.agent_id else None}")

        # Warmup: pre-carica il modello in VRAM in background
        threading.Thread(target=self.warmup, daemon=True).start()
    
    def warmup(self):
        """Pre-carica qwen2.5:7b in VRAM con una richiesta minimale."""
        log.info(f"Warmup | avvio pre-caricamento {self.ollama_model} in VRAM...")
        t0 = time.time()
        try:
            log_api.debug(f"Ollama warmup POST | model={self.ollama_model} url={self.ollama_url}")
            r = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {"num_predict": 1}
                },
                timeout=120
            )
            elapsed = time.time() - t0
            if r.status_code == 200:
                log.info(f"Warmup OK | model={self.ollama_model} elapsed_s={elapsed:.1f}")
            else:
                log.warning(f"Warmup risposta inattesa | status={r.status_code} body={r.text[:200]!r}")
        except Exception as e:
            elapsed = time.time() - t0
            log.warning(f"Warmup FALLITO | model={self.ollama_model} elapsed_s={elapsed:.1f} error={e}")
    
    def extract_memories(self, user_msg: str, think: str, response: str) -> List[MemoryItem]:
        """
        Chiama il LLM Ollama per estrarre memorie dal turno.
        Ritorna lista di MemoryItem.
        """
        # Costruisci il prompt con il turno completo
        turn_context = f"""MESSAGGIO UTENTE:
{user_msg}

PENSIERO SCARLET:
{think if think else "(nessun pensiero esplicito)"}

RISPOSTA SCARLET:
{response}"""

        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": turn_context}
            ],
            "format": "json",
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.3,  # Basso per output deterministico
                "num_predict": 1024
            }
        }
        
        try:
            t0 = time.time()
            log.debug(
                f"extract_memories | user_len={len(user_msg)} think_len={len(think)}"
                f" response_len={len(response)}"
            )
            log_api.debug(f"Ollama extraction POST | model={self.ollama_model} payload_len={len(str(payload))}")
            r = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=120
            )
            elapsed = time.time() - t0

            if r.status_code != 200:
                log.error(f"extract_memories Ollama error | status={r.status_code} body={r.text[:300]!r} elapsed_s={elapsed:.1f}")
                return []

            content = r.json().get("message", {}).get("content", "")
            log_api.debug(f"Ollama response raw | content={content[:500]!r} elapsed_s={elapsed:.1f}")

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                log.warning(f"extract_memories JSON parse error | raw={content[:500]!r} error={e}")
                return []

            memories = data.get("memories", [])
            items = []
            for m in memories:
                if not m.get("content"):
                    log.debug(f"Memoria con content vuoto saltata | raw={m}")
                    continue
                if m.get("category") not in MEMORY_CATEGORIES:
                    log.debug(f"Categoria non riconosciuta | category={m.get('category')!r} memory={m.get('content')[:60]!r}")
                    continue
                items.append(MemoryItem(
                    action=m.get("action", "create"),
                    category=m["category"],
                    content=m["content"],
                    old_id=None
                ))

            log.info(f"extract_memories OK | extracted={len(items)} raw_items={len(memories)} elapsed_s={elapsed:.1f}")
            return items

        except json.JSONDecodeError as e:
            log.warning(f"extract_memories JSON decode fallback | error={e}")
            return []
        except Exception as e:
            log.error(f"extract_memories ERRORE | error={e}")
            return []
    
    def _search_similar(self, text: str, limit: int = 3) -> List[dict]:
        """Cerca memorie simili in archival memory."""
        if not self.agent_id:
            return []

        try:
            log_letta.debug(f"archival search | query_preview={text[:60]!r} limit={limit}")
            t0 = time.time()
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/search",
                headers=self.letta_headers,
                params={"query": text, "limit": limit},
                timeout=30
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                results = r.json().get("results", [])
                log_letta.debug(f"archival search OK | results={len(results)} elapsed_ms={elapsed_ms:.0f}")
                return results
            else:
                log_letta.warning(f"archival search error | status={r.status_code} elapsed_ms={elapsed_ms:.0f}")
        except Exception as e:
            log.warning(f"_search_similar error | error={e}")
        return []
    
    def _insert_memory(self, text: str, tags: List[str]) -> bool:
        """Inserisce una memoria nell'archival memory."""
        if not self.agent_id:
            log.warning("_insert_memory | agent_id mancante, skip")
            return False

        try:
            log_letta.debug(f"archival insert | tags={tags} content_preview={text[:60]!r}")
            t0 = time.time()
            r = requests.post(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory",
                headers=self.letta_headers,
                json={"text": text, "tags": tags},
                timeout=30
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                log_letta.debug(f"archival insert OK | elapsed_ms={elapsed_ms:.0f}")
                return True
            else:
                log_letta.warning(f"archival insert FALLITO | status={r.status_code} body={r.text[:200]!r}")
                return False
        except Exception as e:
            log.warning(f"_insert_memory error | error={e}")
            return False
    
    def _delete_memory(self, memory_id: str) -> bool:
        """Elimina una memoria dall'archival memory."""
        if not self.agent_id:
            log.warning("_delete_memory | agent_id mancante, skip")
            return False

        try:
            log_letta.debug(f"archival delete | memory_id={memory_id}")
            t0 = time.time()
            r = requests.delete(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/{memory_id}",
                headers=self.letta_headers,
                timeout=30
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                log_letta.debug(f"archival delete OK | id={memory_id} elapsed_ms={elapsed_ms:.0f}")
                return True
            else:
                log_letta.warning(f"archival delete FALLITO | status={r.status_code} id={memory_id}")
                return False
        except Exception as e:
            log.warning(f"_delete_memory error | memory_id={memory_id} error={e}")
            return False
    
    def save_memories(self, memories: List[MemoryItem]) -> dict:
        """
        Salva le memorie estratte in archival memory.
        Gestisce deduplicazione: se una memoria simile esiste, la aggiorna.
        
        Returns: {"created": int, "updated": int, "skipped": int}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}

        for mem in memories:
            # Cerca duplicati
            similar = self._search_similar(mem.content, limit=3)

            # Controlla se esiste una memoria molto simile
            duplicate_found = False
            for existing in similar:
                existing_text = existing.get("content", "")
                # Se il testo e' quasi identico, skip
                if self._is_duplicate(mem.content, existing_text):
                    log.debug(f"Dedup DUPLICATO | new={mem.content[:50]!r} existing={existing_text[:50]!r}")
                    stats["skipped"] += 1
                    duplicate_found = True
                    break
                # Se simile ma non identico, aggiorna (delete + create)
                elif self._is_similar(mem.content, existing_text):
                    log.debug(f"Dedup SIMILE (update) | new={mem.content[:50]!r} existing={existing_text[:50]!r}")
                    old_id = existing.get("id", "")
                    if old_id and self._delete_memory(old_id):
                        if self._insert_memory(mem.content, [mem.category]):
                            stats["updated"] += 1
                            duplicate_found = True
                            break

            if not duplicate_found:
                if self._insert_memory(mem.content, [mem.category]):
                    log.debug(f"Memoria creata | category={mem.category} content_preview={mem.content[:60]!r}")
                    stats["created"] += 1

        log.info(f"save_memories | created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}")
        return stats
    
    def _is_duplicate(self, new: str, existing: str) -> bool:
        """Due testi sono considerati duplicati se uno contiene l'altro."""
        new_lower = new.lower().strip()
        existing_lower = existing.lower().strip()
        return new_lower == existing_lower or new_lower in existing_lower or existing_lower in new_lower
    
    def _is_similar(self, new: str, existing: str) -> bool:
        """Due testi sono simili se condividono molte parole chiave."""
        new_words = set(new.lower().split())
        existing_words = set(existing.lower().split())
        if not new_words or not existing_words:
            return False
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        return overlap > 0.6  # 60% overlap = simili
    
    def process_turn(self, user_msg: str, think: str, response: str) -> dict:
        """
        Pipeline completa: estrai memorie dal turno e salvale.
        Chiamato in background dopo ogni risposta di Scarlet.
        """
        t0 = time.time()
        log.debug(
            f"process_turn start | user_len={len(user_msg)}"
            f" think_len={len(think)} response_len={len(response)}"
        )

        # 1. Estrai
        memories = self.extract_memories(user_msg, think, response)

        if not memories:
            log.info("process_turn | nessuna memoria da salvare")
            return {"created": 0, "updated": 0, "skipped": 0}

        # 2. Salva con deduplicazione
        stats = self.save_memories(memories)

        elapsed = time.time() - t0
        log.info(
            f"process_turn completato | elapsed_s={elapsed:.1f}"
            f" created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}"
        )
        return stats
