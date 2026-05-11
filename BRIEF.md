# Brief Claude Code — MD Converter (v2)

## 1. Contexte

Développeur solo (Henluy Soro, ditta individuale Italie). Stack habituel : Next.js + PostgreSQL local pour le dev, déploiement cloud envisagé Phase 3 (Supabase ou Postgres managé).

Besoin : convertir EPUB et PDF en Markdown propre pour alimenter un workflow KDP d'écriture de livres et un usage personnel de bibliothèque.

## 2. Vision produit

**Phase 1 — Outil perso (MVP)** : web app locale, conversion 100% sur ma machine, PostgreSQL local déjà installé, zéro dépendance cloud, zéro coût d'API.

**Phase 2 — Polish** : auth, settings, watch folder, intégration au workflow KDP.

**Phase 3 — SaaS** : même frontend, workers déplacés en cloud, Stripe, freemium. Migration PostgreSQL local → Supabase/Postgres managé sans réécriture de schéma.

**Principe directeur** : architecture découplée et schéma DB portable pour que le passage Phase 1 → Phase 3 ne nécessite qu'un changement de connection string et le déploiement des containers.

## 3. Stack figé

### Frontend
- Next.js 14+ (App Router) — TypeScript strict
- Tailwind CSS + **shadcn/ui** (composants de base)
- **Framer Motion** (micro-animations)
- TanStack Query (polling des jobs)
- react-dropzone (upload)
- next-themes (dark mode dès le MVP)

### Backend conversion
- Python 3.11+
- FastAPI
- Celery + Redis (queue de jobs)
- Pandoc (binaire système) → EPUB
- pymupdf4llm → PDF texte simple
- marker-pdf → PDF complexe / scanné (OCR)
- markitdown → fallback / formats divers

### Database
- **PostgreSQL local** (déjà installé sur la machine — port 5432, user `donthenluyangenorsoro`)
- **Drizzle ORM** côté Next.js (TypeScript-natif, migrations SQL pures, portables vers Supabase plus tard)
- **SQLAlchemy + asyncpg** côté Python (Celery worker écrit dans la même DB)
- Migrations en SQL brut → fonctionnent identiquement sur Postgres local et Supabase

### Storage fichiers
- Filesystem local : `/data/input`, `/data/output` (path configurable via env)
- Phase 3 : remplacer par Supabase Storage ou S3 (interface storage abstraite dès le MVP)

### Déploiement local
- `docker-compose.yml` : web, api, worker, redis (Postgres reste hors-container, sur la machine)
- `Makefile` : `make dev`, `make test`, `make db-migrate`, `make clean`

## 4. Architecture

```
┌─────────────────────┐
│  Next.js (3000)     │  ← UI : upload, queue, preview, download
└──────────┬──────────┘
           │ REST + polling (TanStack Query)
           ▼
┌─────────────────────┐
│  FastAPI (8000)     │  ← API : POST /jobs, GET /jobs/:id, GET /files/:id
└──────────┬──────────┘
           │ enqueue
           ▼
┌─────────────────────┐
│  Redis + Celery     │  ← Queue scalable, locale puis cloud
│  worker             │
└──────────┬──────────┘
           │ dispatch
           ▼
   ┌───────┴───────┬─────────────┬──────────────┐
   ▼               ▼             ▼              ▼
 Pandoc      pymupdf4llm     Marker         MarkItDown
 (EPUB)      (PDF natif)     (PDF scan)     (fallback)
           │
           ▼
┌─────────────────────┐
│  PostgreSQL (local) │  ← jobs, files, history
└─────────────────────┘
           +
┌─────────────────────┐
│  FS /data/{in,out}  │  ← fichiers source + .md générés
└─────────────────────┘
```

## 5. Logique de routage des convertisseurs

| Format détecté | Convertisseur par défaut | Override |
|----------------|--------------------------|----------|
| `.epub` | Pandoc | — |
| `.pdf` texte natif | pymupdf4llm | Marker |
| `.pdf` scanné (images) | Marker (OCR) | — |
| `.docx`, `.html`, autres | MarkItDown | — |

Détection PDF texte vs scanné : sample 3 pages, ratio caractères extractibles / pixels.

## 6. Scope MVP (Phase 1) — strict

