# Deprecation policy

This document defines how **claude-code-chat-browser** evolves its HTTP JSON API and CLI without breaking integrators and the bundled SPA unexpectedly.

## Principles

1. **Documented fields are a contract.** See [API reference](api-reference.md) — each field is marked `stable`, `experimental`, or `deprecated`.
2. **Additive first.** Prefer adding a new field over renaming an existing one.
3. **Deprecate before removing.** A deprecated field remains in responses for at least **one release** after the deprecation is announced in [CHANGELOG](../CHANGELOG.md) and the API reference.
4. **SPA and scripts.** Update `static/js/*.js` and any internal callers before removing a field.

## How we announce deprecation

| Channel | What to update |
|---------|----------------|
| CHANGELOG | `### Deprecated` under the release that announces the change |
| API reference | Set field stability to `deprecated` with a short note and replacement |
| Response (optional) | Future: `Deprecation` header or JSON `_deprecated` map — not required today |

## Removal criteria

A deprecated field may be removed when:

- At least one release has shipped with the field still present but documented as deprecated, and
- The bundled SPA no longer reads the field, and
- Tests and CHANGELOG document the removal.

For fields actively read by the bundled SPA (which does not track an external API version), the deprecation period will span **at least two releases** so the SPA and policy can be updated in the same release cycle as the final removal.

## Example (in progress)

| Field | Endpoint | Status | Replacement |
|-------|----------|--------|-------------|
| `export_count` | `GET /api/export/state` | deprecated | `last_export_session_count` |

## Versioning

Release versions follow `MAJOR.MINOR.PATCH` in `app.__version__` and [CHANGELOG](../CHANGELOG.md). This project is pre-1.0; minor releases may add features; patch releases are fixes and documentation.
