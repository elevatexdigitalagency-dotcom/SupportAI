from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.db.database import current_time, get_db
from app.services.knowledge_base.document_processor import (
    chunk_text,
    compute_sha256,
    crawl_website,
    extract_text_from_file,
    save_workspace_upload,
    validate_upload,
)
from app.services.knowledge_base.embeddings import generate_embeddings
from app.services.knowledge_base.vector_store import (
    delete_source_chunks,
    query_chunks,
    upsert_chunks,
)


def resolve_knowledge_base(
    db,
    workspace_id: int,
    knowledge_base_id: Optional[int] = None,
) -> Dict[str, Any]:
    if knowledge_base_id is not None:
        kb = db.execute(
            "SELECT * FROM knowledge_bases WHERE id = ? AND workspace_id = ?",
            (knowledge_base_id, workspace_id),
        ).fetchone()
        if not kb:
            raise HTTPException(
                status_code=404, detail="Knowledge base not found in workspace."
            )
        return dict(kb)

    kb = db.execute(
        "SELECT * FROM knowledge_bases WHERE workspace_id = ? ORDER BY id ASC LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if kb:
        return dict(kb)

    now = current_time()
    cursor = db.execute(
        """
        INSERT INTO knowledge_bases (workspace_id, name, description, collection_name, created_at, updated_at)
        VALUES (?, 'Default Knowledge Base', 'Primary workspace knowledge base', ?, ?, ?)
        """,
        (workspace_id, f"ws_{workspace_id}_kb", now, now),
    )
    kb_id = cursor.lastrowid
    return dict(
        db.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    )


def _enforce_document_limit(db, workspace_id: int) -> None:
    sub = db.execute(
        """
        SELECT p.document_limit
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.workspace_id = ? AND s.status = 'active'
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()
    if sub:
        cnt_row = db.execute(
            "SELECT COUNT(*) AS total FROM knowledge_sources WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        total = int(cnt_row["total"]) if cnt_row else 0
        if total >= int(sub["document_limit"]):
            raise HTTPException(
                status_code=429,
                detail="Document limit reached for your current subscription plan.",
            )


def _index_extracted_text(
    workspace_id: int,
    kb_id: int,
    source_type: str,
    title: str,
    text: str,
    content_hash: str,
    source_uri: Optional[str] = None,
    file_path: Optional[str] = None,
    file_size_bytes: int = 0,
) -> Dict[str, Any]:
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=422, detail="No indexable text chunks found."
        )

    now = current_time()
    with get_db() as db:
        _enforce_document_limit(db, workspace_id)

        dup = db.execute(
            """
            SELECT id, title FROM knowledge_sources
            WHERE workspace_id = ? AND knowledge_base_id = ? AND content_hash = ? AND status = 'indexed'
            LIMIT 1
            """,
            (workspace_id, kb_id, content_hash),
        ).fetchone()
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate knowledge source already indexed ('{dup['title']}').",
            )

        cursor = db.execute(
            """
            INSERT INTO knowledge_sources
            (workspace_id, knowledge_base_id, source_type, title, source_uri, file_path, content_hash, file_size_bytes, chunk_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'processing', ?, ?)
            """,
            (
                workspace_id,
                kb_id,
                source_type,
                title,
                source_uri,
                file_path,
                content_hash,
                file_size_bytes,
                now,
                now,
            ),
        )
        source_id = cursor.lastrowid
        db.commit()

    try:
        vectors = generate_embeddings(chunks)
        chroma_ids = [f"ws{workspace_id}_src{source_id}_c{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "workspace_id": workspace_id,
                "knowledge_base_id": kb_id,
                "source_id": source_id,
                "source_type": source_type,
                "title": title,
                "source_uri": source_uri or "",
                "chunk_index": idx,
            }
            for idx in range(len(chunks))
        ]
        upsert_chunks(
            workspace_id=workspace_id,
            knowledge_base_id=kb_id,
            ids=chroma_ids,
            documents=chunks,
            embeddings=vectors,
            metadatas=metadatas,
        )

        with get_db() as db:
            done_at = current_time()
            db.executemany(
                """
                INSERT INTO document_chunks
                (workspace_id, knowledge_source_id, chunk_index, chroma_id, content_preview, token_estimate, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        workspace_id,
                        source_id,
                        idx,
                        chroma_ids[idx],
                        chunks[idx][:200],
                        max(1, len(chunks[idx]) // 4),
                        done_at,
                    )
                    for idx in range(len(chunks))
                ],
            )
            db.execute(
                """
                UPDATE knowledge_sources
                SET status = 'indexed', chunk_count = ?, error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (len(chunks), done_at, source_id),
            )
            db.commit()
            source_row = dict(
                db.execute(
                    "SELECT * FROM knowledge_sources WHERE id = ?",
                    (source_id,),
                ).fetchone()
            )
        return source_row
    except Exception as exc:
        with get_db() as db:
            db.execute(
                """
                UPDATE knowledge_sources
                SET status = 'failed', error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(exc)[:500], current_time(), source_id),
            )
            db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to index knowledge source: {exc}",
        ) from exc


