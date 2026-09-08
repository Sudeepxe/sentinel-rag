"""OpenTelemetry tracing for the dataset-case -> retrieval -> generation ->
evaluation -> diagnosis -> repair -> experiment chain (spec section 28).

No-op if `opentelemetry-sdk` isn't installed (`pip install
sentinel-rag[observability]`), matching the pattern in
`sentinel.observability.metrics` — the core library has no hard
dependency on it, and every trace produced is a real span over real work,
never a fabricated one.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

try:
    from opentelemetry import trace as _otel_trace

    _tracer = _otel_trace.get_tracer("sentinel-rag")
    _HAVE_OTEL = True
except ImportError:
    _tracer = None
    _HAVE_OTEL = False


@contextmanager
def span(span_name: str, **attributes: str | int | float | bool) -> Iterator[None]:
    """Usage: `with span("retrieval", strategy=config.strategy): ...`

    `span_name` (not `name`) avoids colliding with an `attributes` key
    literally called "name" (e.g. `span("experiment", name=config.name)`),
    which previously raised "got multiple values for argument 'name'" —
    caught by the integration/CLI/failure-injection tests that actually
    exercise ExperimentRunner.run end to end.

    Attribute values must be primitive (str/int/float/bool) per the OTel
    spec; pass ids/labels, never raw evidence text or secrets (see
    docs/security/threat-model.md's safe-logging requirement).
    """
    if not _HAVE_OTEL or _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(span_name) as otel_span:
        for key, value in attributes.items():
            otel_span.set_attribute(key, value)
        yield


def tracing_enabled() -> bool:
    return _HAVE_OTEL
