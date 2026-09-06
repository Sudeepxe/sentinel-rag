from sentinel.retrieval.bm25 import BM25Index
from sentinel.schemas.documents import Chunk


def _chunk(id_: str, text: str) -> Chunk:
    return Chunk(id=id_, document_id=id_, text=text)


def test_bm25_ranks_exact_term_match_higher():
    chunks = [
        _chunk("a", "the quick brown fox jumps over the lazy dog"),
        _chunk("b", "refund policy annual plans thirty days"),
        _chunk("c", "completely unrelated content about weather patterns"),
    ]
    index = BM25Index(chunks)
    scores = index.score("refund policy")
    best = max(range(len(chunks)), key=lambda i: scores[i])
    assert chunks[best].id == "b"


def test_bm25_empty_index():
    index = BM25Index([])
    assert index.score("anything") == []


def test_bm25_no_query_overlap_scores_zero():
    chunks = [_chunk("a", "apples and oranges")]
    index = BM25Index(chunks)
    assert index.score("zebra giraffe")[0] == 0.0
