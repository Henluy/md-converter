# md-converter — API

FastAPI backend (Phase 1, MVP).

## Démarrage

```bash
cd apps/api
uv sync          # installe deps dans .venv
uv run uvicorn app.main:app --reload --port 8000
```

Vérifier : http://localhost:8000/health

## Tests

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```
