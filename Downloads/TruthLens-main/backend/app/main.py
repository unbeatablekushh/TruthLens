from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
import app.models.auth
import app.models.analysis

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not auto-create tables: {e}")
    yield

app = FastAPI(
    title="TruthLens API",
    description="AI-Powered Fake News Detection & Fact-Checking Assistant",
    version="1.0.0",
    lifespan=lifespan,
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
