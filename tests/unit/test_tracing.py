"""Verifies span() never raises and behaves consistently with
tracing_enabled(), whether or not opentelemetry-sdk is installed in the
current environment (spec section 28: real tracing when available, a
harmless no-op otherwise — never a fabricated trace)."""

from sentinel.observability.tracing import span, tracing_enabled


def test_span_context_manager_does_not_raise():
    with span("unit-test-span", case_id="abc", k=5, ratio=0.5, ok=True):
        pass


def test_span_propagates_exceptions_from_the_body():
    import pytest

    with pytest.raises(ValueError), span("unit-test-span-error"):
        raise ValueError("boom")


def test_tracing_enabled_is_a_bool():
    assert isinstance(tracing_enabled(), bool)


def test_nested_spans_do_not_raise():
    with span("outer", case_id="c1"), span("inner", step="retrieval"):
        pass
