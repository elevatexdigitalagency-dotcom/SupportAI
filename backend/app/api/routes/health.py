import os

from fastapi import APIRouter

from app.core.config import settings
from app.db.database import get_db_path

router = APIRouter()


@router.get("/")
def home():
    return {
        "application": settings.app_name,
        "status": "running",
        "version": settings.app_version,
    }


@router.get("/health")
def health():
    return {
        "status": "healthy",
        "database": get_db_path().exists(),
        "application": settings.app_name,
    }


@router.get("/ai-status")
def ai_status():
    return {
        "configured": bool(os.getenv("GEMINI_API_KEY")),
        "model": os.getenv("GEMINI_MODEL", settings.gemini_model),
    }
