#!/usr/bin/env bash
# Construit l'archive portable d'Asteroid (Linux) et le wheel.
#
#   scripts/build-portable.sh [dossier de sortie]      (défaut : dist/)
#
# L'archive contient le dossier asteroid/ : le lanceur, le wheel (interface compilée
# comprise), la licence et les README. Python n'y est pas : le lanceur crée .venv/ au
# premier lancement. Les données de l'utilisateur (config/, materiaux/) n'y sont pas non
# plus : extraire une nouvelle version par-dessus l'ancienne ne les écrase pas.
#
# Prérequis : uv, npm, tar, unzip, sha256sum.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${1:-$root/dist}"
out="$(cd "${1:-$root/dist}" && pwd)"
version="$(sed -n 's/^version = "\(.*\)"/\1/p' "$root/pyproject.toml")"
name="asteroid-$version-linux"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# Dossier sans numéro de version : la mise à jour s'extrait par-dessus l'ancienne.
app="$work/asteroid"

echo "== Interface et wheel"
(cd "$root/frontend" && npm ci --no-audit --no-fund && npm run build)
mkdir -p "$app/wheels"
uv build --wheel --out-dir "$app/wheels" "$root"
rm -f "$app/wheels/.gitignore"  # écrit par uv build
wheel="$(ls "$app"/wheels/*.whl)"

install -m 755 "$root/packaging/asteroid" "$app/asteroid"
cp "$root/LICENSE" "$root/README.md" "$root/README.en.md" "$app/"
mkdir -p "$app/langues"
cp "$root/packaging/langues-LISEZMOI.txt" "$app/langues/LISEZMOI.txt"

echo "== Contrôle : aucun chemin de la machine de construction"
unzip -q "$wheel" -d "$work/wheel-content"
find "$work/wheel-content" -name '*.gz' -exec sh -c 'gzip -dc "$1" > "$1.plain"' _ {} \;
if leaks="$(grep -rlaF -e "$HOME" -e "/home/$(id -un)" "$app" "$work/wheel-content")"; then
  echo "Chemins de la machine trouvés dans :" >&2
  echo "$leaks" >&2
  exit 1
fi

echo "== Archive"
mtime="$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)"
tar --owner=0 --group=0 --numeric-owner --sort=name --mtime="@$mtime" \
  -C "$work" -czf "$out/$name.tar.gz" asteroid
owners="$(tar -tvzf "$out/$name.tar.gz" | awk '{print $2}' | sort -u)"
[ "$owners" = "0/0" ] || { echo "Propriétaires inattendus dans l'archive : $owners" >&2; exit 1; }
cp "$wheel" "$out/"
(cd "$out" && sha256sum "$name.tar.gz" "$(basename "$wheel")" > "$name.sha256")
ls -l "$out"
