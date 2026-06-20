# Crawfish task runner. Run `just` to list recipes.

# show available recipes
default:
    @just --list

# install the workspace + dev dependencies (editable)
deps:
    uv sync

# serve the docs site locally with live reload (http://127.0.0.1:8000)
docs:
    uv run --group docs mkdocs serve

# build the docs site to ./site (strict: fails on broken links)
docs-build:
    uv run --group docs mkdocs build --strict

# lint, format-check, typecheck, and test — the full gate
check: lint typecheck test

# lint with ruff
lint:
    uv run ruff check .
    uv run ruff format --check .

# auto-format with ruff
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# typecheck with mypy (strict)
typecheck:
    uv run mypy packages/crawfish/src packages/crawfish-slack/src

# run the test suite
test:
    uv run pytest -q

# run the demo end to end (zero key, mock runtime)
demo:
    uv run craw dev demo/triage-bot -i project=acme -i "ticket_body=login is broken"
