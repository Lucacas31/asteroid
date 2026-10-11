#!/usr/bin/env bash
# Lance Asteroid depuis les sources, sans compiler le frontend : backend du dépôt sur un port
# à part, frontend servi par Vite (rechargement à chaud des fichiers de frontend/src).
# L'instance habituelle (port 8765) et le lanceur du menu ne sont pas touchés.
#
# Usage : scripts/asteroid-test.sh [dossier de projet] [--config DIR] [--no-window]
#   --config DIR   réglages et bibliothèque isolés dans DIR (par défaut : les réglages habituels)
#   --no-window    pas de fenêtre ; l'interface est à l'adresse affichée
# Ports : ASTEROID_TEST_PORT (backend, 8766), ASTEROID_TEST_UI_PORT (interface, 5180).
# Une modification du backend (Python) demande de relancer le script ; le frontend se recharge seul.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACK_PORT="${ASTEROID_TEST_PORT:-8766}"
UI_PORT="${ASTEROID_TEST_UI_PORT:-5180}"
PROJECT=""
WINDOW=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) export ASTEROID_CONFIG_DIR="$(realpath -m "$2")"; shift 2 ;;
    --no-window) WINDOW=0; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) PROJECT="$(realpath "$1")"; shift ;;
  esac
done

if [[ ! -x "$ROOT/.venv/bin/asteroid" ]]; then
  echo "Environnement Python absent : cd $ROOT && uv venv && uv pip install -e '.[dev]'" >&2
  exit 1
fi
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Installation des dépendances du frontend…"
  (cd "$ROOT/frontend" && npm install --no-fund --no-audit)
fi
for port in "$BACK_PORT" "$UI_PORT"; do
  if ss -ltn "sport = :$port" | grep -q LISTEN; then
    echo "Le port $port est déjà utilisé (une autre instance de test ?)" >&2
    exit 1
  fi
done

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --keep-running : c'est ce script, pas une fenêtre, qui décide de l'arrêt.
"$ROOT/.venv/bin/asteroid" ${PROJECT:+"$PROJECT"} --port "$BACK_PORT" --no-browser --keep-running &
PIDS+=($!)
(cd "$ROOT/frontend" && ASTEROID_BACKEND="http://127.0.0.1:$BACK_PORT" \
  exec npx vite --port "$UI_PORT" --strictPort --clearScreen false) &
PIDS+=($!)

URL="http://localhost:$UI_PORT"
for _ in $(seq 100); do
  curl -sf "$URL/api/i18n" >/dev/null 2>&1 && break
  sleep 0.2
done
echo
echo "Asteroid (sources, branche $(git -C "$ROOT" branch --show-current)) : $URL"
echo "Backend : http://127.0.0.1:$BACK_PORT · réglages : ${ASTEROID_CONFIG_DIR:-habituels}"
echo "Ctrl+C pour arrêter."

if [[ $WINDOW -eq 1 ]]; then
  BROWSER="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
  if [[ -n "$BROWSER" ]]; then
    # Profil à part (le Chromium en snap n'écrit que dans ~/snap/chromium/common).
    PROFILE="$HOME/.cache/asteroid/browser-test"
    [[ "$BROWSER" == *chromium* && -d "$HOME/snap/chromium/common" ]] && PROFILE="$HOME/snap/chromium/common/asteroid-test-profile"
    mkdir -p "$PROFILE"
    # --class=asteroid : le dock reconnaît le lanceur installé et prend son icône haute résolution.
    "$BROWSER" --app="$URL" --user-data-dir="$PROFILE" --class=asteroid \
      --no-first-run --no-default-browser-check --start-maximized >/dev/null 2>&1 &
  else
    xdg-open "$URL" >/dev/null 2>&1 || true
  fi
fi

wait "${PIDS[0]}"
