"""Deterministic text chunking with stable content-derived identifiers."""
from __future__ import annotations
import hashlib
from aegis_ai.knowledge.contracts import KnowledgeChunk, KnowledgeDocument

def chunk_document(document: KnowledgeDocument, *, chunk_size: int = 1_200, overlap: int = 160) -> tuple[KnowledgeChunk, ...]:
    """Split text on paragraph/sentence boundaries where practical."""
    if not 200 <= chunk_size <= 2_000:
        raise ValueError("chunk_size must be between 200 and 2000")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    text = " ".join(document.content.split())
    if not text:
        raise ValueError("document content cannot be blank")
    chunks: list[KnowledgeChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("; ", start, end))
            if boundary >= start + chunk_size // 2:
                end = boundary + 1
        content = text[start:end].strip()
        if content:
            digest = hashlib.sha256(f"{document.document_id}:{len(chunks)}:{content}".encode("utf-8")).hexdigest()[:24]
            chunks.append(KnowledgeChunk(
                tenant_id=document.tenant_id, chunk_id=f"kc-{digest}",
                document_id=document.document_id, title=document.title, source=document.source,
                content=content, chunk_index=len(chunks), source_uri=document.source_uri,
                classification=document.classification, updated_at=document.updated_at,
            ))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return tuple(chunks)