def ingest_uploaded_file(
    workspace_id: int,
    filename: str,
    content: bytes,
    knowledge_base_id: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        ext, safe_name = validate_upload(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with get_db() as db:
        kb = resolve_knowledge_base(db, workspace_id, knowledge_base_id)
        db.commit()

    saved_path = save_workspace_upload(workspace_id, safe_name, content)
    try:
        text = extract_text_from_file(saved_path, ext)
    except ValueError as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    content_hash = compute_sha256(text.encode("utf-8"))
    try:
        return _index_extracted_text(
            workspace_id=workspace_id,
            kb_id=kb["id"],
            source_type=ext.lstrip("."),
            title=Path(filename).name[:180],
            text=text,
            content_hash=content_hash,
            file_path=str(saved_path),
            file_size_bytes=len(content),
        )
    except Exception:
        # Remove orphaned file if duplicate or failed before indexing
        if not saved_path.exists():
            pass
        raise


def ingest_website_url(
    workspace_id: int,
    url: str,
    max_pages: int = 3,
    knowledge_base_id: Optional[int] = None,
) -> Dict[str, Any]:
    with get_db() as db:
        kb = resolve_knowledge_base(db, workspace_id, knowledge_base_id)
        db.commit()

    try:
        title, text = crawl_website(url, max_pages=max_pages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Website crawling failed: {exc}"
        ) from exc

    content_hash = compute_sha256(text.encode("utf-8"))
    return _index_extracted_text(
        workspace_id=workspace_id,
        kb_id=kb["id"],
        source_type="website",
        title=title[:180],
        text=text,
        content_hash=content_hash,
        source_uri=url.strip(),
        file_size_bytes=len(text.encode("utf-8")),
    )


def remove_knowledge_source(workspace_id: int, source_id: int) -> None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM knowledge_sources WHERE id = ? AND workspace_id = ?",
            (source_id, workspace_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        kb_id = row["knowledge_base_id"]
        file_path = row["file_path"]

    try:
        delete_source_chunks(workspace_id, kb_id, source_id)
    except Exception:
        pass

    with get_db() as db:
        db.execute(
            "DELETE FROM knowledge_sources WHERE id = ? AND workspace_id = ?",
            (source_id, workspace_id),
        )
        db.commit()

    if file_path:
        Path(file_path).unlink(missing_ok=True)


def retrieve_rag_context(
    workspace_id: int,
    query: str,
    knowledge_base_id: Optional[int] = None,
    top_k: int = 4,
) -> Tuple[str, List[Dict[str, Any]]]:
    with get_db() as db:
        if knowledge_base_id is not None:
            kb_rows = db.execute(
                "SELECT id FROM knowledge_bases WHERE id = ? AND workspace_id = ?",
                (knowledge_base_id, workspace_id),
            ).fetchall()
        else:
            kb_rows = db.execute(
                "SELECT id FROM knowledge_bases WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()

        has_sources = db.execute(
            "SELECT 1 FROM knowledge_sources WHERE workspace_id = ? AND status = 'indexed' LIMIT 1",
            (workspace_id,),
        ).fetchone()

    if not kb_rows or not has_sources:
        return "", []

    query_vecs = generate_embeddings([query])
    if not query_vecs:
        return "", []
    query_vec = query_vecs[0]

    all_matches: List[Dict[str, Any]] = []
    for kb_row in kb_rows:
        matches = query_chunks(
            workspace_id=workspace_id,
            knowledge_base_id=kb_row["id"],
            query_embedding=query_vec,
            top_k=top_k,
        )
        all_matches.extend(matches)

    all_matches.sort(
        key=lambda m: m["distance"] if m["distance"] is not None else 999.0
    )
    top_matches = all_matches[:top_k]

    context_parts: List[str] = []
    sources: List[Dict[str, Any]] = []
    seen_sources = set()

    for idx, match in enumerate(top_matches, start=1):
        meta = match.get("metadata") or {}
        title = meta.get("title", "Document")
        source_id = meta.get("source_id")
        source_uri = meta.get("source_uri") or None
        source_type = meta.get("source_type", "document")
        context_parts.append(f"[Source {idx}: {title}]\n{match['content']}")
        if source_id not in seen_sources:
            seen_sources.add(source_id)
            sources.append(
                {
                    "source_id": source_id,
                    "title": title,
                    "source_type": source_type,
                    "source_uri": source_uri,
                    "distance": match.get("distance"),
                }
            )

    return "\n\n".join(context_parts), sources
