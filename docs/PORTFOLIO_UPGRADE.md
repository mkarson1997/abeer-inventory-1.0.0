# Abeer Inventory Portfolio Upgrade Plan

Abeer Inventory already demonstrates security-focused application engineering. The next portfolio upgrades should make verification easier for reviewers.

## Priority 1

- Add a concise architecture decision record for authentication, authorization and inventory integrity.
- Add screenshots or a short demo flow covering login, stock movement, roles and audit history.
- Publish a machine-readable test/quality summary from CI.
- Document the threat model and major mitigations in one reviewer-friendly page.

## Priority 2

- Add browser-level smoke tests for critical workflows.
- Add accessibility checks for Arabic RTL, Turkish and English surfaces.
- Add restore verification to the backup workflow.
- Add a release checklist and tagged releases.

## Portfolio proof

A reviewer should be able to verify:

- RBAC and session hardening,
- CSRF protection,
- upload safety,
- inventory integrity rules,
- auditability,
- multilingual UI,
- backup/restore thinking,
- automated tests and reproducible deployment.