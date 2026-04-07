# ==============================================================================
# Development Commands
# ==============================================================================

.PHONY: dev
dev: ## Run both backend and frontend development servers
	@$(MAKE) -j2 server client

.PHONY: dev-local
dev-local: ## Start both services via the local launcher script (macOS/Linux)
	@bash scripts/dev.sh


.PHONY: server
server: ## Start the backend server in the background
	@echo "Starting server in background..."
	@uv run python server_main.py --port 6400 &

.PHONY: client
client: ## Start the frontend development server
	@cd frontend && npx cross-env VITE_API_BASE_URL=http://localhost:6400 npm run dev

.PHONY: stop
stop: ## Stop MovieDev dev services on macOS/Linux
	@bash scripts/stop.sh

.PHONY: stop-local
stop-local: ## Stop services started by scripts/dev.sh (macOS/Linux)
	@bash scripts/stop.sh

# ==============================================================================
# Tools & Maintenance
# ==============================================================================

.PHONY: sync
sync: ## Sync Vue graphs to the server database
	@uv run python tools/sync_vuegraphs.py

.PHONY: validate-yamls
validate-yamls: ## Validate all YAML configuration files
	@uv run python tools/validate_all_yamls.py

# ==============================================================================
# Help
# ==============================================================================

.PHONY: help
help: ## Display this help message
	@uv run python -c "import re; \
	p=r'$(firstword $(MAKEFILE_LIST))'.strip(); \
	[print(f'{m[0]:<20} {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(p, encoding='utf-8').read(), re.M)]" | sort

# ==============================================================================
# Quality Checks
# ==============================================================================

.PHONY: check-backend
check-backend: ## Run backend quality checks (tests + linting)
	@$(MAKE) backend-tests
	@$(MAKE) backend-lint

.PHONY: backend-tests
backend-tests: ## Run backend tests
	@uv run pytest -v

.PHONY: backend-lint
backend-lint: ## Run backend linting
	@uvx ruff check .
