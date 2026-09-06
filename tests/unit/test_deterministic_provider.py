from sentinel.generation.deterministic import DeterministicLocalProvider
from sentinel.schemas.documents import Chunk
from sentinel.schemas.experiments import GenerationConfig
from sentinel.schemas.retrieval import RetrievalHit


def _hit(chunk_id: str, text: str, rank: int, score: float = 1.0) -> RetrievalHit:
    chunk = Chunk(id=chunk_id, document_id=chunk_id, text=text)
    return RetrievalHit(chunk=chunk, score=score, rank=rank)


def test_refuses_with_no_hits():
    provider = DeterministicLocalProvider()
    result = provider.generate("What is the refund window?", [], GenerationConfig())
    assert result.refused is True
    assert result.citations == []


def test_refuses_when_evidence_score_below_threshold():
    provider = DeterministicLocalProvider()
    hits = [_hit("c1", "Completely unrelated content about zebras and giraffes.", rank=1)]
    result = provider.generate("What is the refund window for annual plans?", hits, GenerationConfig())
    assert result.refused is True


def test_answers_and_cites_when_evidence_present():
    provider = DeterministicLocalProvider()
    hits = [
        _hit(
            "c1",
            "Refund Policy. Annual plan subscribers may request a full refund within 30 days of purchase.",
            rank=1,
        )
    ]
    result = provider.generate("What is the refund window for annual plans?", hits, GenerationConfig())
    assert result.refused is False
    assert len(result.citations) >= 1
    assert all(c.chunk_id == "c1" for c in result.citations)
    assert result.is_deterministic_local is True


def test_deterministic_across_repeated_calls():
    provider = DeterministicLocalProvider()
    hits = [_hit("c1", "Refund Policy. Annual plan subscribers may request a full refund within 30 days.", rank=1)]
    r1 = provider.generate("refund window", hits, GenerationConfig())
    r2 = provider.generate("refund window", hits, GenerationConfig())
    assert r1.answer_text == r2.answer_text
    assert r1.citations == r2.citations


def test_respects_max_context_chunks():
    provider = DeterministicLocalProvider()
    hits = [_hit(f"c{i}", f"Refund topic sentence number {i} about refund policy.", rank=i) for i in range(10)]
    config = GenerationConfig(max_context_chunks=2)
    result = provider.generate("refund policy", hits, config)
    cited_chunks = {c.chunk_id for c in result.citations}
    assert cited_chunks <= {"c0", "c1"}
