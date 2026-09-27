# Data retention policy

Fictional Atlas documentation for DocuLens evaluation. This is not a real service policy.

## Deleted documents

Deleted document content is removed from the active search index immediately. Backup copies expire within 30 days. Previously exported files outside the workspace cannot be recalled by the service.

## Audit history

Workspace audit events are retained for 180 days. Only Owners and Admins can export audit history. Exported audit records are provided as JSON Lines.

## Query history

Question history is retained for 30 days by default. An Admin can disable future question-history collection. Disabling collection does not automatically erase existing history.

## Account closure

Closing a workspace immediately disables new logins. The owner has a 7-day recovery window before primary workspace data is permanently deleted. Backup copies then follow the normal 30-day expiration schedule.

