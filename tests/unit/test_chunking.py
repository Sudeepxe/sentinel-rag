import pytest

from sentinel.retrieval.chunking import chunk_document
from sentinel.schemas.documents import Document


def test_chunk_document_respects_size_and_overlap():
    doc = Document(id="d1", title="", text=" ".join(f"word{i}" for i in range(100)))
    chunks = chunk_document(doc, chunk_size=30, chunk_overlap=10)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text.split()) <= 30
    assert chunks[0].document_id == "d1"
    assert chunks[0].id == "d1::chunk0"


def test_chunk_document_prepends_title():
    doc = Document(id="d1", title="Refund Policy", text="Some body text.")
    chunks = chunk_document(doc, chunk_size=100, chunk_overlap=10)
    assert chunks[0].text.startswith("Refund Policy.")


def test_chunk_document_empty_text_returns_no_chunks():
    doc = Document(id="d1", title="Empty", text="")
    assert chunk_document(doc) == []


def test_chunk_document_rejects_overlap_ge_size():
    doc = Document(id="d1", text="a b c")
    with pytest.raises(ValueError):
        chunk_document(doc, chunk_size=10, chunk_overlap=10)
