# ADR-001: Server-side roles and restricted registration

**Status:** Accepted

## Context

Inventory mutation and user administration have different risk levels. A public registration flow that grants broad permissions would make a small-business deployment unsafe by default.

## Decision

Use server-enforced roles (`admin`, `editor`, `viewer`). Public registration is disabled by default. When registration is explicitly enabled, new accounts enter with viewer-level access rather than administrative permissions.

## Alternatives considered

- Single shared administrator account.
- Client-side UI-only permission hiding.
- Public registration with elevated default permissions.

## Consequences

- Authorization must be checked on the server for protected operations.
- Administrative account management becomes an explicit workflow.
- Tests must cover role boundaries, not only whether buttons are visible.
- Deployments can opt into registration without changing the least-privilege default.
