# ADR-005: Enable SQLite foreign keys and WAL mode

**Status:** Accepted

## Context

SQLite can serve this application's small-business/local deployment model, but relational integrity and concurrent read/write behavior need explicit configuration rather than relying on assumptions.

## Decision

Enable foreign-key enforcement and use Write-Ahead Logging (WAL) mode, alongside database constraints for invalid business values.

## Alternatives considered

- SQLite defaults without explicit foreign-key enforcement.
- Application-only integrity checks.
- Requiring a network database for every installation.

## Consequences

- The database participates in enforcing relational correctness.
- WAL improves common read/write concurrency patterns while remaining operationally simple.
- Backup behavior must account for SQLite consistency correctly.
- A future move to another database should preserve the same domain constraints rather than weakening them.
