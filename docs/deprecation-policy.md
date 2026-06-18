# Deprecation policy

This document defines how **claude-code-chat-browser** evolves its HTTP JSON API and CLI without breaking integrators and the bundled SPA unexpectedly.

## Principles

1. **Documented fields are a contract.** See [API reference](api-reference.md) — each field is marked `stable`, `experimental`, or `deprecated`.
2. **Additive first.** Prefer adding a new field over renaming an existing one.
3. **Deprecate before removing.** A deprecated field remains in responses for at least **one release** after the deprecation is announced in [CHANGELOG](../CHANGELOG.md) and the API reference. Fields still read by the bundled SPA need **at least two releases** — see [Removal criteria](#removal-criteria) below.
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

For fields actively read by the bundled SPA (which does not track an external API version), removal happens no earlier than **two tagged releases** after the release that documented the deprecation in CHANGELOG, and no earlier than **14 calendar days** after that deprecation announcement.

> **Example (illustrative):** if a field is deprecated in version _X_, it may be removed no earlier than version _X+2_. With [`v0.1.0`](../CHANGELOG.md#010---2026-06-18) as the first shipped tag, a field deprecated in `0.2.0` would be removable from `0.4.0` at earliest (versions advance `0.2.0` → `0.3.0` → `0.4.0`).

### Bundled SPA fast path (pre-`v0.1.0`)

Before [`v0.1.0`](../CHANGELOG.md#010---2026-06-18) shipped, the CHANGELOG `[Unreleased]` section was the source of truth for API changes not yet tagged — see [Versioning](#versioning) below. The bundled SPA is deployed from the same repo and commit as the API; it does not consume a separately versioned HTTP contract.

For fields **only read by the bundled SPA** (no external integrators on a tagged API yet), an atomic PR that (1) stops reading the field in `static/js/*.js` and (2) removes it from the JSON response was acceptable **before** `v0.1.0`, provided deprecation was announced in CHANGELOG and api-reference (PR #60) and removal was recorded under `[Unreleased]`. External integrators who pin a **tagged** release must follow the two-release + 14-day rule above.

## Example (completed)

| Field | Endpoint | Status | Replacement | Notes |
|-------|----------|--------|-------------|-------|
| `export_count` | `GET /api/export/state` | removed | `last_export_session_count` | Deprecated in PR #60 (`[Unreleased]`); removed in `[0.1.0]` |

## Versioning

Release versions follow `MAJOR.MINOR.PATCH` in `app.__version__` and [CHANGELOG](../CHANGELOG.md). [`v0.1.0`](https://github.com/cppalliance/claude-code-chat-browser/releases/tag/v0.1.0) is the first shipped git tag; `main` carries a `.dev0` suffix while developing the next release (currently `0.2.0.dev0`). The CHANGELOG `[Unreleased]` section is the source of truth for changes not yet tagged.

| Bump | Pre-1.0 meaning |
|------|-----------------|
| **Patch** | Bug fixes and documentation; no intentional API removals |
| **Minor** | Additive API/features; deprecations may be announced |
| **Major** | Reserved for the `1.0.0` line and later: signals a stable HTTP JSON contract for external integrators and may include breaking removals that completed their deprecation period |

While the project is pre-1.0, treat **minor** bumps as the usual vehicle for deprecations and **patch** bumps for safe fixes.
