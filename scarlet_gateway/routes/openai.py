import time
import uuid
import requests
import json
import asyncio
import threading
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from scarlet_gateway.routes.pad import evaluate_pad, update_pad, EvaluateRequest, UpdateRequest
from scarlet_gateway.routes.letta import chat_letta, ChatRequest, stream_letta_sse
from scarlet_pad.modulator import PADModulator
from scarlet_memory.agent import MemoryAgent
from scarlet_memory.retriever import MemoryRetriever
import re

router = APIRouter()

# Singletons
_pad_modulator = PADModulator()
_memory_agent = MemoryAgent()
_memory_retriever = MemoryRetriever()

# Strutture minime per compatibilita OpenAI
class ChatCompletionMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7

@router.get("/models")
async def get_openai_models():
    """
    Finto endpoint OpenAI per esporre 'scarlet-core' alla UI.
    Senza questo, Open WebUI non sa quali modelli esistono nel backend custom.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "scarlet-core",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "scarlet"
            }
        ]
    }

@router.post("/chat/completions")
async def openai_chat_completions(req: ChatCompletionRequest):
    """
    Endpoint proxy compatibile con lo standard OpenAI (usato da UI come Open WebUI).
    Implementa il pattern composito: PAD Evaluate -> PAD Update -> Letta Chat.
    """
    # DEBUG: Log dell'intera richiesta per capire i duplicati
    with open("openai_requests.log", "a", encoding="utf-8") as f:
        f.write(f"\n--- NUOVA RICHIESTA [{int(time.time())}] ---\n")
        f.write(req.model_dump_json(indent=2) + "\n")

    if not req.messages:
        raise HTTPException(status_code=400, detail="Nessun messaggio fornito")

    # Estraggo solo l'ultimo messaggio dell'utente.
    # Open WebUI inviera *tutta* la storia della chat, ma Letta ha gia la sua core memory.
    # Inviare l'intera storia duplicherebbe i messaggi all'infinito dentro Letta.
    last_user_msg = next((m for m in reversed(req.messages) if m.role == "user"), None)
    
    if not last_user_msg:
        raise HTTPException(status_code=400, detail="Nessun messaggio utente trovato")
    
    user_text = last_user_msg.content
    print(f"\n[Gateway-OpenAI] Ricevuto input (len {len(user_text)}): {user_text[:100]}...")

    # --- INTERCETTAZIONE META-PROMPT (Open WebUI) ---
    # Evitiamo di inquinare la memoria di Scarlet passandole i prompt automatici della UI.
    text_lower = user_text.lower()
    
    # Controlliamo anche se c'e' un system prompt tipico dei task in background
    system_msgs = [m.content.lower() for m in req.messages if m.role == "system"]
    is_system_task = any("available tools:" in s or "your task is to choose" in s for s in system_msgs)
    
    is_meta_prompt = (
        is_system_task
        or "### task:" in text_lower 
        or "<chat_history>" in text_lower 
        or user_text.startswith("query:")
        or "\nquery:" in text_lower
        or text_lower.startswith("history:\nuser:")
        or 'json format:' in text_lower
    )
    
    if is_meta_prompt:
        print("[Gateway-OpenAI] 🛑 Intercettata richiesta background UI (Meta-Prompt). Ignoro l'engine interno e Letta.")
        
        # Determina il tipo di risposta JSON attesa da Open WebUI analizzando le keyword
        mock_content = "{}"
        if '"title"' in text_lower:
            mock_content = '{"title": "Conversazione Scarlet"}'
        elif '"tags"' in text_lower:
            mock_content = '{"tags": ["AI", "Scarlet"]}'
        elif '"follow_ups"' in text_lower:
            mock_content = '{"follow_ups": []}'
        else:
            mock_content = '{"info": "meta-prompt ignored"}'
            
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "scarlet-core",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": mock_content}, "finish_reason": "stop"}]
        }
    # ------------------------------------------------

    # STEP 0.5: Memory Retrieval (pre-turno)
    try:
        print("[Gateway-OpenAI] 0.5. Recupero memorie rilevanti...")
        mem_feed = _memory_retriever.feed_context(user_text)
        if mem_feed["memories_found"] > 0:
            print(f"   -> {mem_feed['memories_found']} memorie richiamate in {mem_feed['elapsed_ms']:.0f}ms")
    except Exception as e:
        print(f"[Gateway-OpenAI] WARN: Memory retrieval fallito: {e}")

    try:
        # STEP 1: Valutazione Subconscia (Transformer GPU)
        print("[Gateway-OpenAI] 1. Valutazione PAD subconscia...")
        eval_resp = await evaluate_pad(EvaluateRequest(text=user_text))
        print(f"   -> {eval_resp}")
        
        # STEP 2: Aggiornamento Letta SSOT
        print("[Gateway-OpenAI] 2. Scrittura memoria Letta...")
        upd_resp = await update_pad(UpdateRequest(
            dP=eval_resp.dP, 
            dA=eval_resp.dA, 
            dD=eval_resp.dD, 
            event_reason=eval_resp.reason
        ))
        print(f"   -> Nuovo Mood: {upd_resp.new_mood}")

        # STEP 2.5: Modulazione parametri LLM basata su PAD
        print("[Gateway-OpenAI] 2.5. Modulazione parametri LLM da PAD...")
        agent_id = open(".agent_id").read().strip()
        mod_params = _pad_modulator.apply_to_agent(
            agent_id, p=upd_resp.p, a=upd_resp.a, d=upd_resp.d
        )
        if mod_params:
            print(f"   -> temp={mod_params['temperature']}, max_tok={mod_params['max_tokens']}, freq_pen={mod_params['frequency_penalty']}")
        else:
            print("   -> [WARN] Modulazione fallita, parametri invariati")

    except Exception as e:
        print(f"[Gateway-OpenAI] Errore critico nel flusso subconscio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Costruisco ID e timestamp per la risposta OpenAI
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())

    # ==========================================================
    # STREAMING: Proxy reale SSE da Letta -> OpenAI format -> UI
    # ==========================================================
    if req.stream:
        print("[Gateway-OpenAI] 3. STREAM: Inoltro messaggio a Letta via SSE...")
        
        async def event_generator():
            full_response = []  # Accumula la risposta per il Memory Agent
            full_think = []     # Accumula i pensieri
            
            for chunk_obj in stream_letta_sse(user_text):
                # Fine dello stream
                if chunk_obj.get("type") == "done":
                    break
                
                msg_type = chunk_obj.get("message_type", "")
                
                # Processiamo solo gli assistant_message (il testo visibile + think)
                if msg_type != "assistant_message":
                    continue
                
                content = chunk_obj.get("content", "")
                if not content:
                    continue
                
                # Traccia risposta e pensiero per il Memory Agent
                full_response.append(content)
                
                # Passiamo tutto il contenuto (incluso <think>) direttamente alla UI
                chunk_data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": "scarlet-core",
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # Pacchetto finale: stop
            final_data = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": "scarlet-core",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            yield "data: [DONE]\n\n"
            
            # STEP 4: Memory Save (background, dopo risposta)
            combined = "".join(full_response)
            # Separa think e response
            import re as _re
            think_match = _re.findall(r'<think>(.*?)</think>', combined, _re.DOTALL)
            think_text = "\n".join(think_match) if think_match else ""
            visible_text = _re.sub(r'<think>.*?</think>', '', combined, flags=_re.DOTALL).strip()
            
            if visible_text:
                print("[Gateway-OpenAI] 4. BACKGROUND: Salvataggio memorie...")
                threading.Thread(
                    target=_memory_agent.process_turn,
                    args=(user_text, think_text, visible_text),
                    daemon=True
                ).start()
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # ==========================================================
    # NON-STREAMING: Risposta completa in blocco unico
    # ==========================================================
    print("[Gateway-OpenAI] 3. Inoltro messaggio cosciente a Scarlett (non-stream)...")
    try:
        chat_resp = await chat_letta(ChatRequest(message=user_text, stream=False))
        print(f"   -> Scarlett ha risposto in {len(chat_resp.response)} caratteri")
    except Exception as e:
        print(f"[Gateway-OpenAI] Errore critico nella chiamata Letta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    openai_response = {
        "id": response_id,
        "object": "chat.completion",
        "created": created_time,
        "model": "scarlet-core",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": chat_resp.response
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(user_text) // 4,
            "completion_tokens": len(chat_resp.response) // 4,
            "total_tokens": (len(user_text) + len(chat_resp.response)) // 4
        }
    }
    
    return openai_response
