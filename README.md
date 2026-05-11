# md-converter

Conversion **locale** d'EPUB et de PDF en Markdown propre. Zéro dépendance cloud, zéro coût d'API.

**Statut**: MVP Phase 1 complet — outil personnel utilisable.

<p align="center">
  <em>Une bibliothèque silencieuse, taillée pour le Markdown.</em>
</p>

---

## Stack

| Couche       | Technologie                                                                 |
|--------------|------------------------------------------------------------------------------|
| Frontend     | Next.js 15 (App Router) · React 19 · TypeScript strict                       |
|              | Tailwind v4 · shadcn-style components · Framer Motion · TanStack Query       |
|              | Geist Sans + Mono · Newsreader (serif éditorial)                              |
| API          | Python 3.11 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async + sync)           |
| Worker       | Celery 5 · Redis 7                                                            |
| Convertisseurs | Pandoc (EPUB) · pymupdf4llm (PDF natif) · MarkItDown (DOCX/HTML/TXT)        |
|              | _Marker (OCR scanné) : prévu en Phase 2 — opt-in via env_                    |
| DB           | PostgreSQL 17 · Drizzle ORM (migrations) · asyncpg (API) · psycopg 3 (worker) |
| Tooling      | uv · pnpm workspaces · Docker Compose · Makefile                             |

Architecture détaillée : voir [`BRIEF.md`](BRIEF.md) §4.

---

## Pré-requis

