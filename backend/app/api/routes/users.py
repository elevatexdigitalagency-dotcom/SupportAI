from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import AuthenticatedUser, get_current_user
from app.core.security import hash_password, verify_password, write_audit_log
from app.db.database import current_time, get_db
from app.schemas.auth import ChangePasswordRequest, UserProfileUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_profile(user: AuthenticatedUser = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute(
            """
            SELECT id, email, full_name, role, is_active, email_verified, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user.id,),
        ).fetchone()
    return {"user": dict(row)}


@router.patch("/me")
def update_profile(
    payload: UserProfileUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    full_name = payload.full_name.strip()
    if len(full_name) < 2:
        raise HTTPException(
            status_code=422, detail="Full name must be at least 2 characters."
        )
    now = current_time()
    with get_db() as db:
        db.execute(
            "UPDATE users SET full_name = ?, updated_at = ? WHERE id = ?",
            (full_name, now, user.id),
        )
        write_audit_log(
            db,
            action="user.profile_updated",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
        )
        db.commit()
        row = db.execute(
            """
            SELECT id, email, full_name, role, email_verified, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user.id,),
        ).fetchone()

    return {"user": dict(row)}


@router.post("/me/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    with get_db() as db:
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user.id,),
        ).fetchone()
        if not row or not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(
                status_code=400, detail="Current password is incorrect."
            )
        try:
            new_hash = hash_password(payload.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, current_time(), user.id),
        )
        write_audit_log(
            db,
            action="user.password_changed",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
        )
        db.commit()

    return {"success": True}
