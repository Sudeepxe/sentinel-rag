# Experiment 4: Query Rewriting Strategies

**Status:** run against `datasets/golden/v1.json`. Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Per spec/design intent, **no strategy is assumed better a priori** — this experiment exists
specifically to measure, not assume, whether query rewriting helps
(`sentinel/retrieval/query_rewrite.py`).

## Method

Five `RetrievalConfig.query_rewrite` values (`none`, `expansion`, `hyde`, `decompose`, `keyword`)
against `hybrid_rrf`, `top_k=5`, otherwise identical config.

## Results

| strategy | recall@5 | MRR | nDCG@5 | latency (ms) | latency vs. none |
|---|---|---|---|---|---|
| none | 1.000 | 0.8270 | 0.9557 | 0.108 | — |
| expansion | 1.000 | 0.8270 | 0.9557 | 0.130 | +20% |
| hyde (local proxy) | 1.000 | 0.8270 | 0.9557 | 0.193 | +79% |
| decompose | 1.000 | 0.8270 | 0.9557 | 0.128 | +18% |
| keyword | 1.000 | 0.8270 | 0.9557 | 0.185 | +71% |

## Interpretation

**None of the four rewriting strategies changed a single retrieval metric** on this dataset —
every strategy produced byte-identical recall/MRR/nDCG to no rewriting at all, while adding
18-79% latency overhead (HyDE's local proxy and keyword extraction cost the most, since both
issue a second scored query against the index). This is a genuine, unflattering result and is
reported as such rather than omitted: **on this dataset, query rewriting is pure overhead**.

The most likely explanation is that all four rewrite strategies here are triggered by fixed
heuristics (a domain-synonym dictionary, sentence-splitting on conjunctions, top-TF keyword
extraction, or a templated "hypothetical answer") that only fire when the query contains specific
trigger patterns (domain synonyms, "and"/semicolons, question words) the golden set's questions
mostly don't contain, or when they do fire, produce a rewritten query variant that scores no
better than the original against an already-easy retrieval target (see Experiment 1's ceiling
discussion).

## Limitations

- `hyde` here is a **local templated proxy** ("The answer relates to `<keywords>`"), not an
  LLM-generated hypothetical answer — the actual HyDE technique from the literature. A real-LLM
  HyDE (swap in `OpenAIProvider`/`AnthropicProvider` to generate the hypothetical passage) could
  behave very differently and is not measured here; this is stated plainly rather than implied.
- Domain-synonym expansion only fires for a small hardcoded glossary
  (`_DOMAIN_SYNONYMS` in `query_rewrite.py`); it was not tuned against this specific dataset's
  vocabulary, by design (tuning it to the benchmark would make the benchmark meaningless — see
  `datasets/golden/README.md`).
- This is a negative result on a small, mostly-unambiguous dataset. It should not be read as "query
  rewriting never helps" — only "these four heuristic implementations did not help on these 53
  cases." Semantic retrieval case `sem-005` was specifically designed to need paraphrase bridging;
  even there, the underlying corpus is small enough that hybrid retrieval already finds the answer
  without rewriting.
