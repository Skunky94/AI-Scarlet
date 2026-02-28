"""
Memory Retriever — Recupero e feed memorie pre-turno
=====================================================
Prima di ogni turno, cerca memorie rilevanti nell'Archival Memory
e popola i Memory Blocks di Letta per dare a Scarlet contesto.

Flusso:
1. Riceve il messaggio dell'utente
2. Cerca nell'archival memory (ricerca semantica)
3. Aggiorna i memory blocks con le memorie top-5 rilevanti
"""

import os
import re
import requests
import time
from typing import List, Dict, Optional, Tuple
from scarlet_observability import get_logger

log       = get_logger("memory.retriever")
log_letta = get_logger("letta")

# Stopwords italiano + inglese per la query semantica ottimizzata
_STOPWORDS = frozenset({
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "e", "o", "ma",
    "se", "che", "di", "da", "in", "con", "su", "per", "tra", "fra", "a",
    "ho", "hai", "ha", "abbiamo", "avete", "hanno", "sono", "sei",
    "non", "si", "mi", "ti", "ci", "vi", "ne", "sì", "no",
    "me", "te", "lui", "lei", "noi", "voi", "loro",
    "questo", "quello", "questa", "quella", "questi", "quelli",
    "cosa", "come", "quando", "dove", "perché", "chi", "quale", "quanto",
    "the", "a", "an", "and", "or", "but", "if", "in", "on", "at", "to",
    "is", "are", "was", "were", "have", "has", "do", "does", "did",
    "very", "also", "just", "about", "this", "that", "with", "not",
    "certo", "stiamo", "posso", "puoi", "può", "fare", "fatto", "anche",
    "poi", "bene", "male", "qui", "lì", "così", "quindi", "allora",
    "più", "meno", "tanto", "molto", "poco", "troppo", "altro", "ogni",
})


