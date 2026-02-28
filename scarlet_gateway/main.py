"""
Main FastAPI app for Scarlet Gateway.
Funge da hub (Heartbeat/API) e proxy OpenAI-compatibile.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scarlet_gateway.routes import pad, letta, openai

app = FastAPI(
    title="Scarlet Gateway (Lego Blocks API)",
    description="Microservizi atomici per il motore cognitivo e PAD subconscio.",
    version="1.0.0"
)

# CORS per eventuali interfacce web custom future
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montaggio Router (I Mattoncini) ---

# Layer 1: Atomic Endpoints (Lego Blocks)
app.include_router(pad.router, prefix="/api/pad", tags=["PAD Subconscio"])
app.include_router(letta.router, prefix="/api/letta", tags=["Letta Core"])

# Layer 2: Composite Proxy (OpenAI Drop-in)
app.include_router(openai.router, prefix="/v1", tags=["OpenAI Proxy"])

@app.get("/")
def health_check():
    return {"status": "ok", "agent": "Scarlet", "subconscious": "active"}

if __name__ == "__main__":
    import uvicorn
    # Avvia in locale sulla porta 8000
    uvicorn.run("scarlet_gateway.main:app", host="0.0.0.0", port=8000, reload=True)
