import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.migrations import (
    get_applied_versions,
    rollback_migration,
    run_migrations,
)


class MigrationTests(unittest.TestCase):
    """Tests for versioned, reversible SQLite migrations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "migration_test.db"

        # Seed a legacy v2 database before any migration table exists
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                mode TEXT NOT NULL,
                customer_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE messages (
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
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'personal',
                customer_id TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            """
            INSERT INTO conversations (title, mode, customer_id, created_at, updated_at)
            VALUES ('Legacy chat', 'personal', NULL, '2026-11-25T00:00:00Z', '2026-11-25T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (1, 'user', 'Preserved message', '2026-11-25T00:00:00Z')
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_upgrade_and_rollback_preserves_legacy_data(self) -> None:
        applied = run_migrations(self.db_path)
        self.assertEqual(
            applied,
            ["001_initial_legacy_tables", "002_saas_core_tables"],
        )
        self.assertEqual(get_applied_versions(self.db_path), [1, 2])

        # Idempotent re-run
        second_run = run_migrations(self.db_path)
        self.assertEqual(second_run, [])

        conn = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for expected in (
                "users",
                "workspaces",
                "workspace_members",
                "plans",
                "subscriptions",
                "usage_records",
                "knowledge_bases",
                "knowledge_sources",
                "document_chunks",
                "chatbots",
                "chatbot_settings",
                "integrations",
                "audit_logs",
                "refresh_tokens",
                "password_reset_tokens",
                "email_verification_tokens",
            ):
                self.assertIn(expected, tables)

            plan_codes = {
                row[0] for row in conn.execute("SELECT code FROM plans").fetchall()
            }
            self.assertEqual(plan_codes, {"free", "pro", "business"})

            conv_cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info('conversations')").fetchall()
            }
            self.assertIn("workspace_id", conv_cols)
            self.assertIn("user_id", conv_cols)
            self.assertIn("status", conv_cols)

            msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            self.assertEqual(msg_count, 1)
        finally:
            conn.close()

        # Rollback migration 002
        rolled_back = rollback_migration(target_version=1, db_path=self.db_path)
        self.assertEqual(rolled_back, ["002_saas_core_tables"])
        self.assertEqual(get_applied_versions(self.db_path), [1])

        conn = sqlite3.connect(self.db_path)
        try:
            tables_after = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertNotIn("users", tables_after)
            self.assertIn("conversations", tables_after)
            self.assertIn("messages", tables_after)
            msg_content = conn.execute("SELECT content FROM messages WHERE id = 1").fetchone()[0]
            self.assertEqual(msg_content, "Preserved message")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
