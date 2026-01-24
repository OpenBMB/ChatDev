# ==============================================================================
# Development Commands
# ==============================================================================

.PHONY: dev
dev: server client ## Run both backend and frontend development servers

.PHONY: server
server: ## Start the backend server in the background
	@echo "Starting server in background..."
	@uv run python server_main.py --port 6400 --reload &

.PHONY: client
client: ## Start the frontend development server
	@cd frontend && VITE_API_BASE_URL=http://localhost:6400 npm run dev

.PHONY: stop
stop: ## Stop backend and frontend servers
	@echo "Stopping backend server (port 6400)..."
	@lsof -t -i:6400 | xargs kill -9 2>/dev/null || echo "Backend server not found on port 6400."
	@echo "Stopping frontend server (port 5173)..."
	@lsof -t -i:5173 | xargs kill -9 2>/dev/null || echo "Frontend server not found on port 5173."

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
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
