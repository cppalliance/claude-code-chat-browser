# Releasing

Manual release flow for claude-code-chat-browser. A release is an annotated git tag and a GitHub Release with notes. There is no CI publish workflow, and no wheel, npm package, or other artifact is attached.

`v0.1.0` (2026-06-18) is the only shipped tag so far. `v0.2.0` is in progress; these steps describe how it is being cut.

## Version source

The only version string is `__version__` in `app.py` (line 3). There is no `pyproject.toml` version field.

Between tagged releases, `master` may carry a `.dev0` suffix (for example `0.2.0.dev0` while `0.2.0` was in development). The shipped tag drops `.dev0`.

## Pre-release checklist

1. Confirm `master` is green in GitHub Actions (`.github/workflows/ci.yml`).
2. Decide the semver bump using [docs/deprecation-policy.md](docs/deprecation-policy.md#versioning) (pre-1.0: patch for safe fixes, minor for additive work and deprecations).
3. If the release removes or renames a documented API field, confirm the [two-release deprecation window](docs/deprecation-policy.md#removal-criteria) is satisfied.

## Release checklist

Do the changelog in one PR and the version bump in a second PR, or combine them on a `release/vX.Y.Z` branch. The `v0.2.0` cut used two PRs: changelog first (`docs/changelog-0-2-0`), then the bump (`release/v0.2.0`).

1. Edit [CHANGELOG.md](CHANGELOG.md) ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)):
   - Move everything under `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section with `### Added`, `### Changed`, `### Fixed`, or `### Removed` as needed.
   - Leave `## [Unreleased]` empty.
   - Update the footer compare links: `[Unreleased]` → `vX.Y.Z...HEAD`, add `[X.Y.Z]` → `vPREVIOUS...vX.Y.Z`.
2. On a branch from current `master`, set `app.py` line 3 to the release version without `.dev0` (for example `"0.2.0"`).
3. From the repo root, grep for the old `.dev0` suffix you are replacing:
   ```sh
   git grep -n "\.dev0"
   ```
   Update any documentation that still names the previous dev version (for example `docs/deprecation-policy.md`).
4. Open a PR, get review, merge to `master`.
5. Tag the merge commit:
   ```sh
   git checkout master
   git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
   Tag format: `vMAJOR.MINOR.PATCH` (for example `v0.2.0`).
6. Publish a GitHub Release, not just the tag. Pull the `## [X.Y.Z]` section from `CHANGELOG.md` and pass it to `gh`:
   ```sh
   VERSION=X.Y.Z
   awk -v ver="$VERSION" '
     $0 ~ "^## \\[" ver "\\]" {found=1}
     found && $0 ~ "^## \\[" && $0 !~ "^## \\[" ver "\\]" {exit}
     found {print}
   ' CHANGELOG.md > /tmp/release-notes.md
   gh release create "v${VERSION}" --title "v${VERSION}" --notes-file /tmp/release-notes.md
   ```
   On macOS, Linux, and Git Bash, `/tmp/release-notes.md` works. You can also create the release in the GitHub UI and paste the section there.
7. Optional: if the project later adds a supported-version table in [SECURITY.md](SECURITY.md), update it when you cut a release. `SECURITY.md` today only says fixes land on latest `master`.

## After release

1. On `master`, bump `app.py` `__version__` to the next development suffix if you are starting the next cycle (for example `0.3.0.dev0` after shipping `0.2.0`). Put that commit in `CHANGELOG.md` under `[Unreleased]` only when there is user-visible work; a bare dev bump can ride with the next feature PR.
2. New work goes under `## [Unreleased]` until the next release.

## References

| Topic | Location |
|-------|----------|
| Changelog format | [CHANGELOG.md](CHANGELOG.md) |
| Version bump | `app.py` line 3 |
| Deprecation / semver | [docs/deprecation-policy.md](docs/deprecation-policy.md) |
| Security reporting | [SECURITY.md](SECURITY.md) |
| CI gates | [CONTRIBUTING.md](CONTRIBUTING.md) |
