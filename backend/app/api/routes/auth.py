import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.dependencies import AuthenticatedUser, get_current_user
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
    write_audit_log,
)
from app.db.database import current_time, get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.workspace_service import list_user_workspaces, provision_workspace

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address format.",
        )
    return cleaned


def _issue_session(
    db,
    user_row: Dict[str, Any],
) -> Dict[str, Any]:
    access_token = create_access_token(
        user_id=user_row["id"],
        email=user_row["email"],
        role=user_row["role"],
    )
    raw_refresh = generate_opaque_token()
    refresh_expires = (
        datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    ).isoformat()
    db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (user_row["id"], hash_token(raw_refresh), refresh_expires, current_time()),
    )
    workspaces = list_user_workspaces(db, user_row["id"])
    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {
            "id": user_row["id"],
            "email": user_row["email"],
            "full_name": user_row["full_name"],
            "role": user_row["role"],
            "email_verified": bool(user_row["email_verified"]),
        },
        "workspaces": workspaces,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    email = _normalize_email(payload.email)
    full_name = payload.full_name.strip()
    if len(full_name) < 2:
        raise HTTPException(
            status_code=422,
            detail="Full name must be at least 2 characters.",
        )

    try:
        pw_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    now = current_time()
    workspace_title = (
        payload.workspace_name.strip()
        if payload.workspace_name and payload.workspace_name.strip()
        else f"{full_name.split()[0]}'s Workspace"
    )

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        cursor = db.execute(
            """
            INSERT INTO users
            (email, full_name, password_hash, role, is_active, email_verified, created_at, updated_at)
            VALUES (?, ?, ?, 'user', 1, 0, ?, ?)
            """,
            (email, full_name, pw_hash, now, now),
        )
        user_id = cursor.lastrowid

        ws = provision_workspace(db, user_id, workspace_title)

        # Create email verification token for verification workflow
        verify_token = generate_opaque_token()
        verify_expires = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).isoformat()
        db.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, used, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (user_id, hash_token(verify_token), verify_expires, now),
        )

        user_row = dict(
            db.execute(
                "SELECT id, email, full_name, role, email_verified FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        )
        session = _issue_session(db, user_row)
        write_audit_log(
            db,
            action="auth.register",
            resource_type="user",
            resource_id=str(user_id),
            user_id=user_id,
            workspace_id=ws["id"],
            ip_address=request.client.host if request.client else None,
        )
        db.commit()

    return session


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    email = _normalize_email(payload.email)
    with get_db() as db:
        row = db.execute(
            """
            SELECT id, email, full_name, password_hash, role, is_active, email_verified
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not bool(row["is_active"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled.",
            )

        session = _issue_session(db, dict(row))
        write_audit_log(
            db,
            action="auth.login",
            resource_type="user",
            resource_id=str(row["id"]),
            user_id=row["id"],
            ip_address=request.client.host if request.client else None,
        )
        db.commit()

    return session


@router.post("/refresh")
def refresh_access_token(payload: RefreshTokenRequest):
    token_digest = hash_token(payload.refresh_token.strip())
    with get_db() as db:
        token_row = db.execute(
            """
            SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked,
                   u.email, u.full_name, u.role, u.is_active, u.email_verified
            FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token_hash = ?
            """,
            (token_digest,),
        ).fetchone()

        if not token_row or bool(token_row["revoked"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token.",
            )

        expires_at = datetime.fromisoformat(token_row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired.",
            )

        if not bool(token_row["is_active"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled.",
            )

        # Rotate refresh token
        db.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE id = ?",
            (token_row["id"],),
        )
        user_dict = {
            "id": token_row["user_id"],
            "email": token_row["email"],
            "full_name": token_row["full_name"],
            "role": token_row["role"],
            "email_verified": token_row["email_verified"],
        }
        session = _issue_session(db, user_dict)
        db.commit()

    return session


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    with get_db() as db:
        if payload.refresh_token:
            db.execute(
                """
                UPDATE refresh_tokens
                SET revoked = 1
                WHERE token_hash = ? AND user_id = ?
                """,
                (hash_token(payload.refresh_token.strip()), user.id),
            )
        else:
            db.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?",
                (user.id,),
            )
        write_audit_log(
            db,
            action="auth.logout",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
        )
        db.commit()

    return {"success": True}


@router.get("/me")
def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    with get_db() as db:
        workspaces = list_user_workspaces(db, user.id)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "email_verified": user.email_verified,
        },
        "workspaces": workspaces,
    }


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = _normalize_email(payload.email)
    with get_db() as db:
        user_row = db.execute(
            "SELECT id FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
        if user_row:
            raw_token = generate_opaque_token()
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat()
            db.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (user_row["id"], hash_token(raw_token), expires_at, current_time()),
            )
            write_audit_log(
                db,
                action="auth.password_reset_requested",
                resource_type="user",
                resource_id=str(user_row["id"]),
                user_id=user_row["id"],
            )
            db.commit()

    return {
        "success": True,
        "message": "If an account exists for that email, password reset instructions have been generated.",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    digest = hash_token(payload.token.strip())
    with get_db() as db:
        row = db.execute(
            """
            SELECT id, user_id, expires_at, used
            FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (digest,),
        ).fetchone()
        if not row or bool(row["used"]):
            raise HTTPException(status_code=400, detail="Invalid or used reset token.")
        if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
            raise HTTPException(status_code=400, detail="Reset token has expired.")

        now = current_time()
        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, now, row["user_id"]),
        )
        db.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
            (row["id"],),
        )
        db.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?",
            (row["user_id"],),
        )
        write_audit_log(
            db,
            action="auth.password_reset_completed",
            resource_type="user",
            resource_id=str(row["user_id"]),
            user_id=row["user_id"],
        )
        db.commit()

    return {"success": True, "message": "Password has been reset successfully."}


@router.post("/request-verification")
def request_email_verification(user: AuthenticatedUser = Depends(get_current_user)):
    if user.email_verified:
        return {"success": True, "message": "Email is already verified."}

    raw_token = generate_opaque_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, used, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (user.id, hash_token(raw_token), expires_at, current_time()),
        )
        db.commit()

    return {"success": True, "message": "Verification token generated."}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest):
    digest = hash_token(payload.token.strip())
    with get_db() as db:
        row = db.execute(
            """
            SELECT id, user_id, expires_at, used
            FROM email_verification_tokens
            WHERE token_hash = ?
            """,
            (digest,),
        ).fetchone()
        if not row or bool(row["used"]):
            raise HTTPException(
                status_code=400, detail="Invalid or used verification token."
            )
        if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
            raise HTTPException(
                status_code=400, detail="Verification token has expired."
            )

        now = current_time()
        db.execute(
            "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
            (now, row["user_id"]),
        )
        db.execute(
            "UPDATE email_verification_tokens SET used = 1 WHERE id = ?",
            (row["id"],),
        )
        write_audit_log(
            db,
            action="auth.email_verified",
            resource_type="user",
            resource_id=str(row["user_id"]),
            user_id=row["user_id"],
        )
        db.commit()

    return {"success": True, "message": "Email verified successfully."}
