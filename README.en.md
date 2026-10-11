# Asteroid

*[Version française](README.md)*

Prepare, run and follow **Code_Aster** static mechanics computations, without Salome-Meca.

```
FreeCAD → STEP → Gmsh → .med mesh → Asteroid → Code_Aster → .rmed results → ParaView
```

Asteroid shows the mesh and its groups in 3D and builds the `.comm` command file block by block: forms for the common commands, free text for everything else. It validates the file continuously against the Code_Aster catalogue, runs the computation, attaches errors to the right block and opens the results in ParaView. It writes the real Code_Aster command and keyword names, with no invented syntax: the generated `.comm` stays readable and editable by hand. Code_Aster itself is in French, so command names, keywords and the messages of a run stay in French.

Interface in English or French. Linux only.

## Installation

### AppImage (simplest)

Download `Asteroid-x86_64.AppImage` from the [Releases](../../releases) page, make it executable and run it:

```bash
chmod +x Asteroid-x86_64.AppImage
./Asteroid-x86_64.AppImage
```

A single file: Python and the dependencies are inside, no internet access is needed at launch. An “Asteroid” entry is added to the applications menu (it points to the file: after moving it, run it once again).

Settings and the material library live in `~/.config/asteroid/` (see [Files](#files)).

**Update**: replace the file with the new version. Settings, materials and projects are kept.

**Portable mode** (USB stick…): create an `Asteroid-x86_64.AppImage.config` folder next to the file; settings and materials then go into that folder. Keep the same file name when updating.

On a distribution without FUSE, run it with `--appimage-extract-and-run`.

### Archive

1. Download `asteroid-<version>-linux.tar.gz` from the [Releases](../../releases) page.
2. Extract it anywhere and run `asteroid`:

   ```bash
   tar -xzf asteroid-*-linux.tar.gz
   ./asteroid/asteroid
   ```

On first launch, the launcher creates a Python environment in `asteroid/.venv/` and installs Asteroid and its dependencies from PyPI (internet access needed, once). It uses [uv](https://docs.astral.sh/uv/) when installed, the system Python otherwise. An “Asteroid” entry is then added to the applications menu.

**Update**: extract the new archive in the same place. Settings and the material library are kept; the Python environment is updated on the next launch.

Alternatively, without a folder: install the release wheel with `pipx install asteroid-<version>-py3-none-any.whl` (or `uv tool install …`) and run `asteroid`. Settings and library then live in `~/.config/asteroid/`.

### What you need alongside

| Tool | Purpose | Required |
|---|---|---|
| Linux | | yes |
| Python 3.11 or newer with the venv module (Debian/Ubuntu: `sudo apt install python3-venv`), or uv | running Asteroid | except AppImage |
| Code_Aster, e.g. the Docker image `simvia/code_aster:stable` (17.4) | computation | yes |
| [ParaView](https://www.paraview.org/download/) with the MEDReader plugin (included in the official binaries) | results | no |
| Chrome or Chromium | dedicated window; otherwise the default browser | no |
| zenity | native file chooser; otherwise a built-in browser | no |
| Gmsh | creating the `.med` mesh | upstream |

## First launch

Asteroid does not guess anything: it runs the commands you give it. The first screen asks for:

- **the Code_Aster run command**, executed by bash from the run folder;
- **the stop command** (Stop button);
- **the ParaView command**, with the full path if `paraview` is not in the `PATH`;
- the interface language.

All of it can be changed later in *Settings → Global settings*.

Variables available in the commands:

| Variable | Value |
|---|---|
| `{run_dir}` | absolute path of the run folder (working directory of the command) |
| `{export}` | the run's `.export` file, relative to the run folder |
| `{comm}`, `{mesh}` | `.comm` file and mesh copied into the run |
| `{run_id}` | run identifier (timestamp), useful to name a container |
| `{image}` | Docker image from the settings |
| `{script}`, `{rmed}` | (ParaView) script that loads MEDReader and opens the `.rmed` files; first `.rmed` of the run |

Suggested value, for the official Docker image (`run_aster` is only in the image's `PATH` after `source /opt/activate.sh`):

```
docker run --rm --name asteroid_{run_id} --user $(id -u):$(id -g) -v {run_dir}:/work -w /work \
  {image} bash -c "source /opt/activate.sh && run_aster {export}"
```

With a local Code_Aster installation, the command is just `run_aster {export}`. For Apptainer or another launcher, adapt the Docker command.

## Files

User data (AppImage, wheel, source):

```
~/.config/asteroid/
├── settings.json     global settings (commands, run profiles, recent projects, language)
├── materiaux/        material library: one JSON file per material
├── langues/          added translations
└── catalog_*.json    catalog re-exported from your Code_Aster version
```

Alongside: the window profile in `~/.cache/asteroid/` (or `~/snap/chromium/common/asteroid-profile` with the snap Chromium) and the menu entry in `~/.local/share/applications/`. *Global settings* shows the settings folder.

To move from the archive to the AppImage, copy `config/settings.json`, `materiaux/` and `langues/` from the archive folder into `~/.config/asteroid/`.

Application folder (archive):

```
asteroid/
├── asteroid          launcher
├── config/           settings (settings.json), created on first launch
├── materiaux/        material library: one JSON file per material
├── langues/          added translations (see langues/LISEZMOI.txt)
├── wheels/           Asteroid (Python package)
└── .venv/            Python environment, created on first launch
```

Project folder: `asteroid.json` (blocks and project settings), `materials.json` (frozen copies of the materials used), the mesh, and `runs/<timestamp>/` for each computation.

Each run is a `run.sh` script detached from the app: closing the window does not stop the computation, and it is picked up again on the next launch. The *Runs* tab lists the runs with a free note, their files, a side-by-side comparison of several runs (one column per run, reordered by drag and drop; the first is the reference for % differences and `.comm` differences), in the panel or in a large window (*Window* button or double-click) and manual cleanup: *Delete* removes the run. Nothing is ever deleted automatically.

Each finished run gets a results summary read from the `.rmed`: maximum displacement, maximum Von Mises, margins (strength / max σVM) for each strength of the library material, per `AFFE_MATERIAU` zone, and an equilibrium check where Asteroid recomputes the applied load from the `.comm` and the geometry and compares it with the sum of `REAC_NODA`. Optionally (*Global settings → ParaView and captures*), `pvbatch` from ParaView renders four views of the deformed shape coloured by Von Mises; compared runs share the same views, colour scale and amplification. Run profiles set `P time_limit` and `P memory_limit` of the `.export`: the arrow next to Run picks one and runs, and *Edit profiles…* is in the same menu. The first profile is the default; limits set in *Settings → Project* become the default choice (“Project”).

### Material library

One JSON file per material in `materiaux/`, in SI units, with the Code_Aster constant names (`E`, `NU`, `ALPHA`, `E_L`, `G_LN`…) and the models `ELAS`, `ELAS_ISTR` or `ELAS_ORTH`. Share a material by copying its file, or a whole library by dropping its folder into `materiaux/` (subfolders are read). *Material library → Import…* accepts a file with one material, a list of materials, or a project's `materials.json`. When a `DEFI_MATERIAU` block uses a material, Asteroid converts it to the project's units (the only conversion the app performs) and keeps a frozen copy in the project.

### Languages

To add a language, create `langues/<code>.json`. Each key is a French sentence of the interface and each value is its translation; missing sentences stay in French. Start from the bundled English file (path given in `langues/LISEZMOI.txt`). Code_Aster keywords and the `.comm` file are never translated.

## From source

```bash
git clone <this repository> && cd asteroid
uv venv && uv pip install -e ".[dev]"
cd frontend && npm install && npm run build && cd ..
.venv/bin/asteroid
```

Settings and library then live in `~/.config/asteroid/`. Tests: `.venv/bin/pytest`. Archive and wheel: `scripts/build-portable.sh` (output in `dist/`). AppImage: `scripts/build-appimage.sh` (output in `dist/`, downloads Python and appimagetool).
scripts/asteroid-test.sh [project]     # sources without building (Vite) on :5180, next to the usual instance

## License

[GPL-3.0-or-later](LICENSE). Code_Aster is free software by EDF under the GPL; the command catalogue bundled in `asteroid/data/` is extracted from it.
