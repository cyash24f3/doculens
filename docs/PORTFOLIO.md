# Portfolio and interview guide

## What this project demonstrates

DocuLens joins document processing, learned embeddings, retrieval algorithms, backend APIs, evaluation, and usable source inspection in one reproducible application. It demonstrates an AI application workflow without making a particular industry the project theme.

## Five-minute demo

1. Show the original fictional sample library and its current versions.
2. Ask how many search requests per minute are permitted; open a citation and verify the value in the source.
3. Switch retrieval mode and inspect how ranking scores differ.
4. Ask an out-of-corpus question and show abstention, then discuss a near-topic question where the gate fails.
5. Upload a document, replace it with a new version, and show current-only versus archived retrieval.
6. Open Evaluation lab and compare semantic search with hybrid search honestly.
7. Inspect one multi-source question and one failed answerable question.
8. Show the API, trace export, tests, and model revision.

## Defensible resume wording

Use only after you have run and understood the application:

- “Built a document intelligence application with local sentence-transformer embeddings, BM25 and hybrid retrieval, source-level citations, and PDF/Markdown/text ingestion.”
- “Implemented immutable document versions, transactional index updates, archived-source filtering, deletion cleanup, and an evaluation harness with 66 labeled questions.”
- “Integrated optional OpenAI-compatible and Bedrock generation adapters with citation-schema validation, provider-error fallback, and configurable token-cost estimates.”

A result claim must name its scope: for example, passage Recall@5 on this authored fictional benchmark. It is not overall answer accuracy, independent real-world validation, or production performance.

Do not claim to have trained the pretrained embedding model, deployed a live Bedrock system without doing so, achieved perfect factual correctness, or built a production multitenant service. The adapter and a live provider deployment are different accomplishments.

## Questions worth preparing for

**Why hybrid retrieval?** Keyword search helps exact identifiers; embeddings help paraphrases. RRF combines ranks without treating raw BM25 and cosine scores as comparable. The benchmark can still favor semantic-only search.

**Why no FAISS?** Exact cosine search is adequate for this bounded local corpus. An ANN index adds consistency and tuning concerns that should be justified by scale and measured latency/recall.

**What does a citation prove?** It identifies the retrieved passage and version. It does not alone prove that generated prose is entailed by the source.

**What happens when a document changes?** Replacement archives the previous version and atomically inserts the new content/vectors. Current-only queries exclude the old version. Explicit archived queries can still find it.

**Can the system know a question is unanswerable?** The local gate estimates relevance heuristically. It has false positives and false negatives. Those limitations are reported explicitly.

**How is evaluation different from a demo?** The evaluator runs a fixed labeled set, checks known evidence, separates dev/test reporting, compares methods under the same corpus, and records per-question failures.

**What would production need?** Authentication, permissions, tenant isolation, durable background jobs, distributed locks, request limits, storage/retention policies, a scalable index, and independent human evaluation.

**How did AI assistance contribute?** Be straightforward that AI assisted the implementation. Understand the algorithms, inspect failures, run the tests, and make an independently explained extension before presenting the work in interviews.

## Useful personal extensions

Choose one, document the hypothesis, and reserve new evaluation questions:

- Add a reranker and measure quality, latency, and cost tradeoffs.
- Evaluate a real configured LLM against independent human judgments.
- Add OCR with a clearly isolated extraction boundary and scanned-page tests.
- Implement per-user document permissions enforced before retrieval.
- Add a new corpus from your own authorized documents and independently label questions.
