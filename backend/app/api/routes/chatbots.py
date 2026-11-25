import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.dependencies import WorkspaceContext, get_workspace_context
from app.core.rate_limit import check_rate_limit
from app.core.security import write_audit_log
from app.db.database import current_time, get_db
from app.services.ai.gemini_service import generate_gemini_reply
from app.services.knowledge_base.rag_service import retrieve_rag_context

router = APIRouter(tags=["chatbots"])


class ChatbotCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    knowledge_base_id: Optional[int] = None
    primary_color: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")
    welcome_message: str = Field(
        default="Hello! How can I help you today?", min_length=1, max_length=500
    )
    system_instructions: str = Field(
        default="You are a helpful AI customer support assistant.",
        min_length=1,
        max_length=2000,
    )
    fallback_message: str = Field(
        default="I could not find that in our documentation. Please reach out to our support team.",
        min_length=1,
        max_length=500,
    )
    allowed_domains: str = Field(default="*", max_length=1000)


class ChatbotUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    knowledge_base_id: Optional[int] = None
    is_enabled: Optional[bool] = None
    allowed_domains: Optional[str] = Field(default=None, max_length=1000)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: Optional[str] = Field(default=None, max_length=500)
    welcome_message: Optional[str] = Field(default=None, min_length=1, max_length=500)
    system_instructions: Optional[str] = Field(
        default=None, min_length=1, max_length=2000
    )
    fallback_message: Optional[str] = Field(default=None, min_length=1, max_length=500)


class WidgetChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(min_length=4, max_length=100)
    conversation_id: Optional[int] = None


