# ISI Macroscope Control System Backend

Backend service for the ISI Macroscope Control System, implementing scientific workflow management, hardware abstraction, and cross-platform support.

## Features

- 12-state scientific workflow state machine
- Cross-platform hardware abstraction (macOS dev, Windows production)
- IPC communication with Electron frontend
- Comprehensive test suite with >80% coverage
- Clean architecture (Domain → Application → Infrastructure)

## Development Setup

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run specific test category
poetry run pytest tests/unit/domain/
poetry run pytest tests/integration/

# Run with coverage
poetry run pytest --cov=src --cov-report=html
```

## Architecture

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and command handlers
- **Infrastructure Layer**: External concerns (hardware, IPC)

Built with Pydantic V2 for type safety and validation.