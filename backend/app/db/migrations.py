import json
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.db.database import current_time, get_db, get_db_path


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(row["name"] == column for row in rows)


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')


def _migration_001_up(conn: sqlite3.Connection) -> None:
    """Ensure baseline legacy tables exist without altering existing rows."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            mode TEXT NOT NULL,
            customer_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'personal',
            customer_id TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL
        )
    """)


def _migration_001_down(conn: sqlite3.Connection) -> None:
    # Legacy baseline tables are never dropped automatically to protect user data.
    pass


def _migration_002_up(conn: sqlite3.Connection) -> None:
    """Add SaaS multi-tenant, knowledge base, chatbot, billing, and audit tables."""
    now = current_time()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            email_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            owner_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(owner_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'owner',
            created_at TEXT NOT NULL,
            UNIQUE(workspace_id, user_id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            monthly_price_cents INTEGER NOT NULL DEFAULT 0,
            monthly_message_limit INTEGER NOT NULL,
            document_limit INTEGER NOT NULL,
            chatbot_limit INTEGER NOT NULL,
            features_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL UNIQUE,
            plan_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            current_period_start TEXT NOT NULL,
            current_period_end TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(plan_id) REFERENCES plans(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            period_month TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            collection_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            knowledge_base_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            source_uri TEXT,
            file_path TEXT,
            content_hash TEXT,
            file_size_bytes INTEGER NOT NULL DEFAULT 0,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            knowledge_source_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chroma_id TEXT NOT NULL UNIQUE,
            content_preview TEXT NOT NULL,
            token_estimate INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(knowledge_source_id) REFERENCES knowledge_sources(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chatbots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            public_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            knowledge_base_id INTEGER,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            allowed_domains TEXT NOT NULL DEFAULT '*',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chatbot_id INTEGER NOT NULL UNIQUE,
            primary_color TEXT NOT NULL DEFAULT '#2563eb',
            logo_url TEXT,
            welcome_message TEXT NOT NULL DEFAULT 'Hello! How can I help you today?',
            system_instructions TEXT NOT NULL DEFAULT 'You are a helpful AI customer support assistant.',
            fallback_message TEXT NOT NULL DEFAULT 'I could not find an answer in our documentation. Please contact support.',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(chatbot_id) REFERENCES chatbots(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Non-destructive column additions on existing tables
    _add_column_if_missing(conn, "conversations", "workspace_id", "INTEGER")
    _add_column_if_missing(conn, "conversations", "user_id", "INTEGER")
    _add_column_if_missing(conn, "conversations", "chatbot_id", "INTEGER")
    _add_column_if_missing(
        conn, "conversations", "status", "TEXT NOT NULL DEFAULT 'open'"
    )
    _add_column_if_missing(conn, "conversations", "assigned_to_user_id", "INTEGER")

    _add_column_if_missing(conn, "messages", "sources_json", "TEXT")
    _add_column_if_missing(conn, "messages", "tokens_used", "INTEGER NOT NULL DEFAULT 0")

    _add_column_if_missing(conn, "memories", "workspace_id", "INTEGER")
    _add_column_if_missing(conn, "memories", "user_id", "INTEGER")

    # Helpful indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id, mode, updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories(workspace_id, scope)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_sources_ws ON knowledge_sources(workspace_id, knowledge_base_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_records_ws_month ON usage_records(workspace_id, period_month, metric)"
    )

    # Seed default SaaS plans if missing
    default_plans = [
        (
            "free",
            "Free",
            0,
            100,
            5,
            1,
            json.dumps(
                [
                    "100 AI messages / month",
                    "5 knowledge sources",
                    "1 website chatbot",
                    "Personal & Support AI playground",
                ]
            ),
            now,
        ),
        (
            "pro",
            "Pro",
            2900,
            2500,
            50,
            5,
            json.dumps(
                [
                    "2,500 AI messages / month",
                    "50 knowledge sources",
                    "5 website chatbots",
                    "Website crawling & RAG citations",
                ]
            ),
            now,
        ),
        (
            "business",
            "Business",
            9900,
            15000,
            500,
            25,
            json.dumps(
                [
                    "15,000 AI messages / month",
                    "500 knowledge sources",
                    "25 website chatbots",
                    "Team members & audit logs",
                ]
            ),
            now,
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO plans
        (code, name, monthly_price_cents, monthly_message_limit, document_limit, chatbot_limit, features_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        default_plans,
    )


def _migration_002_down(conn: sqlite3.Connection) -> None:
    """Safely drop newly introduced SaaS tables while preserving legacy tables."""
    for table in [
        "audit_logs",
        "integrations",
        "chatbot_settings",
        "chatbots",
        "document_chunks",
        "knowledge_sources",
        "knowledge_bases",
        "usage_records",
        "subscriptions",
        "plans",
        "email_verification_tokens",
        "password_reset_tokens",
        "refresh_tokens",
        "workspace_members",
        "workspaces",
        "users",
    ]:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')


MIGRATIONS: List[
    Tuple[int, str, Callable[[sqlite3.Connection], None], Callable[[sqlite3.Connection], None]]
] = [
    (1, "001_initial_legacy_tables", _migration_001_up, _migration_001_down),
    (2, "002_saas_core_tables", _migration_002_up, _migration_002_down),
]


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)


def get_applied_versions(db_path: Optional[Path] = None) -> List[int]:
    with get_db(db_path) as conn:
        _ensure_migrations_table(conn)
        rows = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        return [int(row["version"]) for row in rows]


def run_migrations(
    db_path: Optional[Path] = None,
    target_version: Optional[int] = None,
) -> List[str]:
    target_db = db_path if db_path is not None else get_db_path()
    applied_names: List[str] = []

    with get_db(target_db) as conn:
        _ensure_migrations_table(conn)
        existing = {
            int(row["version"])
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for version, name, up_fn, _ in MIGRATIONS:
            if target_version is not None and version > target_version:
                continue
            if version in existing:
                continue
            up_fn(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, current_time()),
            )
            applied_names.append(name)

        conn.commit()

    return applied_names


def rollback_migration(
    target_version: int,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Roll back migrations strictly greater than target_version."""
    target_db = db_path if db_path is not None else get_db_path()
    rolled_back: List[str] = []

    with get_db(target_db) as conn:
        _ensure_migrations_table(conn)
        applied = {
            int(row["version"])
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for version, name, _, down_fn in reversed(MIGRATIONS):
            if version <= target_version or version not in applied:
                continue
            down_fn(conn)
            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (version,),
            )
            rolled_back.append(name)

        conn.commit()

    return rolled_back
