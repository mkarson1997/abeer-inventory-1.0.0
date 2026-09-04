# Threat Model

This document summarizes the main security boundaries and abuse cases considered by Abeer Inventory. It complements `SECURITY.md` and `AUDIT.md`; it is not a claim of complete security.

## Assets to protect

- user accounts and role assignments,
- session secrets and authenticated sessions,
- inventory quantities and valuation data,
- movement/audit history,
- uploaded product images,
- exports and generated documents,
- backups and database integrity.

## Trust boundaries

```text
Browser
  │ untrusted input
  ▼
Flask application
  │ authorization / validation / CSRF / upload controls
  ▼
SQLite + local file storage
  │
  ├── inventory and account data
  ├── movement history
  └── product images
```

The network, browser input, uploaded files, spreadsheet cells and imported legacy data are treated as untrusted.

## Primary threat scenarios

### Unauthorized stock or account changes

**Risk:** a low-privilege user changes stock or manages accounts.

**Controls:** role-based access checks, admin/editor/viewer separation, server-side authorization, session invalidation after important account-state changes.

### Cross-site request forgery

**Risk:** an authenticated user is tricked into submitting a state-changing request.

**Controls:** CSRF protection on state-changing operations and secure cookie settings for HTTPS deployments.

### Credential guessing

**Risk:** repeated sign-in attempts against an account.

**Controls:** temporary login throttling/lockout and no default administrator password.

### Weak production secrets

**Risk:** predictable or missing session keys undermine session integrity.

**Controls:** production startup refuses weak or missing application secrets; secrets belong in environment configuration and are excluded from Git.

### Malicious image upload

**Risk:** oversized, malformed or metadata-bearing files reach protected storage or downstream consumers.

**Controls:** upload size/content validation, image re-encoding as JPEG and metadata removal.

### Spreadsheet formula injection

**Risk:** exported user-controlled values are interpreted as formulas when opened in spreadsheet software.

**Controls:** export paths neutralize formula-injection payloads.

### Inventory/data-integrity corruption

**Risk:** invalid quantities, mixed-currency totals, orphan records or unsafe concurrent writes corrupt business data.

**Controls:** database constraints, foreign keys, negative-stock protection, integer minor-unit money representation, per-currency valuation and SQLite WAL mode.

### Backup leakage

**Risk:** backups expose secrets or unrelated runtime state.

**Controls:** backup workflow uses a consistent database snapshot and intentionally excludes `.env` and the session secret. Real backups must never be committed.

### Legacy import leaks credentials

**Risk:** importing an older database also imports old users/password hashes or customer media.

**Controls:** legacy import is scoped to product data and excludes legacy users, password hashes and old images.

## Residual risks / future work

- Add browser-level tests for critical authorization paths.
- Add formal architecture decision records for security-sensitive choices.
- Add a documented dependency/security update cadence.
- Add deployment-specific reverse-proxy/TLS hardening guidance.
- Continue validating backup/restore behavior as schema complexity grows.

## Security reporting

Do not open a public issue for a vulnerability that could expose users or data. Follow the process in `SECURITY.md`.
