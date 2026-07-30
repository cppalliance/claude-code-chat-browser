# Releasing

Manual release flow for claude-code-chat-browser. A release is an annotated git tag plus a GitHub Release with notes. No CI publish workflow, and no wheel, npm package, or other artifact.

`v0.1.0` (2026-06-18) is the only shipped tag so far. `v0.2.0` is in progress; these steps describe that cut.

## Version source

The release version is `__version__` in `app.py` line 3. There is no `pyproject.toml` version field.

`SECURITY.md` line 5 names the version again in the supported-versions blurb (`(currently \`...\`)`). Keep it in sync with `app.py` on every release. `README.md` links to that page for supported versions.

Between tagged releases, `master` may use a `.dev0` suffix (for example `0.2.0.dev0` while `0.2.0` was in development). The shipped tag drops `.dev0`.

## Pre-release checklist

1. Confirm `master` is green in GitHub Actions (`.github/workflows/ci.yml`).
2. Decide the semver bump using [docs/deprecation-policy.md](docs/deprecation-policy.md#versioning) (pre-1.0: patch for safe fixes, minor for additive work and deprecations).
3. If the release removes or renames a documented API field, confirm the [two-release deprecation window](docs/deprecation-policy.md#removal-criteria) is satisfied.

## Release checklist

Do the changelog in one PR and the version bump in a second PR, or combine them on a `release/vX.Y.Z` branch. The `v0.2.0` cut used two PRs: changelog first (`docs/changelog-0-2-0`), then the bump (`release/v0.2.0`).

1. Edit [CHANGELOG.md](CHANGELOG.md) ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)):
   - Move everything under `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section with `### Added`, `### Changed`, `### Deprecated`, `### Fixed`, `### Removed`, or `### Security` as needed.
   - Leave `## [Unreleased]` empty.
   - Update the footer compare links: `[Unreleased]` → `vX.Y.Z...HEAD`, add `[X.Y.Z]` → `vPREVIOUS...vX.Y.Z`.
2. On a branch from current `master`, set `app.py` line 3 to the release version without `.dev0` (for example `"0.2.0"`).
3. Update [SECURITY.md](SECURITY.md) line 5 so `(currently \`...\`)` matches that version (for example `(currently \`0.2.0\`)`). Leave the table at lines 7-10 unchanged.
4. From the repo root, grep for stale version strings (the previous `.dev0` suffix, the old `SECURITY.md` parenthetical, or any other doc that still names the prior release):
   ```sh
   git grep -nE '\.dev0|\(currently `'
   ```
   Update any hits that should name the new release (for example `docs/deprecation-policy.md`).
5. Open a PR, get review, merge to `master`.
6. Tag the merge commit:
   ```sh
   git checkout master
   git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
   Tag format: `vMAJOR.MINOR.PATCH` (for example `v0.2.0`).
7. Cut the GitHub Release after the tag. From the repo root, extract the body from `CHANGELOG.md`:
   ```sh
   cd "$(git rev-parse --show-toplevel)"
   VERSION=0.2.0   # no leading v; not the literal X.Y.Z placeholder
   VERSION="${VERSION#v}"
   case "$VERSION" in
     *[!0-9.]*|*.*.*.*|'') echo "error: VERSION must look like 0.2.0" >&2; exit 1 ;;
   esac
   NOTES="$(mktemp)"
   trap 'rm -f "$NOTES"' EXIT
   awk -v ver="$VERSION" '
     /^## \[/ {
       if (found) exit
       if ($0 ~ "^## \\[" ver "\\]") { found=1; next }
     }
     /^\[[^]]+\]:/ { if (found) exit }
     found { print }
   ' CHANGELOG.md >"$NOTES"
   [ -s "$NOTES" ] || { echo "error: no CHANGELOG.md section for $VERSION" >&2; exit 1; }
   gh release create "v${VERSION}" --title "v${VERSION}" --verify-tag --notes-file "$NOTES"
   ```
   On macOS, Linux, and Git Bash, `mktemp` works. Or paste the section in the GitHub UI (skip the `## [X.Y.Z]` heading; the title is already set).

## After release

1. On `master`, bump `app.py` `__version__` to the next development suffix if you are starting the next cycle (for example `0.3.0.dev0` after shipping `0.2.0`). Put that commit in `CHANGELOG.md` under `[Unreleased]` only when there is user-visible work; a bare dev bump can ride with the next feature PR.
2. New work goes under `## [Unreleased]` until the next release.

## References

| Topic | Location |
|-------|----------|
| Changelog format | [CHANGELOG.md](CHANGELOG.md) |
| Version bump | `app.py` line 3 |
| Supported versions blurb | `SECURITY.md` line 5 |
| Deprecation / semver | [docs/deprecation-policy.md](docs/deprecation-policy.md) |
| Security reporting | [SECURITY.md](SECURITY.md) |
| CI gates | [CONTRIBUTING.md](CONTRIBUTING.md) |
