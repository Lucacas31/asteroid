import { describe, expect, it } from "vitest";
import { History, MAX_STEPS, MERGE_DELAY } from "./history";

describe("History", () => {
  it("fusionne les saisies rapprochées en une seule étape", () => {
    const h = new History("a");
    h.record("ab", 0);
    h.record("abc", 100);
    h.record("abcd", 100 + MERGE_DELAY + 1);
    expect(h.undo()).toBe("abc");
    expect(h.undo()).toBe("a");
    expect(h.undo()).toBeNull();
    expect(h.canUndo).toBe(false);
  });

  it("une action franche ouvre toujours une étape, et la saisie suivante aussi", () => {
    const h = new History("a");
    h.record("ab", 0);
    h.record("ab-supprimé", 10, true);
    h.record("ab-supprimé!", 20);
    expect(h.undo()).toBe("ab-supprimé");
    expect(h.undo()).toBe("ab");
    expect(h.undo()).toBe("a");
  });

  it("rétablit, et oublie le rétablissement après une nouvelle modification", () => {
    const h = new History("a");
    h.record("b", 0, true);
    h.record("c", 1, true);
    expect(h.undo()).toBe("b");
    expect(h.redo()).toBe("c");
    expect(h.undo()).toBe("b");
    h.record("d", 5000);
    expect(h.canRedo).toBe(false);
    expect(h.redo()).toBeNull();
  });

  it("annuler enregistre d'abord un état courant non enregistré", () => {
    const h = new History("a");
    h.record("b", 0);
    expect(h.undo("b+")).toBe("b");
    expect(h.redo()).toBe("b+");
  });

  it("amend rattache la suite à l'étape en cours", () => {
    const h = new History("mat");
    h.record("pla", 0);
    h.amend("pla+références");
    expect(h.undo()).toBe("mat");
    expect(h.redo()).toBe("pla+références");
  });

  it("ignore un état identique et borne la taille", () => {
    const h = new History("0");
    expect(h.record("0", 0)).toBe(false);
    expect(h.canUndo).toBe(false);
    for (let i = 1; i <= MAX_STEPS + 10; i++) h.record(String(i), i, true);
    let n = 0;
    while (h.undo() !== null) n++;
    expect(n).toBe(MAX_STEPS);
  });

  it("reset vide l'historique", () => {
    const h = new History("a");
    h.record("b", 0, true);
    h.reset("z");
    expect(h.canUndo).toBe(false);
    expect(h.undo()).toBeNull();
  });
});
