from hypothesis import given
from hypothesis import strategies as st

from sentinel.metrics.retrieval import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k

_ID = st.text(alphabet="abcdefgh", min_size=1, max_size=3)


@given(st.lists(_ID, min_size=0, max_size=10), st.sets(_ID, max_size=5), st.integers(min_value=1, max_value=10))
def test_all_retrieval_metrics_are_bounded_0_1(retrieved, relevant, k):
    assert 0.0 <= recall_at_k(retrieved, relevant, k) <= 1.0
    assert 0.0 <= precision_at_k(retrieved, relevant, k) <= 1.0
    assert 0.0 <= hit_rate_at_k(retrieved, relevant, k) <= 1.0
    assert 0.0 <= mrr(retrieved, relevant) <= 1.0
    assert 0.0 <= ndcg_at_k(retrieved, relevant, k) <= 1.0


@given(st.lists(_ID, min_size=1, max_size=10, unique=True))
def test_recall_and_hit_rate_are_one_when_all_ids_relevant(ids):
    relevant = set(ids)
    assert recall_at_k(ids, relevant, k=len(ids)) == 1.0
    assert hit_rate_at_k(ids, relevant, k=len(ids)) == 1.0