def _get_chatbot_with_settings(db, chatbot_id: int, workspace_id: int) -> dict:
    row = db.execute(
        """
        SELECT c.*, cs.primary_color, cs.logo_url, cs.welcome_message,
               cs.system_instructions, cs.fallback_message
        FROM chatbots c
        JOIN chatbot_settings cs ON cs.chatbot_id = c.id
        WHERE c.id = ? AND c.workspace_id = ?
        """,
        (chatbot_id, workspace_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    return dict(row)


def _validate_domain(request: Request, allowed_domains: str) -> None:
    raw = (allowed_domains or "*").strip()
    if raw == "*" or not raw:
        return
    allowed = {d.strip().lower() for d in raw.split(",") if d.strip()}
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin:
        return
    host = (urlparse(origin).hostname or "").lower()
    if host and host not in allowed and f"*.{host}" not in allowed:
        # Also allow wildcard subdomain matches like *.example.com
        matched = any(
            pattern.startswith("*.") and host.endswith(pattern[1:])
            for pattern in allowed
        )
        if not matched:
            raise HTTPException(
                status_code=403,
                detail="Origin domain is not authorized for this chatbot.",
            )


@router.get("/chatbots")
def list_chatbots(ctx: WorkspaceContext = Depends(get_workspace_context)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT c.*, cs.primary_color, cs.logo_url, cs.welcome_message,
                   cs.system_instructions, cs.fallback_message,
                   kb.name AS knowledge_base_name
            FROM chatbots c
            JOIN chatbot_settings cs ON cs.chatbot_id = c.id
            LEFT JOIN knowledge_bases kb ON kb.id = c.knowledge_base_id
            WHERE c.workspace_id = ?
            ORDER BY c.id DESC
            """,
            (ctx.workspace_id,),
        ).fetchall()
    return {"chatbots": [dict(r) for r in rows]}


@router.post("/chatbots", status_code=status.HTTP_201_CREATED)
def create_chatbot(
    payload: ChatbotCreateRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    now = current_time()
    with get_db() as db:
        sub = db.execute(
            """
            SELECT p.chatbot_limit
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.workspace_id = ? AND s.status = 'active'
            LIMIT 1
            """,
            (ctx.workspace_id,),
        ).fetchone()
        if sub:
            cnt = db.execute(
                "SELECT COUNT(*) AS total FROM chatbots WHERE workspace_id = ?",
                (ctx.workspace_id,),
            ).fetchone()["total"]
            if int(cnt) >= int(sub["chatbot_limit"]):
                raise HTTPException(
                    status_code=429,
                    detail="Chatbot limit reached for your current subscription plan.",
                )

        kb_id = payload.knowledge_base_id
        if kb_id is not None:
            kb = db.execute(
                "SELECT id FROM knowledge_bases WHERE id = ? AND workspace_id = ?",
                (kb_id, ctx.workspace_id),
            ).fetchone()
            if not kb:
                raise HTTPException(
                    status_code=404, detail="Selected knowledge base not found."
                )
        else:
            default_kb = db.execute(
                "SELECT id FROM knowledge_bases WHERE workspace_id = ? ORDER BY id ASC LIMIT 1",
                (ctx.workspace_id,),
            ).fetchone()
            kb_id = default_kb["id"] if default_kb else None

        public_id = f"cb_{secrets.token_hex(8)}"
        cursor = db.execute(
            """
            INSERT INTO chatbots
            (workspace_id, public_id, name, knowledge_base_id, is_enabled, allowed_domains, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                ctx.workspace_id,
                public_id,
                payload.name.strip(),
                kb_id,
                payload.allowed_domains.strip() or "*",
                now,
                now,
            ),
        )
        chatbot_id = cursor.lastrowid
        db.execute(
            """
            INSERT INTO chatbot_settings
            (chatbot_id, primary_color, logo_url, welcome_message, system_instructions, fallback_message, updated_at)
            VALUES (?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                chatbot_id,
                payload.primary_color,
                payload.welcome_message.strip(),
                payload.system_instructions.strip(),
                payload.fallback_message.strip(),
                now,
            ),
        )
        write_audit_log(
            db,
            action="chatbot.created",
            resource_type="chatbot",
            resource_id=str(chatbot_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
        chatbot = _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)

    return {"chatbot": chatbot}


@router.get("/chatbots/{chatbot_id}")
def get_chatbot(
    chatbot_id: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    with get_db() as db:
        chatbot = _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)
    return {"chatbot": chatbot}


@router.patch("/chatbots/{chatbot_id}")
def update_chatbot(
    chatbot_id: int,
    payload: ChatbotUpdateRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    now = current_time()
    with get_db() as db:
        _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)

        bot_updates = []
        bot_params: list = []
        if payload.name is not None:
            bot_updates.append("name = ?")
            bot_params.append(payload.name.strip())
        if payload.knowledge_base_id is not None:
            kb = db.execute(
                "SELECT id FROM knowledge_bases WHERE id = ? AND workspace_id = ?",
                (payload.knowledge_base_id, ctx.workspace_id),
            ).fetchone()
            if not kb:
                raise HTTPException(
                    status_code=404, detail="Selected knowledge base not found."
                )
            bot_updates.append("knowledge_base_id = ?")
            bot_params.append(payload.knowledge_base_id)
        if payload.is_enabled is not None:
            bot_updates.append("is_enabled = ?")
            bot_params.append(1 if payload.is_enabled else 0)
        if payload.allowed_domains is not None:
            bot_updates.append("allowed_domains = ?")
            bot_params.append(payload.allowed_domains.strip() or "*")

        if bot_updates:
            bot_updates.append("updated_at = ?")
            bot_params.extend([now, chatbot_id, ctx.workspace_id])
            db.execute(
                f"UPDATE chatbots SET {', '.join(bot_updates)} WHERE id = ? AND workspace_id = ?",
                tuple(bot_params),
            )

        cfg_updates = []
        cfg_params: list = []
        for field_name in (
            "primary_color",
            "logo_url",
            "welcome_message",
            "system_instructions",
            "fallback_message",
        ):
            val = getattr(payload, field_name)
            if val is not None:
                cfg_updates.append(f"{field_name} = ?")
                cfg_params.append(val.strip() if isinstance(val, str) else val)

        if cfg_updates:
            cfg_updates.append("updated_at = ?")
            cfg_params.extend([now, chatbot_id])
            db.execute(
                f"UPDATE chatbot_settings SET {', '.join(cfg_updates)} WHERE chatbot_id = ?",
                tuple(cfg_params),
            )

        write_audit_log(
            db,
            action="chatbot.updated",
            resource_type="chatbot",
            resource_id=str(chatbot_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
        chatbot = _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)

    return {"chatbot": chatbot}


@router.post("/chatbots/{chatbot_id}/logo")
async def upload_chatbot_logo(
    chatbot_id: int,
    file: UploadFile = File(...),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(
            status_code=400, detail="Logo must be a PNG, JPG, or WEBP image."
        )
    content = await file.read()
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be between 1B and 2MB.")

    with get_db() as db:
        chatbot = _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)
        logo_dir = settings.uploads_dir / "logos"
        logo_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{chatbot['public_id']}{ext}"
        target = logo_dir / filename
        target.write_bytes(content)
        logo_url = f"/widget/{chatbot['public_id']}/logo"
        db.execute(
            "UPDATE chatbot_settings SET logo_url = ?, updated_at = ? WHERE chatbot_id = ?",
            (logo_url, current_time(), chatbot_id),
        )
        db.commit()
        updated = _get_chatbot_with_settings(db, chatbot_id, ctx.workspace_id)

    return {"chatbot": updated}


@router.delete("/chatbots/{chatbot_id}")
def delete_chatbot(
    chatbot_id: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM chatbots WHERE id = ? AND workspace_id = ?",
            (chatbot_id, ctx.workspace_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Chatbot not found.")
        write_audit_log(
            db,
            action="chatbot.deleted",
            resource_type="chatbot",
            resource_id=str(chatbot_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
    return {"success": True}


# --------------------------------------------------
# PUBLIC EMBED WIDGET ENDPOINTS
# --------------------------------------------------


@router.get("/widget/{public_id}/logo")
def get_widget_logo(public_id: str):
    logo_dir = settings.uploads_dir / "logos"
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = logo_dir / f"{public_id}{ext}"
        if candidate.exists():
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Logo not found.")


@router.get("/widget/{public_id}/config")
def get_widget_config(public_id: str, request: Request):
    with get_db() as db:
        row = db.execute(
            """
            SELECT c.public_id, c.name, c.is_enabled, c.allowed_domains,
                   cs.primary_color, cs.logo_url, cs.welcome_message
            FROM chatbots c
            JOIN chatbot_settings cs ON cs.chatbot_id = c.id
            WHERE c.public_id = ?
            """,
            (public_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    _validate_domain(request, row["allowed_domains"])
    return {
        "public_id": row["public_id"],
        "name": row["name"],
        "is_enabled": bool(row["is_enabled"]),
        "primary_color": row["primary_color"],
        "logo_url": row["logo_url"],
        "welcome_message": row["welcome_message"],
    }


@router.post("/widget/{public_id}/chat")
def widget_chat(public_id: str, payload: WidgetChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"widget:{public_id}:{client_ip}", max_requests=25, window_seconds=60)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service is unavailable.")

    with get_db() as db:
        bot = db.execute(
            """
            SELECT c.*, cs.system_instructions, cs.fallback_message
            FROM chatbots c
            JOIN chatbot_settings cs ON cs.chatbot_id = c.id
            WHERE c.public_id = ?
            """,
            (public_id,),
        ).fetchone()
        if not bot:
            raise HTTPException(status_code=404, detail="Chatbot not found.")
        if not bool(bot["is_enabled"]):
            raise HTTPException(status_code=403, detail="This chatbot is currently disabled.")
        _validate_domain(request, bot["allowed_domains"])

        workspace_id = bot["workspace_id"]
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
            used = db.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS total
                FROM usage_records
                WHERE workspace_id = ? AND metric = 'ai_message' AND period_month = ?
                """,
                (workspace_id, period_month),
            ).fetchone()["total"]
            if int(used) >= int(sub["monthly_message_limit"]):
                raise HTTPException(
                    status_code=429,
                    detail="Workspace message quota reached.",
                )

        existing_history = []
        conversation_id = payload.conversation_id
        if conversation_id is not None:
            conv = db.execute(
                """
                SELECT id FROM conversations
                WHERE id = ? AND workspace_id = ? AND chatbot_id = ? AND customer_id = ?
                """,
                (conversation_id, workspace_id, bot["id"], payload.session_id),
            ).fetchone()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            rows = db.execute(
                "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 12",
                (conversation_id,),
            ).fetchall()
            existing_history = [
                {"role": r["role"], "content": r["content"]} for r in reversed(rows)
            ]

    rag_context = ""
    sources = []
    if bot["knowledge_base_id"] is not None:
        try:
            rag_context, sources = retrieve_rag_context(
                workspace_id=bot["workspace_id"],
                query=payload.message,
                knowledge_base_id=bot["knowledge_base_id"],
                top_k=4,
            )
        except Exception:
            rag_context = ""
            sources = []

    history = existing_history + [{"role": "user", "content": payload.message}]
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    prompt = f"""
{bot['system_instructions']}

Rules:
- Only state facts grounded in the KNOWLEDGE BASE CONTEXT or conversation history.
- Never invent prices, policies, warranties, or completed actions.
- If the knowledge base does not contain the answer, respond helpfully using this guidance: "{bot['fallback_message']}"

KNOWLEDGE BASE CONTEXT:
{rag_context or "No knowledge base snippets matched this query."}

CONVERSATION HISTORY:
{transcript}

Respond to the latest user message.
"""
    model = os.getenv("GEMINI_MODEL", settings.gemini_model)

    try:
        answer = generate_gemini_reply(prompt=prompt, api_key=api_key, model=model)
        now = current_time()
        with get_db() as db:
            if conversation_id is None:
                cursor = db.execute(
                    """
                    INSERT INTO conversations
                    (title, mode, customer_id, workspace_id, chatbot_id, status, created_at, updated_at)
                    VALUES (?, 'support', ?, ?, ?, 'open', ?, ?)
                    """,
                    (
                        payload.message[:60],
                        payload.session_id,
                        bot["workspace_id"],
                        bot["id"],
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
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (conversation_id, payload.message, now),
            )
            db.execute(
                "INSERT INTO messages (conversation_id, role, content, sources_json, created_at) VALUES (?, 'assistant', ?, ?, ?)",
                (
                    conversation_id,
                    answer,
                    json.dumps(sources) if sources else None,
                    current_time(),
                ),
            )
            db.execute(
                "INSERT INTO usage_records (workspace_id, metric, quantity, period_month, created_at) VALUES (?, 'ai_message', 1, ?, ?)",
                (bot["workspace_id"], period_month, now),
            )
            db.commit()

        return {
            "success": True,
            "conversation_id": conversation_id,
            "reply": answer,
            "sources": sources,
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Widget chat error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="AI response failed.") from exc


@router.get("/widget.js")
def serve_widget_js(request: Request):
    base_url = str(request.base_url).rstrip("/")
    js = f"""(function(){{
  var s=document.currentScript;
  if(!s)return;
  var botId=s.getAttribute('data-chatbot-id');
  if(!botId)return;
  var apiBase=(s.getAttribute('data-api-url')||'{base_url}').replace(/\\/$/,'');
  var sessionKey='supportai_session_'+botId;
  var sid=localStorage.getItem(sessionKey);
  if(!sid){{sid='vis_'+Math.random().toString(36).slice(2,12);localStorage.setItem(sessionKey,sid);}}
  var convId=null, open=false, cfg={{name:'SupportAI',primary_color:'#2563eb',welcome_message:'Hello! How can I help you?'}};
  var host=document.createElement('div');
  host.id='supportai-widget-root';
  document.body.appendChild(host);
  var shadow=host.attachShadow({{mode:'open'}});
  var style=document.createElement('style');
  style.textContent='*{{box-sizing:border-box;font-family:system-ui,-apple-system,sans-serif}}.btn{{position:fixed;right:20px;bottom:20px;z-index:999999;width:56px;height:56px;border-radius:9999px;border:none;color:#fff;font-size:22px;cursor:pointer;box-shadow:0 10px 25px rgba(2,6,23,.35)}}.win{{position:fixed;right:20px;bottom:88px;z-index:999999;width:360px;max-width:calc(100vw - 24px);height:500px;max-height:calc(100vh - 110px);background:#0f172a;color:#f8fafc;border:1px solid rgba(255,255,255,.12);border-radius:16px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 20px 45px rgba(2,6,23,.5)}}.hdr{{padding:14px 16px;display:flex;align-items:center;justify-content:space-between;color:#fff;font-weight:600}}.msgs{{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}}.b{{max-width:85%;padding:10px 12px;border-radius:12px;font-size:13px;line-height:1.45;white-space:pre-wrap;word-break:break-word}}.u{{align-self:flex-end;background:#2563eb;color:#fff}}.a{{align-self:flex-start;background:#1e293b;color:#e2e8f0;border:1px solid rgba(255,255,255,.08)}}.frm{{display:flex;gap:8px;padding:10px;border-top:1px solid rgba(255,255,255,.1);background:#0b1220}}.inp{{flex:1;background:#1e293b;color:#fff;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:9px 11px;font-size:13px;outline:none}}.snd{{border:none;border-radius:10px;padding:0 14px;color:#fff;font-weight:600;cursor:pointer}}';
  shadow.appendChild(style);
  var btn=document.createElement('button'); btn.className='btn'; btn.textContent='💬';
  var win=document.createElement('div'); win.className='win';
  var hdr=document.createElement('div'); hdr.className='hdr';
  var titleEl=document.createElement('span'); titleEl.textContent=cfg.name;
  var cls=document.createElement('button'); cls.textContent='✕'; cls.style.cssText='background:none;border:none;color:#fff;cursor:pointer;font-size:16px';
  hdr.appendChild(titleEl); hdr.appendChild(cls);
  var msgs=document.createElement('div'); msgs.className='msgs';
  var frm=document.createElement('form'); frm.className='frm';
  var inp=document.createElement('input'); inp.className='inp'; inp.placeholder='Type a message...';
  var snd=document.createElement('button'); snd.className='snd'; snd.type='submit'; snd.textContent='Send';
  frm.appendChild(inp); frm.appendChild(snd);
  win.appendChild(hdr); win.appendChild(msgs); win.appendChild(frm);
  shadow.appendChild(win); shadow.appendChild(btn);
  function addMsg(role,text){{var d=document.createElement('div');d.className='b '+(role==='user'?'u':'a');d.textContent=text;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;}}
  function applyCfg(){{btn.style.background=cfg.primary_color;hdr.style.background=cfg.primary_color;snd.style.background=cfg.primary_color;titleEl.textContent=cfg.name;}}
  applyCfg();
  fetch(apiBase+'/widget/'+encodeURIComponent(botId)+'/config').then(function(r){{return r.json();}}).then(function(d){{if(d&&d.is_enabled===false){{btn.style.display='none';return;}}if(d&&d.name){{cfg=d;applyCfg();}}if(msgs.children.length===0&&cfg.welcome_message){{addMsg('assistant',cfg.welcome_message);}}}}).catch(function(){{}});
  function toggle(){{open=!open;win.style.display=open?'flex':'none';if(open&&msgs.children.length===0&&cfg.welcome_message){{addMsg('assistant',cfg.welcome_message);}}}}
  btn.onclick=toggle; cls.onclick=toggle;
  frm.onsubmit=function(e){{e.preventDefault();var text=inp.value.trim();if(!text)return;inp.value='';addMsg('user',text);snd.disabled=true;fetch(apiBase+'/widget/'+encodeURIComponent(botId)+'/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:text,session_id:sid,conversation_id:convId}})}}).then(function(r){{return r.json().then(function(j){{return {{ok:r.ok,j:j}};}});}}).then(function(res){{if(!res.ok)throw new Error(res.j.detail||'Request failed');convId=res.j.conversation_id;addMsg('assistant',res.j.reply);}}).catch(function(err){{addMsg('assistant',err.message||'Unable to respond right now.');}}).finally(function(){{snd.disabled=false;}});}};
}})();"""
    return Response(content=js, media_type="application/javascript")
