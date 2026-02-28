"""
Cognee Memory Retriever — Recupero memorie pre-turno via Knowledge Graph
========================================================================
Sostituisce retriever.py come layer di archival retrieval.

Invece di ricerca semantica flat su Letta archival, usa Cognee
con SearchType.GRAPH_COMPLETION_COT: ragionamento multi-hop sul grafo
Kuzu, che integra relazioni temporali, entità e link semantici.

Il risultato viene comunque scritto nel blocco Letta 'active_memories'
(meccanismo invariato) così che Scarlet riceva le memorie nel contesto.

Flusso pre-turno:
1. 3 query in parallelo su Cognee (q1 semantica, q2 contesto, q3 PAD emotiva)
2. Dedup + formattazione dei risultati
3. PATCH Letta → blocco active_memories (identico alla vecchia implementazione)
"""

import os
import re
import time
import asyncio
import requests
from typing import List, Optional, Tuple

import cognee
from cognee.modules.search.types import SearchType
from scarlet_observability import get_logger

log       = get_logger("memory.cognee_retriever")
log_letta = get_logger("letta")

# Stopwords italiano + inglese (invariate rispetto a retriever.py)
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


def _build_retrieval_query(text: str) -> str:
    """
    Query semantica ottimizzata: rimuove stopwords, mantiene entità/concetti.
    Stessa logica di MemoryRetriever._build_retrieval_query().
    """
    tokens = re.findall(r"[\w']+", text.lower())
    keywords = [t for t in tokens if len(t) > 3 and t not in _STOPWORDS]
    keywords = keywords[:12]
    if not keywords:
        return text[:120]
    return " ".join(keywords)


def _build_emotional_query(pad_state: Tuple[float, float, float]) -> str:
    """
    Query basata sullo stato PAD: prioritizza memorie emotivamente affini.
    Stessa logica di MemoryRetriever._build_emotional_query().
    """
    P, A, D = pad_state
    keywords = []
    if P > 0.3:    keywords += ["piacere", "soddisfazione", "gioia"]
    elif P < -0.3: keywords += ["tristezza", "difficoltà", "dolore"]
    if A > 0.5:    keywords += ["eccitazione", "curiosità", "energia"]
    elif A < 0.0:  keywords += ["calma", "riflessione", "tranquillità"]
    if D > 0.3:    keywords += ["controllo", "autonomia", "decisione"]
    elif D < 0.0:  keywords += ["incertezza", "dubbio", "vulnerabilità"]
    return " ".join(keywords) if keywords else ""


def _extract_result_text(result) -> str:
    """
    Estrae il testo da un risultato Cognee, indipendentemente dal formato.
    GRAPH_COMPLETION_COT ritorna oggetti di tipi diversi a seconda della versione.
    """
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "content", "answer", "description", "summary"):
            if key in result and isinstance(result[key], str):
                return result[key].strip()
        return str(result).strip()
    for attr in ("text", "content", "answer", "description", "summary"):
        val = getattr(result, attr, None)
        if val and isinstance(val, str):
            return val.strip()
    return str(result).strip()


