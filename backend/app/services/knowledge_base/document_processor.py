import hashlib
import ipaddress
import re
import socket
import uuid
from pathlib import Path
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from docx import Document as DocxDocument
from lxml import html as lxml_html
from pypdf import PdfReader

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(filename: str, content: bytes) -> Tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT, MD."
        )
    if not content:
        raise ValueError("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 10 MB upload limit.")
    safe_name = f"{uuid.uuid4().hex}{ext}"
    return ext, safe_name


def save_workspace_upload(workspace_id: int, safe_filename: str, content: bytes) -> Path:
    ws_dir = settings.uploads_dir / f"ws_{workspace_id}"
    ws_dir.mkdir(parents=True, exist_ok=True)
    target = (ws_dir / safe_filename).resolve()
    if ws_dir.resolve() not in target.parents:
        raise ValueError("Invalid upload path.")
    target.write_bytes(content)
    return target


def extract_text_from_file(file_path: Path, ext: str) -> str:
    if ext == ".pdf":
        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
    elif ext == ".docx":
        doc = DocxDocument(str(file_path))
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = "\n".join(parts)
    elif ext in {".txt", ".md"}:
        raw = file_path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        raise ValueError("No readable text could be extracted from the document.")
    return cleaned


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must start with http:// or https:// and include a valid host.")

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        raise ValueError("Local or internal network URLs are not allowed.")

    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            ip_str = info[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
            ):
                raise ValueError("Private or internal IP addresses cannot be crawled.")
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve hostname '{hostname}'.") from exc

    return parsed.geturl()


def _extract_html_text_and_links(raw_html: str, base_url: str) -> Tuple[str, str, List[str]]:
    tree = lxml_html.fromstring(raw_html)
    for bad in tree.xpath("//script|//style|//noscript|//svg|//footer|//nav"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    title_nodes = tree.xpath("//title/text()")
    title = title_nodes[0].strip() if title_nodes and title_nodes[0].strip() else base_url

    text = "\n".join(
        line.strip()
        for line in tree.text_content().splitlines()
        if line.strip()
    )

    parsed_base = urlparse(base_url)
    links: List[str] = []
    for href in tree.xpath("//a/@href"):
        joined = urljoin(base_url, href).split("#")[0]
        parsed_link = urlparse(joined)
        if (
            parsed_link.scheme in {"http", "https"}
            and parsed_link.netloc == parsed_base.netloc
        ):
            links.append(joined)

    return title, text, links


def crawl_website(url: str, max_pages: int = 3) -> Tuple[str, str]:
    start_url = _validate_public_url(url)
    max_pages = max(1, min(max_pages, 5))

    visited: Set[str] = set()
    queue: List[str] = [start_url]
    collected_parts: List[str] = []
    page_title = start_url

    headers = {"User-Agent": "SupportAI-Crawler/2.0 (+https://supportai.local)"}
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        while queue and len(visited) < max_pages:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            try:
                _validate_public_url(current)
                resp = client.get(current)
                if resp.status_code >= 400:
                    continue
                content_type = resp.headers.get("content-type", "").lower()
                if "html" not in content_type and "text/plain" not in content_type:
                    continue
            except Exception:
                if len(visited) == 1:
                    raise
                continue

            if "text/plain" in content_type:
                text = resp.text.strip()
                if text:
                    collected_parts.append(f"Source: {current}\n{text}")
                continue

            title, text, links = _extract_html_text_and_links(resp.text, current)
            if len(visited) == 1:
                page_title = title
            if text:
                collected_parts.append(f"Page: {title} ({current})\n{text}")
            for link in links:
                if link not in visited and link not in queue and len(visited) + len(queue) < max_pages * 2:
                    queue.append(link)

    combined = "\n\n---\n\n".join(collected_parts).strip()
    if not combined:
        raise ValueError("No readable text content could be extracted from the URL.")
    return page_title, combined


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: List[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            split_at = normalized.rfind("\n", start + chunk_size // 2, end)
            if split_at == -1:
                split_at = normalized.rfind(". ", start + chunk_size // 2, end)
            if split_at == -1:
                split_at = normalized.rfind(" ", start + chunk_size // 2, end)
            if split_at > start:
                end = split_at + 1
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks
