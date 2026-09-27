# Exports & portability

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Export formats

Document metadata can be exported as CSV. Query traces and evaluation results can be exported as JSON. Original uploaded documents keep their original file format when downloaded.

## Export contents

A document metadata export contains the document title, category, version, checksum, and upload timestamp. It does not contain user passwords or API tokens. Content exports must be stored only in locations approved for the underlying documents.

## Data ownership

Customers retain ownership of their uploaded documents. The service does not use uploaded content to train a shared model. Enabling an external language-model provider sends selected passages to that configured provider for answer generation.

## Sensitive data

The application does not automatically redact secrets or personal information from documents. Users must avoid uploading content they are not authorized to process. Deleting a local document cannot delete copies already exported to another system.

