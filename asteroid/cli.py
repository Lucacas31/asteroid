"""Commande `asteroid` : démarre le serveur local et ouvre l'interface."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import sys
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


DEFAULT_PORT = 8765
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
# Classe X11 de la fenêtre : le lanceur .desktop la reconnaît (StartupWMClass) et
# le dock affiche alors l'icône en haute résolution au lieu de la petite icône de la page.
WM_CLASS = "asteroid"
STATIC_ICON = Path(__file__).parent / "static" / "logo.png"


def free_port(preferred: int, strict: bool = False) -> int:
    """Port libre : `preferred` si possible, sinon un port quelconque (sauf si strict)."""
    for port in (preferred,) if strict else (preferred, 0):
        with socket.socket() as s:
            # Même option qu'uvicorn : un port en TIME_WAIT reste utilisable.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise SystemExit(f"asteroid : le port {preferred} est déjà utilisé (une autre instance ?)")


def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def browser_profile(browser: str) -> Path:
    """Profil dédié : la fenêtre vit dans son propre processus, ce qui permet
    d'arrêter le serveur quand l'utilisateur la ferme.

    Le Chromium en snap ne peut pas écrire dans ~/.config : son profil va
    dans ~/snap/chromium/common.
    """
    snap_home = Path.home() / "snap" / "chromium" / "common"
    if "chromium" in Path(browser).name and snap_home.is_dir():
        return snap_home / "asteroid-profile"
    # Cache du navigateur : hors des dossiers de l'utilisateur (config/ du dossier portable).
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "asteroid" / "browser"


def open_window(url: str, quit_on_close: bool) -> None:
    browser = next((b for b in map(shutil.which, BROWSERS) if b), None)
    if browser is None:
        webbrowser.open(url)
        return
    profile = browser_profile(browser)
    profile.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.Popen(
        [browser, f"--app={url}", f"--user-data-dir={profile}", f"--class={WM_CLASS}", "--no-first-run",
         "--no-default-browser-check", "--start-maximized"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    returncode = proc.wait()
    lifetime = time.time() - started
    if lifetime < 5 and returncode != 0:
        # Échec du lancement en mode application : navigateur par défaut.
        webbrowser.open(url)
    elif quit_on_close and lifetime >= 5:
        os.kill(os.getpid(), signal.SIGINT)


def launcher() -> str:
    """Commande qui relance l'app : lanceur du dossier portable, sinon le script `asteroid`."""
    return os.environ.get("ASTEROID_LAUNCHER") or str(Path(sys.argv[0]).resolve())


def _desktop_quote(path: str) -> str:
    # Spécification Desktop Entry : chemin entre guillemets s'il contient des espaces.
    if not any(c in path for c in ' "\\`$'):
        return path
    return '"' + "".join("\\" + c if c in '"`$\\' else c for c in path) + '"'


def install_desktop_entry() -> Path | None:
    """Installe (ou met à jour) le lanceur ~/.local/share/applications/asteroid.desktop."""
    if not STATIC_ICON.exists():
        return None
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    icon = data / "icons" / "asteroid.png"
    entry = data / "applications" / "asteroid.desktop"
    content = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Asteroid",
        "Comment=Préparer, lancer et suivre des calculs Code_Aster",
        f"Exec={_desktop_quote(launcher())}",
        f"Icon={icon}",
        "Terminal=false",
        "Categories=Science;Engineering;",
        f"StartupWMClass={WM_CLASS}",
        "",
    ])
    if entry.exists() and entry.read_text() == content and icon.exists():
        return entry
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STATIC_ICON, icon)
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(content)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(prog="asteroid", description=__doc__)
    parser.add_argument("project", nargs="?", help="dossier de projet à ouvrir")
    parser.add_argument("--port", type=int, help=f"port imposé (par défaut {DEFAULT_PORT}, ou un port libre)")
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir de fenêtre")
    parser.add_argument("--keep-running", action="store_true",
                        help="ne pas arrêter le serveur à la fermeture de la fenêtre")
    parser.add_argument("--no-desktop-entry", action="store_true",
                        help="ne pas installer le lanceur ~/.local/share/applications/asteroid.desktop")
    args = parser.parse_args()

    from .server import app
    from .state import state

    if args.project:
        state.open(Path(args.project).expanduser().resolve())

    port = free_port(args.port or DEFAULT_PORT, strict=args.port is not None)
    url = f"http://127.0.0.1:{port}"
    print(f"Asteroid sur {url}")
    if not args.no_browser and not args.no_desktop_entry:
        try:
            install_desktop_entry()
        except OSError as exc:
            print(f"Lanceur non installé : {exc}")
    if not args.no_browser:
        def launch() -> None:
            if wait_for_server(port):
                open_window(url, quit_on_close=not args.keep_running)

        threading.Thread(target=launch, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
