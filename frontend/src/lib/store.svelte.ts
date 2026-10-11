// État global de l'interface et actions.

import {
  api,
  type AsterMessage,
  type Block,
  type CataEntity,
  type CatalogSummary,
  type CommResult,
  type MeshGroup,
  type MeshSummary,
  type Project,
  type RunInfo,
  type RunSummary,
  type Settings,
  type Snapshot,
} from "./api";
import { autofill, conceptsBefore, missingRequired, type FormCatalog } from "./forms";
import { History } from "./history";
import { i18n, N_, t } from "./i18n.svelte";
import { collectProblems, type Problem } from "./problems";

export type BottomTab = "comm" | "export" | "log" | "history";
type SaveState = "saved" | "dirty" | "saving" | "nodir" | "error";
/** edit : saisie (fusionnée avec les saisies rapprochées) ; step : action franche ; amend : suite de l'étape en cours. */
type Change = "edit" | "step" | "amend";

interface PickerRequest {
  mode: "file" | "dir";
  title: string;
  extensions: string[];
  resolve: (path: string | null) => void;
}

const SAVE_DELAY = 800;
const PREVIEW_DELAY = 200;

// Rang habituel des commandes dans un calcul statique : un nouveau bloc se place
// après le dernier bloc de rang inférieur ou égal. L'ordre reste modifiable.
const COMMAND_RANK: Record<string, number> = {
  LIRE_MAILLAGE: 0,
  MODI_MAILLAGE: 1, DEFI_GROUP: 1, CREA_MAILLAGE: 1,
  AFFE_MODELE: 2,
  DEFI_FONCTION: 3, DEFI_CONSTANTE: 3, FORMULE: 3, DEFI_LIST_REEL: 3, DEFI_LIST_INST: 3,
  DEFI_MATERIAU: 3, INCLUDE_MATERIAU: 3,
  AFFE_MATERIAU: 4,
  AFFE_CARA_ELEM: 5,
  AFFE_CHAR_MECA: 6, AFFE_CHAR_MECA_F: 6, AFFE_CHAR_CINE: 6,
  MECA_STATIQUE: 7, MACRO_ELAS_MULT: 7, STAT_NON_LINE: 7,
  CALC_CHAMP: 8,
  POST_RELEVE_T: 9, POST_ELEM: 9, CREA_CHAMP: 9, CREA_TABLE: 9, CALC_TABLE: 9,
  IMPR_RESU: 10, IMPR_TABLE: 10,
  TEST_RESU: 11, TEST_TABLE: 11,
}; // prettier-ignore

export interface UnitWarning {
  kind: "meters" | "millimeters";
  size: string;
}

function emptyProject(): Project {
  return {
    version: 1,
    name: t("nouveau projet"),
    mesh: null,
    units: "mm-N-MPa",
    runs_dir: "runs",
    time_limit: 300,
    memory_limit: 2048,
    files: [],
    blocks: [],
  };
}

function newId(): string {
  return crypto.randomUUID().replaceAll("-", "").slice(0, 12);
}

class AppStore {
  project = $state<Project>(emptyProject());
  projectDir = $state<string | null>(null);
  settings = $state<Settings | null>(null);
  paths = $state<Snapshot["paths"] | null>(null);
  forms = $state<FormCatalog | null>(null);
  catalog = $state<CatalogSummary | null>(null);
  #commandDefs = new Map<string, Promise<CataEntity | null>>();
  selectedId = $state<string | null>(null);
  preview = $state<CommResult | null>(null);

  mesh = $state<MeshSummary | null>(null);
  meshError = $state<string | null>(null);
  meshLoading = $state(false);
  highlight = $state<{ entity: MeshGroup["entity"]; name: string } | null>(null);
  showEdges = $state(true);

  history = $state<RunSummary[]>([]);
  run = $state<RunInfo | null>(null); // run affiché dans le panneau du bas
  log = $state<string[]>([]);
  activeRunId = $state<string | null>(null); // run en cours d'exécution

  bottomOpen = $state(true);
  bottomTab = $state<BottomTab>("comm");
  saveState = $state<SaveState>("nodir");
  notice = $state<{ text: string; kind: "info" | "error" } | null>(null);
  picker = $state<PickerRequest | null>(null);
  settingsOpen = $state(false);
  importOpen = $state(false);
  materialsOpen = $state(false);
  library = $state<import("./api").Material[]>([]);
  libraryErrors = $state<string[]>([]);
  libraryDir = $state("");

