// Types et appels vers le backend FastAPI.

export type UnitSystem = "mm-N-MPa" | "m-N-Pa";

export interface Block {
  id: string;
  command: string;
  concept: string | null;
  mode: "form" | "text";
  params: Record<string, unknown>;
  text: string;
  fallback_reason: string | null;
  meta: Record<string, unknown>;
}

export type MaterialModel = "ELAS" | "ELAS_ISTR" | "ELAS_ORTH";

/** Matériau de la bibliothèque, en SI (Pa, kg/m³, 1/K). */
export interface Material {
  id: string;
  name: string;
  description: string;
  source: string;
  model: MaterialModel;
  constants: Record<string, number>;
  rho: number | null;
  strengths: { name: string; value: number }[];
}

/** Dossier materiaux/ : un fichier par matériau, sous-dossiers compris. */
export interface MaterialLibrary {
  materials: Material[];
  errors: string[];
  dir: string;
}

// L'identifiant est le chemin relatif du fichier (ex. « partage/petg ») : chaque segment est encodé.
function materialPath(id: string): string {
  return id.split("/").map(encodeURIComponent).join("/");
}

export interface ProjectMaterial {
  material: Material;
  units: UnitSystem;
  converted: { constants: Record<string, number>; strengths: { name: string; value: number }[] };
  copied: string;
}

export interface ExtraFile {
  unit: number;
  path: string; // D : relatif au projet ou absolu ; R : nom écrit dans le run
  mode: "D" | "R";
  kind: string;
}

export interface Unattached {
  command: string;
  unit: number;
}

export interface Project {
  version: number;
  name: string;
  mesh: string | null;
  units: UnitSystem;
  runs_dir: string;
  time_limit: number;
  memory_limit: number;
  /** Profil des réglages globaux choisi au dernier lancement ; null : valeurs du projet. */
  run_profile?: string | null;
  files: ExtraFile[];
  blocks: Block[];
}

export interface Settings {
  docker_image: string;
  run_command: string;
  catalog_command: string;
  stop_command: string;
  paraview_command: string;
  aster_version: string;
  language: string;
  configured: boolean;
  recent_projects: string[];
  run_profiles: RunProfile[];
  capture_command: string;
}

/** Limites d'un run (P time_limit, P memory_limit) ; time_limit null : illimité. */
export interface RunProfile {
  name: string;
  time_limit: number | null;
  memory_limit: number;
}

export interface Snapshot {
  project: Project;
  project_dir: string | null;
  settings: Settings;
  paths: { config: string; materials: string; languages: string };
}

export interface BlockInfo {
  id: string;
  command: string;
  concept: string | null;
  error: string | null;
  start_line: number;
  end_line: number;
  issues: Issue[];
}

/** Message du validateur ; `fix` : correction proposée (casse d'un nom de groupe). */
export interface Issue {
  level: "error" | "warning";
  message: string;
  fix?: { kind: "group_case"; from: string; to: string };
}

export interface CatalogCommand {
  name: string;
  fr: string;
  produces: boolean;
  doc: string | null;
  form: boolean;
}

export interface CatalogSummary {
  version: string;
  source: string;
  commands: CatalogCommand[];
}

/** Définition d'une commande ou d'un mot-clé dans le catalogue exporté. */
export interface CataEntity {
  kind?: string;
  statut?: string;
  typ?: string[];
  into?: unknown[];
  defaut?: unknown;
  fr?: string;
  condition?: string;
  max?: number | string;
  keywords?: Record<string, CataEntity>;
}

export interface FileEntry {
  kind: string;
  name: string;
  mode: "D" | "R";
  unit: number;
}

export interface CommResult {
  comm: string;
  export: string;
  blocks: BlockInfo[];
  files: FileEntry[];
  warnings: string[];
  mesh_scale: number;
  unattached: Unattached[];
}

export type RunStatus = "running" | "ok" | "alarm" | "fail" | "stopped" | "interrupted";

export interface AsterMessage {
  level: "F" | "E" | "A";
  id: string;
  text: string;
  comm_line: number | null;
  count: number;
  block_id: string | null;
}

export interface RunInfo {
  id: string;
  status: RunStatus;
  started: string;
  ended: string | null;
  duration: number | null;
  returncode: number | null;
  diagnostic: string | null;
  messages: AsterMessage[];
  command: string;
  warnings: string[];
  note: string;
  profile: string | null;
  time_limit: number;
  memory_limit: number;
  headline?: Headline | null;
  units?: UnitSystem;
}

export interface RunSummary
  extends Pick<RunInfo, "id" | "status" | "started" | "duration" | "note" | "profile" | "time_limit" | "memory_limit"> {
  size: number;
  has_mesh: boolean;
  headline?: Headline | null;
  units?: UnitSystem;
}

