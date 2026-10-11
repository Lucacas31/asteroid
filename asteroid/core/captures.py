"""Captures des résultats par pvbatch (ParaView piloté en Python).

Quatre vues (iso, X, Y, Z) de la déformée amplifiée, colorée par le Von Mises
(SIEQ_NOEU) ou à défaut par la norme du déplacement. Les paramètres (cadrage,
échelle de couleurs, amplification) sont écrits dans le script : pour comparer
deux runs, les mêmes valeurs servent aux deux, d'où mêmes vues et même échelle.
"""

from __future__ import annotations

import asyncio
import json
import math
import shlex
from pathlib import Path

from .i18n import t

CAPTURE_DIR = "captures"
COMPARE_DIR = "cmp"
SCRIPT_NAME = "captures.py"
TIMEOUT = 180
# (nom, direction de la caméra vers le modèle, vecteur haut)
VIEWS = [("iso", (1, -1, 1), (0, 0, 1)), ("x", (1, 0, 0), (0, 0, 1)), ("y", (0, -1, 0), (0, 0, 1)), ("z", (0, 0, 1), (0, 1, 0))]
DEFORMED_FRACTION = 0.05  # déplacement max affiché : 5 % de la diagonale du modèle

SCRIPT = """\
# Généré par Asteroid : captures du résultat par pvbatch. Paramètres :
P = {params}
from paraview.simple import *
LoadDistributedPlugin("MEDReader", remote=False, ns=globals())
reader = MEDReader(FileNames=[P["rmed"]])
reader.UpdatePipeline()
shown = reader
if P["depl"]:
    shown = WarpByVector(Input=reader, Vectors=["POINTS", P["depl"]], ScaleFactor=P["factor"])
view = CreateView("RenderView")
view.OrientationAxesVisibility = 1
try:
    view.UseColorPaletteForBackground = 0
except AttributeError:
    pass
view.Background = [1, 1, 1]
if P["depl"]:
    # Forme initiale : arêtes du contour seulement (une surface transparente se mêlerait à la déformée).
    ghost = Show(reader, view)
    ghost.SetRepresentationType("Feature Edges")
    ghost.ColorArrayName = ["POINTS", ""]
    ghost.AmbientColor = ghost.DiffuseColor = [0.45, 0.45, 0.5]
    ghost.Opacity = 0.6
display = Show(shown, view)
ColorBy(display, ("POINTS", P["color"], P["component"]))
lut = GetColorTransferFunction(P["color"])
lut.ApplyPreset("Jet", True)
lut.RescaleTransferFunction(*P["range"])
lut.AutomaticRescaleRangeMode = "Never"
bar = GetScalarBar(lut, view)
bar.Title = P["title"]
bar.ComponentTitle = ""
bar.TitleColor = bar.LabelColor = [0.1, 0.1, 0.1]
bar.TitleFontSize = bar.LabelFontSize = 11
bar.ScalarBarLength = 0.4
bar.RangeLabelFormat = "%-#.3g"
bar.Visibility = 1
if P["depl"]:
    label = Text(Text=P["deformation"])
    shown_label = Show(label, view)
    shown_label.Color = [0.1, 0.1, 0.1]
    shown_label.FontSize = 10
    shown_label.WindowLocation = "Upper Left Corner"
lo, hi = P["bounds"]
center = [(a + b) / 2 for a, b in zip(lo, hi)]
diag = max(sum((b - a) ** 2 for a, b in zip(lo, hi)) ** 0.5, 1e-30)
for name, direction, up in P["views"]:
    n = sum(x * x for x in direction) ** 0.5
    view.CameraFocalPoint = center
    view.CameraPosition = [c + 3 * diag * d / n for c, d in zip(center, direction)]
    view.CameraViewUp = up
    view.CameraParallelProjection = 1
    view.CameraParallelScale = 0.6 * diag
    SaveScreenshot(name + ".png", view, ImageResolution=P["size"])
"""


def _nice(x: float) -> float:
    """Arrondi à 1, 2 ou 5 × 10^n (facteur d'amplification lisible)."""
    if x <= 0 or not math.isfinite(x):
        return 1.0
    exp = math.floor(math.log10(x))
    for m in (1, 2, 5, 10):
        if x <= m * 10**exp * 1.0001:
            return float(m * 10**exp)
    return float(10 ** (exp + 1))


