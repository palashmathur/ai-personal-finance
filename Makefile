.PHONY: api install-api

api:
	cd apps/api && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

install-api:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install --upgrade pip setuptools && .venv/bin/pip install ".[dev]"
