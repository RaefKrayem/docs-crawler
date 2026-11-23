# docs-crawler

Distributed, fault-tolerant documentation crawler (ForwardMena Phase 1).

**Status:** in progress

## Prerequisites

- Git
- uv
- Docker Desktop

## Run checks locally

```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```