### À FAIRE
1. Upload drag-drop, single ou batch (max 50 fichiers/job)
2. Détection auto du format + routage convertisseur
3. Queue de jobs avec statut temps réel : `pending`, `processing`, `done`, `failed`
4. Page détail job : preview markdown généré (split view : meta / md)
5. Download single (.md) ou batch (.zip)
6. Historique paginé des conversions
7. Suppression manuelle d'un job + fichiers associés (avec confirmation)
8. Logs d'erreur visibles dans l'UI
9. Dark mode (toggle dans header)

### À NE PAS FAIRE en MVP
- Authentification multi-user
- Stripe / pricing
- Watch folder
- Édition du markdown dans l'UI
- Export vers Drive / KDP folder
- API publique
- Multi-langue UI (FR uniquement)

## 7. Structure de projet

```
md-converter/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml            # Lint + tests sur PR
│   │   └── codeql.yml        # Scan sécurité
│   ├── dependabot.yml        # Auto-update deps
│   └── PULL_REQUEST_TEMPLATE.md
├── apps/
│   ├── web/                  # Next.js
│   │   ├── app/
│   │   │   ├── page.tsx               # Dashboard
│   │   │   ├── jobs/[id]/page.tsx     # Détail job
│   │   │   ├── history/page.tsx
│   │   │   └── api/                   # Route handlers proxy si besoin
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui
│   │   │   ├── upload/
│   │   │   ├── jobs/
│   │   │   └── layout/
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── db.ts                  # Drizzle client
│   │   │   └── schema.ts              # Drizzle schema
│   │   ├── drizzle/
│   │   │   └── migrations/            # SQL généré
│   │   ├── drizzle.config.ts
│   │   └── package.json
│   └── api/                  # FastAPI
│       ├── app/
│       │   ├── main.py
│       │   ├── routes/
│       │   ├── converters/
│       │   │   ├── base.py            # Interface ABC
│       │   │   ├── pandoc.py
│       │   │   ├── pymupdf.py
│       │   │   ├── marker.py
│       │   │   ├── markitdown.py
│       │   │   └── router.py
│       │   ├── tasks/celery_tasks.py
│       │   ├── models/                # Pydantic + SQLAlchemy
│       │   ├── security/              # Validation, sanitization
│       │   └── utils/pdf_inspector.py
│       ├── tests/
│       ├── pyproject.toml
│       └── Dockerfile
├── data/                     # Gitignored
│   ├── input/
│   └── output/
├── docker-compose.yml
├── Makefile
├── .env.example              # Template, committé
├── .env                      # JAMAIS committé
├── .gitignore
├── SECURITY.md
└── README.md
```

## 8. Schéma DB (PostgreSQL — portable Supabase)

```sql
-- migrations/0001_init.sql

create extension if not exists "uuid-ossp";

create table jobs (
  id uuid primary key default uuid_generate_v4(),
  status text not null default 'pending'
    check (status in ('pending', 'processing', 'done', 'failed')),
  created_at timestamptz default now(),
  completed_at timestamptz,
  error_message text,
  total_files int default 0,
  processed_files int default 0
);

create table files (
  id uuid primary key default uuid_generate_v4(),
  job_id uuid references jobs(id) on delete cascade,
  original_filename text not null,
  stored_filename text not null,        -- UUID-based, jamais nom utilisateur
  original_format text not null,
  storage_path text not null,           -- relatif à /data
  output_path text,
  converter_used text,
  size_bytes bigint,
  pages int,
  created_at timestamptz default now()
);

create index files_job_id_idx on files(job_id);
create index jobs_status_idx on jobs(status);
create index jobs_created_at_idx on jobs(created_at desc);

-- Préparation Phase 3 (commenté pour MVP)
-- alter table jobs add column user_id uuid;  -- pour Supabase Auth plus tard
```

**Note** : aucun feature Supabase-spécifique (pas de RLS, pas de `auth.users`). Au passage SaaS, ajout d'`user_id` + RLS policies sans casser l'existant.

## 9. Setup GitHub & versionnage

### Création du repo
```bash
# Via gh CLI (recommandé)
gh repo create md-converter --private --source=. --remote=origin

# Ou via web : github.com/new (privé pour commencer)
git remote add origin git@github.com:henluysoro/md-converter.git
```

