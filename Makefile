PYTHON ?= python3
BACKEND_VENV := backend/.venv
BACKEND_PY := $(BACKEND_VENV)/bin/python
BACKEND_PIP := $(BACKEND_VENV)/bin/pip

.PHONY: setup backend-install frontend-install db-up db-down migrate backend-dev frontend-dev openapi types backend-check frontend-check check

setup: backend-install frontend-install

backend-install:
	$(PYTHON) -m venv $(BACKEND_VENV)
	$(BACKEND_PIP) install --upgrade pip
	$(BACKEND_PIP) install -r backend/requirements-dev.txt

frontend-install:
	cd frontend && npm install --no-audit --no-fund

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	cd backend && .venv/bin/alembic upgrade head

backend-dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

openapi:
	cd backend && .venv/bin/python -m scripts.dump_openapi

types: openapi
	cd frontend && npm run gen:types

backend-check:
	cd backend && .venv/bin/ruff check app tests scripts migrations
	cd backend && .venv/bin/mypy app
	cd backend && .venv/bin/pytest
	cd backend && .venv/bin/python -m scripts.dump_openapi

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

check: backend-check frontend-check
