import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from app.core.config import settings

_client_lock = threading.Lock()
_clients: Dict[str, chromadb.PersistentClient] = {}


def get_chroma_client(chroma_dir: Optional[Path] = None) -> chromadb.PersistentClient:
    target_dir = (chroma_dir or settings.chroma_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    key = str(target_dir)
    with _client_lock:
        client = _clients.get(key)
        if client is None:
            client = chromadb.PersistentClient(path=key)
            _clients[key] = client
        return client


def release_chroma_clients() -> None:
    """Release cached ChromaDB clients (primarily for test teardown on Windows)."""
    with _client_lock:
        for client in _clients.values():
            system = getattr(client, "_system", None)
            if system is not None and hasattr(system, "stop"):
                try:
                    system.stop()
                except Exception:
                    pass
        _clients.clear()
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


def collection_name_for_kb(workspace_id: int, knowledge_base_id: int) -> str:
    return f"ws_{workspace_id}_kb_{knowledge_base_id}"


def upsert_chunks(
    workspace_id: int,
    knowledge_base_id: int,
    ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[Dict[str, Any]],
    chroma_dir: Optional[Path] = None,
) -> None:
    if not ids:
        return
    client = get_chroma_client(chroma_dir)
    name = collection_name_for_kb(workspace_id, knowledge_base_id)
    collection = client.get_or_create_collection(
        name=name,
        metadata={
            "workspace_id": workspace_id,
            "knowledge_base_id": knowledge_base_id,
            "hnsw:space": "cosine",
        },
    )
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def query_chunks(
    workspace_id: int,
    knowledge_base_id: int,
    query_embedding: List[float],
    top_k: int = 4,
    chroma_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    client = get_chroma_client(chroma_dir)
    name = collection_name_for_kb(workspace_id, knowledge_base_id)
    existing_names = {c.name for c in client.list_collections()}
    if name not in existing_names:
        return []

    collection = client.get_collection(name=name)
    total = collection.count()
    if total == 0:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, total),
        where={"workspace_id": workspace_id},
        include=["documents", "metadatas", "distances"],
    )

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    matches: List[Dict[str, Any]] = []
    for idx, doc in enumerate(docs):
        meta = metas[idx] if idx < len(metas) else {}
        dist = dists[idx] if idx < len(dists) else None
        matches.append(
            {
                "content": doc,
                "metadata": meta,
                "distance": dist,
            }
        )
    return matches


def delete_source_chunks(
    workspace_id: int,
    knowledge_base_id: int,
    source_id: int,
    chroma_dir: Optional[Path] = None,
) -> None:
    client = get_chroma_client(chroma_dir)
    name = collection_name_for_kb(workspace_id, knowledge_base_id)
    existing_names = {c.name for c in client.list_collections()}
    if name not in existing_names:
        return

    collection = client.get_collection(name=name)
    collection.delete(
        where={
            "$and": [
                {"workspace_id": workspace_id},
                {"source_id": source_id},
            ]
        }
    )
