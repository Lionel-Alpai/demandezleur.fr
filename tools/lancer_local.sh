#!/usr/bin/env bash
# Lance la maquette vivante en local : backend (:8001) + hugo (:1313).
#   tools/lancer_local.sh            → backend en mode DL_MODE du .env (live par défaut)
#   tools/lancer_local.sh demo       → rejoue les réponses enregistrées, zéro token
#   tools/lancer_local.sh stop       → arrête les deux
# Ouvrir ensuite http://localhost:1313/
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"
VENV=/home/lionel/AI/demandezleur/venv/bin
LOG=/tmp/demandezleur-local; mkdir -p "$LOG"
if [ "${1:-}" = "stop" ]; then
  tourne -k 'uvicorn api:app --host 127.0.0.1 --port 8001' >/dev/null 2>&1 || true
  tourne -k 'hugo server --config hugo.toml,hugo.dev.toml' >/dev/null 2>&1 || true
  echo "arrêté"; exit 0
fi
MODE="${1:-}"
tourne -q 'uvicorn api:app --host 127.0.0.1 --port 8001' 2>/dev/null && echo "backend déjà lancé" || {
  ( cd "$R/backend" && ${MODE:+DL_MODE=$MODE} setsid nohup "$VENV/uvicorn" api:app --host 127.0.0.1 --port 8001 > "$LOG/uvicorn.log" 2>&1 < /dev/null & )
  echo "backend :8001 lancé (${MODE:-mode du .env}) — log $LOG/uvicorn.log"; }
tourne -q 'hugo server --config hugo.toml,hugo.dev.toml' 2>/dev/null && echo "hugo déjà lancé" || {
  ( cd "$R/hugo-src" && setsid nohup /home/lionel/bin/hugo server --config hugo.toml,hugo.dev.toml --port 1313 --bind 127.0.0.1 --disableFastRender > "$LOG/hugo.log" 2>&1 < /dev/null & )
  echo "hugo :1313 lancé — log $LOG/hugo.log"; }
sleep 3; curl -s -o /dev/null -w "backend %{http_code}\n" http://127.0.0.1:8001/api/parlement/etat; curl -s -o /dev/null -w "site    %{http_code}\n" http://127.0.0.1:1313/
echo "→ http://localhost:1313/"
