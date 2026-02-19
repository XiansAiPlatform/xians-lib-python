#!/usr/bin/env bash
echo "Code formatting complete!"

black src tests
echo "Running black..."

isort src tests
echo "Running isort..."

set -e

# Format code with black and isort

