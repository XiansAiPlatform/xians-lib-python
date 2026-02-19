#!/usr/bin/env bash
# Run full CI checks (format, lint, test)

set -e

echo "=== Running format check ==="
./scripts/format.sh

echo ""
echo "=== Running linting ==="
./scripts/lint.sh

echo ""
echo "=== Running tests ==="
./scripts/test.sh

echo ""
echo "✅ All CI checks passed!"

