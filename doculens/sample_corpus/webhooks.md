# Webhook integration

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Event types

The service emits document.created, document.replaced, and document.deleted webhook events. Every event includes an event_id, workspace_id, and created_at timestamp. Event delivery order is not guaranteed.

## Delivery retries

A webhook receiver must respond with a 2xx status code within 5 seconds. Failed deliveries are retried after 1 minute, 5 minutes, 30 minutes, and 2 hours. After the final failed retry, the event is marked undelivered.

## Signature verification

Webhook payloads are signed using HMAC-SHA256. The signature is sent in the X-Atlas-Signature header. Receivers must verify the signature against the raw request body before parsing or processing the event.

## Duplicate events

Webhook consumers must deduplicate using event_id. Retried deliveries reuse the original event_id. A successful response should be returned for an already processed event.

