.PHONY: help lint format test clean

help:
	@echo "Available commands:"
	@echo "  make lint      - Run ruff linter"
	@echo "  make format    - Format code with ruff"
	@echo "  make test      - Run tests with pytest"
	@echo "  make clean     - Clean build artifacts"

lint:
	ruff check src tests worker cli shared

format:
	ruff format src tests worker cli shared

test:
	pytest tests/ -v --cov=src --cov=worker --cov=shared --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf frontend/dist/