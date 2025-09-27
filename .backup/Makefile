# ISI Macroscope Control System - Makefile
# Unified commands for running the system

.PHONY: help run run-dev install clean test lint

# Default target
help:
	@echo "ISI Macroscope Control System"
	@echo "=============================="
	@echo ""
	@echo "Available commands:"
	@echo "  make run        - Run the system in production mode"
	@echo "  make run-dev    - Run the system in development mode"
	@echo "  make install    - Install all dependencies"
	@echo "  make clean      - Clean build artifacts and caches"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run code linters"
	@echo ""

# Run in production mode
run:
	@echo "Starting ISI Macroscope Control System..."
	@python3 run.py

# Run in development mode
run-dev:
	@echo "Starting ISI Macroscope Control System (Development Mode)..."
	@python3 run.py --dev --verbose

# Install all dependencies
install:
	@echo "Installing backend dependencies..."
	@cd backend && poetry install
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install
	@echo "Installation complete!"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf logs/*.log
	@cd backend && rm -rf .pytest_cache __pycache__ dist build *.egg-info
	@cd frontend && rm -rf dist node_modules/.cache
	@echo "Clean complete!"

# Run all tests
test:
	@echo "Running backend tests..."
	@cd backend && poetry run pytest
	@echo "Running frontend tests..."
	@cd frontend && npm test

# Run linters
lint:
	@echo "Linting backend..."
	@cd backend && poetry run ruff check .
	@echo "Linting frontend..."
	@cd frontend && npm run lint