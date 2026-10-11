#!/usr/bin/env bash
# Construit l'AppImage d'Asteroid (Linux x86_64) : un seul fichier, Python et dépendances inclus.
#
#   scripts/build-appimage.sh [dossier de sortie] [wheel]      (défaut : dist/, wheel construit ici)
#
# Python vient de python-build-standalone (version et somme de contrôle figées ci-dessous),
# les dépendances de PyPI. Le nom du fichier ne porte pas de version : le dossier portable
# Asteroid-x86_64.AppImage.config reste reconnu quand on remplace le fichier par une mise à jour.
#
# Prérequis : uv, npm (sans wheel donné), curl, sha256sum, unzip.
set -euo pipefail

PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260510/cpython-3.12.13%2B20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PYTHON_SHA256="d480f5d5878910ecbae212bf23bd7c25d7b209eb8cf5e98823c977384d272e88"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${1:-$root/dist}"
out="$(cd "${1:-$root/dist}" && pwd)"
name="Asteroid-x86_64.AppImage"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
appdir="$work/AppDir"
py="$appdir/usr/python/bin/python3"

if [ -n "${2:-}" ]; then
  wheel="$(readlink -f "$2")"
else
  echo "== Interface et wheel"
  (cd "$root/frontend" && npm ci --no-audit --no-fund && npm run build)
  uv build --wheel --out-dir "$work/wheel" "$root"
  wheel="$(ls "$work"/wheel/*.whl)"
fi

echo "== Python autonome"
curl -sSfL -o "$work/python.tar.gz" "$PYTHON_URL"
echo "$PYTHON_SHA256  $work/python.tar.gz" | sha256sum -c --quiet
mkdir -p "$appdir/usr"
tar -xzf "$work/python.tar.gz" -C "$appdir/usr"
# Inutile à l'app : interface Tk, tests et outils de la bibliothèque standard, pip, en-têtes C.
lib="$appdir/usr/python/lib/python3.12"
rm -rf "$lib"/{test,idlelib,tkinter,turtledemo,ensurepip} "$lib"/lib-dynload/_tkinter* \
  "$lib"/site-packages/pip* "$appdir"/usr/python/lib/{libtcl,libtk,tcl,tk,itcl,thread}* \
  "$appdir/usr/python/include" "$appdir/usr/python/share"
find "$appdir/usr/python/bin" -mindepth 1 ! -name 'python3*' -delete
rm -f "$appdir"/usr/python/bin/python3*-config

echo "== Asteroid et dépendances"
# Bytecode précompilé : à l'exécution, l'AppImage est en lecture seule.
uv pip install --quiet --python "$py" --break-system-packages --compile-bytecode "$wheel"
"$py" -I -m compileall -q -j 0 "$lib" >/dev/null || true
# Scripts d'entrée (uvicorn, f2py…) : leur shebang pointe vers le dossier de construction.
find "$appdir/usr/python/bin" -mindepth 1 ! -name 'python3*' -delete
# Chemin du wheel installé (métadonnée pip) : inutile et propre à la machine.
rm -f "$lib"/site-packages/asteroid-*.dist-info/direct_url.json

install -m 755 "$root/packaging/AppRun" "$appdir/AppRun"
unzip -p "$wheel" asteroid/static/logo.png > "$appdir/asteroid.png"
ln -s asteroid.png "$appdir/.DirIcon"
cp "$root/LICENSE" "$appdir/"
cat > "$appdir/asteroid.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Asteroid
Comment=Préparer, lancer et suivre des calculs Code_Aster
Exec=asteroid
Icon=asteroid
Terminal=false
Categories=Science;Engineering;
StartupWMClass=asteroid
EOF

echo "== Contrôle : l'app démarre et aucun chemin de la machine de construction"
"$py" -I -c "import asteroid.cli, asteroid.server"
# Paquets tiers exclus : leurs métadonnées (SBOM) citent la machine de leurs auteurs, souvent
# /home/runner, qui est aussi le $HOME de GitHub Actions.
if leaks="$(grep -rlaF -e "$HOME" -e "/home/$(id -un)" --exclude-dir=site-packages "$appdir" \
  "$lib"/site-packages/asteroid "$lib"/site-packages/asteroid-*.dist-info)"; then
  echo "Chemins de la machine trouvés dans :" >&2
  echo "$leaks" >&2
  exit 1
fi

echo "== AppImage"
curl -sSfL -o "$work/appimagetool" "$APPIMAGETOOL_URL"
chmod +x "$work/appimagetool"
# Extraction plutôt que montage : pas besoin de FUSE sur la machine de construction.
(cd "$work" && ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 ./appimagetool --no-appstream "$appdir" "$out/$name")
(cd "$out" && sha256sum "$name" > "$name.sha256")
ls -l "$out/$name"
