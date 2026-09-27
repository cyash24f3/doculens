# Public demonstration deployment

The Render entrypoint is `public_demo:app`; the normal local app retains its complete functionality. Render's free plan sleeps when idle and resets local files on restart. Seed data is prepared during build, with no paid database or external inference provider. Never submit sensitive information to the public demo.

Shared uploads, deletion, model promotion, retraining, and evaluation mutations are blocked at the server boundary, not only hidden in the UI. Prediction/search/scenario routes remain live. Bodies are capped at 16 KiB; a global 120 POST/minute bound and two-request concurrency limit protect this small demonstration. These are demo controls, not enterprise tenant isolation.

DocuLens uses the same pinned MiniLM model through ONNX Runtime to fit the free instance. It does not retain query history; trace export is generated in the requesting browser. ServeWatch retains only the latest 5,000 numeric botanical predictions, visible as shared demo telemetry. Cloud AWS configuration remains separate from this free demonstration host.
