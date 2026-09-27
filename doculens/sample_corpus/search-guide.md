# Search & answer quality

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Retrieval modes

Keyword search is useful for exact identifiers, error codes, and product names. Semantic search can retrieve passages with similar meaning even when wording differs. Hybrid search combines keyword and semantic rankings using reciprocal-rank fusion.

## Citations

Every displayed citation points to a specific document passage, including its version and page or section. A citation proves where text was retrieved, not that a generated statement is necessarily correct. Users should inspect the cited evidence before acting on sensitive answers.

## Unanswerable questions

If the selected documents do not provide enough evidence, the assistant should say that it cannot answer from the available sources. It must not fill missing facts using guesses. Adding a relevant document may make the question answerable.

## Filters

Category and document filters are applied before retrieval ranking. Current-only search excludes archived document versions. Broader filters can increase recall while also introducing less relevant passages.

