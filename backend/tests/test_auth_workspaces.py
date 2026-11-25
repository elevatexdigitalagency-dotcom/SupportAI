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
from app.core.security import generate_opaque_token, hash_token


class AuthAndWorkspaceTests(unittest.TestCase):
    """Tests for authentication, JWT tokens, user profiles, and workspace isolation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db = Path(self.temp_dir.name) / "test_auth.db"
        self.original_db_path = app_module.DB_PATH
        app_module.DB_PATH = self.temp_db
        app_module.initialize_database()
        self.client = TestClient(app_module.app)

    def tearDown(self) -> None:
        app_module.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _register(self, email: str, name: str, password: str = "StrongPass123!"):
        res = self.client.post(
            "/auth/register",
            json={"email": email, "full_name": name, "password": password},
        )
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_register_login_refresh_logout_and_profile(self) -> None:
        reg = self._register("alice@example.com", "Alice Smith")
        self.assertIn("access_token", reg)
        self.assertIn("refresh_token", reg)
        self.assertEqual(len(reg["workspaces"]), 1)

        # Duplicate email rejected
        dup = self.client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "full_name": "Alice Two",
                "password": "StrongPass123!",
            },
        )
        self.assertEqual(dup.status_code, 409)

        # Wrong password rejected
        bad_login = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "wrong"},
        )
        self.assertEqual(bad_login.status_code, 401)

        # Valid login
        login = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "StrongPass123!"},
        )
        self.assertEqual(login.status_code, 200)
        tokens = login.json()

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me_res = self.client.get("/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], "alice@example.com")

        # Update profile
        upd = self.client.patch(
            "/users/me",
            json={"full_name": "Alice Updated"},
            headers=headers,
        )
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(upd.json()["user"]["full_name"], "Alice Updated")

        # Refresh token rotation
        ref = self.client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(ref.status_code, 200)
        new_tokens = ref.json()

        # Reusing old refresh token fails
        reuse = self.client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(reuse.status_code, 401)

        # Logout revokes current refresh token
        out = self.client.post(
            "/auth/logout",
            json={"refresh_token": new_tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        )
        self.assertEqual(out.status_code, 200)

        after_out = self.client.post(
            "/auth/refresh",
            json={"refresh_token": new_tokens["refresh_token"]},
        )
        self.assertEqual(after_out.status_code, 401)

    def test_workspace_isolation_prevents_cross_user_access(self) -> None:
        alice = self._register("alice.iso@example.com", "Alice")
        bob = self._register("bob.iso@example.com", "Bob")

        alice_headers = {
            "Authorization": f"Bearer {alice['access_token']}",
            "X-Workspace-Id": str(alice["workspaces"][0]["id"]),
        }
        bob_headers = {
            "Authorization": f"Bearer {bob['access_token']}",
            "X-Workspace-Id": str(bob["workspaces"][0]["id"]),
        }

        mock_response = MagicMock()
        mock_response.text = "Private reply for Alice"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch.object(
            app_module.genai, "Client", return_value=mock_client
        ):
            chat_res = self.client.post(
                "/chat",
                json={"message": "Secret project note", "mode": "personal"},
                headers=alice_headers,
            )
        self.assertEqual(chat_res.status_code, 200)
        conv_id = chat_res.json()["conversation_id"]

        # Bob cannot read, chat in, or delete Alice's conversation
        self.assertEqual(
            self.client.get(
                f"/conversations/{conv_id}/messages", headers=bob_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(
                f"/conversations/{conv_id}", headers=bob_headers
            ).status_code,
            403,
        )
        # Unauthenticated request cannot access workspace-owned conversation
        self.assertEqual(
            self.client.get(f"/conversations/{conv_id}/messages").status_code,
            401,
        )
        # Bob cannot spoof Alice's workspace header
        self.assertEqual(
            self.client.get(
                "/conversations?mode=personal",
                headers={
                    "Authorization": f"Bearer {bob['access_token']}",
                    "X-Workspace-Id": str(alice["workspaces"][0]["id"]),
                },
            ).status_code,
            403,
        )

    def test_password_reset_and_workspace_members(self) -> None:
        alice = self._register("owner@example.com", "Owner User")
        bob = self._register("member@example.com", "Member User")

        alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}
        ws_id = alice["workspaces"][0]["id"]

        add_res = self.client.post(
            f"/workspaces/{ws_id}/members",
            json={"email": "member@example.com", "role": "member"},
            headers=alice_headers,
        )
        self.assertEqual(add_res.status_code, 201)

        members = self.client.get(
            f"/workspaces/{ws_id}/members", headers=alice_headers
        ).json()["members"]
        self.assertEqual(len(members), 2)

        # Verify password reset token flow
        raw_reset = generate_opaque_token()
        conn = sqlite3.connect(self.temp_db)
        conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used, created_at)
            VALUES (?, ?, '2099-01-01T00:00:00+00:00', 0, '2026-11-25T00:00:00+00:00')
            """,
            (bob["user"]["id"], hash_token(raw_reset)),
        )
        conn.commit()
        conn.close()

        reset_res = self.client.post(
            "/auth/reset-password",
            json={"token": raw_reset, "new_password": "NewPassword456!"},
        )
        self.assertEqual(reset_res.status_code, 200)

        new_login = self.client.post(
            "/auth/login",
            json={"email": "member@example.com", "password": "NewPassword456!"},
        )
        self.assertEqual(new_login.status_code, 200)


if __name__ == "__main__":
    unittest.main()
