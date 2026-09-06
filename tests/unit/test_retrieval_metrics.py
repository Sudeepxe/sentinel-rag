from sentinel.metrics.retrieval import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_recall_at_k_perfect():
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_recall_at_k_empty_relevant_is_vacuously_perfect():
    assert recall_at_k(["a"], set(), k=3) == 1.0


def test_precision_at_k():
    assert precision_at_k(["a", "b", "x", "y"], {"a", "b"}, k=4) == 0.5
    assert precision_at_k([], {"a"}, k=5) == 0.0


def test_hit_rate_at_k():
    assert hit_rate_at_k(["x", "a"], {"a"}, k=2) == 1.0
    assert hit_rate_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_mrr_first_hit_position():
    assert mrr(["x", "a", "b"], {"a"}) == 0.5
    assert mrr(["a"], {"a"}) == 1.0
    assert mrr(["x"], {"a"}) == 0.0


def test_ndcg_perfect_ordering_is_one():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0


def test_ndcg_worse_ordering_is_lower_than_perfect():
    perfect = ndcg_at_k(["a", "b"], {"a", "b"}, k=2)
    worse = ndcg_at_k(["c", "a", "b"], {"a", "b"}, k=3)
    assert worse < perfect
