"""Property-based tests using Hypothesis for the citation/claim extraction
machinery, which historically had an off-by-one bug (see
tests/unit/test_citation_metrics.py's regression test) — property testing
is well-suited to catching boundary issues like that across many shapes."""

from hypothesis import given
from hypothesis import strategies as st

from sentinel.metrics.citation import extract_claims

_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
_CHUNK_ID = st.text(alphabet="abcdefghij0123456789-_", min_size=1, max_size=12)


@st.composite
def cited_sentences(draw):
    n = draw(st.integers(min_value=1, max_value=5))
    parts = []
    for _ in range(n):
        words = draw(st.lists(_WORD, min_size=1, max_size=6))
        cid = draw(_CHUNK_ID)
        parts.append(f"{' '.join(words).capitalize()}. [{cid}]")
    return " ".join(parts), n


@given(cited_sentences())
def test_every_synthetic_sentence_keeps_exactly_one_citation(data):
    text, n_sentences = data
    claims = extract_claims(text)
    assert len(claims) == n_sentences
    for claim in claims:
        assert len(claim.inline_citation_ids) == 1
        assert "[" not in claim.text
        assert "]" not in claim.text


@given(st.text())
def test_extract_claims_never_raises_on_arbitrary_text(text):
    extract_claims(text)  # must not raise regardless of input shape


@given(st.lists(_WORD, min_size=0, max_size=20))
def test_extract_claims_on_no_punctuation_text_returns_at_most_one_claim(words):
    text = " ".join(words)
    claims = extract_claims(text)
    assert len(claims) <= 1
