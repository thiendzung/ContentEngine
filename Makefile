PYTHON ?= python3
BACKEND_VENV := backend/.venv
BACKEND_PY := $(BACKEND_VENV)/bin/python
BACKEND_PIP := $(BACKEND_VENV)/bin/pip
BACKUP ?=

.PHONY: setup backend-install frontend-install db-up db-down migrate backend-dev frontend-dev openapi types test-db-prepare ops-preflight backup restore-test backend-check frontend-check check

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
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log

frontend-dev:
	cd frontend && npm run dev

openapi:
	cd backend && .venv/bin/python -m scripts.dump_openapi

types: openapi
	cd frontend && npm run gen:types

test-db-prepare:
	cd backend && APP_ENV=test .venv/bin/python -m scripts.prepare_test_database
	cd backend && APP_ENV=test .venv/bin/alembic upgrade head

ops-preflight:
	cd backend && .venv/bin/python -m scripts.ops_preflight

backup:
	cd backend && .venv/bin/python -m scripts.ops_backup

restore-test:
	@test -n "$(BACKUP)" || (echo "BACKUP is required: make restore-test BACKUP=/path/to/file.dump" && exit 2)
	cd backend && .venv/bin/python -m scripts.ops_restore_verify "$(BACKUP)"

backend-check:
	cd backend && .venv/bin/ruff check app tests scripts migrations
	cd backend && .venv/bin/mypy app
	$(MAKE) test-db-prepare
	cd backend && APP_ENV=test .venv/bin/pytest
	cd backend && APP_ENV=test .venv/bin/python -m scripts.dump_openapi

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

check: backend-check frontend-check
