#!/usr/bin/env bash
# Tag-driven release helper for xians-lib-python.
#
# What it does:
#   1. Validates the requested version string (PEP 440 / SemVer-ish)
#   2. Verifies pyproject.toml's [project].version matches the requested version
#   3. Cleans previous build artifacts
#   4. Runs lint, type check, and tests
#   5. Builds the wheel and sdist with `python -m build`
#   6. Optionally creates and pushes the git tag vX.Y.Z (triggers release.yml)
#
# Usage:
#   ./scripts/release.sh <version> [--tag]
#
# Examples:
#   ./scripts/release.sh 0.2.0              # build + verify only
#   ./scripts/release.sh 0.2.0 --tag        # build, verify, tag, and push
#   ./scripts/release.sh 0.2.0rc1 --tag     # pre-release
#
# Requires:
#   - python 3.10+, pip, git
#   - dev extras installed (pip install -e ".[dev]" build twine)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <version> [--tag]"
  echo "Example: $0 0.2.0 --tag"
  exit 1
fi

VERSION="$1"
PUSH_TAG="false"
if [[ "${2:-}" == "--tag" ]]; then
  PUSH_TAG="true"
fi

# --- Validate version format (PEP 440, practical subset) ---
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?(\.post[0-9]+)?(\.dev[0-9]+)?$ ]]; then
  echo "Error: invalid PEP 440 version '$VERSION'." >&2
  echo "Expected formats: 1.2.3 | 1.2.3rc1 | 1.2.3a1 | 1.2.3.post1" >&2
  exit 1
fi

# --- Ensure pyproject.toml version matches requested version ---
echo "==> Checking pyproject.toml version matches '$VERSION'"
python - <<PY
import pathlib, sys, tomllib
data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
project_version = data["project"]["version"]
if project_version != "${VERSION}":
    sys.exit(
        f"Version mismatch: pyproject.toml={project_version} requested=${VERSION}.\n"
        "Bump [project].version in pyproject.toml before releasing."
    )
print(f"OK: pyproject.toml version = {project_version}")
PY

# --- Require a clean git tree ---
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: git working tree is not clean. Commit or stash changes first." >&2
  git status --short
  exit 1
fi

# --- Refuse to re-release an existing tag ---
if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  echo "Error: git tag 'v${VERSION}' already exists locally." >&2
  exit 1
fi

# --- Clean previous build artifacts ---
echo "==> Cleaning previous build artifacts"
rm -rf build dist ./*.egg-info src/*.egg-info

# --- Quality gates ---
echo "==> Running lint"
ruff check src tests

echo "==> Running type check"
mypy src

echo "==> Running tests"
pytest --cov=src --cov-report=term-missing

# --- Build and verify ---
echo "==> Building wheel and sdist"
python -m build

echo "==> Verifying distributions"
twine check dist/*

echo ""
echo "Built artifacts:"
ls -1 dist/

# --- Optionally create and push tag ---
if [[ "$PUSH_TAG" == "true" ]]; then
  echo "==> Creating tag v${VERSION}"
  git tag -a "v${VERSION}" -m "Release v${VERSION}"
  echo "==> Pushing tag v${VERSION} to origin"
  git push origin "v${VERSION}"
  echo ""
  echo "Tag pushed. GitHub Actions will build, test, and publish the release."
  echo "Watch: https://github.com/XiansAiPlatform/xians-lib-python/actions"
else
  echo ""
  echo "Build succeeded. Re-run with '--tag' to push tag and trigger the release workflow:"
  echo "  $0 ${VERSION} --tag"
fi
