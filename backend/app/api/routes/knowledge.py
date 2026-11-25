from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.dependencies import WorkspaceContext, get_workspace_context
from app.core.security import write_audit_log
from app.db.database import current_time, get_db
from app.services.knowledge_base.rag_service import (
    ingest_uploaded_file,
    ingest_website_url,
    remove_knowledge_source,
    retrieve_rag_context,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class CrawlWebsiteRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    max_pages: int = Field(default=3, ge=1, le=5)
    knowledge_base_id: Optional[int] = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    knowledge_base_id: Optional[int] = None
    top_k: int = Field(default=4, ge=1, le=10)


@router.get("/bases")
def list_knowledge_bases(ctx: WorkspaceContext = Depends(get_workspace_context)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT kb.*,
                   (SELECT COUNT(*) FROM knowledge_sources ks WHERE ks.knowledge_base_id = kb.id) AS source_count
            FROM knowledge_bases kb
            WHERE kb.workspace_id = ?
            ORDER BY kb.id ASC
            """,
            (ctx.workspace_id,),
        ).fetchall()
    return {"knowledge_bases": [dict(r) for r in rows]}


@router.post("/bases", status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    now = current_time()
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO knowledge_bases (workspace_id, name, description, collection_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ctx.workspace_id,
                payload.name.strip(),
                (payload.description or "").strip() or None,
                f"ws_{ctx.workspace_id}_kb_pending",
                now,
                now,
            ),
        )
        kb_id = cursor.lastrowid
        db.execute(
            "UPDATE knowledge_bases SET collection_name = ? WHERE id = ?",
            (f"ws_{ctx.workspace_id}_kb_{kb_id}", kb_id),
        )
        write_audit_log(
            db,
            action="knowledge_base.created",
            resource_type="knowledge_base",
            resource_id=str(kb_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
        row = dict(
            db.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
        )
    return {"knowledge_base": row}


@router.get("/sources")
def list_knowledge_sources(
    knowledge_base_id: Optional[int] = None,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    with get_db() as db:
        if knowledge_base_id is not None:
            rows = db.execute(
                """
                SELECT * FROM knowledge_sources
                WHERE workspace_id = ? AND knowledge_base_id = ?
                ORDER BY id DESC
                """,
                (ctx.workspace_id, knowledge_base_id),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM knowledge_sources
                WHERE workspace_id = ?
                ORDER BY id DESC
                """,
                (ctx.workspace_id,),
            ).fetchall()
    return {"sources": [dict(r) for r in rows]}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_base_id: Optional[int] = Form(default=None),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    content = await file.read()
    source = ingest_uploaded_file(
        workspace_id=ctx.workspace_id,
        filename=file.filename or "upload.txt",
        content=content,
        knowledge_base_id=knowledge_base_id,
    )
    with get_db() as db:
        write_audit_log(
            db,
            action="knowledge_source.uploaded",
            resource_type="knowledge_source",
            resource_id=str(source["id"]),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
            details={"title": source["title"], "chunks": source["chunk_count"]},
        )
        db.commit()
    return {"source": source}


@router.post("/crawl", status_code=status.HTTP_201_CREATED)
def crawl_url(
    payload: CrawlWebsiteRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    source = ingest_website_url(
        workspace_id=ctx.workspace_id,
        url=payload.url,
        max_pages=payload.max_pages,
        knowledge_base_id=payload.knowledge_base_id,
    )
    with get_db() as db:
        write_audit_log(
            db,
            action="knowledge_source.crawled",
            resource_type="knowledge_source",
            resource_id=str(source["id"]),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
            details={"url": payload.url, "chunks": source["chunk_count"]},
        )
        db.commit()
    return {"source": source}


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: int,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    remove_knowledge_source(ctx.workspace_id, source_id)
    with get_db() as db:
        write_audit_log(
            db,
            action="knowledge_source.deleted",
            resource_type="knowledge_source",
            resource_id=str(source_id),
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
        )
        db.commit()
    return {"success": True}


@router.post("/search")
def search_knowledge(
    payload: KnowledgeSearchRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    try:
        context, sources = retrieve_rag_context(
            workspace_id=ctx.workspace_id,
            query=payload.query,
            knowledge_base_id=payload.knowledge_base_id,
            top_k=payload.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Semantic search failed: {exc}"
        ) from exc

    return {"context": context, "sources": sources}