/** Valeurs du tableau des runs (maxima sur tous les résultats, plus petite marge). */
export interface Headline {
  depl_max: number | null;
  vmis_max: number | null;
  rf_min: number | null;
}

/** Phrase française (clé de traduction) et ses variables. */
export interface Note {
  template: string;
  vars: Record<string, unknown>;
}

export interface Extreme {
  max: number;
  node: number;
  xyz: number[];
}

export interface Margin {
  zone: string;
  concept: string;
  vmis_max: number | null;
  material?: string;
  model?: string;
  strengths?: { name: string; value: number; rf: number | null }[];
  note?: Note;
}

export interface ResultItem {
  concept: string;
  order: number;
  notes: Note[];
  depl?: Extreme;
  vmis?: Extreme & { source: string };
  margins?: Margin[];
  reactions?: number[];
  applied: number[] | null;
  applied_note: Note | null;
  equilibrium?: number;
}

export interface ResultSummary {
  units: { length: string; stress: string; force: string };
  results: ResultItem[];
  headline?: Headline;
  note?: Note;
  file?: string;
}

export interface Captures {
  state: "pending" | "ok" | "error" | "none" | "disabled";
  views?: string[];
  error?: string;
}

export interface RunFile {
  name: string;
  size: number;
}

export interface MeshGroup {
  name: string;
  entity: "GROUP_MA" | "GROUP_NO";
  dim: number | null;
  count: number;
  measure: number | null;
}

export interface MeshSummary {
  name: string;
  nodes: number;
  cells: Record<string, number>;
  bbox: [number[], number[]];
  groups: MeshGroup[];
  path: string;
  version: string;
}

export interface GroupGeometry {
  primitive: "triangles" | "lines" | "points";
  indices: Uint32Array;
}

export interface ImportResult {
  blocks: Block[];
  warnings: string[];
  units: string[];
  unattached: Unattached[];
  text: string;
}

export interface DirListing {
  path: string;
  parent: string;
  entries: { name: string; dir: boolean }[];
}

