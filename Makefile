.PHONY: install dev lint typecheck security test test-unit test-integration test-adversarial \
        check dataset evaluate benchmark attack experiments reproduce serve api docker-build \
        docker-up clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

dev: install
	$(PIP) install -e ".[dev,embeddings,providers,observability]"

lint:
	$(VENV)/bin/ruff check src tests scripts

format:
	$(VENV)/bin/ruff format src tests scripts

typecheck:
	$(VENV)/bin/mypy src/sentinel

security:
	$(VENV)/bin/bandit -c pyproject.toml -r src/sentinel -q

test:
	$(VENV)/bin/pytest tests/ -q

test-unit:
	$(VENV)/bin/pytest tests/unit tests/property tests/evaluation -q

test-integration:
	$(VENV)/bin/pytest tests/integration -q

test-adversarial:
	$(VENV)/bin/pytest tests/adversarial -q

check: lint typecheck security test

dataset:
	$(PY) scripts/build_golden_dataset.py

evaluate:
	$(VENV)/bin/sentinel evaluate --config configs/experiments/baseline.yaml

benchmark:
	$(VENV)/bin/sentinel benchmark --config configs/experiments/baseline.yaml

attack:
	$(VENV)/bin/sentinel attack generate --dataset datasets/golden/v1.json --out /tmp/attacks.json
	$(VENV)/bin/sentinel attack run --attacks /tmp/attacks.json

experiments:
	$(PY) scripts/run_all_experiments.py

reproduce: check dataset benchmark experiments
	@echo "Reproduced: lint/typecheck/security/tests passed, dataset regenerated, benchmark + experiments re-run."

serve:
	$(VENV)/bin/uvicorn sentinel.api.main:app --reload --port 8000

docker-build:
	docker build -t sentinel-rag:latest .

docker-up:
	docker compose up --build

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
