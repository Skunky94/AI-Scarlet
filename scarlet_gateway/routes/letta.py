import json
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

LETTA_URL = "http://localhost:8283"
HEADERS = {"Authorization": "Bearer scarlet_dev", "Content-Type": "application/json"}

class ChatRequest(BaseModel):
    message: str
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    raw_messages: list = []

def _get_agent_id() -> str:
    try:
        with open(".agent_id", "r") as f:
            return f.read().strip()
    except Exception:
        raise HTTPException(status_code=500, detail="Impossibile trovare file .agent_id")

@router.post("/chat", response_model=ChatResponse)
async def chat_letta(req: ChatRequest):
    """
    Invia un messaggio all'agente Letta in chiaro. 
    L'utente deve aver gia alterato opzionalmente il PAD su /pad/update.
    """
    agent_id = _get_agent_id()
    url = f"{LETTA_URL}/v1/agents/{agent_id}/messages"
    
    # Payload per l'API di Letta
    payload = {
        "messages": [
            {
                "role": "user",
                "content": req.message
            }
        ],
        "stream": req.stream
    }
    
    # TODO: Implementare streaming SSE vero e proprio se stream=True
    if req.stream:
        # Per ora non supportato nativamente in questo metodo MVP
        raise HTTPException(status_code=501, detail="Streaming non ancora implementato.")
        
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=120)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Errore Letta: {resp.text}")
            
        data = resp.json()
        messages = data.get("messages", [])
        reply = ""
        
        # Estrarre la risposta
        for msg in messages:
            if msg.get("message_type") == "assistant_message":
                reply += msg.get("message", "") + msg.get("content", "") + "\n"
                
        if not reply:
            reply = "[Nessuna risposta 'assistant_message' visibile in Letta]"
            
        return ChatResponse(response=reply.strip(), raw_messages=messages)
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Connessione a Letta fallita: {e}")


def stream_letta_sse(message: str):
    """
    Generatore sincrono che chiama l'endpoint SSE di Letta (/messages/stream)
    e yield-a ogni linea SSE man mano che arriva.
    Ogni yield è un dict parsato dal JSON della linea 'data: {...}'.
    """
    agent_id = _get_agent_id()
    url = f"{LETTA_URL}/v1/agents/{agent_id}/messages/stream"
    
    payload = {
        "messages": [{"role": "user", "content": message}],
        "stream_tokens": True
    }
    
    resp = requests.post(url, headers=HEADERS, json=payload, stream=True, timeout=120)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Errore Letta stream: {resp.text}")
    
    for raw_line in resp.iter_lines():
        if raw_line:
            decoded = raw_line.decode('utf-8')
            if decoded.startswith('data: '):
                data_str = decoded[6:]
                if data_str == '[DONE]':
                    yield {"type": "done"}
                    return
                try:
                    obj = json.loads(data_str)
                    yield obj
                except json.JSONDecodeError:
                    continue
