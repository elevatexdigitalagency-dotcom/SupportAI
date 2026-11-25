from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    AuthenticatedUser,
    get_current_user,
    resolve_workspace_for_user,
)
from app.core.security import write_audit_log
from app.db.database import current_time, get_db
from app.schemas.auth import (
    WorkspaceCreateRequest,
    WorkspaceMemberAddRequest,
    WorkspaceUpdateRequest,
)
from app.services.workspace_service import list_user_workspaces, provision_workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
def list_workspaces(user: AuthenticatedUser = Depends(get_current_user)):
    with get_db() as db:
        workspaces = list_user_workspaces(db, user.id)
    return {"workspaces": workspaces}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(
            status_code=422, detail="Workspace name must be at least 2 characters."
        )

    with get_db() as db:
        ws = provision_workspace(db, user.id, name)
        write_audit_log(
            db,
            action="workspace.created",
            resource_type="workspace",
            resource_id=str(ws["id"]),
            user_id=user.id,
            workspace_id=ws["id"],
        )
        db.commit()

    return {"workspace": ws}


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ctx = resolve_workspace_for_user(user, workspace_id)
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, slug, owner_user_id, created_at, updated_at FROM workspaces WHERE id = ?",
            (ctx.workspace_id,),
        ).fetchone()
    return {"workspace": {**dict(row), "role": ctx.workspace_role}}


@router.patch("/{workspace_id}")
def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ctx = resolve_workspace_for_user(user, workspace_id)
    if ctx.workspace_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Only workspace owners or admins can update settings."
        )
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Workspace name too short.")

    with get_db() as db:
        db.execute(
            "UPDATE workspaces SET name = ?, updated_at = ? WHERE id = ?",
            (name, current_time(), ctx.workspace_id),
        )
        write_audit_log(
            db,
            action="workspace.updated",
            resource_type="workspace",
            resource_id=str(ctx.workspace_id),
            user_id=user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
        row = db.execute(
            "SELECT id, name, slug, owner_user_id, created_at, updated_at FROM workspaces WHERE id = ?",
            (ctx.workspace_id,),
        ).fetchone()
    return {"workspace": {**dict(row), "role": ctx.workspace_role}}


@router.get("/{workspace_id}/members")
def list_workspace_members(
    workspace_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ctx = resolve_workspace_for_user(user, workspace_id)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT u.id AS user_id, u.email, u.full_name, wm.role, wm.created_at
            FROM workspace_members wm
            JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = ?
            ORDER BY wm.id ASC
            """,
            (ctx.workspace_id,),
        ).fetchall()
    return {"members": [dict(r) for r in rows]}


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
def add_workspace_member(
    workspace_id: int,
    payload: WorkspaceMemberAddRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ctx = resolve_workspace_for_user(user, workspace_id)
    if ctx.workspace_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Only workspace owners or admins can invite members."
        )

    email = payload.email.strip().lower()
    with get_db() as db:
        target = db.execute(
            "SELECT id, email, full_name FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
        if not target:
            raise HTTPException(
                status_code=404,
                detail="No active user account found with that email.",
            )

        existing = db.execute(
            "SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (ctx.workspace_id, target["id"]),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="User is already a member of this workspace.",
            )

        now = current_time()
        db.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (ctx.workspace_id, target["id"], payload.role, now),
        )
        write_audit_log(
            db,
            action="workspace.member_added",
            resource_type="workspace_member",
            resource_id=str(target["id"]),
            user_id=user.id,
            workspace_id=ctx.workspace_id,
            details={"member_email": email, "role": payload.role},
        )
        db.commit()

    return {
        "member": {
            "user_id": target["id"],
            "email": target["email"],
            "full_name": target["full_name"],
            "role": payload.role,
        }
    }


@router.delete("/{workspace_id}/members/{member_user_id}")
def remove_workspace_member(
    workspace_id: int,
    member_user_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ctx = resolve_workspace_for_user(user, workspace_id)
    if ctx.workspace_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Only workspace owners or admins can remove members."
        )

    with get_db() as db:
        ws = db.execute(
            "SELECT owner_user_id FROM workspaces WHERE id = ?",
            (ctx.workspace_id,),
        ).fetchone()
        if ws and ws["owner_user_id"] == member_user_id:
            raise HTTPException(
                status_code=400, detail="Cannot remove the workspace owner."
            )

        cursor = db.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (ctx.workspace_id, member_user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Member not found.")
        write_audit_log(
            db,
            action="workspace.member_removed",
            resource_type="workspace_member",
            resource_id=str(member_user_id),
            user_id=user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()

    return {"success": True}
