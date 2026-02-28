import time
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from scarlet_pad.subconscious import SubconsciousEvaluator
from scarlet_pad.core import PADCore
from scarlet_pad.letta_sync import LettaPADSync
from scarlet_observability import get_logger

router = APIRouter()
log = get_logger("gateway.pad")

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
    log.debug(f"/pad/evaluate | text_len={len(req.text)} preview={req.text[:60]!r}")
    t0 = time.time()
    dp, da, dd, reason = evaluator.evaluate_input(req.text)
    elapsed_ms = (time.time() - t0) * 1000
    log.info(f"/pad/evaluate OK | dP={dp:+.3f} dA={da:+.3f} dD={dd:+.3f} reason={reason!r} elapsed_ms={elapsed_ms:.1f}")
    return EvaluateResponse(dP=dp, dA=da, dD=dd, reason=reason)

@router.patch("/update", response_model=UpdateResponse)
async def update_pad(req: UpdateRequest):
    """Aggiorna il blocco emotional_state di Letta con decadimento e stimolo."""
    log.debug(f"/pad/update | dP={req.dP:+.3f} dA={req.dA:+.3f} dD={req.dD:+.3f} reason={req.event_reason!r}")
    agent_id = sync.get_agent_id()
    if not agent_id:
        log.error("/pad/update | AGENT_ID mancante")
        raise HTTPException(status_code=500, detail="Missing .agent_id")

    t0 = time.time()
    try:
        state, block_id = sync.read_current_state(agent_id)
        log.debug(f"/pad/update stato corrente | P={state.p:+.3f} A={state.a:+.3f} D={state.d:+.3f}")

        # 1. Decadimento
        state = core.apply_decay(state, decay_factor=0.05)
        log.debug(f"/pad/update post-decay | P={state.p:+.3f} A={state.a:+.3f} D={state.d:+.3f}")

        # 2. Stimolo Asintotico
        new_state = core.apply_stimulus(state, req.dP, req.dA, req.dD)
        log.debug(f"/pad/update post-stimulus | P={new_state.p:+.3f} A={new_state.a:+.3f} D={new_state.d:+.3f}")

        # 3. Aggiornamento in DB
        success = sync.update_state(agent_id, block_id, new_state, f"API Update: {req.event_reason}")

        mood = core.get_mood_description(new_state)
        elapsed_ms = (time.time() - t0) * 1000

        if success:
            log.info(f"/pad/update OK | P={new_state.p:+.3f} A={new_state.a:+.3f} D={new_state.d:+.3f} mood={mood!r} elapsed_ms={elapsed_ms:.0f}")
        else:
            log.warning(f"/pad/update | sync.update_state fallito | P={new_state.p:+.3f} elapsed_ms={elapsed_ms:.0f}")

        return UpdateResponse(
            success=success,
            new_mood=mood,
            p=new_state.p,
            a=new_state.a,
            d=new_state.d,
            error="" if success else "Generico errore di sincronizzazione su Letta."
        )
    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000
        log.error(f"/pad/update ERRORE | elapsed_ms={elapsed_ms:.0f} error={e} traceback={traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
