# Deployment runbook

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Release checks

Before deployment, the release engineer must confirm that unit tests, integration tests, and database migration checks pass. The release must include a rollback image tag. Production releases require approval from a second engineer.

## Rollout

The standard rollout starts with a 10 percent canary for 15 minutes. Continue only if the API error rate remains below 1 percent and p95 latency stays below 800 milliseconds. Otherwise stop the rollout and investigate.

## Rollback

Rollback restores the last known healthy application image. Database migrations must remain backward compatible for one release. A rollback does not automatically reverse database migrations.

## Health checks

The readiness endpoint is /health/ready and verifies database connectivity. The liveness endpoint is /health/live and verifies that the process is responsive. A process can be live while not ready to accept requests.