  canUndo = $state(false);
  canRedo = $state(false);
  /** Incrémenté à chaque annulation : les éditeurs du bloc sont recréés avec les valeurs restaurées. */
  revision = $state(0);
  /** Bloc dont l'éditeur a le focus : le module d'erreurs attend la fin de la saisie. */
  editingId = $state<string | null>(null);
  /** Liste des erreurs ouverte : consultation, ou avant le lancement d'un run. */
  problemsOpen = $state<"list" | "run" | null>(null);

  #saveTimer: ReturnType<typeof setTimeout> | undefined;
  #previewTimer: ReturnType<typeof setTimeout> | undefined;
  #noticeTimer: ReturnType<typeof setTimeout> | undefined;
  #source: EventSource | null = null;
  #lastSaved = "";
  #history = new History(JSON.stringify(this.project));

  selected = $derived(this.project.blocks.find((b) => b.id === this.selectedId) ?? null);
  running = $derived(this.activeRunId !== null);

  /** Facteur MODI_MAILLAGE(ECHELLE=...) : les mesures affichées sont celles que verra Code_Aster. */
  meshScale = $derived(this.preview?.mesh_scale ?? 1);

  /** Dimensions de la boîte englobante, après mise à l'échelle. */
  meshSize = $derived.by(() => {
    if (!this.mesh) return null;
    const [lo, hi] = this.mesh.bbox;
    return hi.map((h, i) => (h - lo[i]) * this.meshScale);
  });

  /** Maillage dont la taille ne colle pas au système d'unités du projet. */
  unitWarning = $derived.by((): UnitWarning | null => {
    const size = this.meshSize;
    if (!size) return null;
    const diag = Math.hypot(...size);
    const text = size.map((x) => x.toLocaleString(i18n.locale, { maximumSignificantDigits: 3 })).join(" × ");
    if (this.project.units === "mm-N-MPa" && diag > 0 && diag < 1) return { kind: "meters", size: text };
    if (this.project.units === "m-N-Pa" && diag > 50) return { kind: "millimeters", size: text };
    return null;
  });

  /** Infos calculées par le backend (commande, concept, erreur) pour chaque bloc. */
  blockInfo = $derived(new Map((this.preview?.blocks ?? []).map((b) => [b.id, b])));

  /** Champs obligatoires manquants des blocs graphiques. */
  blockMissing = $derived.by(() => {
    const map = new Map<string, string[]>();
    for (const b of this.project.blocks) {
      const schema = b.mode === "form" ? this.forms?.schemas[b.command] : undefined;
      if (!schema) continue;
      const missing = missingRequired(schema.fields, b.params);
      if (missing.length) map.set(b.id, missing);
    }
    return map;
  });

  /** Erreurs repérées avant le run (syntaxe, validation, champs obligatoires). */
  problems = $derived(collectProblems(this.project.blocks, this.blockInfo, this.blockMissing));

  /** Erreurs signalées par le module : aucune pendant l'édition d'un bloc (y compris les erreurs
   *  en cascade d'une saisie inachevée), toutes dès qu'on passe à autre chose. */
  shownProblems = $derived(this.editingId ? [] : this.problems);

  /** Messages du dernier run affiché, rattachés à leur bloc. */
  blockMessages = $derived.by(() => {
    const map = new Map<string, AsterMessage[]>();
    for (const m of this.run?.messages ?? []) {
      if (!m.block_id) continue;
      map.set(m.block_id, [...(map.get(m.block_id) ?? []), m]);
    }
    return map;
  });

  // ------------------------------------------------------------------ chargement

  async init() {
    try {
      await i18n.load();
      this.forms = await api.forms();
      this.catalog = await api.catalog().catch(() => null);
      this.#apply(await api.state());
    } catch (e) {
      this.error(e);
    }
  }