def params_for(items: list[tuple[Path, dict]]) -> dict | None:
    """Paramètres communs aux runs donnés : (dossier du run, résumé). None : rien à montrer."""
    firsts = []
    for run_dir, summary in items:
        result = next((r for r in summary.get("results", []) if "depl" in r or "vmis" in r), None)
        if result is None or not summary.get("bounds"):
            return None
        firsts.append((run_dir, summary, result))
    lo = [min(s["bounds"][0][i] for _, s, _ in firsts) for i in range(3)]
    hi = [max(s["bounds"][1][i] for _, s, _ in firsts) for i in range(3)]
    diag = math.dist(lo, hi)
    depl = [r["depl"]["max"] for _, _, r in firsts if "depl" in r]
    factor = _nice(DEFORMED_FRACTION * diag / max(depl)) if depl and max(depl) > 0 else 1.0
    with_vmis = all("vmis" in r for _, _, r in firsts)
    units = firsts[0][1]["units"]
    if with_vmis:
        top = max(r["vmis"]["max"] for _, _, r in firsts)
        title = f"VMIS ({units['stress']})"
    else:
        top = max(depl) if depl else 1.0
        title = f"|DEPL| ({units['length']})"
    return {
        "bounds": [lo, hi],
        "factor": factor,
        "range": [0.0, top if top > 0 else 1.0],
        "vmis": with_vmis,
        "title": title,
        "deformation": t("déformée ×{factor}", factor=f"{factor:g}"),
        "concepts": {str(d): r["concept"] for d, _, r in firsts},
        "has_depl": {str(d): "depl" in r for d, _, r in firsts},
    }


def script_params(run_dir: Path, summary: dict, shared: dict) -> dict:
    concept = shared["concepts"][str(run_dir)]
    prefix = concept.ljust(8, "_")
    return {
        "rmed": str((run_dir / summary["file"]).resolve()),
        "depl": prefix + "DEPL" if shared["has_depl"][str(run_dir)] else None,
        "factor": shared["factor"],
        "color": prefix + ("SIEQ_NOEU" if shared["vmis"] else "DEPL"),
        "component": "VMIS" if shared["vmis"] else "Magnitude",
        "range": shared["range"],
        "title": shared["title"],
        "deformation": shared["deformation"],
        "bounds": shared["bounds"],
        "views": [[n, list(d), list(u)] for n, d, u in VIEWS],
        "size": [640, 480],
    }


def capture_dir(run_dir: Path, compare: bool = False) -> Path:
    return run_dir / CAPTURE_DIR / (COMPARE_DIR if compare else "")


async def capture(run_dir: Path, summary: dict, shared: dict, command: str, compare: bool = False) -> dict:
    """Lance pvbatch ; renvoie {"views": [...], "params": …} ou {"error": …}."""
    out = capture_dir(run_dir, compare)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    params = script_params(run_dir, summary, shared)
    script = out / SCRIPT_NAME
    script.write_text(SCRIPT.format(params=repr(params)))  # littéral Python (None, True), pas du JSON
    full = command.replace("{script}", shlex.quote(str(script.resolve())))
    with open(out / "pvbatch.log", "w") as log:
        proc = await asyncio.create_subprocess_shell(
            full, cwd=out, stdout=log, stderr=asyncio.subprocess.STDOUT, executable="/bin/bash",
            start_new_session=True,
        )
        try:
            code = await asyncio.wait_for(proc.wait(), TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            code = None
    views = [n for n, _, _ in VIEWS if (out / f"{n}.png").exists()]
    result = {"views": views, "params": params}
    if len(views) != len(VIEWS):
        tail = (out / "pvbatch.log").read_text(errors="replace").strip().splitlines()[-3:]
        result["error"] = t("pvbatch a échoué (code {code}) : {detail}", code=code, detail=" / ".join(tail) or "?")
    (out / "info.json").write_text(json.dumps(result, ensure_ascii=False))
    return result


def capture_info(run_dir: Path, compare: bool = False) -> dict | None:
    path = capture_dir(run_dir, compare) / "info.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def suggest_command(paraview_command: str) -> str:
    """Commande pvbatch proposée à partir de la commande ParaView des réglages (même dossier bin/)."""
    for token in shlex.split(paraview_command or ""):
        if token.endswith("/paraview"):
            return f"{shlex.quote(token[: -len('paraview')] + 'pvbatch')} --force-offscreen-rendering {{script}}"
    return "pvbatch --force-offscreen-rendering {script}"
