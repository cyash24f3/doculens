# API reference

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Authentication

API requests authenticate using a bearer token in the Authorization header. Tokens are created in Account settings and are displayed only once. A missing or invalid token returns HTTP 401.

## Rate limits

The search endpoint allows 120 requests per minute per workspace. Exceeding the limit returns HTTP 429 with a Retry-After header. Clients should wait for the indicated delay before retrying.

## Pagination

List endpoints accept a cursor and a limit parameter. The default page size is 25 records, and the maximum page size is 100 records. A next_cursor value of null means there are no more results.

## Idempotency

Document upload requests may include an Idempotency-Key header. Keys remain valid for 24 hours. Reusing a key with different file content returns HTTP 409.

