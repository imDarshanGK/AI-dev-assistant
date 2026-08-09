# User Data Deletion

Issue: #617

## Overview

Authenticated users can request deletion of their account and stored user-owned data through the user data purge API.

The purge flow is intentionally split into two steps:

1. Preview the records that will be deleted.
2. Confirm irreversible deletion using a fixed confirmation phrase.

## Endpoints

### GET /user/data-purge/preview

Requires a valid bearer token.

Returns:

* number of saved history records
* number of saved favorite records
* whether the account will be deleted
* required confirmation phrase

### POST /user/data-purge

Requires a valid bearer token.

Request body:

```json
{
  "confirmation": "DELETE MY DATA"
}
```

If the confirmation phrase matches, the application deletes:

* the authenticated user's history records
* the authenticated user's favorite records
* the authenticated user's account row

The endpoint does not delete records belonging to any other user.

## Audit trail

A non-sensitive audit record is stored after a successful purge.

The audit record stores:

* hashed user id
* hashed email
* deleted history count
* deleted favorite count
* completion timestamp
* completion status

The audit record does not store:

* raw email
* password hash
* source code
* result JSON
* favorite titles

This preserves an operational deletion trail without retaining the user's original private data.

## Confirmation flow

Deletion is irreversible at the application database level.

The API requires the exact confirmation phrase:

```text
DELETE MY DATA
```

Requests with any other phrase are rejected and no data is deleted.

## Backup and log limitations

This application-level purge removes active database records controlled by the app.

Infrastructure backups, database snapshots, provider logs, access logs, or already-rotated observability data may be governed by deployment/provider retention policies. Those systems should be configured separately to expire retained data according to the deployment's privacy policy.

The application audit trail intentionally stores only hashed identifiers and deletion counts to avoid reintroducing deleted personal data.
