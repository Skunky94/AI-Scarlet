import os
import json
import time
import traceback
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from scarlet_observability import get_logger

router = APIRouter()
log     = get_logger("gateway.letta")   # Logica del route
log_api = get_logger("letta")           # Chiamate HTTP alla Letta API

# Leggono da env var (impostato in Docker) con fallback per uso locale
LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8283")
HEADERS = {
    "Authorization": f"Bearer {os.getenv('LETTA_API_KEY', 'scarlet_dev')}",
    "Content-Type": "application/json"
}

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    system_prefix: Optional[str] = None  # Contesto temporale/sistema da iniettare prima del messaggio utente

class ChatResponse(BaseModel):
    response: str
    raw_messages: list = []

def _get_agent_id() -> str:
    """Legge AGENT_ID da env var (Docker) o da file .agent_id (host)."""
    agent_id = os.getenv("AGENT_ID", "").strip()
    if agent_id:
        return agent_id
    try:
        with open(".agent_id", "r") as f:
            return f.read().strip()
    except Exception:
        raise HTTPException(status_code=500, detail="AGENT_ID non trovato (env var o file .agent_id)")

@router.post("/chat", response_model=ChatResponse)
async def chat_letta(req: ChatRequest):
    """
    Invia un messaggio all'agente Letta in chiaro. 
    L'utente deve aver gia alterato opzionalmente il PAD su /pad/update.
    """
    agent_id = _get_agent_id()
    url = f"{LETTA_URL}/v1/agents/{agent_id}/messages"

    # Costruisci lista messaggi con eventuale prefisso di sistema (es. contesto temporale)
    _msg_list = []
    if req.system_prefix:
        _msg_list.append({"role": "system", "content": req.system_prefix})
    _msg_list.append({"role": "user", "content": req.message})

    payload = {
        "messages": _msg_list,
        "stream": req.stream
    }

    log.debug(f"chat_letta | agent_id={agent_id} message_len={len(req.message)}")
    log.debug(f"chat_letta payload: {json.dumps(payload)[:400]}")

    # TODO: Implementare streaming SSE vero e proprio se stream=True
    if req.stream:
        # Per ora non supportato nativamente in questo metodo MVP
        log.warning("chat_letta | stream=True richiesto ma non implementato su questo path")
        raise HTTPException(status_code=501, detail="Streaming non ancora implementato.")

    t0 = time.time()
    try:
        log_api.debug(f"POST {url} | message_len={len(req.message)}")
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=120)
        elapsed_ms = (time.time() - t0) * 1000
        log_api.debug(f"Letta risposta | status={resp.status_code} elapsed_ms={elapsed_ms:.0f}")

        if resp.status_code != 200:
            log_api.error(
                f"Letta API error | status={resp.status_code}"
                f" body={resp.text[:300]!r} elapsed_ms={elapsed_ms:.0f}"
            )
            raise HTTPException(status_code=resp.status_code, detail=f"Errore Letta: {resp.text}")

        data = resp.json()
        messages = data.get("messages", [])
        log_api.debug(f"Letta response messages | count={len(messages)} types={[m.get('message_type') for m in messages]}")
        reply = ""

        # Estrarre la risposta
        for msg in messages:
            if msg.get("message_type") == "assistant_message":
                reply += msg.get("message", "") + msg.get("content", "") + "\n"

        if not reply:
            log.warning("chat_letta | nessun 'assistant_message' nella risposta Letta")
            reply = "[Nessuna risposta 'assistant_message' visibile in Letta]"
        else:
            log.info(f"chat_letta OK | reply_len={len(reply)} elapsed_ms={elapsed_ms:.0f}")

        return ChatResponse(response=reply.strip(), raw_messages=messages)

    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - t0) * 1000
        log_api.error(f"Connessione Letta fallita | url={url} elapsed_ms={elapsed_ms:.0f} error={e}")
        raise HTTPException(status_code=502, detail=f"Connessione a Letta fallita: {e}")


def stream_letta_sse(message: str, system_prefix: Optional[str] = None):
    """
    Generatore sincrono che chiama l'endpoint SSE di Letta (/messages/stream)
    e yield-a ogni linea SSE man mano che arriva.
    Ogni yield è un dict parsato dal JSON della linea 'data: {...}'.
    """
    agent_id = _get_agent_id()
    url = f"{LETTA_URL}/v1/agents/{agent_id}/messages/stream"

    # Costruisci lista messaggi con eventuale prefisso di sistema
    _sse_messages = []
    if system_prefix:
        _sse_messages.append({"role": "system", "content": system_prefix})
    _sse_messages.append({"role": "user", "content": message})

    payload = {
        "messages": _sse_messages,
        "stream_tokens": True
    }

    log.debug(f"stream_letta_sse | agent_id={agent_id} message_len={len(message)} url={url}")
    log_api.debug(f"SSE POST {url} | message_preview={message[:80]!r}")

    t0 = time.time()
    resp = requests.post(url, headers=HEADERS, json=payload, stream=True, timeout=120)
    if resp.status_code != 200:
        log_api.error(f"Letta SSE error | status={resp.status_code} body={resp.text[:300]!r}")
        raise HTTPException(status_code=resp.status_code, detail=f"Errore Letta stream: {resp.text}")

    log_api.debug(f"Letta SSE connessione aperta | status={resp.status_code}")
    event_count = 0

    for raw_line in resp.iter_lines():
        if raw_line:
            decoded = raw_line.decode('utf-8')
            if decoded.startswith('data: '):
                data_str = decoded[6:]
                if data_str == '[DONE]':
                    elapsed_ms = (time.time() - t0) * 1000
                    log.info(f"stream_letta_sse completato | events={event_count} elapsed_ms={elapsed_ms:.0f}")
                    yield {"type": "done"}
                    return
                try:
                    obj = json.loads(data_str)
                    msg_type = obj.get("message_type", "")
                    content = obj.get("content", "")
                    log_api.debug(
                        f"SSE event #{event_count} | type={msg_type}"
                        f" content_len={len(content)} preview={content[:50]!r}"
                    )
                    event_count += 1
                    yield obj
                except json.JSONDecodeError as e:
                    log_api.warning(f"SSE JSON parse error | raw={decoded[:200]!r} error={e}")
                    continue
