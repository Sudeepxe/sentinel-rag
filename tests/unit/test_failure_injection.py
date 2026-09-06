"""Controlled fault injection (spec section 33): system-level failures
must be reported distinctly from model-quality failures, never silently
swallowed or conflated with a low score."""

from pathlib import Path

import pytest

from sentinel.experiments.runner import ExperimentRunner
from sentinel.generation.base import (
    GenerationProvider,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
)
from sentinel.generation.factory import register_provider
from sentinel.schemas.experiments import ExperimentConfig, GenerationConfig, RetrievalConfig
from sentinel.schemas.generation import GenerationOutput
from sentinel.storage.dataset_store import load_dataset

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class _AlwaysTimesOutProvider(GenerationProvider):
    name = "always_times_out"
    is_deterministic_local = True

    def generate(self, query, hits, config):
        raise ProviderTimeoutError("simulated provider timeout")


class _MalformedResponseProvider(GenerationProvider):
    name = "malformed_response"
    is_deterministic_local = True

    def generate(self, query, hits, config):
        raise ProviderMalformedResponseError("simulated malformed response")


register_provider("always_times_out", _AlwaysTimesOutProvider)
register_provider("malformed_response", _MalformedResponseProvider)


def test_provider_timeout_is_reported_as_case_error_not_a_silent_zero():
    config = ExperimentConfig(
        name="fault-injection-timeout",
        dataset_path=str(FIXTURES / "smoke_dataset.json"),
        retrieval=RetrievalConfig(),
        generation=GenerationConfig(provider="always_times_out"),
    )
    runner = ExperimentRunner()
    result, report = runner.run(config)
    assert result.num_cases == report.total_errors  # every case failed at the system level
    assert all(c.error and "ProviderTimeoutError" in c.error for c in report.case_results)


def test_malformed_response_is_reported_as_case_error():
    config = ExperimentConfig(
        name="fault-injection-malformed",
        dataset_path=str(FIXTURES / "smoke_dataset.json"),
        generation=GenerationConfig(provider="malformed_response"),
    )
    runner = ExperimentRunner()
    _, report = runner.run(config)
    assert report.total_errors == len(load_dataset(FIXTURES / "smoke_dataset.json").cases)


def test_empty_retrieval_index_does_not_crash():
    from sentinel.adapters.reference import ReferenceRAGAdapter

    adapter = ReferenceRAGAdapter()
    adapter.ingest([])
    retrieval = adapter.retrieve("anything")
    assert retrieval.hits == []
    generation = adapter.generate("anything", retrieval)
    assert generation.refused is True


def test_corrupt_dataset_json_raises_clear_validation_error(tmp_path):
    from sentinel.storage.dataset_store import DatasetValidationError

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not valid json")
    with pytest.raises(DatasetValidationError):
        load_dataset(bad_path)


def test_malformed_generation_output_missing_required_field_is_rejected():
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        GenerationOutput(refused=False, provider="x", model="y", latency_ms=1.0)  # missing answer_text
