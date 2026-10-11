// Autocomplétion des blocs texte à partir du catalogue Code_Aster.

import type { Completion, CompletionContext, CompletionResult, CompletionSource } from "@codemirror/autocomplete";
import type { CataEntity, CatalogCommand } from "./api";
import { t } from "./i18n.svelte";

export interface CompletionData {
  commands: () => CatalogCommand[];
  commandDef: (name: string) => Promise<CataEntity | null>;
  concepts: () => string[];
}

interface Level {
  callee: string; // nom avant la parenthèse ("" pour un tuple)
  keyword: string | null; // mot-clé auquel la parenthèse est affectée (KW=(…) ou KW=_F(…))
}

/** Parenthèses ouvertes (non refermées) avant `pos`, de la plus extérieure à la plus intérieure. */
export function openLevels(text: string): Level[] {
  const stack: number[] = [];
  let quote: string | null = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === "\\") i++;
      else if (c === quote) quote = null;
      continue;
    }
    if (c === "#") {
      const nl = text.indexOf("\n", i);
      if (nl < 0) break;
      i = nl;
    } else if (c === '"' || c === "'") quote = c;
    else if (c === "(") stack.push(i);
    else if (c === ")") stack.pop();
  }
  return stack.map((at) => {
    const before = text.slice(0, at);
    const callee = /([A-Za-z_]\w*)\s*$/.exec(before)?.[1] ?? "";
    const head = callee ? before.slice(0, before.length - callee.length) : before;
    const keyword = /([A-Za-z_]\w*)\s*=\s*$/.exec(head)?.[1] ?? null;
    return { callee, keyword };
  });
}

/** Mots-clés d'un niveau, blocs conditionnels aplatis (toutes les variantes). */
function keywordsOf(entity: CataEntity): Map<string, CataEntity> {
  const out = new Map<string, CataEntity>();
  const visit = (e: CataEntity) => {
    for (const [kw, sub] of Object.entries(e.keywords ?? {})) {
      if (sub.kind === "bloc") visit(sub);
      else if (!out.has(kw)) out.set(kw, sub);
    }
  };
  visit(entity);
  return out;
}

function describe(sub: CataEntity): string {
  const parts = [];
  if (sub.statut === "o") parts.push(t("obligatoire"));
  if (sub.kind === "fact") parts.push(t("facteur _F(…)"));
  else if (sub.typ?.length) parts.push(sub.typ.join(" | "));
  if (sub.defaut !== undefined) parts.push(t("défaut {value}", { value: JSON.stringify(sub.defaut) }));
  return parts.join(" · ");
}

const SIMPLE = new Set(["R", "I", "TXM", "C", "grma", "grno", "no", "ma", "UnitDefault", "UnitMed", "not_checked"]);

export function asterCompletion(data: CompletionData): CompletionSource {
  return async (ctx: CompletionContext): Promise<CompletionResult | null> => {
    const before = ctx.state.doc.sliceString(0, ctx.pos);
    const levels = openLevels(before);
    const word = ctx.matchBefore(/[A-Za-z_]\w*/);
    const inString = /(["'])([^"'\n]*)$/.exec(before.slice(before.lastIndexOf("\n") + 1));

    // Hors de toute parenthèse : nom de commande.
    if (!levels.length) {
      if (!word && !ctx.explicit) return null;
      const options: Completion[] = data.commands().map((c) => ({
        label: c.name,
        type: "function",
        detail: c.form ? t("formulaire") : undefined,
        info: c.fr,
        apply: `${c.name}(`,
        boost: c.form ? 10 : 0,
      }));
      return { from: word?.from ?? ctx.pos, options, validFor: /^\w*$/ };
    }

    // Chemin : commande, puis mots-clés facteurs jusqu'au niveau du curseur.
    const command = levels[0].callee;
    const def = await data.commandDef(command);
    if (!def) return null;
    let entity: CataEntity = def;
    for (const level of levels.slice(1)) {
      if (level.callee !== "_F") continue; // parenthèse de tuple : même niveau
      const owner = [...levels].slice(0, levels.indexOf(level) + 1).reverse().find((l) => l.keyword)?.keyword;
      const sub: CataEntity | undefined = owner ? keywordsOf(entity).get(owner) : undefined;
      if (!sub || sub.kind !== "fact") return null;
      entity = sub;
    }
    const keywords = keywordsOf(entity);
    const innermost = levels[levels.length - 1];

    // Dans une chaîne : valeurs permises du mot-clé.
    if (inString) {
      const kw = /([A-Za-z_]\w*)\s*=\s*\(?\s*(?:["'][^"']*["']\s*,\s*)*["'][^"'\n]*$/.exec(before)?.[1];
      const into = kw ? keywords.get(kw)?.into : undefined;
      if (!into?.length) return null;
      const from = ctx.pos - inString[2].length;
      const quote = inString[1];
      const closed = ctx.state.doc.sliceString(ctx.pos, ctx.pos + 1) === quote;
      return {
        from,
        options: into.map((v) => ({ label: String(v), type: "enum", apply: closed ? String(v) : `${v}${quote}` })),
        validFor: /^[^"']*$/,
      };
    }

    // Juste après « KW= » : concepts définis plus haut si le mot-clé attend un concept.
    const assigned = /([A-Za-z_]\w*)\s*=\s*\(?\s*([A-Za-z_]\w*)?$/.exec(before);
    if (assigned && innermost.callee !== "" && keywords.has(assigned[1])) {
      const sub = keywords.get(assigned[1])!;
      const wantsConcept = (sub.typ ?? []).some((t) => !SIMPLE.has(t));
      if (sub.kind === "fact") {
        return { from: word?.from ?? ctx.pos, options: [{ label: "_F(", type: "keyword" }] };
      }
      if (wantsConcept) {
        const from = word?.from ?? ctx.pos;
        return {
          from,
          options: data.concepts().map((c) => ({ label: c, type: "variable", detail: sub.typ?.join(" | ") })),
          validFor: /^\w*$/,
        };
      }
      return null;
    }

    // Position de mot-clé : après « ( » ou « , ».
    const tail = before.slice(0, word?.from ?? ctx.pos);
    if (!/[(,]\s*$/.test(tail) || (innermost.callee === "" && levels.length > 1)) return null;
    if (!word && !ctx.explicit) return null;
    const options: Completion[] = [...keywords].map(([kw, sub]) => ({
      label: kw,
      type: sub.kind === "fact" ? "class" : "property",
      detail: describe(sub),
      info: sub.fr,
      apply: sub.kind === "fact" ? `${kw}=_F(` : `${kw}=`,
      boost: sub.statut === "o" ? 5 : 0,
    }));
    return { from: word?.from ?? ctx.pos, options, validFor: /^\w*$/ };
  };
}
