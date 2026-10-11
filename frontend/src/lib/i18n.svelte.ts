// Traductions : la phrase française sert de clé, `t("Fichier introuvable : {path}", { path })`.
// Les fichiers de langue (langues/<code>.json) sont servis par le backend ; une phrase
// absente reste en français. Les mots-clés Code_Aster ne passent jamais par t().

import { api } from "./api";

export interface Language {
  code: string;
  name: string;
}

const current = $state({ language: "fr", languages: [] as Language[], messages: {} as Record<string, string> });

export const i18n = {
  get language() {
    return current.language;
  },
  get languages() {
    return current.languages;
  },
  /** Locale des nombres et dates. */
  get locale() {
    return current.language === "fr" ? "fr-FR" : current.language;
  },
  async load() {
    const res = await api.i18n();
    current.language = res.language;
    current.languages = res.languages;
    current.messages = res.messages;
    document.documentElement.lang = res.language;
  },
};

/** Marque une phrase traduite plus tard, à l'affichage (convention gettext). */
export const N_ = (text: string) => text;

export function t(text: string, vars?: Record<string, unknown>): string {
  let out = current.messages[text] || text;
  if (vars) for (const [name, value] of Object.entries(vars)) out = out.replaceAll(`{${name}}`, String(value));
  return out;
}
