# ADR-004: Re-encode uploaded product images

**Status:** Accepted

## Context

Uploaded media is untrusted input. Keeping original files can preserve unexpected metadata and creates a wider set of file/parser behaviors to support.

## Decision

Validate uploaded image content and size, decode accepted images, then re-encode them to the application's canonical JPEG representation while removing metadata.

## Alternatives considered

- Store uploads byte-for-byte.
- Trust filename extensions or browser MIME declarations.
- Accept arbitrary media formats.

## Consequences

- Stored images are normalized to a smaller, controlled format surface.
- EXIF/metadata is not preserved.
- Re-encoding adds processing cost and may change image quality slightly.
- Upload limits and decoder behavior remain security-sensitive and require tests.
