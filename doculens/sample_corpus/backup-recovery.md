# Backup & recovery

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Backup schedule

The database receives a full backup every day at 02:00 UTC. Incremental backups are captured every 15 minutes. Backup storage is encrypted and kept in a separate account.

## Recovery targets

The documented recovery point objective is 15 minutes. The recovery time objective is 4 hours. These are planning targets, not a guarantee that every incident will meet them.

## Restore validation

A restore exercise is performed once per quarter. The operator verifies row counts, document checksums, and application readiness. A successful backup job alone does not prove that a restore will succeed.

## Restore authorization

Only the incident commander and a designated database administrator can authorize a production restore. The restore request must identify the target recovery time and expected data loss. Application traffic stays paused until validation finishes.

