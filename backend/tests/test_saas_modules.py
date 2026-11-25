import gc
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as app_module
from app.core.config import settings
from app.services.knowledge_base.vector_store import release_chroma_clients


class SaasModulesTests(unittest.TestCase):
    """End-to-end integration tests for Knowledge Base, RAG, Chatbots, Widget, Analytics, Billing, and Admin."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.temp_db = root / "test_saas.db"
        self.temp_chroma = root / "chroma"
        self.temp_uploads = root / "uploads"

        self.orig_db = app_module.DB_PATH
        self.orig_chroma = settings.chroma_dir
        self.orig_uploads = settings.uploads_dir

        app_module.DB_PATH = self.temp_db
        settings.chroma_dir = self.temp_chroma
        settings.uploads_dir = self.temp_uploads
        app_module.initialize_database()
        self.client = TestClient(app_module.app)

    def tearDown(self) -> None:
        app_module.DB_PATH = self.orig_db
        settings.chroma_dir = self.orig_chroma
        settings.uploads_dir = self.orig_uploads
        release_chroma_clients()
        gc.collect()
        self.temp_dir.cleanup()

    def _register_user(self, email: str, name: str):
        res = self.client.post(
            "/auth/register",
            json={"email": email, "full_name": name, "password": "Password123!"},
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        return data, {
            "Authorization": f"Bearer {data['access_token']}",
            "X-Workspace-Id": str(data["workspaces"][0]["id"]),
        }

    def test_knowledge_upload_rag_chatbot_widget_analytics_billing_and_admin(self) -> None:
        user_data, headers = self._register_user("founder@acme.com", "Founder")

        # 1. Upload TXT knowledge source with mocked embeddings
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
            "app.services.knowledge_base.rag_service.generate_embeddings",
            return_value=[[0.1, 0.2, 0.3, 0.4]],
        ):
            up_res = self.client.post(
                "/knowledge/upload",
                files={
                    "file": (
                        "refund_policy.txt",
                        b"SupportAI refunds are issued within 14 days of purchase.",
                        "text/plain",
                    )
                },
                headers=headers,
            )
        self.assertEqual(up_res.status_code, 201, up_res.text)
        source_id = up_res.json()["source"]["id"]
        self.assertEqual(up_res.json()["source"]["status"], "indexed")

        # Reject invalid file extension
        bad_up = self.client.post(
            "/knowledge/upload",
            files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
            headers=headers,
        )
        self.assertEqual(bad_up.status_code, 400)

        # 2. Create chatbot and verify widget config + embed script + domain check + chat
        bot_res = self.client.post(
            "/chatbots",
            json={
                "name": "Acme Helper",
                "primary_color": "#2563eb",
                "welcome_message": "Welcome to Acme!",
                "allowed_domains": "acme.com",
            },
            headers=headers,
        )
        self.assertEqual(bot_res.status_code, 201, bot_res.text)
        bot = bot_res.json()["chatbot"]
        public_id = bot["public_id"]

        # Free plan chatbot limit is 1 -> second chatbot returns 429
        second_bot = self.client.post(
            "/chatbots",
            json={"name": "Second Bot"},
            headers=headers,
        )
        self.assertEqual(second_bot.status_code, 429)

        # Widget JS endpoint
        js_res = self.client.get("/widget.js")
        self.assertEqual(js_res.status_code, 200)
        self.assertIn("data-chatbot-id", js_res.text)

        # Disallowed origin blocked
        blocked_cfg = self.client.get(
            f"/widget/{public_id}/config",
            headers={"Origin": "https://evil.example.net"},
        )
        self.assertEqual(blocked_cfg.status_code, 403)

        # Allowed origin passes
        ok_cfg = self.client.get(
            f"/widget/{public_id}/config",
            headers={"Origin": "https://acme.com"},
        )
        self.assertEqual(ok_cfg.status_code, 200)
        self.assertEqual(ok_cfg.json()["name"], "Acme Helper")

        # Widget chat uses RAG + Gemini
        mock_reply = MagicMock()
        mock_reply.text = "Refunds are issued within 14 days of purchase."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_reply

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
            "app.services.knowledge_base.rag_service.generate_embeddings",
            return_value=[[0.1, 0.2, 0.3, 0.4]],
        ), patch.object(app_module.genai, "Client", return_value=mock_client):
            wchat = self.client.post(
                f"/widget/{public_id}/chat",
                json={"message": "What is your refund policy?", "session_id": "vis_12345"},
                headers={"Origin": "https://acme.com"},
            )
        self.assertEqual(wchat.status_code, 200, wchat.text)
        self.assertEqual(len(wchat.json()["sources"]), 1)

        # 3. Analytics reflect real database data
        analytics = self.client.get("/analytics/overview", headers=headers)
        self.assertEqual(analytics.status_code, 200)
        metrics = analytics.json()["metrics"]
        self.assertEqual(metrics["total_conversations"], 1)
        self.assertEqual(metrics["total_messages"], 2)
        self.assertEqual(metrics["active_chatbots"], 1)
        self.assertEqual(metrics["knowledge_sources"], 1)
        self.assertEqual(metrics["monthly_ai_usage"], 1)

        # 4. Billing subscription & upgrade to Pro
        sub = self.client.get("/billing/subscription", headers=headers)
        self.assertEqual(sub.status_code, 200)
        self.assertEqual(sub.json()["subscription"]["plan_code"], "free")
        self.assertFalse(sub.json()["payment_provider_connected"])

        upgrade = self.client.post(
            "/billing/change-plan",
            json={"plan_code": "pro"},
            headers=headers,
        )
        self.assertEqual(upgrade.status_code, 200)
        self.assertEqual(upgrade.json()["subscription"]["plan_code"], "pro")

        # 5. Admin protection: regular user gets 403, promoted admin gets 200
        self.assertEqual(
            self.client.get("/admin/stats", headers=headers).status_code,
            403,
        )
        conn = sqlite3.connect(self.temp_db)
        conn.execute(
            "UPDATE users SET role = 'admin' WHERE id = ?",
            (user_data["user"]["id"],),
        )
        conn.commit()
        conn.close()

        # Re-login to obtain admin JWT claim
        admin_login = self.client.post(
            "/auth/login",
            json={"email": "founder@acme.com", "password": "Password123!"},
        ).json()
        admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
        admin_stats = self.client.get("/admin/stats", headers=admin_headers)
        self.assertEqual(admin_stats.status_code, 200)
        self.assertEqual(admin_stats.json()["stats"]["users"], 1)

        # 6. Delete knowledge source cleans up cleanly
        del_src = self.client.delete(f"/knowledge/sources/{source_id}", headers=headers)
        self.assertEqual(del_src.status_code, 200)


if __name__ == "__main__":
    unittest.main()
