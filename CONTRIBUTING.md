# Contributing to Sentinel-RAG

Thanks for considering a contribution. Sentinel-RAG is an evaluation,
diagnosis, adversarial-testing, and repair platform for RAG systems — not a
demo app — so contributions are held to research/production-quality bars:
real measurements, no fabricated numbers, and reproducible experiments.

## Development setup

```bash
git clone <your-fork-url>
cd sentinel-rag
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,embeddings]"
pre-commit install  # optional, if you use pre-commit locally
```

## Workflow

1. Open an issue describing the change before large PRs.
2. Write or update tests for any behavioral change (`tests/unit`,
   `tests/integration`, `tests/evaluation`, `tests/adversarial`, or
   `tests/property` as appropriate).
3. Run the full local gate before opening a PR:

   ```bash
   make check       # lint + type-check + unit/integration tests
   make evaluate     # deterministic golden-dataset evaluation
   ```

4. If you touch retrieval, generation, metrics, or the diagnosis/repair
   engines, run `make benchmark` and include the resulting
   `reports/latest.md` diff in your PR description so reviewers can see the
   measured effect.
5. Never hand-edit files under `experiments/results/` or `reports/` — they
   are generated. Regenerate them instead.

## Engineering principles this project enforces

- **No fabricated metrics.** Every number in a report, README, or PR
  description must come from an executed run. If something can't be
  measured, mark it `unavailable` and say why.
- **Provider-agnostic core.** New retrieval, embedding, or generation
  providers must implement the abstract interfaces in
  `sentinel.retrieval`, `sentinel.generation`, and `sentinel.adapters` —
  do not special-case a provider into shared code paths.
- **Deterministic CI path.** CI must be able to run entirely offline using
  the deterministic local provider. Anything that requires a paid API key
  must be optional and clearly gated.
- **Document decisions.** Non-obvious architectural choices belong in
  `docs/decisions/` as an ADR (see `docs/decisions/adr-template.md`).

## Code style

- Python 3.12+, type-hinted, formatted and linted with `ruff` (`make lint`).
- `mypy` must pass on `src/` (`make typecheck`).
- Keep modules small and single-purpose; prefer composition over inheritance
  for adapters and providers.

## Reporting security issues

See `SECURITY.md`. Do not open a public issue for a vulnerability.
