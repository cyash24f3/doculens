# Verification record

Tested locally with Python 3.12.14 and the exact environment in `requirements.lock`. The embedding identity is recorded in `embedding-model.json`.

## Public deployment — 28 September 2026

- Render Free demo: https://yash-doculens.onrender.com. Live question answering returns source excerpts and clickable document citations; query traces download locally without shared query storage.
- ONNX fp32 MiniLM on the server reproduced the published 66-question retrieval benchmark, including hybrid passage Recall@5 of 97.6% on the 41 answerable test questions.
- 39 local automated tests passed after adding coverage for optional backend metadata. The original remote CI run passed 38 tests and a Docker image build; the updated CI run is https://github.com/cyash24f3/doculens/actions/runs/36345236745.
- Upload/deletion/evaluation writes and shared trace reads are disabled in the public demo. The full private/local application retains these features.
- Free hosting sleeps after inactivity and uses temporary storage. This is a sample corpus portfolio demo, not a production SLA or a live remote-LLM evaluation.

## Completed

- **38 automated tests passed.** Coverage includes PDF page attribution, empty/encrypted/invalid inputs, chunk overlap, keyword/semantic/fused ranking contracts, stable tie ordering, filter-before-ranking behavior, immutable replacement, deletion cleanup, malformed generated citations, provider-error fallback, API validation, evaluation accounting, and hand-calculated token-cost estimates.
- The OpenAI-compatible HTTP request and Bedrock Converse request shapes were tested with mocked clients. No remote LLM was called.
- The actual pinned MiniLM model was downloaded and exercised on all 12 sample documents and 66 evaluation questions, across four retrieval/chunking configurations.
- A separate real-model check verified two-page PDF ingestion, correct source page metadata, normalized vectors, a token-budget warning for dense text, and a cited answer containing the expected 45-day example value.
- Full browser workflow passed: demo ingestion, a locally embedded question, citation inspection, original trace download, category filters, abstention, invalid UTF-8 upload, document replacement, explicit archived search, deletion cleanup, and a live evaluation run.
- All five pages fit a 390px mobile viewport without horizontal document overflow. Desktop and mobile screenshots were inspected. No JavaScript errors were observed in the acceptance workflow.
- Python linting and JavaScript syntax checks passed.
- Installed dependency consistency check passed (`pip check`).
- Docker Compose configuration validation passed.
- A Python wheel was built and checked for application modules, frontend assets, sample documents, and evaluation labels.

## Not established

- Docker was installed but its daemon was not available. The container image was not built or run in this workspace; configuration validation is not runtime validation.
- External LLM credentials/model endpoints were not configured. Provider adapters were contract-tested with mocks, not a live generated-answer quality evaluation.
- Remote CI has run successfully; see the deployment record above.
- Authentication, multitenant access controls, production availability, load/scaling behavior, independent human answer correctness, and robust prompt-injection resistance have not been established.
- Starlette's test client emits a deprecation warning about its current httpx adapter. Tests pass; dependency migration is a future maintenance item.

Passing tests is evidence about the implementation paths exercised, not a guarantee of accurate answers for arbitrary documents. Read `EVALUATION.md` for the actual statistical outcomes and limitations.
