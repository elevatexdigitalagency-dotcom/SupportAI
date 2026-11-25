import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.core.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_optional_current_user,
    resolve_workspace_for_user,
)
from app.db.database import current_time, get_db
from app.schemas.chat import ChatRequest, RegenerateRequest
from app.services.ai.gemini_service import generate_gemini_reply
from app.services.ai.memory_service import retrieve_memories

router = APIRouter()


def build_chat_prompt(
    mode: str,
    memory_context: str,
    transcript: str,
    rag_context: str = "",
) -> str:
    if mode == "personal":
        system_prompt = """
You are SupportAI Personal Assistant.

Help the user with programming, business,
projects, learning, research and daily tasks.

Use relevant stored personal memories and workspace knowledge when available.
Treat memories as contextual information, not guaranteed
truth. If information is missing, ask instead of guessing.
When answering from provided KNOWLEDGE BASE CONTEXT, cite sources accurately and never invent unsupported facts.

Be professional, helpful and conversational.
"""
    else:
        system_prompt = """
You are SupportAI Customer Support Assistant.

Help customers with their questions professionally.

Never invent prices, policies, warranties or completed actions.
Use the supplied knowledge base context, customer context, and conversation history.
If the answer is not in the provided knowledge base or context, clearly say so instead of guessing.
Ask for clarification when necessary.
Protect customer-specific information.
"""

    kb_section = (
        f"\nKNOWLEDGE BASE CONTEXT:\n{rag_context}\n"
        if rag_context
        else ""
    )

    return f"""
{system_prompt}
{kb_section}
RELEVANT SAVED MEMORIES:
{memory_context or "No matching saved memories."}

CONVERSATION HISTORY:
{transcript}

Respond to the latest user message.
"""


def _check_and_record_usage(db, workspace_id: int) -> None:
    period_month = datetime.now(timezone.utc).strftime("%Y-%m")
    sub = db.execute(
        """
        SELECT p.monthly_message_limit
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.workspace_id = ? AND s.status = 'active'
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()
    if sub:
        used_row = db.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_records
            WHERE workspace_id = ? AND metric = 'ai_message' AND period_month = ?
            """,
            (workspace_id, period_month),
        ).fetchone()
        used = int(used_row["total"]) if used_row else 0
        if used >= int(sub["monthly_message_limit"]):
            raise HTTPException(
                status_code=429,
                detail="Monthly AI message quota exceeded for your current plan. Please upgrade your subscription.",
            )


def _record_ai_message_usage(db, workspace_id: int) -> None:
    now = current_time()
    period_month = datetime.now(timezone.utc).strftime("%Y-%m")
    db.execute(
        """
        INSERT INTO usage_records (workspace_id, metric, quantity, period_month, created_at)
        VALUES (?, 'ai_message', 1, ?, ?)
        """,
        (workspace_id, period_month, now),
    )


@router.post("/chat")
def chat(
    request: ChatRequest,
    user: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API key is not configured.",
        )

    if request.mode == "support" and not request.customer_id:
        raise HTTPException(
            status_code=400,
            detail="Customer ID is required for support mode.",
        )

    workspace_id: Optional[int] = None
    user_id: Optional[int] = None
    if user is not None:
        ctx = resolve_workspace_for_user(user, x_workspace_id)
        workspace_id = ctx.workspace_id
        user_id = user.id

    existing_history: List[dict] = []
    conversation_id = request.conversation_id

    with get_db() as db:
        if workspace_id is not None:
            _check_and_record_usage(db, workspace_id)

        if conversation_id is not None:
            conversation = db.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()

            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

            if conversation["workspace_id"] != workspace_id:
                raise HTTPException(
                    status_code=403,
                    detail="Conversation access mismatch.",
                )

            if (
                conversation["mode"] != request.mode
                or conversation["customer_id"] != request.customer_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Conversation access mismatch.",
                )

            rows = db.execute(
                """
                SELECT role, content FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT 20
                """,
                (conversation_id,),
            ).fetchall()

            existing_history = [
                {"role": item["role"], "content": item["content"]}
                for item in reversed(rows)
            ]

    history = existing_history + [{"role": "user", "content": request.message}]
    memories = retrieve_memories(
        request.message,
        request.mode,
        request.customer_id,
        workspace_id=workspace_id,
    )
    memory_context = "\n".join(
        f"- {item['category']}: {item['content']}"
        for item in memories
    )

    rag_context = ""
    sources: List[dict] = []
    if workspace_id is not None:
        try:
            from app.services.knowledge_base.rag_service import retrieve_rag_context

            rag_context, sources = retrieve_rag_context(
                workspace_id=workspace_id,
                query=request.message,
                knowledge_base_id=request.knowledge_base_id,
            )
        except ImportError:
            rag_context = ""
            sources = []

    transcript = "\n".join(
        f"{item['role'].upper()}: {item['content']}"
        for item in history
    )
    prompt = build_chat_prompt(
        request.mode,
        memory_context,
        transcript,
        rag_context=rag_context,
    )
    model = os.getenv("GEMINI_MODEL", settings.gemini_model)

    try:
        answer = generate_gemini_reply(
            prompt=prompt,
            api_key=api_key,
            model=model,
        )

        now = current_time()
        with get_db() as db:
            if conversation_id is None:
                cursor = db.execute(
                    """
                    INSERT INTO conversations
                    (title, mode, customer_id, workspace_id, user_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
                    """,
                    (
                        request.message[:60],
                        request.mode,
                        request.customer_id,
                        workspace_id,
                        user_id,
                        now,
                        now,
                    ),
                )
                conversation_id = cursor.lastrowid
            else:
                db.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )

            db.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, created_at)
                VALUES (?, 'user', ?, ?)
                """,
                (conversation_id, request.message, now),
            )
            db.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, sources_json, created_at)
                VALUES (?, 'assistant', ?, ?, ?)
                """,
                (
                    conversation_id,
                    answer,
                    json.dumps(sources) if sources else None,
                    current_time(),
                ),
            )
            if workspace_id is not None:
                _record_ai_message_usage(db, workspace_id)
            db.commit()

        return {
            "success": True,
            "conversation_id": conversation_id,
            "reply": answer,
            "model": model,
            "mode": request.mode,
            "memories_used": len(memories),
            "sources": sources,
        }

    except HTTPException:
        raise

    except Exception as error:
        print(f"Gemini error: {type(error).__name__}: {error}")
        raise HTTPException(
            status_code=502,
            detail="AI response failed. Please try again.",
        )


