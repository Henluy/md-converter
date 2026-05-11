# md-converter

Conversion locale EPUB / PDF → Markdown propre.

**Statut** : WIP — MVP Phase 1 (outil personnel, 100% local, zéro dépendance cloud).

## Stack

- **Frontend** : Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui + Framer Motion
- **API** : FastAPI + Python 3.11
- **Queue** : Celery + Redis
- **Convertisseurs** : Pandoc (EPUB), pymupdf4llm (PDF natif), marker-pdf (PDF scanné/OCR), markitdown (fallback)
- **DB** : PostgreSQL 17 local (Drizzle ORM côté Next, SQLAlchemy+asyncpg côté worker)
- **Storage** : filesystem local sous `./data/{input,output}`

## Démarrage rapide

```bash
# 1. Pré-requis : Postgres 17 local, Docker, pnpm, Python 3.11, Pandoc, libmagic
# 2. Créer la DB
createdb -U donthenluyangenorsoro md-converter_db

# 3. Copier l'env
cp .env.example .env

# 4. Lancer la stack
make dev
```

Web : http://localhost:3000 — API : http://localhost:8000

## Documentation

- Architecture : voir `BRIEF.md`
- Sécurité : voir `SECURITY.md`

## Licence

MIT — voir `LICENSE`.
