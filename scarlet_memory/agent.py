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
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from scarlet_observability import get_logger

log     = get_logger("memory.agent")
log_api = get_logger("ollama")
log_letta = get_logger("letta")


@dataclass
class MemoryItem:
    """Una singola memoria estratta."""
    action: str        # "create" o "update"
    category: str      # user_profile, user_preference, relationship, event, knowledge, emotion
    content: str       # Testo della memoria
    importance: int = 3  # 1-5: 1=banale, 3=rilevante, 5=fondamentale
    old_id: Optional[str] = None  # ID memoria da aggiornare (per update)


MEMORY_CATEGORIES = [
    "user_profile",      # Chi è l'utente
    "user_preference",   # Preferenze specifiche dell'utente
    "relationship",      # Dinamica relazionale Scarlet↔Utente
    "event",             # Evento significativo nella relazione
    "knowledge",         # Fatto/conoscenza appresa sul mondo
    "emotion",           # Risposta emotiva di Scarlet in questo momento
]

# Ownership: a chi appartiene ogni tipo di memoria.
# "user"    → specifica per l'utente corrente  (filtrata per user_id in multi-user)
# "world"   → conoscenza condivisa, visibile a tutti gli utenti
# "scarlet" → appartiene a Scarlet come individuo (non legata a nessun utente)
CATEGORY_OWNER: Dict[str, str] = {
    "user_profile":    "user",
    "user_preference": "user",
    "relationship":    "user",
    "event":           "user",
    "knowledge":       "world",
    "emotion":         "scarlet",
}

