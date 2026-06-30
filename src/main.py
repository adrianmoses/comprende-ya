import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chunks, profile, videos
from config import settings

load_dotenv()

app = FastAPI(
    title="ComprendeYa API",
    description="API para generar ejercicios de comprensión de Español",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(chunks.router)
app.include_router(profile.router)


@app.get("/")
async def root():
    return {"message": "Bienvenido a ComprendeYa API"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "database_configured": bool(os.getenv("DATABASE_URL")),
    }
