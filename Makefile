# md-converter — orchestration locale
# Postgres tourne hors-container (machine hôte, port 5432).
# Redis + api + worker + web tournent via docker compose (cf. docker-compose.yml).

SHELL := /bin/bash
.DEFAULT_GOAL := help

DC ?= docker compose
PNPM ?= pnpm
PY ?= python3
UV ?= uv
PSQL ?= psql

DB_NAME ?= md-converter_db
DB_USER ?= donthenluyangenorsoro

.PHONY: help
help: ## Affiche cette aide
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<cible>\033[0m\n\nCibles:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

.PHONY: bootstrap
bootstrap: env db-create ## Première installation (env + DB locale)
	@echo "Bootstrap terminé. Lance 'make dev' pour démarrer la stack."

.PHONY: env
env: ## Crée .env depuis .env.example si absent
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✔ .env créé depuis .env.example — édite-le si besoin."; \
	else \
		echo "✓ .env existe déjà."; \
	fi

.PHONY: db-create
db-create: ## Crée la base Postgres locale si absente
	@$(PSQL) -U $(DB_USER) -lqt | cut -d \| -f 1 | grep -qw $(DB_NAME) \
		&& echo "✓ Base '$(DB_NAME)' déjà présente." \
		|| (createdb -U $(DB_USER) $(DB_NAME) && echo "✔ Base '$(DB_NAME)' créée.")

.PHONY: db-drop
db-drop: ## Supprime la base Postgres locale (DESTRUCTIF — demande confirmation)
	@read -p "Supprimer la base '$(DB_NAME)' ? [y/N] " ans && [ "$$ans" = "y" ] \
		&& dropdb -U $(DB_USER) $(DB_NAME) \
		|| echo "Abandon."

# ---------------------------------------------------------------------------
# Dev stack
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Démarre toute la stack (redis + api + worker + web)
	$(DC) up --build

.PHONY: dev-detached
dev-detached: ## Démarre la stack en arrière-plan
	$(DC) up --build -d

.PHONY: stop
stop: ## Arrête la stack sans supprimer les volumes
	$(DC) stop

.PHONY: down
down: ## Stoppe et supprime les containers (volumes conservés)
	$(DC) down

.PHONY: logs
logs: ## Suit les logs de tous les services
	$(DC) logs -f --tail=200

.PHONY: ps
ps: ## Liste les containers actifs
	$(DC) ps

# ---------------------------------------------------------------------------
# Database / migrations
# ---------------------------------------------------------------------------

.PHONY: db-migrate
db-migrate: ## Applique les migrations Drizzle (apps/web)
	cd apps/web && $(PNPM) drizzle-kit migrate

.PHONY: db-generate
db-generate: ## Génère une nouvelle migration Drizzle depuis le schema
	cd apps/web && $(PNPM) drizzle-kit generate

.PHONY: db-studio
db-studio: ## Ouvre Drizzle Studio
	cd apps/web && $(PNPM) drizzle-kit studio

# ---------------------------------------------------------------------------
# Tests & lint
# ---------------------------------------------------------------------------

.PHONY: test
test: test-web test-api ## Lance tous les tests

.PHONY: test-web
test-web: ## Tests TypeScript (vitest/playwright)
	cd apps/web && $(PNPM) test

.PHONY: test-api
test-api: ## Tests Python (pytest)
	cd apps/api && $(UV) run pytest

.PHONY: lint
lint: lint-web lint-api ## Lint l'ensemble du monorepo

.PHONY: lint-web
lint-web: ## Lint + type-check Next.js
	cd apps/web && $(PNPM) lint && $(PNPM) type-check

.PHONY: lint-api
lint-api: ## Lint Python (ruff) + type-check (mypy)
	cd apps/api && $(UV) run ruff check .
	cd apps/api && $(UV) run mypy app

.PHONY: format
format: ## Formate le code (prettier + ruff)
	cd apps/web && $(PNPM) format
	cd apps/api && $(UV) run ruff format .

.PHONY: api-dev
api-dev: ## Démarre l'API en mode reload hors-docker
	cd apps/api && $(UV) run uvicorn app.main:app --reload --port 8000

.PHONY: worker-dev
worker-dev: ## Démarre un worker Celery hors-docker (redis doit tourner)
	cd apps/api && $(UV) run celery -A app.tasks.celery_app:celery_app worker --loglevel=info --concurrency=2

.PHONY: redis-up
redis-up: ## Démarre uniquement Redis via docker compose
	$(DC) up -d redis

.PHONY: api-sync
api-sync: ## uv sync (installe / met à jour les deps Python)
	cd apps/api && $(UV) sync

# ---------------------------------------------------------------------------
# Sécurité
# ---------------------------------------------------------------------------

.PHONY: audit
audit: ## Audit des dépendances (pnpm + pip-audit)
	cd apps/web && $(PNPM) audit --audit-level=moderate || true
	cd apps/api && $(UV) run pip-audit || true

# ---------------------------------------------------------------------------
# Nettoyage
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Nettoie caches & build artifacts
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	@find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	@find . -type d -name ".turbo" -prune -exec rm -rf {} +
	@find . -type d -name ".next" -prune -exec rm -rf {} +
	@find . -type d -name "node_modules" -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "✔ Caches nettoyés."

.PHONY: clean-data
clean-data: ## Vide /data/input et /data/output (DESTRUCTIF — demande confirmation)
	@read -p "Vider /data/input et /data/output ? [y/N] " ans && [ "$$ans" = "y" ] \
		&& find data/input data/output -type f ! -name '.gitkeep' -delete \
		|| echo "Abandon."

.PHONY: nuke
nuke: down clean ## Arrête la stack et nettoie tout (sauf la DB)
	$(DC) down -v
	@echo "✔ Stack nettoyée (volumes inclus)."
