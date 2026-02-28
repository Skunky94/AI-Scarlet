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

import requests
import time
from typing import List, Dict, Optional


class MemoryRetriever:
    """Recupera memorie rilevanti e aggiorna i memory blocks di Scarlet."""
    
    def __init__(
        self,
        letta_url: str = "http://localhost:8283",
        letta_token: str = "scarlet_dev",
        agent_id_file: str = ".agent_id",
        top_k: int = 5,
    ):
        self.letta_url = letta_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {letta_token}",
            "Content-Type": "application/json"
        }
        self.top_k = top_k
        
        try:
            with open(agent_id_file) as f:
                self.agent_id = f.read().strip()
        except Exception:
            self.agent_id = None
            print("[MemoryRetriever] WARN: .agent_id non trovato")
    
    def search_memories(self, query: str, limit: int = None) -> List[dict]:
        """
        Cerca memorie semanticamente rilevanti nell'archival memory.
        Ritorna lista di {id, content, tags, timestamp}.
        """
        if not self.agent_id:
            return []
        
        limit = limit or self.top_k
        
        try:
            r = requests.get(
                f"{self.letta_url}/v1/agents/{self.agent_id}/archival-memory/search",
                headers=self.headers,
                params={"query": query, "limit": limit},
                timeout=10
            )
            if r.status_code == 200:
                return r.json().get("results", [])
        except Exception as e:
            print(f"[MemoryRetriever] Search error: {e}")
        return []
    
    def format_active_memories(self, memories: List[dict]) -> str:
        """
        Formatta le memorie per il blocco active_memories.
        Ogni memoria è una riga con tag e contenuto.
        """
        if not memories:
            return "=== Memorie Attive ===\n(Nessuna memoria rilevante trovata per il contesto attuale)\n"
        
        lines = ["=== Memorie Attive (richiamate per contesto) ==="]
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")
            tags = mem.get("tags", [])
            tag_str = f"[{tags[0]}]" if tags else "[general]"
            lines.append(f"{i}. {tag_str} {content}")
        
        return "\n".join(lines) + "\n"
    
    def update_memory_block(self, block_label: str, content: str) -> bool:
        """Aggiorna un memory block di Scarlet via Letta API."""
        if not self.agent_id:
            return False
        
        try:
            r = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/{block_label}",
                headers=self.headers,
                json={"value": content},
                timeout=5
            )
            return r.status_code == 200
        except Exception as e:
            print(f"[MemoryRetriever] Block update error: {e}")
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
                print(f"[MemoryRetriever] Block create failed: {r_create.text[:200]}")
                return False
            
            block_id = r_create.json().get("id", "")
            
            # Attacca al nostro agente
            r_attach = requests.patch(
                f"{self.letta_url}/v1/agents/{self.agent_id}/core-memory/blocks/attach/{block_id}",
                headers=self.headers,
                timeout=5
            )
            if r_attach.status_code == 200:
                print(f"[MemoryRetriever] Blocco '{block_label}' creato e attaccato")
                return True
            else:
                print(f"[MemoryRetriever] Block attach failed: {r_attach.text[:200]}")
                return False
                
        except Exception as e:
            print(f"[MemoryRetriever] Error creating block: {e}")
            return False
    
    def feed_context(self, user_message: str) -> dict:
        """
        Pipeline completa pre-turno: cerca memorie e popola i blocchi.
        Chiamato PRIMA di inviare il messaggio a Scarlet.
        
        Returns: {"memories_found": int, "block_updated": bool}
        """
        t0 = time.time()
        
        # 1. Cerca memorie rilevanti
        memories = self.search_memories(user_message, limit=self.top_k)
        
        # 2. Formatta e aggiorna il blocco active_memories
        formatted = self.format_active_memories(memories)
        block_ok = self.update_memory_block("active_memories", formatted)
        
        elapsed = (time.time() - t0) * 1000
        count = len(memories)
        
        if count > 0:
            print(f"[MemoryRetriever] Feed: {count} memorie richiamate in {elapsed:.0f}ms")
        
        return {
            "memories_found": count,
            "block_updated": block_ok,
            "elapsed_ms": elapsed
        }
