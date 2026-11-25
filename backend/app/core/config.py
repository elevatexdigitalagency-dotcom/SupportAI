import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)


def _load_or_create_jwt_secret(base_dir: Path) -> str:
    env_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if env_secret:
        return env_secret

    secret_file = base_dir / ".jwt_secret"
    if secret_file.exists():
        existing = secret_file.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    generated = secrets.token_hex(48)
    secret_file.write_text(generated, encoding="utf-8")
    return generated


def _parse_cors_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@dataclass
class Settings:
    app_name: str = "SupportAI"
    app_description: str = "Personal AI and Customer Support SaaS Platform"
    app_version: str = "2.0.0"

    base_dir: Path = BACKEND_DIR
    db_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("SUPPORTAI_DB_PATH", str(BACKEND_DIR / "supportai.db"))
        )
    )
    chroma_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CHROMA_DIR", str(BACKEND_DIR / "data" / "chroma"))
        )
    )
    uploads_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("UPLOADS_DIR", str(BACKEND_DIR / "uploads"))
        )
    )

    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    )
    gemini_embedding_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )

    jwt_secret_key: str = field(
        default_factory=lambda: _load_or_create_jwt_secret(BACKEND_DIR)
    )
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: List[str] = field(default_factory=_parse_cors_origins)

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "").strip()


settings = Settings()
