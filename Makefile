.PHONY: api install-api web install-web dev

# --- Backend (apps/api) ---
api:
	cd apps/api && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

install-api:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install --upgrade pip setuptools && .venv/bin/pip install ".[dev]"

# --- Frontend (apps/web) ---
# Vite dev server on http://localhost:5173 with hot reload.
web:
	cd apps/web && npm run dev

# First-time setup: install node_modules.
install-web:
	cd apps/web && npm install

# Run backend + frontend together. `-j 2` lets make run both recipes in
# parallel; Ctrl-C stops both. Use this for normal local development.
dev:
	@$(MAKE) -j 2 api web
