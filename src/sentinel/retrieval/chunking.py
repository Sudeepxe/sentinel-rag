"""Deterministic word-based chunking with configurable size/overlap."""

from __future__ import annotations

from sentinel.schemas.documents import Chunk, Document


def chunk_document(document: Document, chunk_size: int = 400, chunk_overlap: int = 50) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    words = document.text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    step = chunk_size - chunk_overlap
    position = 0
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        body = " ".join(words[start:end])
        # Prepend the document title to every chunk: titles carry
        # high-value keywords (e.g. "Refund Policy") that may not repeat
        # in the body, and omitting them caused real, measured false
        # refusals in the deterministic provider's evidence-coverage check.
        text = f"{document.title}. {body}" if document.title else body
        chunks.append(
            Chunk(
                id=f"{document.id}::chunk{position}",
                document_id=document.id,
                text=text,
                position=position,
                document_title=document.title,
                source=document.source,
                authority=document.authority,
                timestamp=document.timestamp,
                is_adversarial=document.is_adversarial,
                metadata=document.metadata,
            )
        )
        position += 1
        if end == len(words):
            break
        start += step
    return chunks


def chunk_documents(documents: list[Document], chunk_size: int = 400, chunk_overlap: int = 50) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in documents:
        chunks.extend(chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return chunks
