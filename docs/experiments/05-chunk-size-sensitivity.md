# Experiment 5: Chunk Size Sensitivity

**Status:** run against `datasets/golden/v1.json`. Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Smaller chunks sharpen retrieval scoring (less irrelevant text diluting the match) but risk
splitting relevant context across a chunk boundary; larger chunks do the opposite. There should be
a visible tradeoff curve.

## Method

`chunk_size` in `{100, 200, 400, 800, 1200}` words (`chunk_overlap = min(50, chunk_size/4)`),
`hybrid_rrf`, `top_k=5`, otherwise identical config.

## Results

| chunk_size | recall@5 | MRR | nDCG@5 | citation_precision |
|---|---|---|---|---|
| 100 | 1.000 | 0.8270 | 0.9557 | 1.000 |
| 200 | 1.000 | 0.8270 | 0.9557 | 1.000 |
| 400 | 1.000 | 0.8270 | 0.9557 | 1.000 |
| 800 | 1.000 | 0.8270 | 0.9557 | 1.000 |
| 1200 | 1.000 | 0.8270 | 0.9557 | 1.000 |

## Interpretation

**No measurable sensitivity to chunk size** on this dataset — every value from 100 to 1200 words
produced identical results. The mechanical reason is straightforward and is reported rather than
hidden: golden-set source documents are short (single-paragraph policy/handbook entries, typically
30-80 words). Every configured `chunk_size` in this sweep is larger than every document in the
corpus, so **every configuration produces exactly one chunk per document** — chunk_size is, for
this dataset, a no-op above ~80 words. `long-001`/`long-002`/`long-003` add many *documents* to
stress retrieval-among-many-chunks, but none of the individual documents are long enough to need
*intra-document* splitting.

## Limitations

- This experiment, as measured, tells you about corpus document length more than about chunking
  strategy. It is included specifically to demonstrate that Sentinel does not fabricate a
  chunk-size effect that isn't there — a system genuinely showing zero sensitivity is a real and
  useful (if unglamorous) finding: it tells an operator "your chunk_size knob won't matter until
  your source documents are longer than ~1200 words."
- A meaningful chunk-size sensitivity experiment needs a corpus with multi-paragraph source
  documents (1000+ words) where a single answer-bearing sentence can be diluted by surrounding
  unrelated content at large chunk sizes, or split across a boundary at small ones. This is called
  out as a v1.1 dataset gap rather than papered over with synthetic long documents built to force a
  particular result.
