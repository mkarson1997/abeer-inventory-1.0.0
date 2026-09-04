# Architecture Decision Records

ADRs capture important engineering decisions that affect security, correctness or long-term maintenance.

## Format

Each record contains:

1. **Context** — the problem and constraints.
2. **Decision** — what the project chooses.
3. **Alternatives considered** — realistic options that were not selected.
4. **Consequences** — benefits, costs and follow-up work.

## Records

- [ADR-001: Server-side roles and restricted registration](001-auth-and-roles.md)
- [ADR-002: Store money as integer minor units](002-money-minor-units.md)
- [ADR-003: Keep inventory valuation separated by currency](003-per-currency-valuation.md)
- [ADR-004: Re-encode uploaded product images](004-image-reencoding.md)
- [ADR-005: SQLite foreign keys and WAL mode](005-sqlite-integrity.md)
- [ADR-006: Backups exclude secrets and runtime configuration](006-backup-boundary.md)
