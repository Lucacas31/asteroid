// Schémas des formulaires (servis par /api/forms) et outils associés.

import type { Block, UnitSystem } from "./api";

export interface Field {
  kw: string;
  type: "concept" | "groups" | "flag" | "enum" | "multienum" | "float" | "int" | "text" | "factor";
  required?: boolean;
  label?: string;
  help?: string;
  hidden?: boolean;
  default?: unknown;
  // concept
  ctypes?: string[];
  multiple?: boolean;
  // groups
  entity?: "GROUP_MA" | "GROUP_NO";
  dims?: number[] | null;
  // enum
  into?: string[];
  // nombres
  unit?: string | null;
  size?: number;
  // factor
  fields?: Field[];
  max?: number | null;
  area?: boolean;
  fill_all?: string;
}

export interface Schema {
  doc: string;
  fields: Field[];
  defaults: Record<string, unknown>;
  reuse?: string;
  exclusive?: string[];
}

export interface FormCatalog {
  schemas: Record<string, Schema>;
  concept_types: Record<string, string>;
}

export type Params = Record<string, unknown>;
export interface Ref {
  $ref: string;
}

export function isRef(v: unknown): v is Ref {
  return typeof v === "object" && v !== null && "$ref" in v;
}

const UNITS: Record<UnitSystem, Record<string, string>> = {
  "mm-N-MPa": {
    stress: "MPa",
    pressure: "MPa",
    length: "mm",
    force: "N",
    lineic: "N/mm",
    density: "t/mm³",
    accel: "mm/s²",
    expansion: "1/°C",
    angle: "°",
    angle_rad: "rad",
  },
  "m-N-Pa": {
    stress: "Pa",
    pressure: "Pa",
    length: "m",
    force: "N",
    lineic: "N/m",
    density: "kg/m³",
    accel: "m/s²",
    expansion: "1/°C",
    angle: "°",
    angle_rad: "rad",
  },
};

export function unitLabel(unit: string | null | undefined, system: UnitSystem): string {
  return unit ? (UNITS[system][unit] ?? "") : "";
}

export function docUrl(ref: string): string {
  return `https://code-aster.org/doc/default/fr/man_u/u4/${ref.toLowerCase()}.pdf`;
}

/** Concepts définis avant le bloc `index`, avec leur type (le premier type gagne : reuse). */
export function conceptsBefore(
  blocks: Block[],
  index: number,
  info: (b: Block) => { command: string; concept: string | null },
  types: Record<string, string>,
): { name: string; type: string }[] {
  const seen = new Map<string, string>();
  for (const b of blocks.slice(0, index)) {
    const { command, concept } = info(b);
    if (concept && !seen.has(concept)) seen.set(concept, types[command] ?? "?");
  }
  return [...seen].map(([name, type]) => ({ name, type }));
}

/** Liste des champs obligatoires manquants (chemins lisibles). */
export function missingRequired(fields: Field[], params: Params, path = ""): string[] {
  const out: string[] = [];
  for (const f of fields) {
    if (f.hidden) continue;
    const value = params[f.kw];
    const name = path + f.kw;
    const empty = value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
    if (f.type === "factor") {
      if (empty) {
        if (f.required) out.push(name);
        continue;
      }
      const items = (Array.isArray(value) ? value : [value]) as Params[];
      items.forEach((item) => out.push(...missingRequired(f.fields ?? [], item, `${name}/`)));
    } else if (f.required && empty) {
      out.push(name);
    } else if (f.size && Array.isArray(value) && f.required && value.some((v) => v === null || v === undefined)) {
      out.push(name);
    }
  }
  return out;
}

/** Remplit les champs concept vides avec le dernier concept compatible défini plus haut. */
export function autofill(fields: Field[], params: Params, available: { name: string; type: string }[]) {
  const last = (ctypes: string[] = []) => [...available].reverse().find((c) => ctypes.includes(c.type))?.name;
  for (const f of fields) {
    const value = params[f.kw];
    if (f.type === "concept" && !f.multiple && (value === undefined || value === null) && (f.required || f.kw in params)) {
      const name = last(f.ctypes);
      if (name) params[f.kw] = { $ref: name };
    } else if (f.type === "factor" && value) {
      if (f.fill_all && Array.isArray(value) && value.length === 1) {
        const sub = f.fields?.find((s) => s.kw === f.fill_all);
        const all = available.filter((c) => sub?.ctypes?.includes(c.type));
        if (sub && all.length && (value[0] as Params)[sub.kw] == null) {
          params[f.kw] = all.map((c) => ({ ...(value[0] as Params), [sub.kw]: { $ref: c.name } }));
          continue;
        }
      }
      const items = (Array.isArray(value) ? value : [value]) as Params[];
      items.forEach((item) => autofill(f.fields ?? [], item, available));
    }
  }
}
