from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_optional_current_user,
    resolve_workspace_for_user,
)
from app.db.database import current_time, get_db
from app.schemas.chat import MemoryRequest

router = APIRouter()


@router.post("/memories")
def save_memory(
    request: MemoryRequest,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    if request.scope == "support" and not request.customer_id:
        raise HTTPException(
            status_code=400,
            detail="Customer ID is required for support memories.",
        )

    workspace_id = None
    user_id = None
    if user is not None:
        ctx = resolve_workspace_for_user(user, x_workspace_id)
        workspace_id = ctx.workspace_id
        user_id = user.id

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO memories
            (category, content, scope, customer_id, workspace_id, user_id, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)
            """,
            (
                request.category,
                request.content,
                request.scope,
                request.customer_id,
                workspace_id,
                user_id,
                current_time(),
            ),
        )
        memory_id = cursor.lastrowid
        db.commit()

    return {
        "success": True,
        "memory_id": memory_id,
    }


@router.get("/memories")
def list_memories(
    scope: Literal["personal", "support"] = "personal",
    customer_id: Optional[str] = None,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    with get_db() as db:
        if user is not None:
            ctx = resolve_workspace_for_user(user, x_workspace_id)
            if scope == "personal":
                rows = db.execute(
                    """
                    SELECT * FROM memories
                    WHERE workspace_id = ? AND scope = 'personal'
                    ORDER BY id DESC
                    """,
                    (ctx.workspace_id,),
                ).fetchall()
            else:
                if not customer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Customer ID is required.",
                    )
                rows = db.execute(
                    """
                    SELECT * FROM memories
                    WHERE workspace_id = ? AND scope = 'support' AND customer_id = ?
                    ORDER BY id DESC
                    """,
                    (ctx.workspace_id, customer_id),
                ).fetchall()
        else:
            if scope == "personal":
                rows = db.execute(
                    """
                    SELECT * FROM memories
                    WHERE workspace_id IS NULL AND scope = 'personal'
                    ORDER BY id DESC
                    """
                ).fetchall()
            else:
                if not customer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Customer ID is required.",
                    )
                rows = db.execute(
                    """
                    SELECT * FROM memories
                    WHERE workspace_id IS NULL AND scope = 'support' AND customer_id = ?
                    ORDER BY id DESC
                    """,
                    (customer_id,),
                ).fetchall()

    return {"memories": [dict(row) for row in rows]}


@router.delete("/memories/{memory_id}")
def delete_memory(
    memory_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    ctx = resolve_workspace_for_user(user, x_workspace_id)
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM memories WHERE id = ? AND workspace_id = ?",
            (memory_id, ctx.workspace_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found.")
        db.commit()
    return {"success": True}
