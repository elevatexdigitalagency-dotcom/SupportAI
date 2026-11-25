from typing import List, Optional

from app.db.database import get_db


def retrieve_memories(
    message: str,
    mode: str,
    customer_id: Optional[str] = None,
    workspace_id: Optional[int] = None,
) -> List[dict]:
    words = {
        word.lower().strip(".,!?")
        for word in message.split()
        if len(word) > 3
    }
    if not words:
        return []

    with get_db() as db:
        if mode == "personal":
            if workspace_id is not None:
                rows = db.execute(
                    """
                    SELECT id, category, content
                    FROM memories
                    WHERE scope = 'personal' AND workspace_id = ?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (workspace_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT id, category, content
                    FROM memories
                    WHERE scope = 'personal'
                    ORDER BY id DESC
                    LIMIT 100
                    """
                ).fetchall()
        else:
            if not customer_id:
                return []
            if workspace_id is not None:
                rows = db.execute(
                    """
                    SELECT id, category, content
                    FROM memories
                    WHERE scope = 'support'
                      AND customer_id = ?
                      AND workspace_id = ?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (customer_id, workspace_id),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT id, category, content
                    FROM memories
                    WHERE scope = 'support'
                      AND customer_id = ?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (customer_id,),
                ).fetchall()

    scored = []
    for row in rows:
        text = f"{row['category']} {row['content']}".lower()
        score = sum(1 for word in words if word in text)
        if score > 0:
            scored.append((score, dict(row)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:5]]
