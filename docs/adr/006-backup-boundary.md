# ADR-006: Backups exclude secrets and runtime configuration

**Status:** Accepted

## Context

A useful backup must preserve business data and linked product images without turning application secrets or local runtime configuration into portable archives that are easy to leak.

## Decision

Backups contain a consistent SQLite snapshot, linked product images and a manifest. Environment files and session secrets are explicitly outside the backup boundary.

## Alternatives considered

- Archive the entire application directory.
- Include `.env` so a restore is immediately runnable.
- Back up only the database while ignoring linked product media.

## Consequences

- Restores require deployment secrets to be configured separately.
- Backups remain sensitive business data and must still be protected.
- Backup/restore tests must verify database and media consistency.
- Secret rotation is independent from restoring application data.
