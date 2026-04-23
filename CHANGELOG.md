# Changelog

All notable changes to `xians-lib-python` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
using [PEP 440](https://peps.python.org/pep-0440/) compatible version identifiers.

## [Unreleased]

### Added

- Tag-driven release pipeline with GitHub Actions.
- CI workflow running lint, type-check, and tests on Python 3.10 / 3.11 / 3.12.
- Release helper scripts (`scripts/release.sh`, `scripts/release.ps1`).
- `docs/RELEASING.md` with the full release + install-from-GitHub guide.
- Dynamic `__version__` resolution via `importlib.metadata` in `xians/__init__.py`.

### Changed

- Consolidated `py.typed` marker under the `xians` package (PEP 561).
- Corrected project URLs in `pyproject.toml` to `XiansAiPlatform/xians-lib-python`.
- Packaged distribution now ships only the `xians` top-level package for parity
  with `XiansAi.Lib` (.NET).

### Removed

- `src/llm_adapters/` (orphan placeholder adapters). The SDK is LLM-agnostic:
  users wire their chosen LLM framework inside their own Temporal activities,
  matching the architecture of `XiansAi.Lib` (.NET). The removed package was
  never referenced by `xians.*`, had broken imports (`from src.interfaces.v1 ...`),
  and only contained stub "placeholder" responses.

## [3.23.0a1] - 2026-04-23

### Added

- Initial public package scaffolding.
- Temporal workflow runtime for durable AI agents.
- Xians server integration (knowledge, documents, messaging, metrics, scheduling).

[Unreleased]: https://github.com/XiansAiPlatform/xians-lib-python/compare/v3.23.0a1...HEAD
[3.23.0a1]: https://github.com/XiansAiPlatform/xians-lib-python/releases/tag/v3.23.0a1
