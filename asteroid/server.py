"""Application FastAPI : l'API sous /api, le frontend compilé à la racine."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api import catalog, fs, materials, mesh, project, runs

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Asteroid")
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
