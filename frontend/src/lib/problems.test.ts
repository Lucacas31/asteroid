import { describe, expect, it } from "vitest";
import type { Block, BlockInfo } from "./api";
import { collectProblems } from "./problems";

function block(id: string): Block {
  return { id, command: "", concept: null, mode: "text", params: {}, text: "", fallback_reason: null, meta: {} };
}

function info(id: string, extra: Partial<BlockInfo>): BlockInfo {
  return { id, command: "", concept: null, error: null, start_line: 0, end_line: 0, issues: [], ...extra };
}

describe("collectProblems", () => {
  it("garde les erreurs dans l'ordre des blocs, sans les avertissements", () => {
    const fix = { kind: "group_case" as const, from: "charge", to: "Charge" };
    const infos = new Map([
      ["b", info("b", { issues: [
        { level: "warning", message: "avertissement" },
        { level: "error", message: "groupe absent", fix },
      ] })],
      ["a", info("a", { error: "erreur de syntaxe" })],
    ]);
    const missing = new Map([["c", ["MODELE", "CHAM_MATER"]]]);
    const problems = collectProblems([block("a"), block("b"), block("c")], infos, missing);
    expect(problems).toEqual([
      { blockId: "a", kind: "syntax", message: "erreur de syntaxe" },
      { blockId: "b", kind: "validation", message: "groupe absent", fix },
      { blockId: "c", kind: "missing", message: "MODELE, CHAM_MATER" },
    ]);
  });

  it("ignore les blocs supprimés depuis la dernière validation", () => {
    const infos = new Map([["old", info("old", { error: "x" })]]);
    expect(collectProblems([block("a")], infos, new Map())).toEqual([]);
  });
});
