import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from app.core.config import settings

_current_db_path: Path = settings.db_path


def get_db_path() -> Path:
    return _current_db_path


def set_db_path(path: Path) -> None:
    global _current_db_path
    _current_db_path = Path(path)


def current_time() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    target = Path(db_path) if db_path is not None else _current_db_path
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
