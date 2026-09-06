from pathlib import Path

from typer.testing import CliRunner

from sentinel.cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_dataset_validate_success():
    result = runner.invoke(app, ["dataset", "validate", str(FIXTURES / "smoke_dataset.json")])
    assert result.exit_code == 0
    assert "VALID" in result.stdout


def test_dataset_validate_missing_file_exits_nonzero():
    result = runner.invoke(app, ["dataset", "validate", "does/not/exist.json"])
    assert result.exit_code != 0


def test_dataset_validate_json_format():
    result = runner.invoke(app, ["dataset", "validate", str(FIXTURES / "smoke_dataset.json"), "--format", "json"])
    assert result.exit_code == 0
    assert '"valid": true' in result.stdout


def test_evaluate_smoke_dataset_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--config",
            str(Path(__file__).resolve().parent.parent.parent / "configs/experiments/baseline.yaml"),
            "--dataset",
            str(FIXTURES / "smoke_dataset.json"),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "experiment_id" in result.stdout


def test_doctor_reports_missing_golden_dataset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor", "--format", "json"])
    assert result.exit_code == 1
    assert "golden_dataset_present" in result.stdout
