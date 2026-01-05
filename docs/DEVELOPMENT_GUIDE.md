# Contributing to Xians Python SDK

Thank you for your interest in contributing to the Xians Python SDK!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/xians-platform/xians-lib-python.git
   cd xians-lib-python
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

## Code Standards

### Style Guide
- Follow PEP 8 strictly
- Use Black for formatting (line length: 100)
- Use isort for import sorting
- Use type hints for all functions

### Type Checking
- All code must pass `mypy` strict mode
- Use `typing` module for complex types
- Avoid `Any` when possible

### Documentation
- Use Google-style docstrings
- Document all public APIs
- Include examples in docstrings

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration
```

### Writing Tests
- Use pytest fixtures (see `tests/conftest.py`)
- Mark tests appropriately (`@pytest.mark.unit`, `@pytest.mark.integration`)
- Aim for >90% code coverage
- Test both happy paths and error cases

## Code Quality Checks

### Format Code
```bash
./scripts/format.sh
```

### Lint Code
```bash
./scripts/lint.sh
```

### Run All Checks
```bash
./scripts/ci.sh
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following our standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Run quality checks**
   ```bash
   ./scripts/ci.sh
   ```

4. **Commit your changes**
   ```bash
   git commit -m "feat: add your feature description"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `refactor:` for refactoring
   - `chore:` for maintenance

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then create a Pull Request on GitHub.

## Project Structure

```
src/
├── configs/v1/          # Configuration models
├── constants/v1/        # Constants and enums
├── exceptions/v1/       # Custom exceptions
├── interfaces/v1/       # Abstract interfaces
├── llm_adapters/v1/     # LLM provider adapters
├── models/v1/           # Pydantic data models
├── temporal_workflows/v1/ # Temporal workflows
└── utils/v1/            # Utility functions
```

## Questions?

- Open an issue for bugs or feature requests
- Join our Discord for discussions
- Email: dev@xians.ai

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

