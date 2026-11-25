import os
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


class BaselineApiTests(unittest.TestCase):
    """Baseline regression tests for existing SupportAI v2 endpoints."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db = Path(self.temp_dir.name) / "test_supportai.db"
        self.original_db_path = app_module.DB_PATH
        app_module.DB_PATH = self.temp_db
        app_module.initialize_database()
        self.client = TestClient(app_module.app)

    def tearDown(self) -> None:
        app_module.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_health_and_root_endpoints(self) -> None:
        root_res = self.client.get("/")
        self.assertEqual(root_res.status_code, 200)
        self.assertEqual(root_res.json()["application"], "SupportAI")

        health_res = self.client.get("/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertTrue(health_res.json()["database"])

        ai_res = self.client.get("/ai-status")
        self.assertEqual(ai_res.status_code, 200)
        self.assertIn("configured", ai_res.json())
        self.assertIn("model", ai_res.json())

    def test_conversation_lifecycle_personal_and_support(self) -> None:
        create_res = self.client.post(
            "/conversations",
            json={"mode": "personal", "title": "Baseline Personal"},
        )
        self.assertEqual(create_res.status_code, 200)
        conv_id = create_res.json()["conversation_id"]

        list_res = self.client.get("/conversations", params={"mode": "personal"})
        self.assertEqual(list_res.status_code, 200)
        ids = [c["id"] for c in list_res.json()["conversations"]]
        self.assertIn(conv_id, ids)

        msg_res = self.client.get(f"/conversations/{conv_id}/messages")
        self.assertEqual(msg_res.status_code, 200)
        self.assertEqual(msg_res.json()["messages"], [])

        support_missing = self.client.get("/conversations", params={"mode": "support"})
        self.assertEqual(support_missing.status_code, 400)

        del_res = self.client.delete(f"/conversations/{conv_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["success"])

        after_del = self.client.get(f"/conversations/{conv_id}/messages")
        self.assertEqual(after_del.status_code, 404)

    def test_memories_endpoints(self) -> None:
        res = self.client.post(
            "/memories",
            json={
                "category": "preference",
                "content": "Uses Python and FastAPI",
                "scope": "personal",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        list_res = self.client.get("/memories", params={"scope": "personal"})
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()["memories"]), 1)

        bad_support = self.client.post(
            "/memories",
            json={"category": "faq", "content": "No customer", "scope": "support"},
        )
        self.assertEqual(bad_support.status_code, 400)

    def test_chat_endpoint_with_mocked_gemini(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "Mocked Gemini reply for baseline test."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch.object(
            app_module.genai, "Client", return_value=mock_client
        ):
            res = self.client.post(
                "/chat",
                json={"message": "Hello SupportAI", "mode": "personal"},
            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["reply"], "Mocked Gemini reply for baseline test.")

        conv_id = body["conversation_id"]
        msgs = self.client.get(f"/conversations/{conv_id}/messages").json()["messages"]
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_chat_failure_leaves_no_orphan_records(self) -> None:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Upstream error")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch.object(
            app_module.genai, "Client", return_value=mock_client
        ):
            res = self.client.post(
                "/chat",
                json={"message": "Will fail", "mode": "personal"},
            )

        self.assertEqual(res.status_code, 502)
        convs = self.client.get("/conversations", params={"mode": "personal"}).json()[
            "conversations"
        ]
        self.assertEqual(convs, [])


if __name__ == "__main__":
    unittest.main()
