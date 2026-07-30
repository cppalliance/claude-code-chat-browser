# Releasing

Manual release flow for **claude-code-chat-browser**. There is **no CI publish workflow**: a release is an annotated git tag plus a GitHub Release with notes. No wheel, npm package, or other artifact is attached.

`v0.1.0` (2026-06-18) is the only shipped tag so far. `v0.2.0` is in progress and these steps describe how it is being cut.

## Version source

The only version string is `__version__` in `app.py` (line 3). There is no `pyproject.toml` version field.

Between tagged releases, `master` may carry a `.dev0` suffix (for example `0.2.0.dev0` while `0.2.0` was in development). The shipped tag always drops `.dev0`.

## Pre-release checklist

1. Confirm `master` is green in GitHub Actions (`.github/workflows/ci.yml`).
2. Decide the semver bump using [docs/deprecation-policy.md](docs/deprecation-policy.md#versioning) (pre-1.0: patch for safe fixes, minor for additive work and deprecations).
3. If the release removes or renames a documented API field, confirm the [two-release deprecation window](docs/deprecation-policy.md#removal-criteria) is satisfied.

## Release checklist

Do the changelog in one PR and the version bump in a second PR, or combine them on a `release/vX.Y.Z` branch. The `v0.2.0` cut used two PRs: changelog first (`docs/changelog-0-2-0`), then the bump (`release/v0.2.0`).

1. **Changelog** — edit [CHANGELOG.md](CHANGELOG.md) ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)):
   - Move everything under `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section with `### Added`, `### Changed`, `### Fixed`, or `### Removed` as needed.
   - Leave `## [Unreleased]` empty.
   - Update the footer compare links: `[Unreleased]` → `vX.Y.Z...HEAD`, add `[X.Y.Z]` → `vPREVIOUS...vX.Y.Z`.
2. **Version bump** — on a branch from current `master`, set `app.py` line 3 to the release version without `.dev0` (for example `"0.2.0"`).
3. **Stale references** — from the repo root, grep for the old `.dev0` suffix you are replacing:
   ```powershell
   git grep -n "\.dev0"
   ```
   Update any documentation that still names the previous dev version (for example `docs/deprecation-policy.md`).
4. **Open a PR**, get review, merge to `master`.
5. **Tag** on the merge commit:
   ```powershell
   git checkout master
   git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
   Tag format: `vMAJOR.MINOR.PATCH` (for example `v0.2.0`).
6. **GitHub Release** — publish a Release object, not just the tag. Copy the `## [X.Y.Z]` section from `CHANGELOG.md` into a scratch file, then:
   ```powershell
   # paste the ## [X.Y.Z] section into this file first
   notepad $env:TEMP\release-notes.md
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file $env:TEMP\release-notes.md
   ```
   Or create the release in the GitHub UI and paste the section there.
7. **Optional** — if the project later adds an explicit supported-version table in [SECURITY.md](SECURITY.md), update it when you cut a release. Today `SECURITY.md` only states that fixes land on latest `master`.

## After release

1. On `master`, bump `app.py` `__version__` to the next development suffix if you are starting the next cycle (for example `0.3.0.dev0` after shipping `0.2.0`). Record that commit in `CHANGELOG.md` under `[Unreleased]` only if there is user-visible work; a bare dev bump can ride with the next feature PR.
2. New work accumulates under `## [Unreleased]` until the next release.

## References

| Topic | Location |
|-------|----------|
| Changelog format | [CHANGELOG.md](CHANGELOG.md) |
| Version bump | `app.py` line 3 |
| Deprecation / semver | [docs/deprecation-policy.md](docs/deprecation-policy.md) |
| Security reporting | [SECURITY.md](SECURITY.md) |
| CI gates | [CONTRIBUTING.md](CONTRIBUTING.md) |
