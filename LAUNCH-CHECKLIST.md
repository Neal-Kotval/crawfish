# Launch checklist — human-only actions

Everything that is a *file* or *commit* for the open-source launch has been done
in the repo. The steps below require GitHub/PyPI account access or
repo ownership and **cannot be performed from the codebase** — do them in the
respective web UIs. Each item says where to click.

> Convention: anywhere you see `TODO-maintainer/crawfish` in a file, replace it
> with the real GitHub `owner/repo` slug. Search the tree with
> `grep -rn "TODO-maintainer" .` and `grep -rn "TODO(maintainer)" .`.

---

## 1. Fill the TODO(maintainer) placeholders

Search and replace these before anything is published. `grep -rn "TODO(maintainer)" .`

- [x] **Copyright holder** — set to **Neal Kotval** in `NOTICE`,
      `packages/crawfish/NOTICE`, and `packages/crawfish/pyproject.toml` `authors`.
      (Change here if it should be an org instead.)
- [ ] **Security contact email** — `SECURITY.md` and `CODE_OF_CONDUCT.md`
      (Contributor Covenant enforcement contact).
- [ ] **GitHub org/repo slug** — replace `TODO-maintainer/crawfish` everywhere
      (`pyproject.toml` `[project.urls]`, README badges/links, issue-template
      `config.yml`, release docs).
- [ ] **Published PyPI dist name** — assumed `crawfish`. Confirm availability
      (step 4) and update if a different name is reserved.
- [ ] **Maintainer handles** — `MAINTAINERS.md` and `CODEOWNERS` use
      `@TODO-maintainer-handle`. Replace with real GitHub handles/team.

## 2. GitHub repository settings

- [ ] **Private vulnerability reporting** — Settings → *Code security and analysis*
      → enable **Private vulnerability reporting**. This is the channel `SECURITY.md`
      points people to ("Security" tab → *Report a vulnerability*).
- [ ] **Discussions** — Settings → *General* → *Features* → enable **Discussions**.
      The issue-template `config.yml` and README already link to
      `…/discussions`. (Optional: create a Discord and drop the invite in the README
      where the placeholder is.)
- [ ] **Branch protection on `main`** — Settings → *Branches* → add a rule for `main`:
      - Require a pull request before merging (≥1 approval).
      - Require status checks to pass → select the **CI** workflow (`check`) and
        the **DCO** check.
      - Require branches to be up to date; dismiss stale approvals.
      - Restrict / disallow direct pushes (no bypass for non-admins).
      This is the protection `GOVERNANCE.md` documents.
- [ ] **DCO check** — install the DCO GitHub App (or keep the DCO CI job) so the
      `Signed-off-by` requirement from `CONTRIBUTING.md` is enforced on PRs.

## 3. Public claimable backlog (labels + issues)

- [ ] Authenticate the CLI once: `gh auth login` (scope: `repo`), and confirm the
      default repo: `gh repo set-default TODO-maintainer/crawfish`.
- [ ] Run the seed script: `bash scripts/seed-github-backlog.sh`. It creates the
      label set (`.github/labels.yml`) and opens the seed issues
      (`good first issue` / `connector` / etc.). Re-runnable / idempotent.
- [ ] **Projects board** — create a public Project (Projects → *New project* →
      *Board*), add the seeded issues, and pin it from the repo. See
      `docs/roadmap/public-backlog.md` for which roadmap items are mirrored and the
      claim convention.

## 4. PyPI / Test-PyPI (trusted publishing — no tokens)

- [ ] **Reserve the name** — confirm `crawfish` (or your chosen dist name) is
      available on both https://pypi.org and https://test.pypi.org. If taken, pick a
      name and update the `name =` in `packages/crawfish/pyproject.toml` + the TODOs.
- [ ] **Configure the trusted publisher** (Test-PyPI first):
      PyPI → your project (or *Pending publishers* if not yet uploaded) → *Publishing*
      → add a **GitHub Actions** trusted publisher:
      - Owner: your GitHub org · Repository: `crawfish`
      - Workflow filename: `release.yml`
      - Environment: match the `environment:` in `.github/workflows/release.yml`
        (`testpypi` for the dry run, `pypi` for production).
- [ ] **Dry run on Test-PyPI** — trigger the release workflow's Test-PyPI path
      (`workflow_dispatch`), then from a clean venv:
      `pip install -i https://test.pypi.org/simple/ crawfish && craw --version`.
- [ ] **First real release** — follow `RELEASING.md`: bump version, update
      `CHANGELOG.md`, tag `vX.Y.Z`, push the tag → the workflow publishes to PyPI.
      Verify `pip install crawfish && craw --version` from a clean env.

## 5. README demo asset

- [ ] Record the above-the-fold demo and embed it. The exact recording commands are
      in the README/`docs/assets/` demo block (the `craw init → craw dev` zero-key
      flow). Replace the `<!-- TODO(maintainer): embed demo.gif … -->` placeholder.

## 6. Final verification (after the above)

- [ ] GitHub **community profile** (Insights → Community Standards) shows green for:
      Description, README, Code of conduct, Contributing, License, Issue templates,
      Pull request template, Security policy.
- [ ] `pip install <dist>` from a clean environment + `craw --version` works.
- [ ] No internal tracker IDs in any public-facing file:
      `grep -rn "CRA-" README.md CLAUDE.md ROADMAP.md docs/guide/` returns nothing.