@router.post("/conversations/{conversation_id}/regenerate")
def regenerate_last_reply(
    conversation_id: int,
    payload: RegenerateRequest = RegenerateRequest(),
    user: AuthenticatedUser = Depends(get_current_user),
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Gemini API key is not configured.")

    ctx = resolve_workspace_for_user(user, x_workspace_id)
    with get_db() as db:
        _check_and_record_usage(db, ctx.workspace_id)
        conversation = db.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if conversation["workspace_id"] != ctx.workspace_id:
            raise HTTPException(status_code=403, detail="Conversation access forbidden.")

        rows = db.execute(
            "SELECT id, role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()

    if not rows:
        raise HTTPException(status_code=400, detail="Conversation has no messages.")

    msg_list = [dict(r) for r in rows]
    last_assistant_id: Optional[int] = None
    if msg_list[-1]["role"] == "assistant":
        last_assistant_id = msg_list[-1]["id"]
        msg_list = msg_list[:-1]

    if not msg_list or msg_list[-1]["role"] != "user":
        raise HTTPException(
            status_code=400,
            detail="No user message available to regenerate a reply for.",
        )

    latest_user_text = msg_list[-1]["content"]
    memories = retrieve_memories(
        latest_user_text,
        conversation["mode"],
        conversation["customer_id"],
        workspace_id=ctx.workspace_id,
    )
    memory_context = "\n".join(
        f"- {item['category']}: {item['content']}"
        for item in memories
    )

    rag_context = ""
    sources: List[dict] = []
    try:
        from app.services.knowledge_base.rag_service import retrieve_rag_context

        rag_context, sources = retrieve_rag_context(
            workspace_id=ctx.workspace_id,
            query=latest_user_text,
            knowledge_base_id=payload.knowledge_base_id,
        )
    except ImportError:
        pass

    transcript = "\n".join(
        f"{item['role'].upper()}: {item['content']}"
        for item in msg_list[-20:]
    )
    prompt = build_chat_prompt(
        conversation["mode"],
        memory_context,
        transcript,
        rag_context=rag_context,
    )
    model = os.getenv("GEMINI_MODEL", settings.gemini_model)

    try:
        answer = generate_gemini_reply(prompt=prompt, api_key=api_key, model=model)
        now = current_time()
        with get_db() as db:
            if last_assistant_id is not None:
                db.execute(
                    "UPDATE messages SET content = ?, sources_json = ?, created_at = ? WHERE id = ?",
                    (
                        answer,
                        json.dumps(sources) if sources else None,
                        now,
                        last_assistant_id,
                    ),
                )
            else:
                db.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content, sources_json, created_at)
                    VALUES (?, 'assistant', ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        answer,
                        json.dumps(sources) if sources else None,
                        now,
                    ),
                )
            db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            _record_ai_message_usage(db, ctx.workspace_id)
            db.commit()

        return {
            "success": True,
            "conversation_id": conversation_id,
            "reply": answer,
            "model": model,
            "sources": sources,
        }
    except HTTPException:
        raise
    except Exception as error:
        print(f"Gemini regenerate error: {type(error).__name__}: {error}")
        raise HTTPException(
            status_code=502,
            detail="AI response failed. Please try again.",
        )
