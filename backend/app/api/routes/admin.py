from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import AuthenticatedUser, require_admin_user
from app.core.security import write_audit_log
from app.db.database import current_time, get_db, get_db_path

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[Literal["user", "admin"]] = None


@router.get("/stats")
def platform_stats(_: AuthenticatedUser = Depends(require_admin_user)):
    with get_db() as db:
        stats = {
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "workspaces": db.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0],
            "chatbots": db.execute("SELECT COUNT(*) FROM chatbots").fetchone()[0],
            "conversations": db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
            "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "knowledge_sources": db.execute(
                "SELECT COUNT(*) FROM knowledge_sources"
            ).fetchone()[0],
            "active_subscriptions": db.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE status = 'active'"
            ).fetchone()[0],
        }
    return {
        "stats": stats,
        "system": {
            "database_exists": get_db_path().exists(),
            "status": "healthy",
        },
    }


@router.get("/users")
def list_all_users(_: AuthenticatedUser = Depends(require_admin_user)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, email, full_name, role, is_active, email_verified, created_at, updated_at
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()
    return {"users": [dict(r) for r in rows]}


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    admin_user: AuthenticatedUser = Depends(require_admin_user),
):
    if user_id == admin_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself.")

    with get_db() as db:
        target = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")

        updates = []
        params: list = []
        if payload.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if payload.is_active else 0)
        if payload.role is not None:
            updates.append("role = ?")
            params.append(payload.role)

        if updates:
            updates.append("updated_at = ?")
            params.extend([current_time(), user_id])
            db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            write_audit_log(
                db,
                action="admin.user_updated",
                resource_type="user",
                resource_id=str(user_id),
                user_id=admin_user.id,
                details={
                    "is_active": payload.is_active,
                    "role": payload.role,
                },
            )
            db.commit()

        row = db.execute(
            "SELECT id, email, full_name, role, is_active, email_verified, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return {"user": dict(row)}


@router.get("/workspaces")
def list_all_workspaces(_: AuthenticatedUser = Depends(require_admin_user)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT w.*, u.email AS owner_email, p.name AS plan_name,
                   (SELECT COUNT(*) FROM workspace_members wm WHERE wm.workspace_id = w.id) AS member_count,
                   (SELECT COUNT(*) FROM chatbots c WHERE c.workspace_id = w.id) AS chatbot_count
            FROM workspaces w
            JOIN users u ON u.id = w.owner_user_id
            LEFT JOIN subscriptions s ON s.workspace_id = w.id
            LEFT JOIN plans p ON p.id = s.plan_id
            ORDER BY w.id DESC
            """
        ).fetchall()
    return {"workspaces": [dict(r) for r in rows]}


@router.get("/chatbots")
def list_all_chatbots(_: AuthenticatedUser = Depends(require_admin_user)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT c.id, c.public_id, c.name, c.is_enabled, c.allowed_domains, c.created_at,
                   w.name AS workspace_name
            FROM chatbots c
            JOIN workspaces w ON w.id = c.workspace_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return {"chatbots": [dict(r) for r in rows]}


@router.get("/audit-logs")
def list_audit_logs(_: AuthenticatedUser = Depends(require_admin_user)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT al.*, u.email AS actor_email
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.user_id
            ORDER BY al.id DESC
            LIMIT 100
            """
        ).fetchall()
    return {"audit_logs": [dict(r) for r in rows]}
