#!/usr/bin/env bash
# Run linting checks

set -e

echo "Running ruff..."
ruff check src tests

echo "Running mypy..."
mypy src

echo "Linting complete!"

