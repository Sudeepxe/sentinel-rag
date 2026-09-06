"""Prometheus-compatible metrics, with a no-op fallback when
`prometheus_client` isn't installed so the core library never hard-depends
on it (spec section 35 metric names below).
"""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram

    _HAVE_PROMETHEUS = True
except ImportError:
    _HAVE_PROMETHEUS = False

    class _NoOpMetric:
        def labels(self, *_args: object, **_kwargs: object) -> _NoOpMetric:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            pass

        def observe(self, *_args: object, **_kwargs: object) -> None:
            pass

    def Counter(*_args: object, **_kwargs: object) -> _NoOpMetric:
        return _NoOpMetric()

    def Histogram(*_args: object, **_kwargs: object) -> _NoOpMetric:
        return _NoOpMetric()


evaluation_total = Counter("sentinel_evaluation_total", "Evaluations run", ["dataset", "config"])
evaluation_failure_total = Counter(
    "sentinel_evaluation_failure_total", "Evaluation failures by type", ["failure_type"]
)
retrieval_latency_ms = Histogram("sentinel_retrieval_latency_ms", "Retrieval latency", ["strategy"])
generation_latency_ms = Histogram("sentinel_generation_latency_ms", "Generation latency", ["provider"])
evaluation_latency_ms = Histogram("sentinel_evaluation_latency_ms", "Per-case evaluation latency")
retrieval_recall = Histogram("sentinel_retrieval_recall", "Recall@k values observed", ["k"])
citation_precision_metric = Histogram("sentinel_citation_precision", "Citation precision values observed")
citation_recall_metric = Histogram("sentinel_citation_recall", "Citation recall values observed")
faithfulness_metric = Histogram("sentinel_faithfulness", "Faithfulness scores observed")
refusal_accuracy = Histogram("sentinel_refusal_accuracy", "1.0 if refusal decision was correct, else 0.0")
attack_success_rate_metric = Histogram("sentinel_attack_success_rate", "Attack success rate observed", ["attack_class"])
