// Mise en forme des valeurs de résultats (3 chiffres significatifs, puissance de 10 au besoin).

export function formatValue(x: number | null | undefined, locale?: string): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-3 || a >= 1e6)) return x.toExponential(2).replace(".", locale?.startsWith("fr") ? "," : ".");
  return x.toLocaleString(locale, { maximumSignificantDigits: 3 });
}

export function formatVector(v: number[] | null | undefined, locale?: string): string {
  return v ? `(${v.map((x) => formatValue(Math.abs(x) < 1e-9 * Math.max(...v.map(Math.abs)) ? 0 : x, locale)).join(" ; ")})` : "—";
}
