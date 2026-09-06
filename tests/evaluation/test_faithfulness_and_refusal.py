from sentinel.evaluation.faithfulness import MechanicalFaithfulnessJudge, compute_judge_disagreement
from sentinel.metrics.citation import Claim
from sentinel.metrics.refusal import RefusalOutcome, aggregate_refusal_metrics


def test_mechanical_judge_supports_grounded_claim():
    judge = MechanicalFaithfulnessJudge(threshold=0.28)
    claim = Claim(index=0, text="AES-256 is used for encryption")
    verdict = judge.judge(claim, ["Data is encrypted using AES-256 at rest."])
    assert verdict.supported is True


def test_mechanical_judge_rejects_ungrounded_claim():
    judge = MechanicalFaithfulnessJudge(threshold=0.28)
    claim = Claim(index=0, text="the moon is made of cheese")
    verdict = judge.judge(claim, ["Data is encrypted using AES-256 at rest."])
    assert verdict.supported is False


def test_judge_disagreement_requires_at_least_two_judges():
    assert compute_judge_disagreement({"a": []}) is None


def test_judge_disagreement_computed_correctly():
    from sentinel.evaluation.faithfulness import JudgeVerdict

    verdicts_a = [JudgeVerdict(claim_index=0, supported=True, confidence=1.0, reasoning="", judge_name="a")]
    verdicts_b = [JudgeVerdict(claim_index=0, supported=False, confidence=1.0, reasoning="", judge_name="b")]
    disagreement = compute_judge_disagreement({"a": verdicts_a, "b": verdicts_b})
    assert disagreement == 1.0


def test_refusal_outcome_labels():
    assert RefusalOutcome("c1", should_answer=False, refused=True).label == "correct_refusal"
    assert RefusalOutcome("c2", should_answer=True, refused=True).label == "false_refusal"
    assert RefusalOutcome("c3", should_answer=False, refused=False).label == "unsafe_answer"
    assert RefusalOutcome("c4", should_answer=True, refused=False).label == "correct_answer"


def test_aggregate_refusal_metrics_mixed_outcomes():
    outcomes = [
        RefusalOutcome("1", True, False),  # correct_answer
        RefusalOutcome("2", False, True),  # correct_refusal
        RefusalOutcome("3", True, True),  # false_refusal
        RefusalOutcome("4", False, False),  # unsafe_answer
    ]
    metrics = aggregate_refusal_metrics(outcomes)
    assert metrics["correct_refusal_rate"] == 0.5  # 1 of 2 should-refuse cases handled correctly
    assert metrics["false_refusal_rate"] == 0.5  # 1 of 2 should-answer cases wrongly refused
    assert metrics["unsafe_answer_rate"] == 0.5


def test_aggregate_refusal_metrics_empty_list():
    metrics = aggregate_refusal_metrics([])
    assert all(v is None for v in metrics.values())
