# Indexing & document versions

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Chunking

The default chunker respects section and page boundaries. A chunk targets 150 words with a 25-word overlap. Small sections remain independent rather than being merged across headings.

## Version replacement

Replacing a document creates a new immutable version. The prior version becomes archived and is excluded from current-only search. Archived versions remain available only when the reader explicitly includes archived content.

## Reindexing

Changing the embedding model requires reindexing all document vectors. Existing vectors remain searchable until a complete replacement index is ready. Vectors from different embedding models must never be compared directly.

## Extraction limitations

PDF extraction preserves page numbers but cannot reliably reconstruct every table or multicolumn layout. A page with no extractable text is reported to the uploader. Documents should be inspected after extraction when layout carries meaning.

