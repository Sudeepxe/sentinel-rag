# Faithfulness and Citation Evaluation

"Faithfulness" asks: are the claims in the generated answer supported by the retrieved evidence?
"Citation correctness" asks the narrower, more mechanical question: does the *specific chunk cited*
for a claim actually support that claim? Sentinel-RAG evaluates both, with every score explicitly
labeled by the method that produced it.

## Claim extraction

`sentinel.metrics.citation.extract_claims` splits an answer into claim units at sentence
boundaries, with one deliberate refinement: a sentence boundary immediately followed by a citation
bracket (`"Sentence. [chunk_id] Next sentence."`) does **not** split before the bracket — it splits
after it. Without this, naive sentence-splitting shifts every citation onto the following claim by
one position. This was a real bug found while building the deterministic provider (see
`tests/unit/test_citation_metrics.py`'s regression test and
`tests/property/test_citation_properties.py`'s property-based coverage of the same invariant) —
not a hypothetical edge case description, an actual defect this project shipped and then fixed.

## Mechanical layer (`MechanicalFaithfulnessJudge`, `lexical_support_score`)

`lexical_support_score(chunk_text, claim_text)` computes the overlap coefficient — token overlap
relative to the *claim's* token count, not Jaccard — between a chunk and a claim. This asymmetry is
deliberate: a long chunk fully containing a short claim's key terms should score as fully
supporting, even though the chunk also contains lots of unrelated text (Jaccard would penalize this
via a large union). A claim is "supported" if the best-scoring evidence chunk clears a threshold
(default 0.28).

**Known false positives:** two unrelated sentences sharing several common words (e.g., both
mentioning "customer," "support," and "policy") can exceed the threshold without one actually
entailing the other. **Known false negatives:** a claim that correctly paraphrases evidence using
different words (e.g., "the ticket gets closed" vs. "the ticket is resolved") will score low despite
being faithful, since the metric has no notion of synonymy.

## LLM-judge layer (`LLMFaithfulnessJudge`)

Interface and a versioned prompt (`JUDGE_PROMPT_VERSION = "faithfulness-judge-v1"`,
`sentinel.generation.prompts.JUDGE_SYSTEM_PROMPT`/`JUDGE_USER_TEMPLATE`) are implemented; the actual
model call inside `.judge()` raises `NotImplementedError` pointing at this document, rather than a
half-wired implementation that would produce plausible-but-meaningless numbers without a
real backing model. Prompt versioning exists because judge scores are prompt-sensitive: changing
the prompt's wording without bumping the version would silently invalidate any historical
comparison against scores produced under the old prompt.

**Documented biases** (to weigh once a real judge is wired in): judges tend toward leniency on
fluent-sounding unsupported claims and can be stricter on terse-but-correct ones; using the same
model family as both generator and judge inflates apparent faithfulness (self-preference bias) —
prefer a different vendor/model as judge than as generator. `compute_judge_disagreement` is
provided for exactly the case of running multiple judges and wanting to see where they disagree
rather than averaging disagreement away.

## Citation precision and recall

Given per-claim citation checks (`CitationCheck`):

- **citation_precision** = fraction of *cited* claims whose citation actually supports them.
- **citation_recall** = fraction of *all* claims that end up supported (cited + supporting).

Both are `None` (method=`"unavailable"`) when the case was refused, rather than a misleading 0 or
1 — a refused case has no claims to check citations against at all.

## Reading a faithfulness score honestly

A `faithfulness: 1.0 [mechanical]` result in a report means "every claim cleared the lexical-overlap
bar against the evidence it was shown" — it does not mean "a human or a strong LLM would agree the
answer is fully faithful." Treat mechanical scores as a floor signal for CI gating and quick
iteration, and the LLM-judge layer (once wired to a real provider) as the higher-fidelity but
costlier and less reproducible check for release-quality validation.