### `.gitignore` (non-négociable, à inclure dès le premier commit)
```
# Env & secrets
.env
.env.local
.env.*.local
*.pem
*.key

# Data (fichiers utilisateur)
/data/input/*
/data/output/*
!/data/input/.gitkeep
!/data/output/.gitkeep

# Node
node_modules/
.next/
out/
*.log

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/

# DB locales
*.sqlite
*.db

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
```

### Stratégie de branches
- `main` : protégée, déploiement uniquement
- `dev` : branche d'intégration
- `feat/xxx`, `fix/xxx`, `chore/xxx` : feature branches
- **Conventional Commits** obligatoires : `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`

### Branch protection sur `main`
- Require PR avant merge
- Require status checks (CI green)
- Pas de force push
- Pas de suppression

### GitHub Actions (CI minimal)
`.github/workflows/ci.yml` doit faire sur chaque PR :
- Lint TypeScript (`pnpm lint`)
- Type-check TS (`pnpm type-check`)
- Tests web (`pnpm test`)
- Lint Python (`ruff check`)
- Tests API (`pytest`)
- Scan vulnérabilités deps (`pnpm audit`, `pip-audit`)

### Dependabot
Activer sur npm et pip. Auto-merge des patches mineurs après CI green.

## 10. Sécurité — non-négociable

### Secrets
- `.env` jamais committé (vérifier `.gitignore` au premier commit)
- `.env.example` committé avec valeurs factices
- Si fuite : rotation immédiate, `git filter-repo` pour nettoyer l'historique
- Aucun secret dans le code, dans les logs, ou dans les messages d'erreur exposés à l'UI

### Validation des uploads
Chaque fichier uploadé doit passer :
1. **Whitelist d'extensions** : `.epub`, `.pdf`, `.docx`, `.html`, `.txt` uniquement
2. **Magic number check** : valider le vrai type via `python-magic`, pas juste l'extension
3. **Limite de taille** : 100 MB max par fichier, 500 MB max par job
4. **Limite de nombre** : 50 fichiers max par job
5. **Nom de fichier sanitisé** : le nom original est stocké en DB, mais sur le filesystem on utilise un UUID (`{uuid}.pdf`). Jamais le nom utilisateur sur disque.

### Prévention path traversal
- Tous les chemins de stockage validés avec `Path(target).resolve().is_relative_to(DATA_DIR.resolve())`
- Reject si un chemin sort de `/data`
- Pas de concaténation de strings pour les paths, toujours `pathlib.Path`

### Sécurité PDF
- Les PDF peuvent contenir du JavaScript, des liens malveillants, des objets actifs
- Avant traitement : strip JS via `pikepdf` ou désactiver l'exécution dans le parser
- Marker et pymupdf4llm n'exécutent pas le JS → safe par défaut, mais documenter
- Limites de ressources sur le worker : timeout 5 min par fichier, max RAM 2 GB

### XSS dans la preview markdown
- Le markdown généré peut contenir du HTML injecté par le PDF source
- Render la preview avec un sanitizer : `DOMPurify` côté client, ou `markdown-it` + sanitize plugin
- Pas de `dangerouslySetInnerHTML` sur du contenu non-sanitisé

### API
- CORS : restreint à `http://localhost:3000` en dev
- Rate limiting : `slowapi` (FastAPI) — 60 req/min par IP en local, même valeur préparée pour cloud
- Pas de stack traces dans les responses d'erreur en prod
- Logs structurés (JSON) sans inclure de contenu de fichier

### Containers
- Dockerfiles : non-root user obligatoire
- Images de base : versions pinnées (pas de `:latest`)
- Pas de secrets dans les layers
- `docker scout` ou `trivy` dans la CI

### Dépendances
- Lockfiles committés (`pnpm-lock.yaml`, `poetry.lock` ou `requirements.txt` figé)
- Dependabot actif
- Audit régulier avec `pnpm audit` et `pip-audit`

### Fichier `SECURITY.md` à la racine
Reporter les vulnérabilités à `sorohenluy@gmail.com`, PGP key optionnelle.

## 11. Frontend — design impeccable (non-négociable)

### Direction artistique
**Pas un dashboard SaaS générique.** L'app convertit des livres : l'esthétique doit être **éditoriale, calme, typographique, premium**. Évoque une bibliothèque numérique haut de gamme.

