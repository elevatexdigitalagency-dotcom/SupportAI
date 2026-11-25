from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.security import decode_access_token
from app.db.database import get_db


@dataclass
class AuthenticatedUser:
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    email_verified: bool


@dataclass
class WorkspaceContext:
    user: AuthenticatedUser
    workspace_id: int
    workspace_name: str
    workspace_role: str


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format.",
        )
    return parts[1].strip()


def get_optional_current_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[AuthenticatedUser]:
    token = _extract_bearer_token(authorization)
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc

    with get_db() as db:
        row = db.execute(
            """
            SELECT id, email, full_name, role, is_active, email_verified
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if not row or not bool(row["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or no longer exists.",
        )

    return AuthenticatedUser(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        email_verified=bool(row["email_verified"]),
    )


def get_current_user(
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
) -> AuthenticatedUser:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def require_admin_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


def resolve_workspace_for_user(
    user: AuthenticatedUser,
    requested_workspace_id: Optional[int],
) -> WorkspaceContext:
    with get_db() as db:
        if requested_workspace_id is not None:
            row = db.execute(
                """
                SELECT w.id AS workspace_id, w.name AS workspace_name, wm.role AS workspace_role
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE wm.user_id = ? AND wm.workspace_id = ?
                """,
                (user.id, requested_workspace_id),
            ).fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access to the requested workspace is forbidden.",
                )
        else:
            row = db.execute(
                """
                SELECT w.id AS workspace_id, w.name AS workspace_name, wm.role AS workspace_role
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE wm.user_id = ?
                ORDER BY wm.id ASC
                LIMIT 1
                """,
                (user.id,),
            ).fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No workspace found for user.",
                )

    return WorkspaceContext(
        user=user,
        workspace_id=row["workspace_id"],
        workspace_name=row["workspace_name"],
        workspace_role=row["workspace_role"],
    )


def get_workspace_context(
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
) -> WorkspaceContext:
    return resolve_workspace_for_user(user, x_workspace_id)
