PYTHON ?= python3
BACKEND_VENV := backend/.venv
BACKEND_PY := $(BACKEND_VENV)/bin/python
BACKEND_PIP := $(BACKEND_VENV)/bin/pip
COMPOSE_PROJECT_NAME ?= contentengine
BACKUP ?=
AUTHORIZED_HEAD ?=
MODEL ?=
APPROVED_BY ?=
OCR_BASE ?=
OCR_HEAD ?=
OCR_PREVIEW_OUTPUT ?= artifacts/ocr/preview.json
OCR_OUTPUT ?= artifacts/ocr/review.json
OCR_BACKGROUND := .opencodereview/background.md

.PHONY: setup backend-install frontend-install db-up db-down migrate backend-dev frontend-dev operator-worker operator-worker-loop activate-test-angle-runtime openapi types test-db-prepare test-db-reset ops-inspect ops-preflight backup restore-test migration-rehearsal operational-migrate backend-check frontend-check check ocr-validate-refs ocr-preview ocr-review-direct

setup: backend-install frontend-install

backend-install:
	$(PYTHON) -m venv $(BACKEND_VENV)
	$(BACKEND_PIP) install --upgrade pip
	$(BACKEND_PIP) install -r backend/requirements-dev.txt

frontend-install:
	cd frontend && npm install --no-audit --no-fund

db-up:
	docker compose -p $(COMPOSE_PROJECT_NAME) up -d postgres

db-down:
	docker compose -p $(COMPOSE_PROJECT_NAME) down

migrate:
	cd backend && .venv/bin/alembic upgrade head

backend-dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log

frontend-dev:
	cd frontend && npm run dev

operator-worker:
	cd backend && .venv/bin/python -m scripts.run_operator_worker

operator-worker-loop:
	cd backend && .venv/bin/python -m scripts.run_operator_worker_loop

activate-test-angle-runtime:
	@test -n "$(MODEL)" || (echo "MODEL is required" && exit 2)
	@test -n "$(APPROVED_BY)" || (echo "APPROVED_BY is required" && exit 2)
	cd backend && APP_ENV=test .venv/bin/python -m scripts.activate_test_angle_runtime --model "$(MODEL)" --approved-by "$(APPROVED_BY)"

openapi:
	cd backend && .venv/bin/python -m scripts.dump_openapi

types: openapi
	cd frontend && npm run gen:types

test-db-prepare:
	cd backend && APP_ENV=test .venv/bin/python -m scripts.prepare_test_database
	cd backend && APP_ENV=test .venv/bin/alembic upgrade head

test-db-reset:
	cd backend && APP_ENV=test .venv/bin/python -m scripts.prepare_test_database --reset
	cd backend && APP_ENV=test .venv/bin/alembic upgrade head

ops-inspect:
	cd backend && .venv/bin/python -m scripts.ops_inspect

ops-preflight:
	cd backend && .venv/bin/python -m scripts.ops_preflight

backup:
	cd backend && COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) .venv/bin/python -m scripts.ops_backup

restore-test:
	@test -n "$(BACKUP)" || (echo "BACKUP is required: make restore-test BACKUP=/path/to/file.dump" && exit 2)
	cd backend && COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) .venv/bin/python -m scripts.ops_restore_verify "$(BACKUP)"

migration-rehearsal:
	@test -n "$(BACKUP)" || (echo "BACKUP is required: make migration-rehearsal BACKUP=/path/to/file.dump" && exit 2)
	cd backend && COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) .venv/bin/python -m scripts.ops_migration_rehearsal "$(BACKUP)"

operational-migrate:
	@test -n "$(BACKUP)" || (echo "BACKUP is required: make operational-migrate BACKUP=/path/to/file.dump AUTHORIZED_HEAD=<sha>" && exit 2)
	@test -n "$(AUTHORIZED_HEAD)" || (echo "AUTHORIZED_HEAD is required" && exit 2)
	cd backend && .venv/bin/python -m scripts.ops_operational_migrate "$(BACKUP)" --authorized-head "$(AUTHORIZED_HEAD)"

backend-check:
	cd backend && .venv/bin/ruff check app tests scripts migrations
	cd backend && .venv/bin/mypy app
	$(MAKE) test-db-reset
	cd backend && APP_ENV=test .venv/bin/pytest
	cd backend && APP_ENV=test .venv/bin/python -m scripts.dump_openapi

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

check: backend-check frontend-check

ocr-validate-refs:
	@$(PYTHON) -c 'import re, sys; sys.exit(0 if re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]) else 2)' "$(OCR_BASE)" || { echo "OCR_BASE must be the exact full 40-character lowercase commit SHA"; exit 2; }
	@$(PYTHON) -c 'import re, sys; sys.exit(0 if re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]) else 2)' "$(OCR_HEAD)" || { echo "OCR_HEAD must be the exact full 40-character lowercase commit SHA"; exit 2; }
	@git cat-file -e "$(OCR_BASE)^{commit}" 2>/dev/null || { echo "OCR_BASE must identify an existing commit"; exit 2; }
	@git cat-file -e "$(OCR_HEAD)^{commit}" 2>/dev/null || { echo "OCR_HEAD must identify an existing commit"; exit 2; }

ocr-preview: ocr-validate-refs
	mkdir -p "$(dir $(OCR_PREVIEW_OUTPUT))"
	ocr delegate preview --format json --from "$(OCR_BASE)" --to "$(OCR_HEAD)" --background-file "$(OCR_BACKGROUND)" > "$(OCR_PREVIEW_OUTPUT)"
	cat "$(OCR_PREVIEW_OUTPUT)"

ocr-review-direct: ocr-validate-refs
	mkdir -p "$(dir $(OCR_OUTPUT))"
	ocr review --audience agent --format json --from "$(OCR_BASE)" --to "$(OCR_HEAD)" --background-file "$(OCR_BACKGROUND)" --output "$(OCR_OUTPUT)"