### Références d'inspiration (à étudier avant de coder)
- **Linear** (clarté, vitesse perçue, micro-interactions)
- **Read.cv** (typographie éditoriale, espace généreux)
- **Readwise Reader** (interface livre/lecture)
- **Vercel dashboard** (sobriété premium)
- **Things 3** (calme, hiérarchie typographique)

### Système de design

**Typographie** :
- UI : `Geist Sans` (Vercel) ou `Inter`
- Contenu / preview markdown : `Newsreader` ou `Source Serif Pro` (serif pour le markdown rendu)
- Mono (code, paths) : `Geist Mono` ou `JetBrains Mono`

**Couleurs (light mode)** :
- Background : `#FAFAF7` (parchemin très subtil, pas blanc pur)
- Foreground : `#1A1A1A` (encre, pas noir pur)
- Muted : `#F0EFEA`
- Accent : `#8B6F47` (encre brune) ou `#2D5F3F` (vert forêt)
- Border : `#E5E3DC`

**Couleurs (dark mode)** :
- Background : `#0F0E0C`
- Foreground : `#F0EFEA`
- Muted : `#1A1916`
- Accent : `#D4A574` (encre claire)

**Espacement** : généreux. Base 8px. Padding minimum 24px sur les cards. Aérer.

**Bordures** : `1px solid` subtil, rayon `8px` (pas `rounded-full` partout).

**Ombres** : minimales. Privilégier les bordures aux ombres lourdes.

### Composants clés à soigner

**1. Zone d'upload (dashboard)**
- Pleine largeur, prend de la place
- Bordure pointillée subtile au repos
- Au drag : fond ambré léger, scale subtle, bordure accent
- Icône large (Lucide `BookOpen` ou `FileText`)
- Texte hiérarchique : titre serif, sous-titre sans-serif gris
- Pas de bouton "Browse" laid → toute la zone clickable

**2. Liste des jobs**
- Cards verticales, pas de table dense
- Chaque card : titre fichier (truncate), statut (badge subtle), nombre de pages, durée, taille
- Statuts animés : `processing` avec pulse subtil, `done` avec check qui apparaît
- Hover : élévation légère, transition 150ms

**3. Page détail job — preview markdown**
- Split view : panneau gauche métadonnées (étroit), panneau droit preview (large)
- Preview rendue avec `react-markdown` + `rehype-highlight`
- Typo serif pour le rendu, comme on lirait un livre
- Bouton download flottant en bas-droite
- Bouton "Copier le markdown" qui copie le raw

**4. Empty states**
- Pas de "No data" plat
- Illustration SVG simple (livre ouvert, plume) + phrase invitante
- "Glisse ton premier livre ici pour commencer"

**5. Loading states**
- Skeleton screens, pas de spinner centré
- Progress bar pour la conversion : déterminée si possible (pages traitées / total), sinon barre infinie élégante

**6. Animations (Framer Motion)**
- Entrée des cards : stagger 50ms, fade + translate-y 8px
- Modale : scale 0.96 → 1, fade
- Page transitions : fade léger
- **Pas d'animations bouncy ou clownesques**. Easing `[0.16, 1, 0.3, 1]` (out-expo).

### Non-négociables visuels
- Dark mode dès le MVP, toggle visible
- Responsive : utilisable sur tablette (laptop minimum)
- Aucune emoji dans l'UI (à part Lucide icons)
- Aucun gradient agressif
- Aucun bouton "néon"
- Pas de modal qui prend 80% de l'écran pour une simple confirmation

### À utiliser obligatoirement
- Lire `/mnt/skills/public/frontend-design/SKILL.md` avant de commencer la moindre composante UI
- shadcn/ui pour les primitives (button, dialog, dropdown, toast)
- Lucide React pour les icônes
- Framer Motion pour les animations
- `cmdk` pour la palette de commandes (Ctrl+K) — phase 1.5

## 12. Conventions de code

### TypeScript
- `strict: true`
- Pas de `any` sauf justification commentée
- Server Components par défaut, `'use client'` uniquement quand nécessaire
- Data fetching via Server Actions ou route handlers (pas fetch direct dans composants)
- `zod` pour valider tous les inputs côté API routes

### Python
- Type hints partout
- Pydantic v2 pour tous les modèles d'API
- `ruff` + `black` configurés
- Pattern Strategy pour convertisseurs : héritent de `BaseConverter` avec `convert(input_path: Path) -> ConversionResult`

