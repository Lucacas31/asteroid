import { describe, expect, it } from "vitest";
import { formatValue, formatVector } from "./format";

describe("formatValue", () => {
  it("3 chiffres significatifs, puissance de 10 pour les très petites valeurs", () => {
    expect(formatValue(3.340603, "en")).toBe("3.34");
    expect(formatValue(23.5, "fr")).toBe("23,5");
    expect(formatValue(8.1255e-6, "fr")).toBe("8,13e-6");
    expect(formatValue(null)).toBe("—");
    expect(formatValue(Number.NaN)).toBe("—");
  });

  it("annule le bruit numérique d'une composante de vecteur", () => {
    expect(formatVector([-1000, 1e-10, 0], "en")).toBe("(-1,000 ; 0 ; 0)");
    expect(formatVector(null)).toBe("—");
  });
});