async function binary(url: string): Promise<{ data: ArrayBuffer; headers: Headers }> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return { data: await res.arrayBuffer(), headers: res.headers };
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail) detail = JSON.stringify(data.detail);
    } catch {
      /* réponse non JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  state: () => request<Snapshot>("GET", "/api/state"),
  newProject: (dir: string | null) => request<Snapshot>("POST", "/api/project/new", { dir }),
  openProject: (dir: string) => request<Snapshot>("POST", "/api/project/open", { dir }),
  saveProject: (project: Project) => request<{ saved: boolean }>("PUT", "/api/project", project),
  saveAs: (dir: string) => request<Snapshot>("POST", "/api/project/save_as", { dir }),
  setMesh: (path: string) => request<Snapshot>("POST", "/api/project/mesh", { path }),
  preview: (project: Project) => request<CommResult>("POST", "/api/comm", project),
  importComm: (source: { text?: string; path?: string }) =>
    request<ImportResult>("POST", "/api/comm/import", source),
  catalog: () => request<CatalogSummary>("GET", "/api/catalog"),
  catalogCommand: (name: string) => request<CataEntity>("GET", `/api/catalog/command/${encodeURIComponent(name)}`),
  updateCatalog: () => request<{ version: string; commands: number; path: string }>("POST", "/api/catalog/update"),
  materials: () => request<MaterialLibrary>("GET", "/api/materials"),
  createMaterial: (m: Partial<Material>) => request<Material>("POST", "/api/materials", m),
  updateMaterial: (m: Material) => request<Material>("PUT", `/api/materials/${materialPath(m.id)}`, m),
  duplicateMaterial: (id: string) => request<Material>("POST", `/api/materials/${materialPath(id)}/duplicate`),
  deleteMaterial: (id: string) => request<{ deleted: string }>("DELETE", `/api/materials/${materialPath(id)}`),
  importMaterials: (path: string) => request<Material[]>("POST", "/api/materials/import", { path }),
  openMaterialsFolder: () => request<{ dir: string }>("POST", "/api/materials/open-folder"),
  useMaterial: (id: string, units: UnitSystem) =>
    request<{ params: Record<string, unknown>; units: UnitSystem; material: Material }>(
      "POST",
      `/api/materials/${materialPath(id)}/use`,
      { units },
    ),
  projectMaterials: () => request<Record<string, ProjectMaterial>>("GET", "/api/materials/project"),
  forms: () => request<import("./forms").FormCatalog>("GET", "/api/forms"),
  toForm: (text: string) =>
    request<{ ok: boolean; reason?: string; command?: string; concept?: string | null; params?: Record<string, unknown> }>(
      "POST",
      "/api/blocks/to_form",
      { text },
    ),
  toText: (block: Block) => request<{ text: string }>("POST", "/api/blocks/to_text", block),
  renameConcept: (blocks: Block[], index: number, old: string, name: string) =>
    request<{ blocks: Block[]; count: number }>("POST", "/api/blocks/rename_concept", { blocks, index, old, new: name }),
  replaceGroup: (block: Block, old: string, name: string) =>
    request<{ block: Block; count: number }>("POST", "/api/blocks/replace_group", { block, old, new: name }),
  newBlock: (command: string, taken: string[]) =>
    request<Block>("POST", "/api/blocks/new", { command, taken }),
  getSettings: () => request<Settings>("GET", "/api/settings"),
  i18n: () =>
    request<{ language: string; languages: { code: string; name: string }[]; messages: Record<string, string> }>(
      "GET",
      "/api/i18n",
    ),
  putSettings: (s: Settings) => request<Settings>("PUT", "/api/settings", s),

  runs: () => request<RunSummary[]>("GET", "/api/runs"),
  startRun: (profile: string | null) => request<RunInfo>("POST", "/api/runs", { profile }),
  setRunNote: (id: string, note: string) => request<{ note: string }>("PATCH", `/api/runs/${encodeURIComponent(id)}`, { note }),
  deleteRun: (id: string) => request<{ deleted: string }>("DELETE", `/api/runs/${encodeURIComponent(id)}`),
  lightenRun: (id: string) => request<{ freed: number }>("POST", `/api/runs/${encodeURIComponent(id)}/lighten`),
  runFiles: (id: string) => request<RunFile[]>("GET", `/api/runs/${encodeURIComponent(id)}/files`),
  runFileText: async (id: string, name: string): Promise<string> => {
    const res = await fetch(`/api/runs/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `${res.status}`);
    return res.text();
  },
  openRunDir: (id: string) => request<{ path: string }>("POST", `/api/runs/${encodeURIComponent(id)}/open_dir`),
  runSummary: (id: string) =>
    request<{ summary: ResultSummary; captures: Captures }>("GET", `/api/runs/${encodeURIComponent(id)}/summary`),
  makeCaptures: (id: string) => request<Captures>("POST", `/api/runs/${encodeURIComponent(id)}/captures`),
  compareCaptures: (a: string, b: string) =>
    request<Record<string, Captures>>("POST", "/api/runs/compare/captures", { a, b }),
  captureUrl: (id: string, kind: "run" | "cmp", view: string, stamp: number) =>
    `/api/runs/${encodeURIComponent(id)}/captures/${kind}/${view}.png?t=${stamp}`,
  captureSuggestion: (paraview: string) =>
    request<{ command: string }>("GET", `/api/settings/capture_suggestion?paraview=${encodeURIComponent(paraview)}`),
  compareRuns: (a: string, b: string) =>
    request<{ diff: string[] }>("GET", `/api/runs/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  runInfo: (id: string) => request<RunInfo>("GET", `/api/runs/${encodeURIComponent(id)}`),
  stopRun: (id: string) => request<{ stopped: boolean }>("POST", `/api/runs/${encodeURIComponent(id)}/stop`),
  paraview: (id: string) =>
    request<{ command: string }>("POST", `/api/runs/${encodeURIComponent(id)}/paraview`),
  logUrl: (id: string) => `/api/runs/${encodeURIComponent(id)}/log`,

  mesh: () => request<MeshSummary>("GET", "/api/mesh"),
  meshPositions: async () => new Float32Array((await binary("/api/mesh/positions")).data),
  meshSkin: async () => new Uint32Array((await binary("/api/mesh/skin")).data),
  meshEdges: async () => new Uint32Array((await binary("/api/mesh/edges")).data),
  meshGroup: async (entity: string, name: string): Promise<GroupGeometry> => {
    const q = `entity=${encodeURIComponent(entity)}&name=${encodeURIComponent(name)}`;
    const { data, headers } = await binary(`/api/mesh/group?${q}`);
    return {
      primitive: (headers.get("X-Primitive") ?? "triangles") as GroupGeometry["primitive"],
      indices: new Uint32Array(data),
    };
  },

  pick: (mode: "file" | "dir", title: string, filters: string[] = [], start?: string | null) =>
    request<{ path: string | null; fallback: boolean }>("POST", "/api/fs/pick", {
      mode,
      title,
      filters,
      start: start ?? null,
    }),
  listDir: (path: string) => request<DirListing>("GET", `/api/fs/list?path=${encodeURIComponent(path)}`),
};