  #apply(snap: Snapshot, keepHistory = false) {
    this.project = snap.project;
    const json = JSON.stringify(snap.project);
    if (keepHistory) this.#history.record(json, performance.now());
    else this.#history.reset(json);
    this.#syncHistory();
    this.problemsOpen = null;
    this.projectDir = snap.project_dir;
    this.settings = snap.settings;
    this.paths = snap.paths;
    this.#lastSaved = JSON.stringify(snap.project);
    this.saveState = snap.project_dir ? "saved" : "nodir";
    if (!this.project.blocks.some((b) => b.id === this.selectedId)) {
      this.selectedId = this.project.blocks[0]?.id ?? null;
    }
    this.run = null;
    this.log = [];
    this.schedulePreview();
    this.refreshHistory();
    this.loadMesh();
  }

  async loadMesh() {
    this.highlight = null;
    this.meshError = null;
    if (!this.project.mesh || !this.projectDir) {
      this.mesh = null;
      return;
    }
    this.meshLoading = true;
    try {
      this.mesh = await api.mesh();
    } catch (e) {
      this.mesh = null;
      this.meshError = e instanceof Error ? e.message : String(e);
    } finally {
      this.meshLoading = false;
    }
  }

  /** Recharge le maillage s'il a été réexporté (date de modification changée). */
  async refreshMesh() {
    if (!this.mesh || this.meshLoading) return;
    try {
      const fresh = await api.mesh();
      if (fresh.version === this.mesh.version) return;
      this.mesh = fresh;
      const h = this.highlight;
      if (h && !fresh.groups.some((g) => g.entity === h.entity && g.name === h.name)) this.highlight = null;
      this.info(t("Maillage rechargé (fichier modifié)"));
    } catch (e) {
      this.meshError = e instanceof Error ? e.message : String(e);
      this.mesh = null;
    }
  }

  /** Groupe du maillage portant ce nom (GROUP_MA en priorité). */
  findGroup(name: string, entity?: MeshGroup["entity"]): MeshGroup | undefined {
    const groups = this.mesh?.groups ?? [];
    return (
      groups.find((g) => g.name === name && (!entity || g.entity === entity)) ??
      groups.find((g) => g.name === name)
    );
  }

  toggleHighlight(group: MeshGroup) {
    const same = this.highlight?.entity === group.entity && this.highlight.name === group.name;
    this.highlight = same ? null : { entity: group.entity, name: group.name };
  }

  info(text: string) {
    this.#notify(text, "info");
  }

  error(e: unknown) {
    this.#notify(e instanceof Error ? e.message : String(e), "error");
  }

  #notify(text: string, kind: "info" | "error") {
    this.notice = { text, kind };
    clearTimeout(this.#noticeTimer);
    this.#noticeTimer = setTimeout(() => (this.notice = null), kind === "error" ? 8000 : 3500);
  }

  // ------------------------------------------------------------------ sauvegarde

  /** Appelé à chaque modification du projet. */
  touch(change: Change = "edit") {
    const json = JSON.stringify(this.project);
    if (change === "amend") this.#history.amend(json);
    else this.#history.record(json, performance.now(), change === "step");
    this.#syncHistory();
    this.#changed(json);
  }

  #syncHistory() {
    this.canUndo = this.#history.canUndo;
    this.canRedo = this.#history.canRedo;
  }

  /** Aperçu et sauvegarde différée, sans toucher à l'historique. */
  #changed(json: string) {
    this.schedulePreview();
    if (json === this.#lastSaved) return;
    if (!this.projectDir) {
      this.saveState = "nodir";
      return;
    }
    this.saveState = "dirty";
    clearTimeout(this.#saveTimer);
    this.#saveTimer = setTimeout(() => this.save(), SAVE_DELAY);
  }

  async save(): Promise<boolean> {
    clearTimeout(this.#saveTimer);
    if (!this.projectDir) {
      return this.saveAs();
    }
    const json = JSON.stringify(this.project);
    this.saveState = "saving";
    try {
      await api.saveProject($state.snapshot(this.project));
      this.#lastSaved = json;
      this.saveState = JSON.stringify(this.project) === json ? "saved" : "dirty";
      return true;
    } catch (e) {
      this.saveState = "error";
      this.error(e);
      return false;
    }
  }

  // ------------------------------------------------------------------ annuler / rétablir

  undo() {
    this.#restore(this.#history.undo(JSON.stringify(this.project)));
  }

  redo() {
    this.#restore(this.#history.redo(JSON.stringify(this.project)));
  }

  #restore(json: string | null) {
    this.#syncHistory();
    if (json === null) return;
    const before = new Set(this.project.blocks.map((b) => b.id));
    this.project = JSON.parse(json);
    // Un bloc qui réapparaît (suppression annulée) devient le bloc sélectionné.
    const back = this.project.blocks.find((b) => !before.has(b.id));
    if (back) this.selectedId = back.id;
    else if (!this.project.blocks.some((b) => b.id === this.selectedId)) {
      this.selectedId = this.project.blocks[0]?.id ?? null;
    }
    this.revision++;
    this.#changed(json);
  }

  schedulePreview() {
    clearTimeout(this.#previewTimer);
    this.#previewTimer = setTimeout(async () => {
      try {
        this.preview = await api.preview($state.snapshot(this.project));
      } catch (e) {
        this.error(e);
      }
    }, PREVIEW_DELAY);
  }

  /** Aperçu à jour tout de suite (avant un run, après une correction). */
  async refreshPreview() {
    clearTimeout(this.#previewTimer);
    try {
      this.preview = await api.preview($state.snapshot(this.project));
    } catch (e) {
      this.error(e);
    }
  }

  // ------------------------------------------------------------------ fichiers

  /** Sélecteur natif (zenity) côté backend, sinon explorateur intégré. */
  async pick(mode: "file" | "dir", title: string, filters: string[] = []): Promise<string | null> {
    try {
      const res = await api.pick(mode, title, filters, this.projectDir);
      if (!res.fallback) return res.path;
    } catch (e) {
      this.error(e);
      return null;
    }
    const extensions = filters.flatMap((f) =>
      (f.split("|")[1] ?? "").trim().split(/\s+/).map((p) => p.replace("*", "")),
    );
    return new Promise((resolve) => {
      this.picker = { mode, title, extensions: extensions.filter(Boolean), resolve };
    });
  }

  closePicker(path: string | null) {
    this.picker?.resolve(path);
    this.picker = null;
  }

  async newProject() {
    await this.#flush();
    try {
      this.#apply(await api.newProject(null));
    } catch (e) {
      this.error(e);
    }
  }

  async openProject(dir?: string) {
    const path = dir ?? (await this.pick("dir", t("Ouvrir un projet Asteroid")));
    if (!path) return;
    await this.#flush();
    try {
      this.#apply(await api.openProject(path));
      this.info(t("Projet ouvert : {name}", { name: this.project.name }));
    } catch (e) {
      this.error(e);
    }
  }

  async saveAs(): Promise<boolean> {
    const dir = await this.pick("dir", t("Dossier du projet"));
    if (!dir) return false;
    try {
      await api.saveProject($state.snapshot(this.project));
      this.#apply(await api.saveAs(dir), true);
      this.info(t("Projet enregistré dans {path}", { path: dir }));
      return true;
    } catch (e) {
      this.error(e);
      return false;
    }
  }

  async #flush() {
    if (this.projectDir && this.saveState === "dirty") await this.save();
  }

  async chooseMesh() {
    const path = await this.pick("file", t("Choisir le maillage"), [`${t("Maillage MED")} | *.med *.mmed`]);
    if (!path) return;
    try {
      await api.saveProject($state.snapshot(this.project));
      const selected = this.selectedId;
      this.#apply(await api.setMesh(path));
      this.selectedId = selected ?? this.selectedId;
      if (this.project.blocks.length === 0) await this.#addBaseBlocks();
      this.info(t("Maillage : {path}", { path: this.project.mesh }));
    } catch (e) {
      this.error(e);
    }
  }

  async #addBaseBlocks() {
    for (const command of ["LIRE_MAILLAGE", "AFFE_MODELE"]) await this.addBlock(command);
    this.selectedId = this.project.blocks[0]?.id ?? null;
  }

  // ------------------------------------------------------------------ blocs

  /** Définition d'une commande (chargée une fois, à la demande). */
  commandDef(name: string): Promise<CataEntity | null> {
    if (!this.#commandDefs.has(name)) {
      this.#commandDefs.set(name, api.catalogCommand(name).catch(() => null));
    }
    return this.#commandDefs.get(name)!;
  }

  commandInfo(name: string) {
    return this.catalog?.commands.find((c) => c.name === name);
  }

  async loadLibrary() {
    try {
      const lib = await api.materials();
      this.library = lib.materials;
      this.libraryErrors = lib.errors;
      this.libraryDir = lib.dir;
    } catch (e) {
      this.error(e);
    }
  }

  /** Remplit un bloc DEFI_MATERIAU avec un matériau de la bibliothèque, converti et copié dans le projet. */
  async applyMaterial(block: Block, materialId: string) {
    try {
      const res = await api.useMaterial(materialId, this.project.units);
      block.params = res.params;
      block.meta = { ...(block.meta ?? {}), material: materialId, units: res.units };
      this.touch("step");
      this.info(
        this.projectDir
          ? t("« {name} » converti en {units} et copié dans materials.json", { name: res.material.name, units: res.units })
          : t("« {name} » converti en {units}", { name: res.material.name, units: res.units }),
      );
    } catch (e) {
      this.error(e);
    }
  }

  async updateCatalog(): Promise<boolean> {
    try {
      const res = await api.updateCatalog();
      this.catalog = await api.catalog();
      this.#commandDefs.clear();
      if (this.settings) this.settings.aster_version = res.version;
      this.info(t("Catalogue {version} installé ({count} commandes)", { version: res.version, count: res.commands }));
      this.schedulePreview();
      return true;
    } catch (e) {
      this.error(e);
      return false;
    }
  }

  blockCommand(b: Block): { command: string; concept: string | null } {
    const info = this.blockInfo.get(b.id);
    if (b.mode === "form" || !info) return { command: b.command, concept: b.concept };
    return { command: info.command || b.command, concept: info.concept };
  }

  /** Concepts définis au-dessus du bloc, avec leur type. */
  conceptsFor(blockId: string): { name: string; type: string }[] {
    const index = this.project.blocks.findIndex((b) => b.id === blockId);
    return conceptsBefore(this.project.blocks, index < 0 ? 0 : index, (b) => this.blockCommand(b), this.forms?.concept_types ?? {});
  }

  /** Bascule graphique ↔ texte. Renvoie false (avec la raison) si le texte ne tient pas dans le formulaire. */
  async toggleMode(block: Block): Promise<boolean> {
    try {
      if (block.mode === "form") {
        const { text } = await api.toText($state.snapshot(block) as Block);
        block.text = text;
        block.mode = "text";
        block.fallback_reason = null;
      } else {
        const res = await api.toForm(block.text);
        if (!res.ok) {
          block.fallback_reason = res.reason ?? t("non géré par le formulaire");
          this.touch();
          return false;
        }
        block.command = res.command!;
        block.concept = res.concept ?? null;
        block.params = res.params!;
        block.mode = "form";
        block.fallback_reason = null;
      }
      this.touch("step");
      return true;
    } catch (e) {
      this.error(e);
      return false;
    }
  }

  conceptNames(): string[] {
    return this.project.blocks
      .map((b) => this.blockInfo.get(b.id)?.concept ?? b.concept)
      .filter((c): c is string => !!c);
  }

  async addBlock(command: string, index?: number, text?: string) {
    try {
      const block = await api.newBlock(command, this.conceptNames());
      if (text !== undefined) {
        block.text = text;
        block.mode = "text";
      }
      const at = index ?? this.#insertIndex(block.command);
      const schema = this.forms?.schemas[block.command];
      if (block.mode === "form" && schema) {
        const available = conceptsBefore(this.project.blocks, at, (b) => this.blockCommand(b), this.forms!.concept_types);
        autofill(schema.fields, block.params, available);
        if (schema.reuse && isRefValue(block.params[schema.reuse])) {
          block.concept = (block.params[schema.reuse] as { $ref: string }).$ref;
        }
      }
      this.project.blocks.splice(at, 0, block);
      this.#backfill(at + 1);
      this.selectedId = block.id;
      this.touch("step");
    } catch (e) {
      this.error(e);
    }
  }

  /** Complète les champs concept vides des blocs graphiques à partir de `from`. */
  #backfill(from: number) {
    const types = this.forms?.concept_types ?? {};
    this.project.blocks.forEach((b, i) => {
      const schema = this.forms?.schemas[b.command];
      if (i < from || b.mode !== "form" || !schema) return;
      autofill(schema.fields, b.params, conceptsBefore(this.project.blocks, i, (x) => this.blockCommand(x), types));
    });
  }

  #insertIndex(command: string): number {
    const rank = COMMAND_RANK[command];
    if (rank === undefined) {
      const i = this.project.blocks.findIndex((b) => b.id === this.selectedId);
      return i < 0 ? this.project.blocks.length : i + 1;
    }
    let at = 0;
    this.project.blocks.forEach((b, i) => {
      const r = COMMAND_RANK[this.blockInfo.get(b.id)?.command || b.command];
      if (r !== undefined && r <= rank) at = i + 1;
    });
    return at;
  }

  // ------------------------------------------------------------------ unités

  setUnits(units: Project["units"]) {
    this.project.units = units;
    this.touch("step");
  }

  /** Ajoute MODI_MAILLAGE(ECHELLE=...) juste après la lecture du maillage. */
  async addScaleBlock(factor: number) {
    const read = this.project.blocks.find(
      (b) => (this.blockInfo.get(b.id)?.command || b.command) === "LIRE_MAILLAGE",
    );
    const mail = (read && (this.blockInfo.get(read.id)?.concept ?? read.concept)) || "mail";
    const value = Number.isInteger(factor) ? factor.toFixed(1) : String(factor);
    const text = `${mail} = MODI_MAILLAGE(reuse=${mail}, MAILLAGE=${mail}, ECHELLE=${value})`;
    await this.addBlock("MODI_MAILLAGE", undefined, text);
  }

  /** Chemin relatif au dossier du projet quand le fichier y est, absolu sinon. */
  relativePath(path: string): string {
    const dir = this.projectDir?.replace(/\/$/, "");
    return dir && path.startsWith(dir + "/") ? path.slice(dir.length + 1) : path;
  }

  /** Rattache un fichier de données à une unité logique (déclaré dans le .export, copié dans le run). */
  attachFile(unit: number, path: string, mode: "D" | "R" = "D") {
    this.project.files ??= [];
    const entry = { unit, path: mode === "D" ? this.relativePath(path) : path, mode, kind: "libr" };
    const i = this.project.files.findIndex((f) => f.unit === unit);
    if (i >= 0) this.project.files[i] = entry;
    else this.project.files.push(entry);
    this.touch("step");
  }

  async pickAndAttach(unit: number) {
    const path = await this.pick("file", t("Fichier pour l'unité {unit}", { unit }));
    if (path) this.attachFile(unit, path);
  }

  /** Blocs issus d'un .comm importé, à la place des blocs existants ou à la suite. */
  applyImport(blocks: Block[], mode: "replace" | "append") {
    if (mode === "replace") this.project.blocks.splice(0, this.project.blocks.length, ...blocks);
    else this.project.blocks.push(...blocks);
    this.selectedId = blocks[0]?.id ?? this.selectedId;
    this.touch("step");
    this.info(t("{count} bloc(s) importé(s)", { count: blocks.length }));
  }

  duplicateBlock(id: string) {
    const i = this.project.blocks.findIndex((b) => b.id === id);
    if (i < 0) return;
    const copy: Block = { ...$state.snapshot(this.project.blocks[i]), id: newId() };
    this.project.blocks.splice(i + 1, 0, copy);
    this.selectedId = copy.id;
    this.touch("step");
  }

  removeBlock(id: string) {
    const i = this.project.blocks.findIndex((b) => b.id === id);
    if (i < 0) return;
    this.project.blocks.splice(i, 1);
    if (this.selectedId === id) {
      this.selectedId = this.project.blocks[Math.min(i, this.project.blocks.length - 1)]?.id ?? null;
    }
    this.touch("step");
  }

  /** Propage le nouveau nom d'un concept aux blocs qui le référencent (même étape d'annulation). */
  async renameConcept(blockId: string, old: string | null, name: string | null) {
    if (!old || !name || old === name) return;
    const index = this.project.blocks.findIndex((b) => b.id === blockId);
    if (index < 0) return;
    if (this.project.blocks.some((b, i) => i !== index && this.blockCommand(b).concept === name)) {
      this.info(t("« {name} » est déjà défini : les références à « {old} » ne sont pas modifiées", { name, old }));
      return;
    }
    try {
      const res = await api.renameConcept($state.snapshot(this.project.blocks) as Block[], index, old, name);
      // Projet modifié entre-temps (annulation…) : réponse périmée.
      if (!res.count || this.project.blocks[index]?.id !== blockId || this.project.blocks[index].concept !== name) return;
      for (const updated of res.blocks) {
        const block = this.project.blocks.find((b) => b.id === updated.id);
        if (!block) continue;
        if (JSON.stringify(block.params) !== JSON.stringify(updated.params)) block.params = updated.params;
        if (block.text !== updated.text) block.text = updated.text;
        if (block.concept !== updated.concept) block.concept = updated.concept;
      }
      this.touch("amend");
      this.info(t("{count} référence(s) à « {old} » renommée(s) en « {name} »", { count: res.count, old, name }));
    } catch (e) {
      this.error(e);
    }
  }

  /** Corrige un nom de groupe (casse) dans un bloc. */
  async fixGroup(blockId: string, fix: NonNullable<Problem["fix"]>) {
    const block = this.project.blocks.find((b) => b.id === blockId);
    if (!block) return;
    try {
      const res = await api.replaceGroup($state.snapshot(block) as Block, fix.from, fix.to);
      if (!res.count) {
        this.info(t("« {name} » n'apparaît pas tel quel dans le bloc : à corriger à la main", { name: fix.from }));
        return;
      }
      block.params = res.block.params;
      block.text = res.block.text;
      this.touch("step");
      await this.refreshPreview();
    } catch (e) {
      this.error(e);
    }
  }

  moveBlock(from: number, to: number) {
    if (from === to || from + 1 === to) return;
    const [block] = this.project.blocks.splice(from, 1);
    this.project.blocks.splice(to > from ? to - 1 : to, 0, block);
    this.touch("step");
  }

  // ------------------------------------------------------------------ runs

  async refreshHistory() {
    if (!this.projectDir) {
      this.history = [];
      return;
    }
    try {
      this.history = await api.runs();
      // Run resté en cours pendant que l'app était fermée : repris par le serveur, suivi ici.
      const running = this.history.find((r) => r.status === "running");
      if (running && !this.activeRunId) {
        this.activeRunId = running.id;
        this.#follow(await api.runInfo(running.id));
      }
    } catch (e) {
      this.error(e);
    }
  }

  /** Libellé d'un profil de run (les profils par défaut sont traduits, les autres affichés tels quels). */
  profileLabel(name: string | null | undefined): string {
    return name ? t(name) : t("Valeurs du projet");
  }

  /** Limites affichées : « 3600 s · 8192 Mo », ou « illimité ». */
  limitsLabel(time: number | null, memory: number): string {
    const tl = time === null || time >= UNLIMITED_TIME ? t("illimité") : `${time} s`;
    return `${tl} · ${memory} Mo`;
  }

  async setRunNote(id: string, note: string) {
    try {
      await api.setRunNote(id, note);
      const item = this.history.find((r) => r.id === id);
      if (item) item.note = note;
      if (this.run?.id === id) this.run.note = note;
    } catch (e) {
      this.error(e);
    }
  }

  /** Supprime des runs (dossiers entiers), après confirmation dans l'interface. */
  async deleteRuns(ids: string[]) {
    for (const id of ids) {
      try {
        await api.deleteRun(id);
        if (this.run?.id === id) {
          this.#source?.close();
          this.run = null;
          this.log = [];
        }
      } catch (e) {
        this.error(e);
      }
    }
    await this.refreshHistory();
  }

  /** Retire la copie du maillage des runs choisis ; résultats, .comm et message restent. */
  async lightenRuns(ids: string[]) {
    let freed = 0;
    for (const id of ids) {
      try {
        freed += (await api.lightenRun(id)).freed;
      } catch (e) {
        this.error(e);
      }
    }
    await this.refreshHistory();
    this.info(t("{size} libéré(s)", { size: formatSize(freed) }));
  }

  async openRunDir(id: string) {
    try {
      await api.openRunDir(id);
    } catch (e) {
      this.error(e);
    }
  }

  /** Lance le calcul ; s'il reste des erreurs, les montre d'abord (`force` : lancer quand même).
   *  `profile` : profil des réglages globaux (null : valeurs du projet), retenu pour les lancements suivants. */
  async startRun(force = false, profile?: string | null) {
    if (this.running) return;
    if (profile !== undefined && profile !== (this.project.run_profile ?? null)) {
      this.project.run_profile = profile;
      this.touch("step");
    }
    if (!this.projectDir && !(await this.saveAs())) return;
    if (!(await this.save())) return;
    await this.refreshPreview();
    if (!force && this.problems.length) {
      this.problemsOpen = "run";
      return;
    }
    this.problemsOpen = null;
    // Autorisation des notifications de fin de run, demandée au premier lancement.
    if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
    try {
      const info = await api.startRun(this.project.run_profile ?? null);
      this.activeRunId = info.id;
      this.bottomOpen = true;
      this.bottomTab = "log";
      this.#follow(info);
      this.refreshHistory();
    } catch (e) {
      this.error(e);
    }
  }

  async stopRun() {
    if (!this.activeRunId) return;
    try {
      await api.stopRun(this.activeRunId);
    } catch (e) {
      this.error(e);
    }
  }

  async showRun(id: string) {
    try {
      this.#follow(await api.runInfo(id));
      this.bottomTab = "log";
    } catch (e) {
      this.error(e);
    }
  }

  #follow(info: RunInfo) {
    this.#source?.close();
    this.run = info;
    this.log = [];
    const source = new EventSource(api.logUrl(info.id));
    this.#source = source;
    let pending: string[] = [];
    let frame = 0;
    source.onmessage = (ev) => {
      pending.push(JSON.parse(ev.data));
      // Regroupe les lignes par image pour rester fluide sur les gros logs.
      frame ||= requestAnimationFrame(() => {
        this.log.push(...pending);
        pending = [];
        frame = 0;
      });
    };
    source.addEventListener("end", (ev) => {
      source.close();
      if (pending.length) this.log.push(...pending);
      const final = JSON.parse((ev as MessageEvent).data) as RunInfo;
      if (this.run?.id === final.id) this.run = final;
      if (this.activeRunId === final.id) {
        this.activeRunId = null;
        this.#announce(final);
      }
      this.refreshHistory();
    });
    source.onerror = () => {
      source.close();
      if (this.activeRunId === info.id) this.activeRunId = null;
    };
  }

  #announce(info: RunInfo) {
    const label = statusLabel(info.status);
    const text = `Run ${info.id} : ${label}${info.duration ? ` (${info.duration} s)` : ""}`;
    if (info.status === "fail") this.#notify(text, "error");
    else this.info(text);
    // Notification du bureau si l'app n'est pas au premier plan.
    if ((document.hidden || !document.hasFocus()) && "Notification" in window && Notification.permission === "granted") {
      new Notification(`Asteroid — ${this.project.name}`, { body: text, icon: "/logo.png" });
    }
  }

  async openParaview(id?: string) {
    const runId = id ?? this.run?.id ?? this.history[0]?.id;
    if (!runId) {
      this.info(t("Aucun run à ouvrir"));
      return;
    }
    try {
      await api.paraview(runId);
      this.info(t("ParaView lancé sur {run}", { run: runId }));
    } catch (e) {
      this.error(e);
    }
  }

  // ------------------------------------------------------------------ réglages

  async setLanguage(language: string) {
    if (this.settings) await this.saveSettings({ ...$state.snapshot(this.settings), language } as Settings);
  }

  /** Nouvelle langue : traductions et libellés des formulaires (traduits par le backend). */
  async #reloadLanguage() {
    await i18n.load();
    this.forms = await api.forms();
  }

  async saveSettings(settings: Settings) {
    try {
      const language = this.settings?.language;
      this.settings = await api.putSettings(settings);
      if (settings.language !== language) await this.#reloadLanguage();
    } catch (e) {
      this.error(e);
    }
  }
}

function isRefValue(v: unknown): boolean {
  return typeof v === "object" && v !== null && "$ref" in v;
}

export function statusLabel(status: RunInfo["status"]): string {
  return t(STATUS_LABELS[status]);
}

const STATUS_LABELS: Record<RunInfo["status"], string> = {
  running: N_("en cours"),
  ok: "OK",
  alarm: N_("alarmes"),
  fail: N_("échec"),
  stopped: N_("arrêté"),
  interrupted: N_("interrompu"),
};

/** Valeur écrite pour le profil « illimité » (100 jours, run_aster impose sinon 1 jour). */
export const UNLIMITED_TIME = 8_640_000;

export function formatSize(bytes: number): string {
  const units = ["o", "Ko", "Mo", "Go"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${bytes.toLocaleString(i18n.locale, { maximumFractionDigits: i ? 1 : 0 })} ${units[i]}`;
}

export const app = new AppStore();
