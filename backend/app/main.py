from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TruthLens API",
    description="AI-Powered Fake News Detection & Fact-Checking Assistant",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to FRONTEND_URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routers import auth, analysis

app.include_router(auth.router)
app.include_router(analysis.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to TruthLens API"}
