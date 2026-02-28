from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from scarlet_pad.subconscious import SubconsciousEvaluator
from scarlet_pad.core import PADCore
from scarlet_pad.letta_sync import LettaPADSync

router = APIRouter()

# Inizializzatori globali (per evitare overhead a ogni chiamata)
# Idealmente andrebbero iniettati come dependencies in un'app strutturata
evaluator = SubconsciousEvaluator()
sync = LettaPADSync()
core = PADCore()

class EvaluateRequest(BaseModel):
    text: str

class EvaluateResponse(BaseModel):
    dP: float
    dA: float
    dD: float
    reason: str

class UpdateRequest(BaseModel):
    dP: float
    dA: float
    dD: float
    event_reason: str

class UpdateResponse(BaseModel):
    success: bool
    new_mood: str
    p: float
    a: float
    d: float
    error: str = ""

@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_pad(req: EvaluateRequest):
    """Zero-side-effects endpoint per ricavare i delta PAD da un testo utente."""
    dp, da, dd, reason = evaluator.evaluate_input(req.text)
    return EvaluateResponse(dP=dp, dA=da, dD=dd, reason=reason)

@router.patch("/update", response_model=UpdateResponse)
async def update_pad(req: UpdateRequest):
    """Aggiorna il blocco emotional_state di Letta con decadimento e stimolo."""
    agent_id = sync.get_agent_id()
    if not agent_id:
        raise HTTPException(status_code=500, detail="Missing .agent_id")
    
    try:
        state, block_id = sync.read_current_state(agent_id)
        
        # 1. Decadimento
        state = core.apply_decay(state, decay_factor=0.05)
        # 2. Stimolo Asintotico
        new_state = core.apply_stimulus(state, req.dP, req.dA, req.dD)
        
        # 3. Aggiornamento in DB
        success = sync.update_state(agent_id, block_id, new_state, f"API Update: {req.event_reason}")
        
        mood = core.get_mood_description(new_state)
        
        return UpdateResponse(
            success=success,
            new_mood=mood,
            p=new_state.p,
            a=new_state.a,
            d=new_state.d,
            error="" if success else "Generico errore di sincronizzazione su Letta."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
