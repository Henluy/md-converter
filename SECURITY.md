# Politique de sécurité

## Versions supportées

Le projet est en développement actif. Seule la branche `main` reçoit des correctifs de sécurité.

## Signaler une vulnérabilité

Merci de ne **pas** ouvrir d'issue publique pour une faille de sécurité.

Contact : **sorohenluy@gmail.com**

Inclure dans le rapport :

- Description de la vulnérabilité
- Étapes de reproduction (idéalement un PoC minimal)
- Impact potentiel
- Versions affectées
- Suggestion de correctif si possible

Réponse sous 7 jours. Coordination de divulgation possible.

## Modèle de menaces (Phase 1 — outil local mono-utilisateur)

Cible : un binaire qui tourne sur la machine de l'auteur, accède à `localhost:5432`, ingère ses propres fichiers EPUB/PDF.

Menaces hors-périmètre Phase 1 (couvertes au passage SaaS Phase 3) :
- Multi-tenant / abus inter-utilisateurs
- Authentification, autorisation
- Exfiltration via SSRF (pas d'appel HTTP sortant côté worker)

Menaces dans le périmètre Phase 1 :
1. **Fichier malveillant en entrée** (PDF/EPUB hostile, extension usurpée)
2. **Path traversal** via un nom de fichier ou un `storage_path` manipulé
3. **Dépôt de fichiers oversized** qui sature le disque ou la RAM du worker
4. **XSS dans la preview Markdown** (HTML embarqué dans le PDF source)
5. **Fuite de secrets** dans logs / messages d'erreur / git
6. **Compromission de la chaîne de dépendances**

## Mitigations en place

| Menace | Mitigation | Localisation |
|--------|------------|--------------|
| Extension usurpée | Whitelist d'extensions + check magic-number via `libmagic` | `app.security.validation.detect_format` |
| Fichier oversized (par fichier) | `max_file_size_mb` (100 MB) appliqué avant routage | `validate_upload` |
| Batch oversized | `max_files_per_job` (50) et `max_job_size_mb` (500) appliqués à `create_job` | `app.services.jobs.create_job` |
| Path traversal | `safe_resolve_relative(base, untrusted)` exigé avant tout I/O ; rejette chemins absolus, `..`, symlinks externes | `app.security.storage` + `convert_file_task` |
| Collision / nom hostile sur disque | `sanitise_filename` + préfixe UUID systématique ; nom utilisateur jamais utilisé comme chemin | `app.converters.base.sanitise_filename` |
| Timeout / OOM du convertisseur | Soft + hard time limits Celery (5 min) ; chaque task isolée dans un fork pool | `app.tasks.celery_app` |
| Détection texte vs scanné (PDF) | Échantillon des 3 premières pages, ratio char/pixel | `app.utils.pdf_inspector` |
| Exposition de stack traces | Handlers d'erreur globaux qui renvoient un message générique | `app.main.create_app` |
| CORS | Whitelist d'origines, méthodes restreintes | `app.main.create_app` |
| Rate limiting | `slowapi`, 60 req/min par IP | `app.main.create_app` |
| Secrets dans le code | `.env` gitignored ; `pydantic-settings` lit l'environnement uniquement | `app.config.Settings` |
| Chaîne de dépendances | Lockfiles committés (`uv.lock`, `pnpm-lock.yaml`), Dependabot actif, `pip-audit` + `pnpm audit` en CI, CodeQL hebdo | `.github/dependabot.yml`, `.github/workflows/` |
| Container hardening | Non-root user (uid 1000), images `python:3.11-slim-bookworm` pinnées, `no-new-privileges`, Redis read-only avec `tmpfs:/tmp` | `apps/api/Dockerfile`, `docker-compose.yml` |
| Secret scan | `gitleaks-action` dans CI | `.github/workflows/ci.yml` |

## Risques connus (acceptés en Phase 1)

| Risque | Décision |
|--------|----------|
| **Exécution de JavaScript embarqué dans un PDF** | `pymupdf4llm` et `pandoc` n'exécutent pas le JS embarqué. Strip explicite via `pikepdf` reporté à la Phase 3 (poids ML de Marker rend déjà l'image lourde). |
| **XSS dans la preview Markdown** | Géré côté frontend au ticket 14 (rendu via `react-markdown` + sanitizer ; jamais `dangerouslySetInnerHTML` sur contenu non-sanitisé). |
| **Trust proxy / X-Forwarded-For** | Pas exposé hors `localhost` en Phase 1. À reconfigurer au passage cloud (`uvicorn --forwarded-allow-ips`). |
| **Marker (OCR scanné)** | Pas encore intégré (ticket 8b) — l'utilisateur reçoit une erreur claire `FormatNotSupportedError` au lieu d'un faux résultat. |

## Tests sécurité

- `tests/security/test_validation.py` : extensions hors-whitelist, MIME usurpé, oversized, file absent
- `tests/security/test_storage.py` : `../` traversal, chemin absolu, symlink hors-base
- `tests/services/test_jobs.py` : limites batch (`max_files_per_job`, `max_job_size_mb`)
- `tests/tasks/test_conversion.py` : task qui marque le job `failed` proprement quand validation rejette

## En cas de fuite de secret

1. Rotation immédiate de la valeur compromise
2. `git filter-repo` pour purger l'historique
3. `git push --force` après avoir prévenu les éventuels collaborateurs
4. Audit de la durée d'exposition (logs GitHub, alerts Dependabot/SecretScanning)
