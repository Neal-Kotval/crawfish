# Releasing Crawfish

How a Crawfish version gets cut and published. Publishing is automated by
[`.github/workflows/release.yml`](.github/workflows/release.yml) — a human bumps the
version, updates the changelog, and pushes a tag; the workflow builds and publishes.

## Versioning policy (semver + stability tiers)

Crawfish follows [SemVer 2.0.0](https://semver.org). Every public name (anything
re-exported from `crawfish/__init__.py`) carries a **stability tier**, declared in code
with the decorators in [`crawfish.stability`](packages/crawfish/src/crawfish/stability.py)
and readable via `stability_of(obj)`. The three tiers are:

| Tier | Decorator | Promise |
|------|-----------|---------|
| **stable** | `@stable` | Covered by semver. Broken only on a major bump, and only after going through deprecation. |
| **experimental** | `@experimental` | May change or break in any minor release. **Default** for untagged public names — nothing is stable until promoted. |
| **deprecated** | `@deprecated(since=…, removed_in=…, use=…)` | Still works, emits a `DeprecationWarning` naming the replacement; removed on the named major. |

What each bump may break:

**Pre-1.0 (`0.x`):**

- **patch** (`0.1.0 → 0.1.1`): bug fixes only; never breaks any API.
- **minor** (`0.1.x → 0.2.0`): may break **experimental** APIs. Stable APIs go through
  deprecation first.
- There is no major axis below 1.0, but the deprecation discipline already applies to
  anything tagged `@stable`.

**Post-1.0:**

- **major** (`1.x → 2.0`): the only release that may remove or break a **stable** API,
  and only one already deprecated for ≥ 1 minor release.
- **minor** (`1.4 → 1.5`): additive for stable APIs; may break experimental ones.
- **patch** (`1.4.0 → 1.4.1`): bug fixes only.

Tooling computes the coarse breaking signal with `crawfish.stability.is_breaking(old,
new)` and renders a summary with `migration_note(old, new)`.

## Deprecation policy

A stable API is never removed in one step:

1. **Mark** it `@deprecated(since="<this-version>", removed_in="<next-major>",
   use="<replacement>")`.
2. **Warn for ≥ 1 minor release** — it stays callable (warning only) so downstream code
   has a release to migrate in.
3. **Remove on the named major** — never in a minor or patch.

A breaking change is inseparable from a deprecation plus a migration note; both are
required to merge a breaking PR. See
[`docs/architecture/API-STABILITY.md`](docs/architecture/API-STABILITY.md) for the full
contract, including the migration-guide + codemod requirement.

## Cutting a release

1. **Confirm the gate is green** on `main`:
   - `just check` (ruff + `mypy packages/crawfish/src` strict + `pytest -q`)
   - `just docs-build` (`mkdocs build --strict`)
2. **Bump the version** in
   [`packages/crawfish/pyproject.toml`](packages/crawfish/pyproject.toml) (`[project]
   version`) per the policy above.
3. **Update [`CHANGELOG.md`](CHANGELOG.md)**: rename `## [Unreleased]` to the new
   `## [X.Y.Z]`, add the date, start a fresh empty `## [Unreleased]`, and update the
   comparison links at the bottom.
4. **Commit** both, signed off (`git commit -s`), and merge to `main` via PR.
5. **Tag and push**:

   ```bash
   git tag vX.Y.Z          # tag must match the pyproject version, prefixed with `v`
   git push origin vX.Y.Z
   ```

   The pushed `v*` tag triggers `release.yml`: it builds the sdist + wheel
   (`uv build packages/crawfish`), publishes to **PyPI via trusted publishing**, and
   creates the GitHub Release.

## Test-PyPI dry run

Before the first real publish (or any time you want to rehearse), publish to Test-PyPI
without tagging:

1. Actions → **release** → **Run workflow** → set **target = testpypi**.
2. The `build` job builds the distribution; the `publish-testpypi` job uploads it to
   `https://test.pypi.org/legacy/` via trusted publishing.
3. Verify the install from Test-PyPI:

   ```bash
   pip install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ crawfish
   ```

## Trusted publishing (no stored secrets)

Publishing uses **PyPI trusted publishing (OIDC)** — there are **no API tokens or
secrets** stored in the repo or in GitHub. Identity is brokered at runtime via the
`id-token: write` permission and the `pypa/gh-action-pypi-publish` action.

One-time human setup (in the PyPI / Test-PyPI web UI, not in code):

1. Create the trusted publisher on [PyPI](https://pypi.org/manage/account/publishing/)
   and [Test-PyPI](https://test.pypi.org/manage/account/publishing/): owner =
   `<github-org>`, repo = `crawfish`, workflow = `release.yml`, environment = `pypi`
   (and `testpypi` on Test-PyPI).
2. Create the GitHub Environments `pypi` and `testpypi` (Settings → Environments). Add
   required reviewers to `pypi` if you want a manual approval gate before publish.

<!-- TODO(maintainer): confirm the dist name `crawfish` is available on PyPI/Test-PyPI
     and set the org/repo slug when configuring the trusted publishers above. -->
