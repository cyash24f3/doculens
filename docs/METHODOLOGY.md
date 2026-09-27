# Retrieval and answer evaluation

## Extraction and chunking

Markdown headings become section metadata. Text files use a document section. PDF text extraction preserves actual 1-based page numbers; empty pages are reported and do not renumber later pages. The extractor does not promise reading-order or table reconstruction for arbitrary PDF layouts.

Default chunks contain at most 150 whitespace-delimited words with 25-word overlap when a section is longer than one window. Sections and pages are not merged in this strategy. Embeddings include document title, section heading, and passage text. The model has a subword-token budget, so unusually token-dense passages can still be truncated for semantic encoding; full passage text remains indexed for keyword search and displayed in citations.

The benchmark's alternative fixed strategy combines sections within each page before applying the same 150/25 windows. It does not merge PDF pages. This is a controlled illustrative chunking comparison, not an exhaustive optimization sweep.

## Keyword search

Tokens are lowercase alphanumeric sequences of length at least two, excluding a documented stopword set in `retrieval.py`. BM25 uses `k1 = 1.5` and `b = 0.75`, with IDF:

`log(1 + (N - df + 0.5) / (df + 0.5))`.

All metadata filters are applied first. Only passages with positive keyword scores enter the keyword ranking.

## Semantic search

The default model is `sentence-transformers/all-MiniLM-L6-v2`, pinned to the revision in the model manifest. Query and passage embeddings are normalized. Dot products then equal cosine similarity. Exact ranking is used rather than an approximate nearest-neighbor index.

A corpus containing vectors with a different fingerprint or missing vectors cannot participate in semantic/hybrid search until reindexed. There is no silent random-vector, hash-vector, or keyword fallback advertised as semantic search.

## Hybrid ranking

Reciprocal-rank fusion combines the first 30 candidates from keyword and semantic rankings:

`RRF(chunk) = sum(1 / (60 + rank_in_method))`.

A passage present in one method gets that method's contribution only. Stable filename/version/ordinal/text ordering resolves exact score ties, so regenerated random database IDs do not control tie outcomes. RRF scores are not probabilities and do not necessarily outperform a standalone retriever.

## Answerability and excerpts

The default relevance gate accepts a candidate with cosine similarity at least 0.40 and at least one non-stopword query token in its text/section. Without semantic vectors, keyword-only evidence needs at least two shared non-stopword tokens and at least 40% query-token coverage.

These are fixed heuristics, not learned classifiers or calibrated probabilities. A plausible passage can pass without answering a question; paraphrases can fail despite relevant evidence. Both false acceptance and false abstention appear in the benchmark.

Evidence mode selects up to four verbatim sentences from up to three eligible passages using lexical overlap. These are source excerpts, not comprehensive summaries. Cited source membership can be verified exactly, but a quote can still be irrelevant or incomplete.

## Generated answers

An optional provider receives the question and up to five eligible passages under explicit source identifiers. It must return an abstention flag or one to four statements with allowed citations. Empty statements, unknown citations, invalid JSON, and request failures trigger a labeled extractive fallback.

The application checks schema and source-ID validity, not semantic entailment. A real LLM's correctness, hallucination rate, and prompt-injection resistance require independent evaluation using that provider/model. The included local benchmark does not establish these properties.

## Question set

`sample_corpus/evaluation.json` contains 66 questions:

- Development: 16 questions (13 answerable, 3 unanswerable).
- Test: 50 questions (41 answerable, 9 unanswerable).
- Two test questions require evidence from multiple passages/documents.

Labels specify expected filenames and literal supporting substrings, plus expected answer terms for a simple proxy. They were authored from the original fictional corpus before the initial benchmark run. They are not independently human-reviewed and are not a representative sample of arbitrary user questions.

The evaluation only runs against unchanged sample source hashes and excludes user documents. The report records the label-set hash, corpus hashes, embedding revision, settings, and package versions. Reported latency depends on the machine, model loading, caching, and query order; it is not a production SLA.

## Metrics and denominators

- **Passage Recall@5:** for each answerable question, fraction of labeled evidence requirements matched by a top-five passage; macro-average over answerable questions. Both filename and expected supporting text must match.
- **MRR@5:** reciprocal position of the first matching passage, or zero; average over answerable questions. Multi-source completeness is captured by recall, not MRR.
- **Answerable response rate:** fraction of answerable questions that do not abstain. It does not imply their responses are correct.
- **Unanswerable abstention rate:** fraction of unanswerable questions that abstain. A non-abstaining extract may simply be irrelevant; this is not automatically a fabricated statement.
- **Answer-term coverage proxy:** fraction of expected lexical terms appearing in the displayed excerpts; macro-average over answerable questions. Negation, paraphrases, and superficial matches can invalidate this proxy as a correctness measure.
- **Verbatim quote fidelity:** fraction of displayed evidence statements that occur literally inside a cited passage. This is source membership, not relevance or factual truth.
- **p50/p95 latency:** observed local end-to-end retrieval and extractive answering times per question.

No overall “AI accuracy” score is claimed. Do not combine these distinct metrics into one unsupported accuracy percentage.

## Reproducibility and next steps

Run `doculens setup`, `doculens demo`, then `doculens evaluate`. Preserve the pinned model and dependency versions. Timing will vary; deterministic text rankings should not depend on random document IDs.

For a stronger next iteration, collect independent human labels, add document-version conflicts and realistic long documents, evaluate a specific LLM separately, and reserve new untouched questions before tuning retrieval/gating parameters. Adding more terminology or changing thresholds after inspecting the test set makes it development feedback rather than fresh validation.

## Primary implementation references

- [Sentence Transformers model API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
- [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [pypdf extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [Amazon Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
