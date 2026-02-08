# ==============================================================================
# Development Commands
# ==============================================================================

.PHONY: dev
dev: ## Run both backend and frontend development servers
	@$(MAKE) -j2 server client


.PHONY: server
server: ## Start the backend server in the background
	@echo "Starting server in background..."
	@uv run python server_main.py --port 6400 --reload &

.PHONY: client
client: ## Start the frontend development server
	@cd frontend && npx cross-env VITE_API_BASE_URL=http://localhost:6400 npm run dev

.PHONY: stop
stop: ## Stop backend and frontend servers cross-platform
	@echo "Stopping backend server (port 6400)..."
	@npx kill-port 6400
	@echo "Stopping frontend server (port 5173)..."
	@npx kill-port 5173

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
	@python -c "import re; \
	[print(f'{m[0]:<20} {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open('$(MAKEFILE_LIST)').read(), re.M)]" | sort
