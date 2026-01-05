#!/usr/bin/env bash
# Run all tests with coverage

set -e

echo "Running pytest with coverage..."
pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml

echo ""
echo "Tests complete! Coverage report available in htmlcov/index.html"

