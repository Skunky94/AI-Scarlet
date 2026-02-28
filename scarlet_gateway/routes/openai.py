import time
import uuid
import requests
import json
import asyncio
import threading
import traceback
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from scarlet_gateway.routes.pad import evaluate_pad, update_pad, EvaluateRequest, UpdateRequest
from scarlet_gateway.routes.letta import chat_letta, ChatRequest, stream_letta_sse
from scarlet_pad.modulator import PADModulator
from scarlet_memory.agent import MemoryAgent
from scarlet_memory.retriever import MemoryRetriever
from scarlet_observability import get_logger
import re

router = APIRouter()
log = get_logger("gateway.openai")

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
    if not req.messages:
        raise HTTPException(status_code=400, detail="Nessun messaggio fornito")

    # Log strutturato della richiesta in ingresso
    log.info(
        f"Richiesta | model={req.model} n_messages={len(req.messages)}"
        f" stream={req.stream} temp={req.temperature}"
    )
    log.debug(f"Payload completo richiesta: {req.model_dump_json()}")

    # Estraggo solo l'ultimo messaggio dell'utente.
    # Open WebUI invia *tutta* la storia, ma Letta ha gia' la sua core memory.
    # Inviare la storia duplicherebbe i messaggi all'infinito dentro Letta.
    last_user_msg = next((m for m in reversed(req.messages) if m.role == "user"), None)

    if not last_user_msg:
        raise HTTPException(status_code=400, detail="Nessun messaggio utente trovato")

    user_text = last_user_msg.content
    log.info(f"User input | len={len(user_text)} preview={user_text[:120]!r}")

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
        # Pattern che ha triggerato l'intercettazione (per debug)
        patterns_hit = [
            ("is_system_task",             is_system_task),
            ("### task:",                  "### task:" in text_lower),
            ("<chat_history>",             "<chat_history>" in text_lower),
            ("query: prefix",              user_text.startswith("query:")),
            ("json format:",               'json format:' in text_lower),
        ]
        triggered = [p for p, v in patterns_hit if v]
        log.info(f"Meta-prompt intercettato | pattern={triggered} user_preview={user_text[:80]!r}")
        log.debug(f"Meta-prompt system_msgs: {system_msgs[:2]}")

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

        log.debug(f"Mock response: {mock_content}")
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
        log.debug(f"Step 0.5 Memory Retrieval | query_preview={user_text[:60]!r}")
        t_mem = time.time()
        mem_feed = _memory_retriever.feed_context(user_text)
        elapsed_mem = (time.time() - t_mem) * 1000
        log.info(
            f"Step 0.5 Memory Retrieval OK | memories_found={mem_feed['memories_found']}"
            f" block_updated={mem_feed.get('block_updated')} elapsed_ms={elapsed_mem:.0f}"
        )
    except Exception as e:
        log.warning(f"Step 0.5 Memory Retrieval FALLITO | error={e}")

    try:
        # STEP 1: Valutazione Subconscia (Transformer GPU)
        log.debug(f"Step 1 PAD Evaluate | input_len={len(user_text)}")
        t_eval = time.time()
        eval_resp = await evaluate_pad(EvaluateRequest(text=user_text))
        elapsed_eval = (time.time() - t_eval) * 1000
        log.info(f"Step 1 PAD Evaluate OK | dP={eval_resp.dP:+.3f} dA={eval_resp.dA:+.3f} dD={eval_resp.dD:+.3f} reason={eval_resp.reason!r} elapsed_ms={elapsed_eval:.1f}")

        # STEP 2: Aggiornamento Letta SSOT
        log.debug(f"Step 2 PAD Update | dP={eval_resp.dP:+.3f} dA={eval_resp.dA:+.3f} dD={eval_resp.dD:+.3f}")
        t_upd = time.time()
        upd_resp = await update_pad(UpdateRequest(
            dP=eval_resp.dP,
            dA=eval_resp.dA,
            dD=eval_resp.dD,
            event_reason=eval_resp.reason
        ))
        elapsed_upd = (time.time() - t_upd) * 1000
        log.info(f"Step 2 PAD Update OK | P={upd_resp.p:+.3f} A={upd_resp.a:+.3f} D={upd_resp.d:+.3f} mood={upd_resp.new_mood!r} elapsed_ms={elapsed_upd:.1f}")

        # STEP 2.5: Modulazione parametri LLM basata su PAD
        log.debug(f"Step 2.5 LLM Modulation | P={upd_resp.p:+.3f} A={upd_resp.a:+.3f} D={upd_resp.d:+.3f}")
        t_mod = time.time()
        try:
            agent_id = open(".agent_id").read().strip()
        except Exception:
            agent_id = ""
        mod_params = _pad_modulator.apply_to_agent(
            agent_id, p=upd_resp.p, a=upd_resp.a, d=upd_resp.d
        )
        elapsed_mod = (time.time() - t_mod) * 1000
        if mod_params:
            log.info(
                f"Step 2.5 LLM Modulation OK | temp={mod_params['temperature']}"
                f" max_tokens={mod_params['max_tokens']} freq_pen={mod_params['frequency_penalty']}"
                f" elapsed_ms={elapsed_mod:.1f}"
            )
        else:
            log.warning(f"Step 2.5 LLM Modulation FALLITA | parametri invariati elapsed_ms={elapsed_mod:.1f}")

    except Exception as e:
        log.error(f"Errore critico flusso subconscio | error={e} traceback={traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

    # Costruisco ID e timestamp per la risposta OpenAI
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())

    # ==========================================================
    # STREAMING: Proxy reale SSE da Letta -> OpenAI format -> UI
    # ==========================================================
    if req.stream:
        log.debug(f"Step 3 STREAM | avvio SSE proxy verso Letta | user_len={len(user_text)}")
        _stream_start = time.time()

        async def event_generator():
            full_response = []   # Accumula la risposta per il Memory Agent
            chunk_count = 0
            first_chunk_ms: float = 0.0

            for chunk_obj in stream_letta_sse(user_text):
                if chunk_obj.get("type") == "done":
                    break

                msg_type = chunk_obj.get("message_type", "")
                log.debug(f"SSE event | type={msg_type} keys={list(chunk_obj.keys())}")

                # Processiamo solo gli assistant_message (testo visibile + think)
                if msg_type != "assistant_message":
                    continue

                content = chunk_obj.get("content", "")
                if not content:
                    continue

                full_response.append(content)
                chunk_count += 1

                if chunk_count == 1:
                    first_chunk_ms = (time.time() - _stream_start) * 1000
                    log.debug(f"Primo chunk SSE | first_chunk_ms={first_chunk_ms:.0f} preview={content[:40]!r}")

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

            total_elapsed_ms = (time.time() - _stream_start) * 1000
            combined = "".join(full_response)
            log.info(
                f"Step 3 STREAM completato | chunks={chunk_count}"
                f" response_len={len(combined)} first_chunk_ms={first_chunk_ms:.0f}"
                f" total_elapsed_ms={total_elapsed_ms:.0f}"
            )

            # STEP 4: Memory Save (background, dopo che la risposta e' stata inviata)
            import re as _re
            think_match = _re.findall(r'<think>(.*?)</think>', combined, _re.DOTALL)
            think_text = "\n".join(think_match) if think_match else ""
            visible_text = _re.sub(r'<think>.*?</think>', '', combined, flags=_re.DOTALL).strip()

            if visible_text:
                log.info(
                    f"Step 4 BACKGROUND Memory Save | user_len={len(user_text)}"
                    f" response_len={len(visible_text)} think_len={len(think_text)}"
                )
                threading.Thread(
                    target=_memory_agent.process_turn,
                    args=(user_text, think_text, visible_text),
                    daemon=True
                ).start()
            else:
                log.debug("Step 4 BACKGROUND Memory Save | visible_text vuota, skip")

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # ==========================================================
    # NON-STREAMING: Risposta completa in blocco unico
    # ==========================================================
    log.debug(f"Step 3 NON-STREAM | inoltro a Letta user_len={len(user_text)}")
    t_chat = time.time()
    try:
        chat_resp = await chat_letta(ChatRequest(message=user_text, stream=False))
        elapsed_chat = (time.time() - t_chat) * 1000
        log.info(f"Step 3 Letta risposta | response_len={len(chat_resp.response)} elapsed_ms={elapsed_chat:.0f}")
        log.debug(f"Risposta Letta (preview): {chat_resp.response[:200]!r}")
    except Exception as e:
        elapsed_chat = (time.time() - t_chat) * 1000
        log.error(f"Errore chiamata Letta non-stream | elapsed_ms={elapsed_chat:.0f} error={e} traceback={traceback.format_exc()}")
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
