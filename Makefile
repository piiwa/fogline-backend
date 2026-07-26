.PHONY: install run stop test format format-check lint typecheck migrate check

install:
	poetry install

# Frees the port first: a previous --reload run leaves a listener behind often
# enough that "Address already in use" became the normal way to start the app.
run:
	@lsof -ti:8250 | xargs kill -9 2>/dev/null || true
	poetry run uvicorn app.main:app --reload --port 8250

stop:
	@lsof -ti:8250 | xargs kill -9 2>/dev/null || true
	@echo "port 8250 free"

test:
	poetry run pytest -q

format:
	poetry run black app tests && poetry run isort app tests

# Verification only — never rewrites the tree. `check` used to run `format`,
# which meant a formatting problem was silently fixed instead of reported.
format-check:
	poetry run black --check app tests && poetry run isort --check-only app tests

lint:
	poetry run flake8 app tests

typecheck:
	poetry run mypy app

migrate:
	poetry run alembic upgrade head

check: format-check lint typecheck test
