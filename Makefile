.PHONY: install test lint format build clean all help check-env

# Default target
all: check-env format lint test build ## Run all checks and build

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-env: ## Check if uv is installed
	@command -v uv >/dev/null 2>&1 || { echo >&2 "Error: 'uv' is not installed. Please install it from https://github.com/astral-sh/uv"; exit 1; }

install: check-env ## Install dependencies
	uv sync

test: check-env ## Run tests
	uv run pytest

test-cov: check-env ## Run tests with coverage
	uv run pytest --cov=otel_mcp --cov-report=term-missing

lint: check-env ## Run linter with auto-fix
	uv run ruff check --fix .

format: check-env ## Format code
	uv run ruff format .

typecheck: check-env ## Run type checker
	uv run mypy src/

build: check-env install ## Build distribution packages
	uv build

clean: ## Clean build artifacts and caches
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +

run-mcp: check-env ## Run MCP server
	uv run otel-mcp

run-api: check-env ## Run REST API server
	uv run otel-mcp-api

docker-up: ## Start Jaeger in Docker
	docker-compose up -d

docker-down: ## Stop Jaeger in Docker
	docker-compose down
