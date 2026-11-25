from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import WorkspaceContext, get_workspace_context
from app.core.security import write_audit_log
from app.db.database import current_time, get_db

router = APIRouter(tags=["analytics"])


class IntegrationCreateRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    config: dict = Field(default_factory=dict)


@router.get("/analytics/overview")
def analytics_overview(
    days: int = Query(default=30, ge=1, le=365),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    with get_db() as db:
        total_conversations = db.execute(
            "SELECT COUNT(*) AS c FROM conversations WHERE workspace_id = ?",
            (ctx.workspace_id,),
        ).fetchone()["c"]

        total_messages = db.execute(
            """
            SELECT COUNT(*) AS c
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.workspace_id = ?
            """,
            (ctx.workspace_id,),
        ).fetchone()["c"]

        active_chatbots = db.execute(
            "SELECT COUNT(*) AS c FROM chatbots WHERE workspace_id = ? AND is_enabled = 1",
            (ctx.workspace_id,),
        ).fetchone()["c"]

        knowledge_sources = db.execute(
            "SELECT COUNT(*) AS c FROM knowledge_sources WHERE workspace_id = ?",
            (ctx.workspace_id,),
        ).fetchone()["c"]

        monthly_ai_usage = db.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_records
            WHERE workspace_id = ? AND metric = 'ai_message' AND period_month = ?
            """,
            (ctx.workspace_id, month_key),
        ).fetchone()["total"]

        daily_conversations = db.execute(
            """
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count
            FROM conversations
            WHERE workspace_id = ? AND created_at >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (ctx.workspace_id, since),
        ).fetchall()

        daily_messages = db.execute(
            """
            SELECT substr(m.created_at, 1, 10) AS day, COUNT(*) AS count
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.workspace_id = ? AND m.created_at >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (ctx.workspace_id, since),
        ).fetchall()

        mode_breakdown = db.execute(
            """
            SELECT mode, COUNT(*) AS count
            FROM conversations
            WHERE workspace_id = ?
            GROUP BY mode
            """,
            (ctx.workspace_id,),
        ).fetchall()

    return {
        "days": days,
        "metrics": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "active_chatbots": active_chatbots,
            "knowledge_sources": knowledge_sources,
            "monthly_ai_usage": monthly_ai_usage,
        },
        "daily_conversations": [dict(r) for r in daily_conversations],
        "daily_messages": [dict(r) for r in daily_messages],
        "mode_breakdown": [dict(r) for r in mode_breakdown],
    }


@router.get("/integrations")
def list_integrations(ctx: WorkspaceContext = Depends(get_workspace_context)):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM integrations WHERE workspace_id = ? ORDER BY id DESC",
            (ctx.workspace_id,),
        ).fetchall()
    return {"integrations": [dict(r) for r in rows]}


@router.post("/integrations", status_code=status.HTTP_201_CREATED)
def create_integration(
    payload: IntegrationCreateRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    import json

    now = current_time()
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO integrations (workspace_id, provider, name, config_json, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                ctx.workspace_id,
                payload.provider.strip().lower(),
                payload.name.strip(),
                json.dumps(payload.config),
                now,
                now,
            ),
        )
        integration_id = cursor.lastrowid
        write_audit_log(
            db,
            action="integration.created",
            resource_type="integration",
            resource_id=str(integration_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
        row = dict(
            db.execute("SELECT * FROM integrations WHERE id = ?", (integration_id,)).fetchone()
        )
    return {"integration": row}


@router.delete("/integrations/{integration_id}")
def delete_integration(
    integration_id: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM integrations WHERE id = ? AND workspace_id = ?",
            (integration_id, ctx.workspace_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Integration not found.")
        db.commit()
    return {"success": True}
