<#
.SYNOPSIS
    Tag-driven release helper for xians-lib-python (Windows/PowerShell).

.DESCRIPTION
    Mirrors scripts/release.sh for Windows users.

    Steps:
      1. Validates the version string (PEP 440 / SemVer-ish).
      2. Verifies pyproject.toml's [project].version matches the requested version.
      3. Cleans previous build artifacts.
      4. Runs lint, type check, and tests.
      5. Builds the wheel and sdist with `python -m build`.
      6. Optionally creates and pushes the git tag `vX.Y.Z` (triggers release.yml).

.PARAMETER Version
    The version to release (e.g. 0.2.0, 0.2.0rc1).

.PARAMETER Tag
    Also create and push the git tag `v<Version>` to origin.

.EXAMPLE
    ./scripts/release.ps1 -Version 0.2.0
    ./scripts/release.ps1 -Version 0.2.0 -Tag
    ./scripts/release.ps1 -Version 0.2.0rc1 -Tag
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version,

    [switch]$Tag
)

$ErrorActionPreference = "Stop"

# --- Validate version format (PEP 440, practical subset) ---
if ($Version -notmatch '^\d+\.\d+\.\d+((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$') {
    Write-Error "Invalid PEP 440 version '$Version'. Expected: 1.2.3 | 1.2.3rc1 | 1.2.3a1 | 1.2.3.post1"
}

# --- Ensure pyproject.toml version matches requested version ---
Write-Host "==> Checking pyproject.toml version matches '$Version'"
$env:XIANS_RELEASE_VERSION = $Version
$checkScript = @'
import os, pathlib, sys, tomllib
data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
project_version = data["project"]["version"]
requested = os.environ["XIANS_RELEASE_VERSION"]
if project_version != requested:
    sys.exit(
        f"Version mismatch: pyproject.toml={project_version} requested={requested}.\n"
        "Bump [project].version in pyproject.toml before releasing."
    )
print(f"OK: pyproject.toml version = {project_version}")
'@
$checkScript | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- Require a clean git tree ---
$status = git status --porcelain
if ($status) {
    Write-Host $status
    Write-Error "git working tree is not clean. Commit or stash changes first."
}

# --- Refuse to re-release an existing tag ---
$existing = git tag -l "v$Version"
if ($existing) {
    Write-Error "git tag 'v$Version' already exists locally."
}

# --- Clean previous build artifacts ---
Write-Host "==> Cleaning previous build artifacts"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
Get-ChildItem -Recurse -Directory -Filter "*.egg-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# --- Quality gates ---
Write-Host "==> Running lint"
ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running type check"
mypy src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running tests"
pytest --cov=src --cov-report=term-missing
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- Build and verify ---
Write-Host "==> Building wheel and sdist"
python -m build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Verifying distributions"
twine check (Get-ChildItem dist | ForEach-Object FullName)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Built artifacts:"
Get-ChildItem dist | ForEach-Object { Write-Host "  $($_.Name)" }

# --- Optionally create and push tag ---
if ($Tag) {
    Write-Host "==> Creating tag v$Version"
    git tag -a "v$Version" -m "Release v$Version"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Pushing tag v$Version to origin"
    git push origin "v$Version"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "Tag pushed. GitHub Actions will build, test, and publish the release."
    Write-Host "Watch: https://github.com/XiansAiPlatform/xians-lib-python/actions"
}
else {
    Write-Host ""
    Write-Host "Build succeeded. Re-run with -Tag to push tag and trigger the release workflow:"
    Write-Host "  ./scripts/release.ps1 -Version $Version -Tag"
}