| Outil       | Version minimale | Pourquoi                                                |
|-------------|------------------|---------------------------------------------------------|
| PostgreSQL  | 17               | Stockage des jobs et files                              |
| Node.js     | 20.x             | Frontend Next.js                                        |
| pnpm        | 9.x              | Workspaces monorepo                                     |
| Python      | 3.11             | Backend FastAPI + worker Celery                         |
| uv          | 0.5+             | Gestion des deps Python                                 |
| Docker      | 24+              | Redis containerisé (et plus tard l'API en prod)         |
| Pandoc      | 3.x              | Conversion EPUB                                         |
| libmagic    | 5.x              | Détection MIME des uploads                              |

Sur macOS :

```bash
brew install postgresql@17 pandoc libmagic redis
brew services start postgresql@17
curl -LsSf https://astral.sh/uv/install.sh | sh
corepack enable && corepack prepare pnpm@9 --activate
```

---

## Démarrage rapide

```bash
git clone <url> md-converter && cd md-converter

# 1) Env local
cp .env.example .env
# (ajuste DATABASE_URL si ton user/DB diffèrent)

# 2) Crée la base
make db-create     # ≈ createdb -U donthenluyangenorsoro md-converter_db

# 3) Installe les deps
pnpm install            # workspaces Node
cd apps/api && uv sync && cd ../..

# 4) Applique le schéma (Drizzle)
pnpm --filter @md/web db:migrate

# 5) Lance la stack
make redis-up           # Redis dans Docker
make api-dev            # FastAPI sur :8000 (autoreload)
make worker-dev         # Worker Celery (autre terminal)
cd apps/web && pnpm dev # Next.js sur :3000 (autre terminal)
```

Ouvre **http://localhost:3000**, glisse un fichier, regarde le job passer `pending → processing → done` en temps réel.

> `make dev` lance toute la stack via `docker compose up --build` une fois les Dockerfiles ticket 11/12 finalisés. En attendant, lance API / worker / web en local comme ci-dessus.

---

## Formats supportés

| Extension | Convertisseur par défaut | Override possible      |
|-----------|---------------------------|------------------------|
| `.epub`   | Pandoc                    | —                      |
| `.pdf` texte | pymupdf4llm            | Marker (Phase 2)       |
| `.pdf` scanné | Marker (Phase 2)      | —                      |
| `.docx`   | MarkItDown                | —                      |
| `.html`   | MarkItDown                | —                      |
| `.txt`    | MarkItDown                | —                      |

La détection texte/scan se fait via [`app/utils/pdf_inspector.py`](apps/api/app/utils/pdf_inspector.py) : échantillon des 3 premières pages, ratio caractères/pixels.

---

## Endpoints API

```
GET    /health                    Liveness probe
GET    /readiness                 Readiness (vérifie la DB)
POST   /api/jobs                  Multipart upload, crée un job, dispatch
GET    /api/jobs                  Liste paginée (limit, offset)
GET    /api/jobs/{id}             Détail d'un job + ses files
DELETE /api/jobs/{id}             Supprime job + files (DB + disque)
GET    /api/jobs/{id}/download    Stream d'un .zip de tous les .md
GET    /api/files/{id}/content    Markdown en text/markdown (preview)
GET    /api/files/{id}/download   .md en Content-Disposition attachment
```

Swagger interactif : http://localhost:8000/docs (en dev).

---

## Tests

```bash
# Backend (60+ tests intégration contre Postgres local)
make test-api

# Frontend (type-check + lint + build)
make test-web

# Tout
make test
```

CI GitHub Actions ([`/.github/workflows/ci.yml`](.github/workflows/ci.yml)) :

- `repo-lint` (gitleaks, `.env` non commit, `docker compose config`)
- `web` (lint, type-check, build production)
- `api` (ruff, mypy strict, pytest contre Postgres 17 service, pip-audit)
- CodeQL hebdo JS/TS + Python ([`codeql.yml`](.github/workflows/codeql.yml))
- Dependabot sur npm, uv, github-actions, docker ([`dependabot.yml`](.github/dependabot.yml))

---

## Structure du projet

```
md-converter/
├── apps/
│   ├── api/                  FastAPI + Celery worker (Python 3.11, uv)
│   │   ├── app/
│   │   │   ├── main.py             FastAPI app + middleware
│   │   │   ├── config.py           pydantic-settings
│   │   │   ├── db.py + db_sync.py  Async (asyncpg) + sync (psycopg) engines
│   │   │   ├── models/             SQLAlchemy + Pydantic
│   │   │   ├── routes/             health, jobs, files
│   │   │   ├── converters/         Pandoc, pymupdf4llm, MarkItDown + router
│   │   │   ├── security/           validation, storage path-traversal
│   │   │   ├── services/jobs.py    CRUD jobs/files (transactions sync)
│   │   │   ├── tasks/              Celery app + conversion task
│   │   │   ├── utils/pdf_inspector PDF text-vs-scan heuristic
│   │   │   └── cli.py              Conversion CLI sans queue
│   │   ├── tests/                  pytest intégration (Postgres réel)
│   │   ├── Dockerfile              Multi-stage, non-root, libmagic + pandoc
│   │   └── pyproject.toml          uv-managed
│   └── web/                  Next.js 15 (TypeScript, Tailwind v4)
│       ├── app/                    /, /jobs/[id], /history
│       ├── components/             upload/, jobs/, markdown/, ui/
│       ├── lib/                    api-client, hooks, providers, utils
│       ├── drizzle/                Schema + migrations Postgres
│       └── package.json
├── data/                     Gitignored — input/output filesystem
├── docker-compose.yml        Redis hardened (+ worker/api/web prêts)
├── Makefile                  bootstrap, dev, test, db-*, clean, audit, nuke
├── BRIEF.md                  Spécifications complètes
└── SECURITY.md               Modèle de menaces + mitigations
```

---

## Sécurité

Voir [`SECURITY.md`](SECURITY.md) pour le modèle de menaces complet. Résumé :

- Whitelist d'extensions (`.epub`, `.pdf`, `.docx`, `.html`, `.txt`)
- Magic-number check via `libmagic` (l'extension seule ne suffit pas)
- Limites: 100 MB/fichier, 500 MB/job, 50 fichiers/job
- Path traversal : `safe_resolve_relative(base, untrusted)` exigé sur tout I/O
- Sanitization noms : UUID-prefix sur disque, jamais le nom utilisateur tel quel
- CORS strict, rate limit 60 req/min (`slowapi`)
- Pas de stack traces dans les responses
- Containers non-root (uid 1000), `no-new-privileges`, Dockerfiles pinnés
- Lockfiles committés, Dependabot + CodeQL + gitleaks

Reporter une vulnérabilité : **sorohenluy@gmail.com**

---

## Troubleshoot

| Symptôme                                        | Piste                                                            |
|--------------------------------------------------|-------------------------------------------------------------------|
| `psql: command not found`                        | Ajoute `/opt/homebrew/opt/postgresql@17/bin` au `PATH`.            |
| `python-magic` lance `libmagic not found`        | `brew install libmagic`, vérifie `LD_LIBRARY_PATH`/`DYLD_*`.       |
| `pandoc: command not found`                      | `brew install pandoc` (ou inclure dans la PATH du container).      |
| Worker boucle sur `connection refused`           | Redis pas démarré : `make redis-up`.                               |
| FastAPI lève `database_url` not set              | Crée `.env` à la racine (cf. `.env.example`).                       |
| `GET /readiness` répond `degraded`               | DB injoignable. Vérifie `pg_isready`, `DATABASE_URL`, droits user.  |
| pytest plante en `SIGSEGV` sur macOS aarch64     | Bug pymupdf+pytest connu. Le `pytest_sessionfinish` workaround dans `tests/conftest.py` masque le crash de shutdown ; les tests eux-mêmes passent. |
| Frontend dit `Échec de l'upload — Failed to fetch` | API down ou CORS. Vérifie `NEXT_PUBLIC_API_URL` et `CORS_ORIGINS`. |
| Marker mentionné mais pas dispo                  | Phase 2 — non intégré dans le MVP. Les PDF scannés renvoient une erreur claire `marker not registered`. |

---

## Roadmap

**Phase 1 (livré)** :

- Backend complet : routes, worker, converters, sécurité, tests intégration
- Frontend complet : upload drag-drop, dashboard, polling, preview, download, suppression, historique paginé
- CI GitHub Actions, Dependabot, CodeQL, gitleaks

**Phase 2** (à venir) :

- Marker (OCR PDF scanné) en option opt-in via env
- Auth multi-user
- Watch folder (sync automatique d'un dossier)
- Intégration workflow KDP

**Phase 3** (SaaS) :

- Déploiement managed : Supabase ou Postgres cloud
- Stripe, freemium
- API publique

---

## Licence

MIT — voir [`LICENSE`](LICENSE).
