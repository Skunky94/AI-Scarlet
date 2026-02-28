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

import json
import time
import threading
import requests
from typing import List, Optional
from dataclasses import dataclass, field


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
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:7b",
        letta_url: str = "http://localhost:8283",
        letta_token: str = "scarlet_dev",
        agent_id_file: str = ".agent_id",
    ):
        self.ollama_url = ollama_url.rstrip('/')
        self.ollama_model = ollama_model
        self.letta_url = letta_url.rstrip('/')
        self.letta_headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json"
        }
        
        # Leggi agent_id
        try:
            with open(agent_id_file) as f:
                self.agent_id = f.read().strip()
        except Exception:
            self.agent_id = None
            print("[MemoryAgent] WARN: .agent_id non trovato")
        
        # Warmup: pre-carica il modello in VRAM in background
        threading.Thread(target=self.warmup, daemon=True).start()
    
    def warmup(self):
        """Pre-carica qwen2.5:7b in VRAM con una richiesta minimale."""
        try:
            t0 = time.time()
            print(f"[MemoryAgent] Warmup: caricamento {self.ollama_model} in VRAM...")
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
                print(f"[MemoryAgent] Warmup OK: {self.ollama_model} caricato in {elapsed:.1f}s")
            else:
                print(f"[MemoryAgent] Warmup WARN: {r.status_code}")
        except Exception as e:
            print(f"[MemoryAgent] Warmup error: {e}")
    
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
            r = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=120
            )
            elapsed = time.time() - t0
            
            if r.status_code != 200:
                print(f"[MemoryAgent] Ollama error {r.status_code}: {r.text[:200]}")
                return []
            
            content = r.json().get("message", {}).get("content", "")
            data = json.loads(content)
            memories = data.get("memories", [])
            
            items = []
            for m in memories:
                if m.get("content") and m.get("category") in MEMORY_CATEGORIES:
                    items.append(MemoryItem(
                        action=m.get("action", "create"),
                        category=m["category"],
                        content=m["content"],
                        old_id=None
                    ))
            
            print(f"[MemoryAgent] Estratte {len(items)} memorie in {elapsed:.1f}s")
            return items
            
        except json.JSONDecodeError as e:
            print(f"[MemoryAgent] JSON parse error: {e}")
            return []
        except Exception as e:
            print(f"[MemoryAgent] Error: {e}")
            return []
    
    def _search_similar(self, text: str, limit: int = 3) -> List[dict]:
        """Cerca memorie simili in archival memory."""
        if not self.agent_id:
            return []
        
        try:
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/search",
                headers=self.letta_headers,
                params={"query": text, "limit": limit},
                timeout=30
            )
            if r.status_code == 200:
                return r.json().get("results", [])
        except Exception as e:
            print(f"[MemoryAgent] Search error: {e}")
        return []
    
    def _insert_memory(self, text: str, tags: List[str]) -> bool:
        """Inserisce una memoria nell'archival memory."""
        if not self.agent_id:
            return False
        
        try:
            r = requests.post(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory",
                headers=self.letta_headers,
                json={"text": text, "tags": tags},
                timeout=30
            )
            return r.status_code == 200
        except Exception as e:
            print(f"[MemoryAgent] Insert error: {e}")
            return False
    
    def _delete_memory(self, memory_id: str) -> bool:
        """Elimina una memoria dall'archival memory."""
        if not self.agent_id:
            return False
        
        try:
            r = requests.delete(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/{memory_id}",
                headers=self.letta_headers,
                timeout=30
            )
            return r.status_code == 200
        except Exception as e:
            print(f"[MemoryAgent] Delete error: {e}")
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
                # Se il testo è quasi identico, skip
                if self._is_duplicate(mem.content, existing_text):
                    stats["skipped"] += 1
                    duplicate_found = True
                    break
                # Se simile ma non identico, aggiorna (delete + create)
                elif self._is_similar(mem.content, existing_text):
                    old_id = existing.get("id", "")
                    if old_id and self._delete_memory(old_id):
                        if self._insert_memory(mem.content, [mem.category]):
                            stats["updated"] += 1
                            duplicate_found = True
                            break
            
            if not duplicate_found:
                if self._insert_memory(mem.content, [mem.category]):
                    stats["created"] += 1
        
        print(f"[MemoryAgent] Saved: {stats}")
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
        
        # 1. Estrai
        memories = self.extract_memories(user_msg, think, response)
        
        if not memories:
            print("[MemoryAgent] Nessuna memoria da salvare")
            return {"created": 0, "updated": 0, "skipped": 0}
        
        # 2. Salva con deduplicazione
        stats = self.save_memories(memories)
        
        elapsed = time.time() - t0
        print(f"[MemoryAgent] Turno processato in {elapsed:.1f}s")
        
        return stats
