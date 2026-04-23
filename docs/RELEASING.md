# Releasing `xians-lib-python`

End-to-end guide for versioning, building, tagging, and publishing releases
of the Xians Python SDK — currently distributed directly from GitHub
(not yet PyPI).

> Release philosophy mirrors `XiansAi.Lib` (.NET): **tags drive releases**.
> Push a `vX.Y.Z` tag → CI builds, tests, and publishes a GitHub Release
> containing the wheel and sdist that users can `pip install` from.

---

## Table of Contents

1. [Versioning Strategy](#1-versioning-strategy)
2. [Where Version Lives](#2-where-version-lives)
3. [Release Prerequisites](#3-release-prerequisites)
4. [Automated Release via GitHub Actions (Recommended)](#4-automated-release-via-github-actions-recommended)
5. [Manual Release via Helper Script](#5-manual-release-via-helper-script)
6. [Pre-Releases (alpha / beta / rc)](#6-pre-releases-alpha--beta--rc)
7. [Installing from GitHub](#7-installing-from-github)
8. [Testing a Release Locally Before Tagging](#8-testing-a-release-locally-before-tagging)
9. [Hotfix / Re-Release](#9-hotfix--re-release)
10. [Troubleshooting](#10-troubleshooting)
11. [Production Readiness Checklist](#11-production-readiness-checklist)

---

## 1. Versioning Strategy

We follow [Semantic Versioning 2.0](https://semver.org/) expressed using
[PEP 440](https://peps.python.org/pep-0440/).

| Bump    | When to use                                          | Example                 |
| ------- | ---------------------------------------------------- | ----------------------- |
| `MAJOR` | Breaking public API changes                          | `1.0.0` → `2.0.0`       |
| `MINOR` | Backward-compatible new features                     | `1.2.0` → `1.3.0`       |
| `PATCH` | Backward-compatible bug fixes                        | `1.2.3` → `1.2.4`       |
| `aN`    | Alpha pre-release                                    | `1.3.0a1`               |
| `bN`    | Beta pre-release                                     | `1.3.0b1`               |
| `rcN`   | Release candidate                                    | `1.3.0rc1`              |

Rules of thumb:

- Never reuse a version number.
- Bump versions in one commit (`chore(release): 0.2.0`) and then tag.
- Keep `CHANGELOG.md` updated before tagging.

---

## 2. Where Version Lives

There is a **single source of truth**: `pyproject.toml`.

```toml
[project]
name = "xians-lib-python"
version = "0.1.0"
```

At runtime, `xians.__version__` is derived dynamically from the installed
distribution metadata:

```python
# src/xians/__init__.py
from importlib.metadata import PackageNotFoundError, version as _dist_version
try:
    __version__ = _dist_version("xians-lib-python")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
```

The release workflow (`.github/workflows/release.yml`) fails the build if
`[project].version` in `pyproject.toml` does not match the pushed git tag
(minus the `v` prefix). This prevents accidental drift between the tag,
the built artifact, and `xians.__version__`.

---

## 3. Release Prerequisites

Only needed the **first time** you set up your environment.

1. Clone the repo and install dev deps:

    ```bash
    git clone https://github.com/XiansAiPlatform/xians-lib-python.git
    cd xians-lib-python
    python -m venv .venv
    # Linux/macOS
    source .venv/bin/activate
    # Windows (PowerShell)
    .\.venv\Scripts\Activate.ps1

    pip install -e ".[dev]" build twine
    ```

2. Verify you are on the target release branch (usually `main`):

    ```bash
    git checkout main
    git pull
    ```

3. Confirm you have push permissions (tags trigger the release workflow).

---

## 4. Automated Release via GitHub Actions (Recommended)

This is the **preferred** path — it mirrors the `XiansAi.Lib` NuGet flow.

### Step 1 — Bump the version

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.0"
```

Update `CHANGELOG.md`:

```md
## [0.2.0] - 2026-04-28
### Added
- ...
### Fixed
- ...
```

### Step 2 — Commit and push to `main`

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): 0.2.0"
git push origin main
```

### Step 3 — Create and push the tag

```bash
# Linux/macOS
export VERSION=0.2.0
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin "v$VERSION"
```

```powershell
# Windows (PowerShell)
$env:VERSION = "0.2.0"
git tag -a "v$env:VERSION" -m "Release v$env:VERSION"
git push origin "v$env:VERSION"
```

### What happens next

The `.github/workflows/release.yml` pipeline:

1. Extracts the version from the tag (strips `v`).
2. Validates PEP 440 format.
3. Confirms `pyproject.toml` matches the tag.
4. Installs dev deps and runs `ruff`, `mypy`, and `pytest`.
5. Builds the wheel and sdist with `python -m build`.
6. Runs `twine check` on the artifacts.
7. Smoke-tests the wheel in a clean venv (`import xians`).
8. Creates a **GitHub Release** with auto-generated notes and attaches:
    - `xians_lib_python-<version>-py3-none-any.whl`
    - `xians_lib_python-<version>.tar.gz`
9. Publishes a summary with ready-to-copy install commands.

Monitor the run at:
`https://github.com/XiansAiPlatform/xians-lib-python/actions`

---

## 5. Manual Release via Helper Script

Use the helper when you want to build locally before tagging. Mirrors the
`nuget-push.sh` approach from `XiansAi.Lib`.

### Linux / macOS

```bash
# 1. Bump pyproject.toml to 0.2.0 and commit it
# 2. Dry-run: build + lint + test, but don't tag
./scripts/release.sh 0.2.0

# 3. Full release: build, test, tag, and push (triggers release.yml)
./scripts/release.sh 0.2.0 --tag
```

### Windows (PowerShell)

```powershell
# Dry-run
./scripts/release.ps1 -Version 0.2.0

# Full release
./scripts/release.ps1 -Version 0.2.0 -Tag
```

The script will:

- Reject invalid PEP 440 versions.
- Fail if `pyproject.toml` does not match the requested version.
- Fail if the working tree is dirty.
- Fail if the tag already exists locally.
- Clean old `build/`, `dist/`, and `*.egg-info/`.
- Run `ruff`, `mypy`, and `pytest`.
- Build the wheel and sdist.
- Run `twine check`.
- Optionally push the tag (when `--tag` / `-Tag` is supplied) so CI takes over.

---

## 6. Pre-Releases (alpha / beta / rc)

Same flow, different version suffix:

```bash
# Alpha
git tag -a v0.3.0a1 -m "Release v0.3.0a1"
git push origin v0.3.0a1

# Beta
git tag -a v0.3.0b1 -m "Release v0.3.0b1"
git push origin v0.3.0b1

# Release candidate
git tag -a v0.3.0rc1 -m "Release v0.3.0rc1"
git push origin v0.3.0rc1
```

The release workflow automatically flags these as **Pre-release** on the
GitHub Releases page, so consumers know they are not stable.

Consumers opting into pre-releases install them explicitly:

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.3.0rc1"
```

---

## 7. Installing from GitHub

Since we do not publish to PyPI yet, all installs go through GitHub.

### Install a specific release tag (recommended)

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.2.0"
```

### Install the wheel from a GitHub Release directly

```bash
pip install https://github.com/XiansAiPlatform/xians-lib-python/releases/download/v0.2.0/xians_lib_python-0.2.0-py3-none-any.whl
```

### Install the latest `main` branch

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@main"
```

### Pin to a specific commit SHA

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@<commit_sha>"
```

### Use in a `requirements.txt`

```text
xians-lib-python @ git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.2.0
```

### Use in another `pyproject.toml`

```toml
[project]
dependencies = [
    "xians-lib-python @ git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.2.0",
]
```

> Tip: always pin to a **tag or commit SHA** in production. Pinning to a
> branch (`@main`) will silently pull future changes on next install.

### Private repo installs

If the repo is private, the consumer must authenticate. Easiest option:

```bash
pip install "git+https://<GITHUB_TOKEN>@github.com/XiansAiPlatform/xians-lib-python.git@v0.2.0"
```

Or use SSH:

```bash
pip install "git+ssh://git@github.com/XiansAiPlatform/xians-lib-python.git@v0.2.0"
```

---

## 8. Testing a Release Locally Before Tagging

Do this before every real release.

### Build locally

```bash
python -m pip install --upgrade pip build twine
python -m build
twine check dist/*
ls dist/
```

You should see both:

```text
dist/xians_lib_python-0.2.0-py3-none-any.whl
dist/xians_lib_python-0.2.0.tar.gz
```

### Install into a clean venv

```bash
python -m venv /tmp/xians-smoke
source /tmp/xians-smoke/bin/activate  # or Windows equivalent
pip install dist/xians_lib_python-0.2.0-py3-none-any.whl
python -c "import xians; print(xians.__version__)"
```

Expected output:

```text
0.2.0
```

### Test a `git+https` install before tagging

You can point `pip` at a branch or commit to simulate the post-tag install
experience:

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@<branch-or-sha>"
```

---

## 9. Hotfix / Re-Release

### Never re-use a version number

If `v0.2.0` is already released, publish `v0.2.1` instead of retagging.

### Deleting a botched tag (before anyone installed it)

```bash
# Local delete
git tag -d v0.2.0
# Remote delete
git push origin :refs/tags/v0.2.0
```

Then bump to the **next** version (`0.2.1`), update `pyproject.toml` and
`CHANGELOG.md`, and re-tag.

### Deleting a botched GitHub Release

Go to the repo → **Releases** → edit the release → **Delete**.

---

## 10. Troubleshooting

### "Version mismatch between pyproject.toml and git tag"

You tagged `v0.3.0` but `pyproject.toml` still says `0.2.0`.
Fix `pyproject.toml`, commit, delete the bad tag, re-tag.

### "Invalid PEP 440 version"

Check your tag. Valid: `v1.2.3`, `v1.2.3a1`, `v1.2.3rc1`, `v1.2.3.post1`.
Invalid: `v1.2.3-beta` (SemVer style — **not** PEP 440 for Python).

### "mypy errors only in CI"

Ensure you ran `mypy src` locally with the same Python version as CI (3.10).

### `pip install git+...` fails with "Could not find a version"

Usually means the tag does not exist on the remote, or the branch name is
wrong. Verify:

```bash
git ls-remote --tags origin
```

### Wheel builds but `import xians` fails

Check that `src/xians/__init__.py` exists and that `pyproject.toml` has:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["xians*"]
```

### GitHub Release was not created

- Confirm the workflow run succeeded under **Actions**.
- Confirm the tag starts with `v` (e.g. `v0.2.0` — the workflow trigger is
  `tags: - 'v*'`).
- Confirm `permissions: contents: write` is present in `release.yml`.

---

## 11. Production Readiness Checklist

Before cutting a `v1.0.0` release, verify:

- [ ] `pyproject.toml` metadata is accurate (authors, URLs, description).
- [ ] `CHANGELOG.md` is up to date.
- [ ] `LICENSE` is present and correct.
- [ ] `README.md` reflects current public API.
- [ ] `src/xians/py.typed` exists (PEP 561).
- [ ] All public modules have type hints and pass `mypy --strict`.
- [ ] `pytest` passes on Python 3.10, 3.11, and 3.12 in CI.
- [ ] `ruff`, `black`, `isort` pass in CI.
- [ ] `python -m build` produces both wheel and sdist.
- [ ] `twine check dist/*` passes.
- [ ] Wheel installs cleanly in a fresh venv, `import xians` works, and
      `xians.__version__` returns the expected value.
- [ ] Tag format is `vX.Y.Z` (or PEP 440 pre-release suffix).
- [ ] GitHub Release includes both `*.whl` and `*.tar.gz`.
- [ ] Install-from-GitHub commands in the README work end-to-end.

---

## Reference: Files Involved in the Release Process

| Path                                        | Purpose                                               |
| ------------------------------------------- | ----------------------------------------------------- |
| `pyproject.toml`                            | Source of truth for version and package metadata      |
| `src/xians/__init__.py`                     | Exposes `xians.__version__` via `importlib.metadata`  |
| `CHANGELOG.md`                              | Human-readable release notes                          |
| `.github/workflows/ci.yml`                  | Runs on PRs / pushes: lint, type, tests, build        |
| `.github/workflows/release.yml`             | Tag-driven release: builds + GitHub Release artifacts |
| `scripts/release.sh`                        | Bash helper mirroring `XiansAi.Lib`'s `nuget-push.sh` |
| `scripts/release.ps1`                       | PowerShell helper for Windows users                   |
| `docs/RELEASING.md`                         | This file                                             |
