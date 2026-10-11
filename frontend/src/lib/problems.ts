// Erreurs repérées avant le run : syntaxe, validation par le catalogue, champs obligatoires.

import type { Block, BlockInfo, Issue } from "./api";

export interface Problem {
  blockId: string;
  kind: "syntax" | "validation" | "missing";
  message: string;
  fix?: Issue["fix"];
}

/** Erreurs des blocs, dans l'ordre du projet (les avertissements n'en font pas partie). */
export function collectProblems(
  blocks: Block[],
  infos: Map<string, BlockInfo>,
  missing: Map<string, string[]>,
): Problem[] {
  const out: Problem[] = [];
  for (const b of blocks) {
    const info = infos.get(b.id);
    if (info?.error) out.push({ blockId: b.id, kind: "syntax", message: info.error });
    for (const issue of info?.issues ?? []) {
      if (issue.level === "error") out.push({ blockId: b.id, kind: "validation", message: issue.message, fix: issue.fix });
    }
    const keywords = missing.get(b.id);
    if (keywords?.length) out.push({ blockId: b.id, kind: "missing", message: keywords.join(", ") });
  }
  return out;
}
