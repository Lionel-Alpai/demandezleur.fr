#!/usr/bin/env bash
# Lance la maquette vivante en local : backend (:8001) + hugo (:1313).
#   tools/lancer_local.sh            → backend en mode DL_MODE du .env (live par défaut)
#   tools/lancer_local.sh demo       → rejoue les réponses enregistrées, zéro token
#   tools/lancer_local.sh stop       → arrête les deux
#
# ESSAI DE MODÈLE, en local seulement (la production reste sur DeepSeek) :
#   tools/lancer_local.sh mistral            → mistral-small-latest
#   tools/lancer_local.sh mistral-large      → mistral-large-latest
#   tools/lancer_local.sh deepseek           → revient au défaut
# La clé n'est jamais écrite ici : on passe le NOM de la variable qui la porte
# (MISTRAL_API_KEY, exportée par ~/.bashrc depuis `pass show api/mistral`).
# Ouvrir ensuite http://localhost:1313/
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"
VENV=/home/lionel/AI/demandezleur/venv/bin
LOG=/tmp/demandezleur-local; mkdir -p "$LOG"
if [ "${1:-}" = "stop" ]; then
  tourne -k 'uvicorn api:app' >/dev/null 2>&1 || true
  tourne -k 'hugo server --config hugo.toml,hugo.dev.toml' >/dev/null 2>&1 || true
  echo "arrêté"; exit 0
fi
ARG="${1:-}"
MODE=""; FOURNISSEUR=""
case "$ARG" in
  mistral)        FOURNISSEUR="DL_BASE_URL=https://api.mistral.ai/v1 DL_CLE_VAR=MISTRAL_API_KEY DL_MODELE=mistral-small-latest" ;;
  mistral-large)  FOURNISSEUR="DL_BASE_URL=https://api.mistral.ai/v1 DL_CLE_VAR=MISTRAL_API_KEY DL_MODELE=mistral-large-latest" ;;
  deepseek)       FOURNISSEUR="DL_BASE_URL=https://api.deepseek.com DL_CLE_VAR=DEEPSEEK_API_KEY DL_MODELE=deepseek-v4-flash" ;;
  *)              MODE="$ARG" ;;
esac
if [ -n "$FOURNISSEUR" ] && [ -z "${MISTRAL_API_KEY:-}${DEEPSEEK_API_KEY:-}" ]; then
  echo "⚠ aucune clé dans l'environnement — lance depuis un shell interactif (~/.bashrc les exporte depuis pass)"; fi
tourne -q 'uvicorn api:app' 2>/dev/null && echo "backend déjà lancé" || {
  ( cd "$R/backend" && env ${MODE:+DL_MODE=$MODE} $FOURNISSEUR setsid nohup "$VENV/uvicorn" api:app --host 0.0.0.0 --port 8001 > "$LOG/uvicorn.log" 2>&1 < /dev/null & )
  echo "backend :8001 lancé (${FOURNISSEUR:-${MODE:-mode du .env}}) — log $LOG/uvicorn.log"; }
tourne -q 'hugo server --config hugo.toml,hugo.dev.toml' 2>/dev/null && echo "hugo déjà lancé" || {
  ( cd "$R/hugo-src" && setsid nohup /home/lionel/bin/hugo server --config hugo.toml,hugo.dev.toml --port 1313 --bind 0.0.0.0 --baseURL "http://${DL_HOTE:-192.168.1.13}:1313/" --appendPort=false --disableFastRender > "$LOG/hugo.log" 2>&1 < /dev/null & )
  echo "hugo :1313 lancé — log $LOG/hugo.log"; }
sleep 3; curl -s -o /dev/null -w "backend %{http_code}\n" http://127.0.0.1:8001/api/parlement/etat; curl -s -o /dev/null -w "site    %{http_code}\n" http://127.0.0.1:1313/
echo "→ http://localhost:1313/  ·  LAN http://192.168.1.13:1313/  ·  WireGuard http://10.0.0.3:1313/"