class CogneeRetriever:
    """
    Recupera memorie rilevanti dal grafo Cognee e aggiorna i memory blocks di Scarlet.
    Interfaccia drop-in per scarlet_memory.retriever.MemoryRetriever (metodi async).

    Thread-safety: usa cognee async + requests sync (update_memory_block).
    Chiamare feed_context_async() tramite await in contesto FastAPI async.
    """

    def __init__(
        self,
        letta_url: str = os.getenv("LETTA_URL", "http://localhost:8283"),
        letta_token: str = os.getenv("LETTA_API_KEY", "scarlet_dev"),
        agent_id_file: str = ".agent_id",
        top_k: int = 5,
    ):
        self.letta_url = letta_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json",
        }
        self.top_k = top_k

        # Leggi agent_id: env var (Docker) → file (host)
        self.agent_id = os.getenv("AGENT_ID", "").strip() or None
        if not self.agent_id:
            try:
                with open(agent_id_file) as f:
                    self.agent_id = f.read().strip()
            except Exception:
                self.agent_id = None
                log.warning(
                    "AGENT_ID non trovato | controllare env var AGENT_ID "
                    "o file .agent_id"
                )

        log.debug(
            f"CogneeRetriever init | letta={self.letta_url}"
            f" agent_id={str(self.agent_id)[:20] if self.agent_id else None}"
            f" top_k={self.top_k}"
        )

    # ─────────────────────────────────────────────────────────────────
    # Letta — aggiornamento blocco active_memories (invariato rispetto
    # a retriever.py: stesso endpoint PATCH, stesse credenziali)
    # ─────────────────────────────────────────────────────────────────

    def update_memory_block(self, block_label: str, content: str) -> bool:
        """Aggiorna un memory block Letta via PATCH REST API (sync)."""
        if not self.agent_id:
            return False

        log_letta.debug(
            f"PATCH core-memory block | label={block_label}"
            f" content_len={len(content)}"
        )
        t0 = time.time()
        try:
            r = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}"
                f"/core-memory/blocks/{block_label}",
                headers=self.headers,
                json={"value": content},
                timeout=5,
            )
            elapsed_ms = (time.time() - t0) * 1000
            if r.status_code == 200:
                log_letta.debug(
                    f"Block update OK | label={block_label}"
                    f" elapsed_ms={elapsed_ms:.0f}"
                )
                return True
            log_letta.warning(
                f"Block update FALLITO | label={block_label}"
                f" status={r.status_code} elapsed_ms={elapsed_ms:.0f}"
            )
        except Exception as e:
            log.warning(f"update_memory_block error | label={block_label} error={e}")
        return False

    # ─────────────────────────────────────────────────────────────────
    # Cognee — ricerca nel grafo
    # ─────────────────────────────────────────────────────────────────

    async def _search_cognee(self, query: str, dataset: str) -> List[str]:
        """
        Esegue una singola query GRAPH_COMPLETION_COT su Cognee.
        Ritorna lista di stringhe di testo (eventualmente vuota su errore).
        """
        if not query:
            return []
        try:
            log.debug(
                f"cognee.search | dataset={dataset!r}"
                f" query_preview={query[:60]!r}"
            )
            results = await cognee.search(
                query,
                query_type=SearchType.GRAPH_COMPLETION_COT,
                node_sets=[dataset],
            )
            texts = []
            for r in (results or []):
                t = _extract_result_text(r)
                if t:
                    texts.append(t)
            return texts
        except Exception as e:
            log.warning(f"cognee.search ERRORE | dataset={dataset!r} error={e}")
            return []

    def format_active_memories(self, memory_texts: List[str]) -> str:
        """
        Formatta le memorie per il blocco active_memories di Scarlet.
        Ogni voce è un paragrafo numerato restituito da GRAPH_COMPLETION_COT.
        """
        if not memory_texts:
            return (
                "=== Memorie Attive ===\n"
                "(Nessuna memoria rilevante trovata per il contesto attuale)\n"
            )

        lines = ["=== Memorie Attive (grafo Cognee — GRAPH_COMPLETION_COT) ==="]
        for i, text in enumerate(memory_texts, 1):
            # Trunca a 400 caratteri per stare nel limite del block Letta
            snippet = text[:400].replace("\n", " ").strip()
            lines.append(f"{i}. {snippet}")

        return "\n".join(lines) + "\n"

    # ─────────────────────────────────────────────────────────────────
    # Entry point principale — equivalente async di feed_context()
    # ─────────────────────────────────────────────────────────────────

    async def feed_context_async(
        self,
        user_message: str,
        user_id: str = "default",
        conversation_context: Optional[List[str]] = None,
        pad_state: Optional[Tuple[float, float, float]] = None,
    ) -> dict:
        """
        Pipeline completa pre-turno: cerca nel grafo Cognee e popola
        il blocco Letta 'active_memories'.

        3 query in parallelo (asyncio.gather):
          q1: keyword semantiche dal messaggio utente corrente
          q2: keyword semantiche dagli ultimi 2 turni (tema conversazione)
          q3: query emotiva basata sullo stato PAD corrente

        Args:
            user_message:         Testo dell'utente
            user_id:              Identità utente (isolamento dataset Cognee)
            conversation_context: Ultimi N turni utente per contesto tematico
            pad_state:            Stato PAD Scarlet per query emotiva

        Returns:
            {"memories_found": int, "block_updated": bool, "elapsed_ms": float}
        """
        t0 = time.time()
        dataset = f"scarlet_{user_id}"

        # ——— Costruzione query ———
        q1 = _build_retrieval_query(user_message)

        q2 = ""
        if conversation_context:
            merged_ctx = " ".join(conversation_context[-2:])
            q2 = _build_retrieval_query(merged_ctx)

        q3 = _build_emotional_query(pad_state) if pad_state else ""

        log.debug(
            f"feed_context_async start | user_id={user_id!r}"
            f" dataset={dataset!r} q1={q1!r}"
            f" q2={repr(q2) if q2 else '(skip)'}"
            f" q3={repr(q3) if q3 else '(skip)'}"
        )

        # ——— 3 query in parallelo su Cognee ———
        results_1, results_2, results_3 = await asyncio.gather(
            self._search_cognee(q1, dataset),
            self._search_cognee(q2, dataset),
            self._search_cognee(q3, dataset),
        )

        # ——— Merge + dedup per testo ———
        seen: set = set()
        merged: List[str] = []
        for text in results_1 + results_2 + results_3:
            key = text[:100]  # primo blocco come fingerprint
            if key not in seen:
                seen.add(key)
                merged.append(text)

        # Limita a top_k ricordi (già ordinati per rilevanza da Cognee)
        top_memories = merged[: self.top_k]

        # ——— Formatta e aggiorna il blocco Letta active_memories ———
        formatted = self.format_active_memories(top_memories)
        log.debug(f"active_memories formatted | len={len(formatted)}")

        # update_memory_block è sync (requests) — ok perché è una sola chiamata
        # rapida e non blocca l'event loop per >5s
        block_ok = self.update_memory_block("active_memories", formatted)

        elapsed = (time.time() - t0) * 1000
        count = len(top_memories)

        log.info(
            f"feed_context_async OK | user_id={user_id!r} dataset={dataset!r}"
            f" q1={len(results_1)} q2={len(results_2)} q3={len(results_3)}"
            f" merged={len(merged)} final={count}"
            f" block_updated={block_ok} elapsed_ms={elapsed:.0f}"
        )

        return {
            "memories_found": count,
            "block_updated": block_ok,
            "elapsed_ms": elapsed,
        }
