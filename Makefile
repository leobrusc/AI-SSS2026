# Makefile - Compatibility interface for TraceAI
# Primary interface is tasks.ps1 on Windows.
# This Makefile provides the same commands for Linux/macOS or when make is available.

SHELL := /bin/bash
PROFILE ?= local
QUICK ?=

.PHONY: help doctor bootstrap smoke security-campaign availability-campaign \
        analyze publication-artifacts all test lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

doctor: ## Run environment doctor
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 doctor -Profile $(PROFILE)

bootstrap: ## Bootstrap environment and install dependencies
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 bootstrap -Profile $(PROFILE)

smoke: ## Run smoke tests
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 smoke -Profile $(PROFILE)

security-campaign: ## Run security campaign
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 security-campaign -Profile $(PROFILE) $(if $(QUICK),-Quick,)

availability-campaign: ## Run availability campaign
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 availability-campaign -Profile $(PROFILE) $(if $(QUICK),-Quick,)

analyze: ## Analyze campaign results
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 analyze -Profile $(PROFILE)

publication-artifacts: ## Generate publication artifacts
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 publication-artifacts -Profile $(PROFILE)

all: ## Run full pipeline
	@powershell -ExecutionPolicy Bypass -File tasks.ps1 all -Profile $(PROFILE) $(if $(QUICK),-Quick,)

test: ## Run pytest
	.venv/Scripts/python -m pytest tests/unit -q

test-integration: ## Run integration tests
	.venv/Scripts/python -m pytest tests/integration -q

lint: ## Run linter
	.venv/Scripts/python -m ruff check src/ tests/

compile-check: ## Verify all Python files compile
	.venv/Scripts/python -m compileall src/ tests/

clean: ## Clean generated files (requires confirmation)
	@powershell -ExecutionPolicy Bypass -File scripts/clean_generated.ps1

quick: ## Run quick campaign pipeline
	$(MAKE) security-campaign QUICK=1
	$(MAKE) availability-campaign QUICK=1
	$(MAKE) analyze
	$(MAKE) publication-artifacts