class MemoryRetriever:
    """Recupera memorie rilevanti e aggiorna i memory blocks di Scarlet."""
    
    def __init__(
        self,
        letta_url: str = os.getenv("LETTA_URL", "http://localhost:8283"),
        letta_token: str = os.getenv("LETTA_API_KEY", "scarlet_dev"),
        agent_id_file: str = ".agent_id",
        top_k: int = 5,
    ):
        self.letta_url = letta_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json"
        }
        self.top_k = top_k
        
        # Leggi agent_id: env var (Docker) -> file (host)
        self.agent_id = os.getenv("AGENT_ID", "").strip() or None
        if not self.agent_id:
            try:
                with open(agent_id_file) as f:
                    self.agent_id = f.read().strip()
            except Exception:
                self.agent_id = None
                log.warning("AGENT_ID non trovato | controllare env var AGENT_ID o file .agent_id")
        log.debug(f"MemoryRetriever init | letta={self.letta_url} agent_id={(str(self.agent_id)[:20] if self.agent_id else None)} top_k={self.top_k}")
    
    def _build_retrieval_query(self, text: str) -> str:
        """
        Costruisce una query semantica ottimizzata rimuovendo stopwords
        e mantenendo entità e concetti chiave.
        Zero latency aggiuntiva rispetto a raw text.
        """
        # Tokenizza e rimuovi punteggiatura
        tokens = re.findall(r"[\w']+", text.lower())
        # Filtra: lunghezza > 3, non stopword
        keywords = [t for t in tokens if len(t) > 3 and t not in _STOPWORDS]
        # Limita a 12 parole chiave per query concisa
        keywords = keywords[:12]
        if not keywords:
            return text[:120]  # fallback al testo originale
        query = " ".join(keywords)
        log.debug(f"_build_retrieval_query | original_len={len(text)} query={query!r}")
        return query

    @staticmethod
    def _filter_by_owner(
        memories: List[dict],
        user_id: str,
        top_k: int,
    ) -> List[dict]:
        """
        Filtra client-side le memorie per owner rilevante all'utente corrente.
        Criteri di inclusione (OR):
        - owner:user:{user_id}  → memorie di questo utente
        - owner:world           → conoscenza condivisa
        - owner:scarlet         → stato/riflessioni di Scarlet
        - nessun owner tag      → legacy (pre-ownership), sempre incluse
        """
        allowed = {f"owner:user:{user_id}", "owner:world", "owner:scarlet"}
        result = []
        for m in memories:
            tags = m.get("tags") or []
            owner_tags = [t for t in tags if t.startswith("owner:")]
            if not owner_tags or any(ot in allowed for ot in owner_tags):
                result.append(m)
        return result[:top_k]

    def search_memories(self, query: str, limit: int = None) -> List[dict]:
        """
        Cerca memorie semanticamente rilevanti nell'archival memory.
        Ritorna lista di {id, content, tags, timestamp}.
        """
        if not self.agent_id:
            return []

        limit = limit or self.top_k
        log_letta.debug(f"archival search | query_preview={query[:60]!r} limit={limit}")

        t0 = time.time()
        try:
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/search",
                headers=self.headers,
                params={"query": query, "limit": limit},
                timeout=10
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                results = r.json().get("results", [])
                for i, m in enumerate(results, 1):
                    tags = m.get("tags", [])
                    log_letta.debug(f"  memoria #{i} | [{tags[0] if tags else 'general'}] {m.get('content','')[:80]!r}")
                log.info(f"search_memories OK | query_preview={query[:40]!r} results={len(results)} elapsed_ms={elapsed_ms:.0f}")
                return results
            else:
                log_letta.warning(f"archival search error | status={r.status_code} elapsed_ms={elapsed_ms:.0f}")
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            log.warning(f"search_memories error | elapsed_ms={elapsed_ms:.0f} error={e}")
        return []
    
    def format_active_memories(self, memories: List[dict]) -> str:
        """
        Formatta le memorie per il blocco active_memories.
        Mostra categoria e ownership per contesto.
        """
        if not memories:
            return "=== Memorie Attive ===\n(Nessuna memoria rilevante trovata per il contesto attuale)\n"

        lines = ["=== Memorie Attive (richiamate per contesto) ==="]
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")
            tags = mem.get("tags") or []
            # Prendi il primo tag non-owner e non-pad come categoria
            category_tags = [t for t in tags if not t.startswith(("owner:", "pad:"))]
            tag_str = f"[{category_tags[0]}]" if category_tags else "[general]"
            lines.append(f"{i}. {tag_str} {content}")

        return "\n".join(lines) + "\n"
    
    def update_memory_block(self, block_label: str, content: str) -> bool:
        """Aggiorna un memory block di Scarlet via Letta API."""
        if not self.agent_id:
            return False

        log_letta.debug(f"PATCH core-memory block | label={block_label} content_len={len(content)}")
        t0 = time.time()
        try:
            r = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.headers,
                json={"value": content},
                timeout=5
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                log_letta.debug(f"Block update OK | label={block_label} elapsed_ms={elapsed_ms:.0f}")
                return True
            else:
                log_letta.warning(f"Block update FALLITO | label={block_label} status={r.status_code} elapsed_ms={elapsed_ms:.0f}")
                return False
        except Exception as e:
            log.warning(f"update_memory_block error | label={block_label} error={e}")
            return False
    
    def ensure_block_exists(self, block_label: str, initial_value: str = "") -> bool:
        """Verifica che il blocco esista, altrimenti lo crea e attacca."""
        if not self.agent_id:
            return False
        
        # Controlla se il blocco già esiste
        try:
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.headers,
                timeout=5
            )
            if r.status_code == 200:
                return True  # Esiste già
        except Exception:
            pass
        
        # Crea il blocco
        try:
            r_create = requests.post(
                f"{self.letta_url}/v1/blocks",
                headers=self.headers,
                json={
                    "label": block_label,
                    "value": initial_value or f"=== {block_label} ===\n(vuoto)\n",
                    "limit": 5000
                },
                timeout=5
            )
            if r_create.status_code not in [200, 201]:
                log.warning(f"ensure_block_exists create failed | label={block_label} status={r_create.status_code} body={r_create.text[:200]!r}")
                return False

            block_id = r_create.json().get("id", "")

            # Attacca al nostro agente
            r_attach = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/attach/{block_id}",
                headers=self.headers,
                timeout=5
            )
            if r_attach.status_code == 200:
                log.info(f"ensure_block_exists | blocco '{block_label}' creato e attaccato | block_id={block_id}")
                return True
            else:
                log.warning(f"ensure_block_exists attach failed | label={block_label} status={r_attach.status_code} body={r_attach.text[:200]!r}")
                return False

        except Exception as e:
            log.warning(f"ensure_block_exists error | label={block_label} error={e}")
            return False
    
    def feed_context(self, user_message: str, user_id: str = "default") -> dict:
        """
        Pipeline completa pre-turno: cerca memorie e popola i blocchi.
        Chiamato PRIMA di inviare il messaggio a Scarlet.

        Args:
            user_message: Testo dell'utente (non usato grezzo come query)
            user_id:      Identità utente per filtering ownership

        Returns: {"memories_found": int, "block_updated": bool}
        """
        t0 = time.time()

        # 1. Costruisci query semantica ottimizzata (non raw text)
        query = self._build_retrieval_query(user_message)
        log.debug(f"feed_context start | user_id={user_id!r} query={query!r} top_k={self.top_k}")

        # 2. Cerca memorie con over-fetch per compensare il filtraggio owner
        raw_memories = self.search_memories(query, limit=self.top_k * 3)

        # 3. Filtra per owner rilevante all'utente corrente
        memories = self._filter_by_owner(raw_memories, user_id=user_id, top_k=self.top_k)

        # 4. Formatta e aggiorna il blocco active_memories
        formatted = self.format_active_memories(memories)
        log.debug(f"feed_context active_memories formatted | len={len(formatted)}")
        block_ok = self.update_memory_block("active_memories", formatted)

        elapsed = (time.time() - t0) * 1000
        count = len(memories)

        log.info(
            f"feed_context | user_id={user_id!r} raw={len(raw_memories)}"
            f" filtered={count} block_updated={block_ok} elapsed_ms={elapsed:.0f}"
        )
        if count > 0:
            log.debug(f"Memorie richiamate per contesto: {[m.get('content','')[:50] for m in memories]}")

        return {
            "memories_found": count,
            "block_updated": block_ok,
            "elapsed_ms": elapsed
        }
