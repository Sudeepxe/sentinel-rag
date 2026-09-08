from sentinel.retrieval.retriever import HybridRetriever
from sentinel.schemas.documents import Chunk
from sentinel.schemas.experiments import RetrievalConfig


def _chunk(id_: str, text: str, source: str, **metadata: str) -> Chunk:
    return Chunk(id=id_, document_id=id_, text=text, source=source, metadata=metadata)


def test_metadata_filter_restricts_candidate_pool():
    chunks = [
        _chunk("a", "refund policy annual plans", source="policy-docs"),
        _chunk("b", "refund policy annual plans", source="community-forum"),
    ]
    retriever = HybridRetriever(
        chunks, config=RetrievalConfig(strategy="bm25", top_k=5, metadata_filter={"source": "policy-docs"})
    )
    result = retriever.retrieve("refund policy")
    assert [h.chunk.id for h in result.hits] == ["a"]


def test_metadata_filter_on_custom_metadata_field():
    chunks = [
        _chunk("a", "refund policy annual plans", source="docs", authority_tier="official"),
        _chunk("b", "refund policy annual plans", source="docs", authority_tier="draft"),
    ]
    retriever = HybridRetriever(
        chunks, config=RetrievalConfig(strategy="bm25", top_k=5, metadata_filter={"authority_tier": "official"})
    )
    result = retriever.retrieve("refund policy")
    assert [h.chunk.id for h in result.hits] == ["a"]


def test_no_metadata_filter_returns_all_matches():
    chunks = [
        _chunk("a", "refund policy annual plans", source="policy-docs"),
        _chunk("b", "refund policy annual plans", source="community-forum"),
    ]
    retriever = HybridRetriever(chunks, config=RetrievalConfig(strategy="bm25", top_k=5))
    result = retriever.retrieve("refund policy")
    assert {h.chunk.id for h in result.hits} == {"a", "b"}


def test_metadata_filter_matching_nothing_yields_empty_result():
    chunks = [_chunk("a", "refund policy annual plans", source="policy-docs")]
    retriever = HybridRetriever(
        chunks, config=RetrievalConfig(strategy="bm25", top_k=5, metadata_filter={"source": "nonexistent"})
    )
    result = retriever.retrieve("refund policy")
    assert result.hits == []
