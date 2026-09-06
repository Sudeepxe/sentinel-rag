from sentinel.metrics.citation import (
    check_citations,
    citation_precision,
    citation_recall,
    extract_claims,
    lexical_support_score,
    unsupported_claims,
)


def test_extract_claims_keeps_citation_attached_to_its_own_sentence():
    """Regression test: citation tags must not shift onto the following
    sentence when the whole answer is re-split for claim extraction."""
    answer = (
        "Refund Policy. [doc-a::chunk0] Annual plan subscribers may request a full refund "
        "within 30 days of purchase. [doc-a::chunk0] Monthly plans are non-refundable. "
        "[doc-a::chunk0]"
    )
    claims = extract_claims(answer)
    assert len(claims) == 3
    for claim in claims:
        assert claim.inline_citation_ids == ["doc-a::chunk0"]
        assert "[" not in claim.text and "]" not in claim.text


def test_extract_claims_handles_no_citations():
    claims = extract_claims("The sky is blue. Water is wet.")
    assert [c.text for c in claims] == ["The sky is blue.", "Water is wet."]
    assert all(c.inline_citation_ids == [] for c in claims)


def test_lexical_support_score_full_overlap():
    assert lexical_support_score("the cat sat on the mat", "cat sat mat") == 1.0


def test_lexical_support_score_no_overlap():
    assert lexical_support_score("completely unrelated text here", "cat sat mat") == 0.0


def test_check_citations_flags_unsupported_claim():
    claims = extract_claims("Northwind uses AES-256 encryption. [doc-1] Cats are mammals. [doc-1]")
    chunks_by_id = {"doc-1": "Northwind Cloud encrypts data at rest using AES-256."}
    checks = check_citations(claims, [], chunks_by_id)
    assert checks[0].supported is True
    assert checks[1].supported is False
    unsupported = unsupported_claims(checks)
    assert len(unsupported) == 1
    assert "Cats" in unsupported[0].text


def test_citation_precision_and_recall_all_supported():
    claims = extract_claims("AES-256 is used. [doc-1]")
    chunks_by_id = {"doc-1": "Data is encrypted using AES-256."}
    checks = check_citations(claims, [], chunks_by_id)
    assert citation_precision(checks) == 1.0
    assert citation_recall(checks) == 1.0


def test_citation_metrics_none_when_no_claims():
    assert citation_precision([]) is None
    assert citation_recall([]) is None
