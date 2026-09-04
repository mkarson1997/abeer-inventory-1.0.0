# ADR-002: Store money as integer minor units

**Status:** Accepted

## Context

Binary floating-point values can introduce rounding artifacts in financial calculations and equality comparisons.

## Decision

Represent monetary amounts internally as integer minor units where the application controls storage and arithmetic.

## Alternatives considered

- Binary floating-point values.
- Free-form localized currency strings.
- Decimal values everywhere without a canonical storage convention.

## Consequences

- Arithmetic is deterministic for supported currencies with fixed minor-unit scales.
- Formatting becomes a presentation concern.
- Import/export code must convert deliberately between external representations and stored minor units.
- Currency identity must remain separate from the numeric amount.
