.PHONY: server
server:
	@uv run python server_main.py --port 6400 --reload

.PHONY: client
client:
	@cd frontend && VITE_API_BASE_URL=http://localhost:6400 npm run dev
