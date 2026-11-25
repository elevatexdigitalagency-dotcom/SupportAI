import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import WorkspaceContext, get_workspace_context
from app.core.security import write_audit_log
from app.db.database import current_time, get_db

router = APIRouter(prefix="/billing", tags=["billing"])


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(min_length=2, max_length=32)


@router.get("/plans")
def list_plans():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM plans ORDER BY monthly_price_cents ASC"
        ).fetchall()
    plans = []
    for r in rows:
        item = dict(r)
        item["features"] = json.loads(item.pop("features_json", "[]"))
        plans.append(item)
    return {"plans": plans}


@router.get("/subscription")
def get_subscription(ctx: WorkspaceContext = Depends(get_workspace_context)):
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    with get_db() as db:
        sub = db.execute(
            """
            SELECT s.id, s.status, s.current_period_start, s.current_period_end,
                   p.code AS plan_code, p.name AS plan_name, p.monthly_price_cents,
                   p.monthly_message_limit, p.document_limit, p.chatbot_limit, p.features_json
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.workspace_id = ?
            LIMIT 1
            """,
            (ctx.workspace_id,),
        ).fetchone()

        if not sub:
            raise HTTPException(status_code=404, detail="Subscription record not found.")

        messages_used = db.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_records
            WHERE workspace_id = ? AND metric = 'ai_message' AND period_month = ?
            """,
            (ctx.workspace_id, month_key),
        ).fetchone()["total"]

        documents_used = db.execute(
            "SELECT COUNT(*) AS total FROM knowledge_sources WHERE workspace_id = ?",
            (ctx.workspace_id,),
        ).fetchone()["total"]

        chatbots_used = db.execute(
            "SELECT COUNT(*) AS total FROM chatbots WHERE workspace_id = ?",
            (ctx.workspace_id,),
        ).fetchone()["total"]

    sub_dict = dict(sub)
    sub_dict["features"] = json.loads(sub_dict.pop("features_json", "[]"))
    return {
        "subscription": sub_dict,
        "usage": {
            "period_month": month_key,
            "messages_used": int(messages_used),
            "documents_used": int(documents_used),
            "chatbots_used": int(chatbots_used),
        },
        "payment_provider_connected": False,
    }


@router.post("/change-plan")
def change_plan(
    payload: ChangePlanRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    if ctx.workspace_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only workspace owners or admins can change plans.",
        )

    code = payload.plan_code.strip().lower()
    now = datetime.now(timezone.utc)
    period_end = (now + timedelta(days=30)).isoformat()
    now_iso = now.isoformat()

    with get_db() as db:
        plan = db.execute(
            "SELECT * FROM plans WHERE code = ?",
            (code,),
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found.")

        existing = db.execute(
            "SELECT id FROM subscriptions WHERE workspace_id = ?",
            (ctx.workspace_id,),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE subscriptions
                SET plan_id = ?, status = 'active', current_period_start = ?, current_period_end = ?, updated_at = ?
                WHERE workspace_id = ?
                """,
                (plan["id"], now_iso, period_end, now_iso, ctx.workspace_id),
            )
        else:
            db.execute(
                """
                INSERT INTO subscriptions
                (workspace_id, plan_id, status, current_period_start, current_period_end, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?, ?, ?)
                """,
                (ctx.workspace_id, plan["id"], now_iso, period_end, now_iso, now_iso),
            )

        write_audit_log(
            db,
            action="billing.plan_changed",
            resource_type="subscription",
            resource_id=str(ctx.workspace_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
            details={"plan_code": code},
        )
        db.commit()

    return get_subscription(ctx)
