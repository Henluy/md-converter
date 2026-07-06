#!/usr/bin/env bash
#
# dev.sh — lance toute la stack md-converter en une commande.
#
#   ./dev.sh                # API :8000, worker Celery, web :3000
#   API_PORT=8001 WEB_PORT=3002 ./dev.sh   # ports personnalisés
#
# Ctrl+C arrête proprement l'API, le worker et le web (Redis/Postgres, eux,
# restent en place — ce sont des services partagés).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
REDIS_PORT="${REDIS_PORT:-6379}"
LOG_DIR="$ROOT/.dev/logs"
mkdir -p "$LOG_DIR"

# --- couleurs (désactivées si pas un terminal) -----------------------------
if [ -t 1 ]; then B="\033[1m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; D="\033[2m"; N="\033[0m"; else B=""; G=""; Y=""; R=""; D=""; N=""; fi
say()  { printf "${B}▸ %s${N}\n" "$*"; }
ok()   { printf "  ${G}✓${N} %s\n" "$*"; }
warn() { printf "  ${Y}!${N} %s\n" "$*"; }
die()  { printf "  ${R}✗ %s${N}\n" "$*" >&2; exit 1; }

# --- 1. prérequis ----------------------------------------------------------
say "Vérification des prérequis"
for bin in uv pnpm node pandoc; do
  command -v "$bin" >/dev/null || die "'$bin' introuvable — installe-le avant de lancer."
done
command -v weasyprint >/dev/null || warn "weasyprint absent : l'export PDF échouera (DOCX/EPUB OK)."
[ -f "$ROOT/.env" ] || die ".env manquant à la racine — copie .env.example vers .env."
ok "binaires + .env présents"

# --- 2. Redis --------------------------------------------------------------
say "Redis (:$REDIS_PORT)"
if redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
  ok "déjà démarré"
elif command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  docker compose up -d redis >/dev/null 2>&1 && ok "démarré via docker compose"
elif command -v redis-server >/dev/null; then
  redis-server --port "$REDIS_PORT" --daemonize yes >/dev/null 2>&1 && ok "démarré (redis-server)"
else
  die "Redis injoignable et ni docker ni redis-server dispo."
fi

# --- 3. Postgres + migrations ---------------------------------------------
say "PostgreSQL + migrations"
DB_URL="$(grep -E '^DATABASE_URL=' "$ROOT/.env" | cut -d= -f2- || true)"
[ -n "$DB_URL" ] || die "DATABASE_URL absent de .env."
if command -v pg_isready >/dev/null; then
  pg_isready -d "$DB_URL" >/dev/null 2>&1 || die "Postgres injoignable ($DB_URL). Démarre-le (ex: brew services start postgresql)."
fi
pnpm --filter @md/web db:migrate >/dev/null 2>&1 && ok "schéma à jour" || die "échec des migrations Drizzle."

# --- 4. ports libres ? -----------------------------------------------------
port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
port_busy "$API_PORT" && die "port $API_PORT déjà utilisé (relance avec API_PORT=…)."
port_busy "$WEB_PORT" && die "port $WEB_PORT déjà utilisé (relance avec WEB_PORT=…)."

# --- 5. démarrage des services ---------------------------------------------
export CORS_ORIGINS="http://localhost:$WEB_PORT,http://localhost:3000"
export NEXT_PUBLIC_API_URL="http://localhost:$API_PORT"
PIDS=()

cleanup() {
  printf "\n${B}▸ Arrêt de la stack…${N}\n"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  # backstop ciblé (signatures exactes — n'affecte pas d'autres projets)
  pkill -f "uvicorn app.main:app --host 0.0.0.0 --port $API_PORT" 2>/dev/null || true
  pkill -f "celery -A app.tasks.celery_app:celery_app worker"      2>/dev/null || true
  pkill -f "next dev --port $WEB_PORT"                             2>/dev/null || true
  ok "arrêté (Redis + Postgres laissés tourner)"
}
trap cleanup INT TERM EXIT

say "Démarrage des services"
( cd "$ROOT/apps/api" && exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" ) \
  > "$LOG_DIR/api.log" 2>&1 & PIDS+=($!); ok "API      → http://localhost:$API_PORT  ($D$LOG_DIR/api.log$N)"

( cd "$ROOT/apps/api" && exec uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=info --concurrency=2 ) \
  > "$LOG_DIR/worker.log" 2>&1 & PIDS+=($!); ok "worker   → Celery x2                ($D$LOG_DIR/worker.log$N)"

( cd "$ROOT" && exec pnpm --filter @md/web exec next dev --port "$WEB_PORT" ) \
  > "$LOG_DIR/web.log" 2>&1 & PIDS+=($!); ok "web      → http://localhost:$WEB_PORT  ($D$LOG_DIR/web.log$N)"

# --- 6. attente readiness --------------------------------------------------
say "Attente du démarrage…"
for i in $(seq 1 60); do
  curl -fsS "http://localhost:$API_PORT/health" >/dev/null 2>&1 && { ok "API prête"; break; }
  [ "$i" = 60 ] && warn "API pas encore prête (voir $LOG_DIR/api.log)"
  sleep 1
done
for i in $(seq 1 60); do
  curl -fsS "http://localhost:$WEB_PORT" >/dev/null 2>&1 && { ok "web prêt"; break; }
  [ "$i" = 60 ] && warn "web pas encore prêt (voir $LOG_DIR/web.log)"
  sleep 1
done

printf "\n${B}${G}✅ md-converter est lancé${N} — ouvre ${B}http://localhost:$WEB_PORT${N}\n"
printf "${D}   Logs en direct ci-dessous. Ctrl+C pour tout arrêter.${N}\n\n"

# --- 7. logs en direct (garde le script au premier plan) -------------------
tail -n +1 -F "$LOG_DIR/api.log" "$LOG_DIR/worker.log" "$LOG_DIR/web.log"
