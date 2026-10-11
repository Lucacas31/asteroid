"""Application FastAPI : l'API sous /api, le frontend compilé à la racine."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .api import catalog, fs, materials, mesh, project, runs

STATIC_DIR = Path(__file__).parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _local(netloc: str) -> bool:
    return urlsplit("//" + netloc).hostname in LOCAL_HOSTS


class LocalOnly:
    """Refuse les requêtes d'une autre origine que l'app.

    L'API lance des commandes shell (réglages, runs) : une page web quelconque ne doit
    pas pouvoir l'appeler, ni directement (Origin étrangère), ni par DNS rebinding
    (Host étranger qui pointe vers 127.0.0.1).
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
            origin = headers.get("origin")
            if not _local(headers.get("host", "")) or (origin is not None and not _local(urlsplit(origin).netloc)):
                await PlainTextResponse("Origine refusée", status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app = FastAPI(title="Asteroid")
app.add_middleware(LocalOnly)
app.include_router(project.router)
app.include_router(runs.router)
app.include_router(fs.router)
app.include_router(mesh.router)
app.include_router(catalog.router)
app.include_router(materials.router)

if (STATIC_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:

    @app.get("/", response_class=HTMLResponse)
    def not_built() -> str:
        return (
            "<h1>Asteroid</h1><p>Le frontend n'est pas compilé : "
            "<code>cd frontend && npm install && npm run build</code></p>"
        )
