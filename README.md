# Asteroid

*[English version](README.en.md)*

Préparer, lancer et suivre des calculs **Code_Aster** en mécanique statique, sans Salome-Meca.

```
FreeCAD → STEP → Gmsh → maillage .med → Asteroid → Code_Aster → résultats .rmed → ParaView
```

Asteroid affiche le maillage et ses groupes en 3D, construit le fichier de commandes `.comm` bloc par bloc (formulaires pour les commandes courantes, texte libre pour tout le reste), le valide en continu avec le catalogue de Code_Aster, lance le calcul, rattache les erreurs au bon bloc et ouvre les résultats dans ParaView. Il écrit les vrais noms de commandes et de mots-clés Code_Aster, sans syntaxe réinventée : le `.comm` généré reste lisible et modifiable à la main.

Interface en français ou en anglais. Linux uniquement.

## Installation

1. Télécharger l'archive `asteroid-<version>-linux.tar.gz` depuis la page [Releases](../../releases).
2. L'extraire où l'on veut, puis lancer `asteroid` :

   ```bash
   tar -xzf asteroid-*-linux.tar.gz
   ./asteroid/asteroid
   ```

Au premier lancement, le lanceur crée un environnement Python dans `asteroid/.venv/` et y installe Asteroid et ses dépendances depuis PyPI (connexion internet nécessaire, une seule fois). Il utilise [uv](https://docs.astral.sh/uv/) s'il est installé, sinon le Python du système. Un lanceur « Asteroid » est ensuite ajouté au menu des applications.

**Mise à jour** : extraire la nouvelle archive au même endroit. Les réglages et la bibliothèque de matériaux sont conservés ; l'environnement Python est mis à jour au lancement suivant.

Autre possibilité, sans dossier : installer le wheel de la release avec `pipx install asteroid-<version>-py3-none-any.whl` (ou `uv tool install …`), puis lancer `asteroid`. Réglages et bibliothèque vont alors dans `~/.config/asteroid/`.

### Ce qu'il faut à côté

| Outil | Rôle | Obligatoire |
|---|---|---|
| Linux | | oui |
| Python 3.11 ou plus avec le module venv (Debian/Ubuntu : `sudo apt install python3-venv`), ou uv | exécution d'Asteroid | oui |
| Code_Aster, par exemple l'image Docker `simvia/code_aster:stable` (17.4) | calcul | oui |
| [ParaView](https://www.paraview.org/download/) avec le plugin MEDReader (inclus dans les binaires officiels) | résultats | non |
| Chrome ou Chromium | fenêtre dédiée ; sinon le navigateur par défaut | non |
| zenity | sélecteur de fichiers natif ; sinon un explorateur intégré | non |
| Gmsh | création du maillage `.med` | en amont |

## Premier lancement

Asteroid ne devine rien : il exécute les commandes que vous lui donnez. Le premier écran demande :

- **la commande de lancement de Code_Aster**, exécutée par bash depuis le dossier du run ;
- **la commande d'arrêt** (bouton Stop) ;
- **la commande ParaView**, avec le chemin complet si `paraview` n'est pas dans le `PATH` ;
- la langue de l'interface.

Tout reste modifiable dans *Réglages → Réglages globaux*.

Variables utilisables dans les commandes :

| Variable | Valeur |
|---|---|
| `{run_dir}` | chemin absolu du dossier du run (dossier courant de la commande) |
| `{export}` | fichier `.export` du run, relatif au dossier du run |
| `{comm}`, `{mesh}` | fichier `.comm` et maillage copiés dans le run |
| `{run_id}` | identifiant du run (horodatage), utile pour nommer un conteneur |
| `{image}` | image Docker des réglages |
| `{script}`, `{rmed}` | (ParaView) script qui charge MEDReader et ouvre les `.rmed`, premier `.rmed` du run |

Valeur proposée, pour l'image Docker officielle (`run_aster` n'est dans le `PATH` de l'image qu'après `source /opt/activate.sh`) :

```
docker run --rm --name asteroid_{run_id} --user $(id -u):$(id -g) -v {run_dir}:/work -w /work \
  {image} bash -c "source /opt/activate.sh && run_aster {export}"
```

Avec une installation locale de Code_Aster, la commande se réduit à `run_aster {export}`. Pour Apptainer ou un autre lanceur, adapter la commande Docker.

ParaView ne lit les `.rmed` qu'une fois le plugin MEDReader chargé : la valeur par défaut `paraview --script={script}` s'en charge.

## Fichiers

Dossier de l'app (archive) :

```
asteroid/
├── asteroid          lanceur
├── config/           réglages (settings.json), créé au premier lancement
├── materiaux/        bibliothèque de matériaux : un fichier JSON par matériau
├── langues/          traductions ajoutées (voir langues/LISEZMOI.txt)
├── wheels/           Asteroid (paquet Python)
└── .venv/            environnement Python, créé au premier lancement
```

Dossier d'un projet : `asteroid.json` (blocs et réglages du projet), `materials.json` (copies figées des matériaux utilisés), le maillage, et `runs/<horodatage>/` pour chaque calcul (`run.comm`, `run.export`, `message`, `run.log`, `resultat.rmed`…).

### Bibliothèque de matériaux

Un fichier JSON par matériau dans `materiaux/`, en unités SI, avec les noms de constantes de Code_Aster :

```json
{
  "units": "SI (Pa, kg/m³, 1/K)",
  "name": "Acier S235",
  "description": "Acier de construction non allié",
  "source": "EN 1993-1-1",
  "model": "ELAS",
  "constants": { "E": 210000000000.0, "NU": 0.3, "ALPHA": 1.2e-05 },
  "rho": 7850,
  "strengths": [{ "name": "Limite élastique fy", "value": 235000000.0 }]
}
```

Modèles : `ELAS` (isotrope), `ELAS_ISTR` (isotrope transverse), `ELAS_ORTH` (orthotrope).

- **Partager** un matériau : copier son fichier. Une bibliothèque entière : déposer son dossier dans `materiaux/` (les sous-dossiers sont lus).
- **Importer** (*Bibliothèque matériaux → Importer…*) : un fichier contenant un matériau, une liste de matériaux, ou le `materials.json` d'un projet.
- Quand un bloc `DEFI_MATERIAU` utilise un matériau, Asteroid le convertit dans les unités du projet (seule conversion faite par l'app) et en garde une copie figée dans le projet : un ancien calcul reste reproductible même si la bibliothèque change.

### Langues

L'interface existe en français et en anglais. Pour une autre langue, ajouter `langues/<code>.json` : la clé est la phrase française, la valeur sa traduction ; une phrase absente reste en français. Le fichier anglais livré sert de point de départ. Les mots-clés Code_Aster et le `.comm` ne sont jamais traduits.

## Fonctions

- **Maillage** : lecture du `.med` (groupes, aires, volumes), vue 3D, surbrillance d'un groupe, détection d'un maillage en mètres dans un projet en millimètres (correction par `MODI_MAILLAGE(ECHELLE=…)`).
- **Blocs** : formulaires pour LIRE_MAILLAGE, MODI_MAILLAGE, AFFE_MODELE, DEFI_MATERIAU, AFFE_MATERIAU, AFFE_CARA_ELEM, AFFE_CHAR_MECA, MECA_STATIQUE, MACRO_ELAS_MULT, CALC_CHAMP, IMPR_RESU ; bascule formulaire ↔ texte ; texte libre avec autocomplétion pour toutes les autres commandes.
- **Validation** : en continu, à partir du catalogue de Code_Aster 17.4 livré. *Réglages → Mettre à jour le catalogue* l'exporte depuis votre version de Code_Aster (commande modifiable, Docker par défaut).
- **Import** d'un `.comm` existant : un bloc par commande, texte d'origine et commentaires conservés.
- **Édition** : erreurs repérées signalées avant le run (correction proposée quand seule la casse d'un nom de groupe diffère), annuler/rétablir (Ctrl+Z, Ctrl+Maj+Z), renommage d'un concept propagé aux blocs qui l'utilisent.
- **Runs** : log en direct, diagnostic, messages `<F>`, `<E>`, `<A>` rattachés à leur bloc, Stop, ouverture dans ParaView. Le calcul tourne dans un script `run.sh` détaché de l'app : fermer la fenêtre ne l'arrête pas, et il est repris à la réouverture. Notification du bureau en fin de run.
- **Profils de run** (*Réglages globaux*) : temps et mémoire limites (`P time_limit`, `P memory_limit` du `.export`), choisis au lancement dans le menu à côté de Run ; « Valeurs du projet » utilise ceux du projet.
- **Onglet Runs** : tableau des runs avec une note libre par run, fichiers du run (consultables dans l'app), comparaison de deux runs (différences des `.comm`), nettoyage manuel : « Alléger » retire la copie du maillage en gardant les résultats, « Supprimer » efface le run. Rien n'est jamais supprimé automatiquement.

## Depuis les sources

Pour développer :

```bash
git clone <ce dépôt> && cd asteroid
uv venv && uv pip install -e ".[dev]"
cd frontend && npm install && npm run build && cd ..
.venv/bin/asteroid
```

Réglages et bibliothèque vont alors dans `~/.config/asteroid/`. Autres commandes :

```bash
.venv/bin/pytest                       # tests ; le cas réel tourne dans Docker si l'image est présente
cd frontend && npm run dev             # interface sur :5173, /api relayé vers le serveur sur :8765
scripts/build-portable.sh              # archive et wheel dans dist/
```

Options de la commande : `asteroid [dossier de projet] [--port N] [--no-browser] [--keep-running] [--no-desktop-entry]`.

## Licence

[GPL-3.0-or-later](LICENSE). Code_Aster est un logiciel libre d'EDF sous licence GPL ; le catalogue des commandes livré dans `asteroid/data/` en est extrait.
