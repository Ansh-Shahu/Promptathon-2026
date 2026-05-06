# =============================================================================
#  HVAC Predictive Maintenance Platform — Developer Makefile
#  Usage: make <target>
# =============================================================================

.DEFAULT_GOAL := help

.PHONY: help install run test freeze clean format lint typecheck check

# -----------------------------------------------------------------------------
#  HELP  (cross-platform echo — compatible with Windows CMD and PowerShell)
# -----------------------------------------------------------------------------

help: ## Show this help message and exit
	@echo.
	@echo   HVAC Predictive Maintenance API — Available Commands
	@echo   =====================================================
	@echo.
	@echo   Target           Description
	@echo   -------------- --------------------------------------------------
	@echo   install          Install all dependencies from requirements.txt
	@echo   run              Start the FastAPI dev server with hot-reload on :8000
	@echo   test             Run the full pytest suite (verbose, warnings suppressed)
	@echo   freeze           Snapshot current environment into requirements.txt
	@echo   clean            Remove __pycache__, .pyc, .pytest_cache, .mypy_cache
	@echo   format           Auto-format source with black and sort imports with isort
	@echo   lint             Check for style violations with ruff (no auto-fix)
	@echo   typecheck        Run static type analysis across the codebase with mypy
	@echo   check            CI gate: format + lint + typecheck + test (in order)
	@echo   help             Show this help message and exit
	@echo.

# -----------------------------------------------------------------------------
#  CORE TARGETS
# -----------------------------------------------------------------------------

install: ## Install all dependencies from requirements.txt
	pip install -r requirements.txt

run: ## Start the FastAPI development server with hot-reload on :8000
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

test: ## Run the full pytest suite with verbose output (warnings suppressed)
	pytest tests/ -v -W ignore

freeze: ## Snapshot current environment into requirements.txt
	pip freeze > requirements.txt

clean: ## Remove all Python cache artefacts (__pycache__, .pyc, .mypy_cache, etc.)
	find . -type d -name "__pycache__"   -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache"   -exec rm -rf {} +
	find . -type f -name "*.pyc"         -delete
	find . -type f -name ".coverage"     -delete
	@echo "✅  Cache artefacts removed."

# -----------------------------------------------------------------------------
#  ENTERPRISE / CODE QUALITY TARGETS
# -----------------------------------------------------------------------------

format: ## Auto-format source code with black and sort imports with isort
	black .
	isort .

lint: ## Check for style violations with ruff (zero-tolerance, no auto-fix)
	ruff check .

typecheck: ## Run static type analysis across the entire codebase with mypy
	mypy .

check: format lint typecheck test ## Master CI gate: format → lint → typecheck → test
	@echo.
	@echo   All checks passed — safe to push.