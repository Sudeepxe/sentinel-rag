import numpy as np

from sentinel.retrieval.fusion import mmr_select, reciprocal_rank_fusion


def test_rrf_combines_two_rankings():
    ranking_a = ["x", "y", "z"]
    ranking_b = ["y", "x", "z"]
    fused = reciprocal_rank_fusion([ranking_a, ranking_b])
    # y is rank 2 then rank 1 (sum highest), x is rank1 then rank2 -> tie expected close;
    # both x and y should outrank z regardless.
    assert fused["z"] < fused["x"]
    assert fused["z"] < fused["y"]


def test_rrf_requires_matching_weights_length():
    import pytest

    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0])


def test_mmr_select_prefers_diverse_candidates():
    vectors = {
        "a": np.array([1.0, 0.0]),
        "b": np.array([0.99, 0.01]),  # near-duplicate of a
        "c": np.array([0.0, 1.0]),  # distinct
    }
    relevance = {"a": 1.0, "b": 0.95, "c": 0.5}
    selected = mmr_select(["a", "b", "c"], relevance, vectors, top_k=2, lambda_mult=0.5)
    assert selected[0] == "a"
    assert "c" in selected  # diversity should pull in the distinct vector over the near-duplicate
