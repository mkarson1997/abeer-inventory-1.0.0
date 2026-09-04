# ADR-003: Keep inventory valuation separated by currency

**Status:** Accepted

## Context

Adding values denominated in TRY, USD and EUR into one total produces a number with no valid financial meaning unless an explicit exchange-rate conversion policy exists.

## Decision

Keep inventory valuation separated by currency. Do not silently combine unlike currencies into one aggregate.

## Alternatives considered

- Sum every monetary amount regardless of currency.
- Convert automatically using an implicit or hard-coded exchange rate.
- Store a single currency label for the whole application.

## Consequences

- Reports may show multiple currency totals.
- Any future consolidated/base-currency report must define rate source, timestamp and rounding rules explicitly.
- Data integrity is preferred over presenting a deceptively simple single number.