EXTRACTION_PROMPT = """Sei il sistema di memoria di Scarlet, un'intelligenza artificiale.
Il tuo compito è analizzare la conversazione e identificare informazioni da memorizzare.

PERSONAGGI NELLA CONVERSAZIONE:
- "l'utente" o "user" = la persona umana che parla con Scarlet
- "Scarlet" = l'intelligenza artificiale (NON l'utente)

CATEGORIE E LORO SOGGETTO:
- user_profile     → chi è L'UTENTE (es. professione, età, luogo)
- user_preference  → preferenze DI L'UTENTE (cosa piace/non piace ALL'UTENTE)
- relationship     → la dinamica tra Scarlet e L'UTENTE
- event            → evento importante accaduto nella conversazione
- knowledge        → fatto/conoscenza appresa SUL MONDO (valida indipendentemente dall'utente)
- emotion          → risposta emotiva DI SCARLET in questo momento (NON dell'utente)

ATTENZIONE CRITICA:
- Se l'informazione riguarda Scarlet ("Scarlet vuole...", "Scarlet si sente...") usa SOLO 'emotion' o NON salvare
- Se riguarda L'UTENTE ("l'utente preferisce...", "l'utente lavora come...") usa user_profile o user_preference
- NON salvare come user_preference le caratteristiche di Scarlet

REGOLE:
- Estrai SOLO informazioni utili e significative, non banalità
- Ogni memoria deve essere un fatto concreto, una preferenza, o un evento importante
- Rispondi SOLO con JSON valido, nessun altro testo
- Se non c'è nulla da memorizzare, rispondi con {"memories": []}

IMPORTANZA (obbligatoria per ogni memoria):
- 1: informazione banale o ridondante
- 2: utile ma poco significativa
- 3: rilevante, vale la pena ricordare
- 4: importante, probabilmente influenzerà conversazioni future
- 5: fondamentale per la relazione o l'identità di Scarlet

FORMATO OUTPUT:
{"memories": [{"action": "create", "category": "categoria", "content": "testo memoria", "importance": 3}]}

Se una memoria AGGIORNA una esistente, usa action "update" e includi la vecchia memoria in "old_content":
{"memories": [{"action": "update", "category": "categoria", "content": "nuovo testo", "old_content": "vecchio testo simile", "importance": 4}]}
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
                    importance=max(1, min(5, int(m.get("importance", 3)))),
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
    
    def _search_similar(
        self,
        text: str,
        limit: int = 3,
        owner_filter: Optional[str] = None,
    ) -> List[dict]:
        """
        Cerca memorie simili in archival memory.
        Se owner_filter è fornito, filtra client-side per mantenere solo
        memorie dello stesso owner (o legacy senza owner tag).
        """
        if not self.agent_id:
            return []

        # Richiediamo più risultati per compensare il filtraggio client-side
        fetch_limit = limit * 3 if owner_filter else limit
        try:
            log_letta.debug(f"archival search | query_preview={text[:60]!r} limit={fetch_limit} owner_filter={owner_filter!r}")
            t0 = time.time()
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/search",
                headers=self.letta_headers,
                params={"query": text, "limit": fetch_limit},
                timeout=30
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                results = r.json().get("results", [])
                if owner_filter:
                    results = self._filter_by_owner_tag(results, owner_filter)
                results = results[:limit]
                log_letta.debug(f"archival search OK | results={len(results)} elapsed_ms={elapsed_ms:.0f}")
                return results
            else:
                log_letta.warning(f"archival search error | status={r.status_code} elapsed_ms={elapsed_ms:.0f}")
        except Exception as e:
            log.warning(f"_search_similar error | error={e}")
        return []

    @staticmethod
    def _filter_by_owner_tag(memories: List[dict], owner_tag: str) -> List[dict]:
        """
        Filtra lista di memorie per owner tag client-side.
        Memorie senza tag owner (legacy) vengono sempre incluse per
        compatibilità retroattiva.
        """
        result = []
        for m in memories:
            tags = m.get("tags") or []
            owner_tags = [t for t in tags if t.startswith("owner:")]
            # Nessun owner tag = memoria legacy, includi sempre
            if not owner_tags:
                result.append(m)
            elif owner_tag in owner_tags:
                result.append(m)
        return result
    
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
    
    def save_memories(
        self,
        memories: List[MemoryItem],
        user_id: str = "default",
        pad_state: Optional[Tuple[float, float, float]] = None,
    ) -> dict:
        """
        Salva le memorie estratte in archival memory.
        Gestisce deduplicazione scoped per owner e attach PAD salience.

        Tag applicati a ogni memoria:
        - Categoria semantica (es. 'user_preference')
        - Owner (es. 'owner:user:davide', 'owner:world', 'owner:scarlet')
        - PAD encoding (es. 'pad:+0.21:+0.52:+0.11') se pad_state disponibile

        Returns: {"created": int, "updated": int, "skipped": int}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}

        from datetime import date as _date

        for mem in memories:
            # Salta memorie a bassa importanza (rumore cognitivo)
            if mem.importance < 3:
                log.debug(f"skip low-importance | importance={mem.importance} content={mem.content[:50]!r}")
                stats["skipped"] += 1
                continue

            # Determina owner tag in base alla categoria
            owner_type = CATEGORY_OWNER.get(mem.category, "user")
            owner_tag = (
                f"owner:user:{user_id}" if owner_type == "user"
                else f"owner:{owner_type}"
            )

            # Costruisci i tag per questa memoria (categoria + owner + data + importanza + PAD)
            tags = [
                mem.category,
                owner_tag,
                f"ts:{_date.today().isoformat()}",   # Fase 1: timestamp per recency decay
                f"imp:{mem.importance}",               # Fase 2: importanza per re-ranking
            ]
            if pad_state is not None:
                P, A, D = pad_state
                tags.append(f"pad:{P:+.2f}:{A:+.2f}:{D:+.2f}")

            log.debug(
                f"save_memories prepare | category={mem.category}"
                f" owner={owner_tag!r} pad={pad_state}"
            )

            # Cerca duplicati nello stesso owner-scope
            similar = self._search_similar(mem.content, limit=3, owner_filter=owner_tag)

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
                        if self._insert_memory(mem.content, tags):
                            stats["updated"] += 1
                            duplicate_found = True
                            break

            if not duplicate_found:
                if self._insert_memory(mem.content, tags):
                    log.debug(f"Memoria creata | category={mem.category} owner={owner_tag!r} importance={mem.importance} content_preview={mem.content[:60]!r}")
                    stats["created"] += 1

                    # Fase 5: importanza >= 4 → aggiorna blocchi evolutivi
                    if mem.importance >= 4:
                        if mem.category == "emotion":
                            threading.Thread(
                                target=self._append_to_block,
                                args=("inner_world", mem.content),
                                daemon=True
                            ).start()
                        elif mem.category == "relationship":
                            threading.Thread(
                                target=self._append_to_block,
                                args=("relationships", mem.content),
                                daemon=True
                            ).start()

        log.info(f"save_memories | user_id={user_id!r} created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}")
        return stats
    
    # ─── Deduplication semantica (Fase 5) ────────────────────────────────────

    def _get_embedding(self, text: str) -> Optional[list]:
        """
        Chiama mxbai-embed-large via Ollama per ottenere l'embedding del testo.
        Fallisce silenziosamente: ritorna None se Ollama non risponde.
        """
        try:
            r = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": "mxbai-embed-large", "prompt": text},
                timeout=8
            )
            if r.status_code == 200:
                return r.json().get("embedding")
        except Exception:
            pass
        return None

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        """Cosine similarity tra due vettori 1024-dim."""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if not mag_a or not mag_b:
            return 0.0
        return dot / (mag_a * mag_b)

    def _is_duplicate(self, new: str, existing: str) -> bool:
        """
        Duplicato semantico: cosine similarity >= 0.85 (via embedding),
        con fallback su match letterale se embedding non disponibile.
        """
        emb_new = self._get_embedding(new)
        emb_ex  = self._get_embedding(existing)
        if emb_new and emb_ex:
            return self._cosine_similarity(emb_new, emb_ex) >= 0.85
        # Fallback: match letterale
        n, e = new.lower().strip(), existing.lower().strip()
        return n == e or n in e or e in n

    def _is_similar(self, new: str, existing: str) -> bool:
        """
        Simile ma non identico: cosine similarity 0.70–0.84 (via embedding),
        con fallback su word-overlap 60%.
        """
        emb_new = self._get_embedding(new)
        emb_ex  = self._get_embedding(existing)
        if emb_new and emb_ex:
            sim = self._cosine_similarity(emb_new, emb_ex)
            return 0.70 <= sim < 0.85
        # Fallback: word overlap
        new_words = set(new.lower().split())
        existing_words = set(existing.lower().split())
        if not new_words or not existing_words:
            return False
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        return overlap > 0.6

    # ─── Blocchi evolutivi (Fase 5) ────────────────────────────────────────────

    def _append_to_block(self, block_label: str, text: str) -> bool:
        """
        Appende un testo datato a un memory block di Letta.
        Usato per aggiornare inner_world (emotion) e relationships (relationship)
        quando vengono salvate memorie con importanza >= 4.
        """
        if not self.agent_id:
            return False
        from datetime import date as _date
        try:
            # 1. Leggi valore corrente
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.letta_headers,
                timeout=5
            )
            if r.status_code != 200:
                log.debug(f"_append_to_block GET fallito | label={block_label} status={r.status_code}")
                return False
            current = r.json().get("value", "")

            # 2. Appendi con timestamp
            new_content = current.rstrip() + f"\n\n[{_date.today().isoformat()}] {text}"

            # 3. PATCH
            r2 = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.letta_headers,
                json={"value": new_content},
                timeout=5
            )
            if r2.status_code == 200:
                log_letta.debug(f"_append_to_block OK | label={block_label} appended_len={len(text)}")
                return True
            log.debug(f"_append_to_block PATCH fallito | label={block_label} status={r2.status_code}")
        except Exception as e:
            log.debug(f"_append_to_block error | label={block_label} error={e}")
        return False
    
    def process_turn(
        self,
        user_msg: str,
        think: str,
        response: str,
        user_id: str = "default",
        pad_state: Optional[Tuple[float, float, float]] = None,
    ) -> dict:
        """
        Pipeline completa: estrai memorie dal turno e salvale.
        Chiamato in background dopo ogni risposta di Scarlet.

        Args:
            user_msg:  Messaggio dell'utente
            think:     Blocco <think> di Scarlet per questo turno
            response:  Risposta visibile di Scarlet
            user_id:   Identità dell'utente (per ownership e multi-user)
            pad_state: Snapshot PAD al momento della risposta (P, A, D),
                       usato per codificare la salienza emotiva della memoria
        """
        t0 = time.time()
        log.debug(
            f"process_turn start | user_id={user_id!r} user_len={len(user_msg)}"
            f" think_len={len(think)} response_len={len(response)}"
            f" pad_state={pad_state}"
        )

        # 1. Estrai
        memories = self.extract_memories(user_msg, think, response)

        if not memories:
            log.info(f"process_turn | user_id={user_id!r} nessuna memoria da salvare")
            return {"created": 0, "updated": 0, "skipped": 0}

        # 2. Salva con ownership, PAD salience e deduplicazione
        stats = self.save_memories(memories, user_id=user_id, pad_state=pad_state)

        elapsed = time.time() - t0
        log.info(
            f"process_turn completato | user_id={user_id!r} elapsed_s={elapsed:.1f}"
            f" created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}"
        )
        return stats
