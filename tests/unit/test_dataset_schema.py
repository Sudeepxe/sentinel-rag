import pytest
from pydantic import ValidationError

from sentinel.schemas.dataset import DatasetCase, EvaluationDataset
from sentinel.schemas.documents import Document


def test_answerable_case_requires_reference_or_acceptable_answers():
    with pytest.raises(ValidationError):
        DatasetCase(id="c1", question="Q?", should_answer=True)


def test_unanswerable_case_rejects_reference_answer():
    with pytest.raises(ValidationError):
        DatasetCase(id="c1", question="Q?", should_answer=False, reference_answer="shouldn't be here")


def test_relevant_document_ids_must_exist_in_documents():
    with pytest.raises(ValidationError):
        DatasetCase(
            id="c1",
            question="Q?",
            documents=[Document(id="d1", text="text")],
            relevant_document_ids=["missing-doc"],
            reference_answer="answer",
        )


def test_valid_case_passes():
    case = DatasetCase(
        id="c1",
        question="Q?",
        documents=[Document(id="d1", text="text")],
        relevant_document_ids=["d1"],
        reference_answer="answer",
    )
    assert case.id == "c1"


def test_dataset_rejects_duplicate_case_ids():
    case_kwargs = {"question": "Q?", "reference_answer": "a"}
    with pytest.raises(ValidationError):
        EvaluationDataset(
            name="d", version="v1",
            cases=[DatasetCase(id="dup", **case_kwargs), DatasetCase(id="dup", **case_kwargs)],
        )


def test_empty_question_rejected():
    with pytest.raises(ValidationError):
        DatasetCase(id="c1", question="   ", reference_answer="a")