### Tests minimum
- API : pytest sur le routeur + chaque convertisseur (1 fichier test/converter)
- Web : Playwright sur le flow upload → download
- Pas de couverture exigée, juste les chemins critiques

## 13. Variables d'environnement (.env.example)

```dotenv
# Database (local Postgres déjà installé)
DATABASE_URL=postgresql://donthenluyangenorsoro@localhost:5432/md-converter_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=md-converter_db
DB_USER=donthenluyangenorsoro
DB_PASSWORD=

# API
API_PORT=8000
DATA_DIR=./data
MAX_FILE_SIZE_MB=100
MAX_JOB_SIZE_MB=500
MAX_FILES_PER_JOB=50

# Redis (containerisé)
REDIS_URL=redis://redis:6379

# Web
NEXT_PUBLIC_API_URL=http://localhost:8000

# Convertisseurs
MARKER_USE_GPU=false
MARKER_BATCH_SIZE=2
PANDOC_PATH=/usr/local/bin/pandoc

# Sécurité
CORS_ORIGINS=http://localhost:3000
RATE_LIMIT_PER_MINUTE=60
```

**Important** : `DB_NAME=md-converter_db` (cohérent avec `DATABASE_URL`). Si la DB n'existe pas encore localement :
```bash
createdb -U donthenluyangenorsoro md-converter_db
```

## 14. Critères d'acceptation Phase 1

- [ ] `make dev` démarre web, api, worker, redis sans erreur
- [ ] La DB est connectée et les migrations passent
- [ ] Drag-drop de 10 fichiers mixtes (EPUB + PDF) → tout converti en < 5 min
- [ ] EPUB converti ouvert dans VSCode : structure markdown propre (titres, listes, italique)
- [ ] PDF avec tableaux passe en Marker, tableaux préservés
- [ ] Historique survit à un redémarrage des containers
- [ ] Dark mode fonctionne sans flash au reload
- [ ] Tous les checks CI passent sur la PR initiale
- [ ] `.env` jamais apparu dans `git log`
- [ ] Test de path traversal échoue proprement (`../../../etc/passwd` rejeté)
- [ ] Aucune dépendance à une API cloud payante

## 15. Hors-scope explicite (refuser même si tentant)

- Édition du markdown dans l'UI
- Génération de PDF inverse
- Intégration directe au workflow KDP (sera fait en Phase 2)
- Multi-user / partage
- Marketing pages / landing
- Tests E2E exhaustifs (juste le flow critique)
- i18n
- Mobile responsive complet (tablet OK, mobile plus tard)

## 16. Plan d'attaque (ordre des tickets)

Chaque ticket = un commit qui marche en isolation.

1. **Init repo GitHub** : `gh repo create`, `.gitignore`, README minimal, `SECURITY.md`, branch protection, dependabot
2. **Setup monorepo** : structure dossiers, `docker-compose.yml`, `Makefile`, `.env.example`
3. **DB + Drizzle** : migration init, schema, connection client TS, vérifier sur Postgres local
4. **API squelette** : FastAPI, SQLAlchemy + asyncpg, route `/health`, Pydantic models
5. **Convertisseur Pandoc seul** : sans queue, ligne de commande directe
6. **Queue Celery + Redis** : un job manuel converti via worker
7. **Routeur de convertisseurs** + détection format + magic number check
8. **Ajout pymupdf4llm, marker, markitdown**
9. **Validation sécurité** : taille, extension, path traversal, sanitization noms
10. **Persistance des jobs** en DB
11. **Frontend setup** : Next.js, shadcn/ui, Tailwind, Geist + Newsreader fonts, dark mode
12. **Composant upload + dashboard** (soigner le design)
13. **Liste jobs avec polling TanStack**
14. **Page détail job + preview markdown**
15. **Download single + ZIP**
16. **Historique + suppression**
17. **CI GitHub Actions** : lint + tests + audit
18. **README complet** : install, run, troubleshoot, screenshots

---

**Avant de coder, à confirmer :**
1. Nom définitif du projet (placeholder : `md-converter`)
2. Repo GitHub : privé pour commencer ? (recommandé)
3. Marker en GPU ou CPU ?
4. Marque visuelle / nom commercial Phase 3 envisagé ?
