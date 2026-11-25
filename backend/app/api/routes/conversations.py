from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.dependencies import (
    AuthenticatedUser,
    WorkspaceContext,
    get_current_user,
    get_optional_current_user,
    resolve_workspace_for_user,
)
from app.db.database import current_time, get_db
from app.schemas.chat import ConversationRequest, ConversationUpdateRequest

router = APIRouter()


def _authorize_conversation(
    db,
    conversation_id: int,
    user: Optional[AuthenticatedUser],
    x_workspace_id: Optional[int],
):
    conversation = db.execute(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv_workspace_id = conversation["workspace_id"]
    if conv_workspace_id is not None:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        ctx = resolve_workspace_for_user(user, conv_workspace_id)
        if x_workspace_id is not None and x_workspace_id != ctx.workspace_id:
            raise HTTPException(status_code=403, detail="Workspace mismatch.")
    elif user is not None:
        # Authenticated SaaS users must not read unowned legacy rows by guessing IDs.
        raise HTTPException(status_code=403, detail="Conversation access forbidden.")

    return conversation


@router.post("/conversations")
def create_conversation(
    request: ConversationRequest,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    workspace_id = None
    user_id = None
    if user is not None:
        ctx = resolve_workspace_for_user(user, x_workspace_id)
        workspace_id = ctx.workspace_id
        user_id = user.id

    now = current_time()
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO conversations
            (title, mode, customer_id, workspace_id, user_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                request.title,
                request.mode,
                request.customer_id,
                workspace_id,
                user_id,
                now,
                now,
            ),
        )
        conversation_id = cursor.lastrowid
        db.commit()

    return {
        "success": True,
        "conversation_id": conversation_id,
    }


@router.get("/conversations")
def list_conversations(
    mode: Literal["personal", "support", "all"] = "personal",
    customer_id: Optional[str] = None,
    status_filter: Literal["open", "archived", "all"] = Query(
        default="open", alias="status"
    ),
    search: Optional[str] = None,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        if user is not None:
            ctx = resolve_workspace_for_user(user, x_workspace_id)
            conditions = ["workspace_id = ?"]
            params: list = [ctx.workspace_id]

            if mode != "all":
                conditions.append("mode = ?")
                params.append(mode)

            if customer_id:
                conditions.append("customer_id = ?")
                params.append(customer_id)

            if status_filter != "all":
                conditions.append("status = ?")
                params.append(status_filter)

            if search and search.strip():
                conditions.append("LOWER(title) LIKE ?")
                params.append(f"%{search.strip().lower()}%")

            where_clause = " AND ".join(conditions)
            rows = db.execute(
                f"""
                SELECT * FROM conversations
                WHERE {where_clause}
                ORDER BY updated_at DESC
                """,
                tuple(params),
            ).fetchall()
        else:
            if mode == "personal":
                rows = db.execute(
                    """
                    SELECT * FROM conversations
                    WHERE workspace_id IS NULL AND mode = 'personal'
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
            elif mode == "support":
                if not customer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Customer ID is required.",
                    )
                rows = db.execute(
                    """
                    SELECT * FROM conversations
                    WHERE workspace_id IS NULL AND mode = 'support' AND customer_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (customer_id,),
                ).fetchall()
            else:
                raise HTTPException(status_code=401, detail="Authentication required.")

    return {"conversations": [dict(row) for row in rows]}


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        conversation = _authorize_conversation(db, conversation_id, user, x_workspace_id)
        rows = db.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

    return {
        "conversation": dict(conversation),
        "messages": [dict(row) for row in rows],
    }


@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        conversation = _authorize_conversation(db, conversation_id, user, x_workspace_id)
        updates = []
        params: list = []

        if payload.title is not None:
            updates.append("title = ?")
            params.append(payload.title.strip())
        if payload.status is not None:
            updates.append("status = ?")
            params.append(payload.status)
        if payload.assigned_to_user_id is not None:
            member = db.execute(
                "SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (conversation["workspace_id"], payload.assigned_to_user_id),
            ).fetchone()
            if not member:
                raise HTTPException(
                    status_code=400,
                    detail="Assigned user is not a member of this workspace.",
                )
            updates.append("assigned_to_user_id = ?")
            params.append(payload.assigned_to_user_id)

        if updates:
            updates.append("updated_at = ?")
            params.append(current_time())
            params.append(conversation_id)
            db.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            db.commit()

        updated = db.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

    return {"conversation": dict(updated)}


@router.post("/conversations/{conversation_id}/clear")
def clear_conversation_messages(
    conversation_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        _authorize_conversation(db, conversation_id, user, x_workspace_id)
        db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (current_time(), conversation_id),
        )
        db.commit()
    return {"success": True}


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        conversation = _authorize_conversation(db, conversation_id, user, x_workspace_id)
        messages = db.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()

    return {
        "conversation": dict(conversation),
        "messages": [dict(m) for m in messages],
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        _authorize_conversation(db, conversation_id, user, x_workspace_id)
        cursor = db.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )
        db.commit()

    return {"success": True}
