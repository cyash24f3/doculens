# Measured benchmark results

These values were produced by the delivered code and pinned local MiniLM model. The corpus contains 12 original fictional documents. The 50-question test split contains 41 answerable and 9 unanswerable questions. Labels were authored with the project, not independently human-reviewed.

## Test split

| Configuration | Passage Recall@5 | MRR@5 | Unanswerable abstention | Answerable response rate | Answer-term proxy |
|---|---:|---:|---:|---:|---:|
| keyword-section | 92.7% | 0.898 | 77.8% | 85.4% | 78.0% |
| semantic-section | 100.0% | 1.000 | 77.8% | 85.4% | 82.9% |
| hybrid-section | 97.6% | 0.947 | 77.8% | 85.4% | 80.5% |
| hybrid-fixed | 100.0% | 0.947 | 88.9% | 63.4% | 56.1% |

The full report, including both development/test splits, latencies, source hashes, and every question's retrieved evidence, is in [evaluation-results.json](evaluation-results.json).

## What the results support

Semantic retrieval finds the labeled evidence very well on this small authored corpus. Hybrid search is not uniformly better than semantic search. Fixed-window chunking can retrieve broad relevant context while producing less useful selected excerpts and more false abstentions. Retrieval quality and answer quality are distinct.

Verbatim quote fidelity is 100% here because local evidence statements are selected directly from source passages. That does not imply perfect relevance, completeness, or factual correctness of a generated answer.

## Known failures remain visible

- Some answerable questions receive no evidence answer because the conservative similarity/token-overlap gate rejects their passages. An example is the question about handling HTTP 429: retrieval finds the relevant API passage, but the gate can still reject it.
- Some near-topic unanswerable questions receive excerpts rather than abstention. A missing price or a request for a credit-card number can retrieve related billing text without containing the requested fact.
- Expected-term coverage can count superficial lexical matches and miss valid paraphrases. It is not an accuracy score.
- The benchmark does not measure a remote LLM: all evaluated answers use local extraction.

The search/gating parameters were not tuned to maximize the displayed test scores. Stable tie ordering was corrected as a reproducibility issue; the report was regenerated with the delivered implementation. Use new independent questions before tuning against this test set.

## Reproduce

```bash
doculens setup
doculens demo
doculens evaluate --output data/evaluation.json
```

Run this against the unmodified sample corpus and pinned model/dependency versions. Latency differs by machine, cache state, and model loading. Evaluate your own corpus and user questions before relying on the system operationally.
