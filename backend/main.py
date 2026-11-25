from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from app.api.routes import (
    admin,
    analytics,
    auth,
    billing,
    chat,
    chatbots,
    conversations,
    health,
    knowledge,
    memories,
    users,
    workspaces,
)
from app.core.config import settings
from app.db.database import get_db, set_db_path
from app.db.migrations import run_migrations

BASE_DIR = settings.base_dir
DB_PATH = settings.db_path
MODEL = settings.gemini_model


def initialize_database():
    set_db_path(DB_PATH)
    run_migrations(DB_PATH)


initialize_database()

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(workspaces.router)
app.include_router(conversations.router)
app.include_router(memories.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(chatbots.router)
app.include_router(analytics.router)
app.include_router(billing.router)
app.include_router(admin.router)

__all__ = ["app", "DB_PATH", "MODEL", "genai", "get_db", "initialize_database"]
