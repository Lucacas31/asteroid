// Historique annuler / rétablir du projet, par instantanés JSON.
//
// Les modifications rapprochées (saisie dans un champ) forment une seule étape ;
// une action franche (suppression, import, déplacement…) en ouvre toujours une.

export const MERGE_DELAY = 1000;
export const MAX_STEPS = 200;

export class History {
  #undo: string[] = [];
  #redo: string[] = [];
  #current: string;
  #last = -Infinity;

  constructor(initial: string) {
    this.#current = initial;
  }

  get canUndo(): boolean {
    return this.#undo.length > 0;
  }

  get canRedo(): boolean {
    return this.#redo.length > 0;
  }

  /** Repart de `state`, sans historique (projet ouvert ou créé). */
  reset(state: string) {
    this.#undo = [];
    this.#redo = [];
    this.#current = state;
    this.#last = -Infinity;
  }

  /** Enregistre l'état après une modification. `step` : étape distincte, jamais fusionnée. */
  record(state: string, now: number, step = false): boolean {
    if (state === this.#current) return false;
    if (step || now - this.#last > MERGE_DELAY || !this.#undo.length) {
      this.#undo.push(this.#current);
      if (this.#undo.length > MAX_STEPS) this.#undo.shift();
    }
    this.#current = state;
    this.#redo = [];
    // Après une action franche, la saisie suivante ouvre une nouvelle étape.
    this.#last = step ? -Infinity : now;
    return true;
  }

  /** Rattache `state` à l'étape en cours (suite automatique d'une saisie, ex. renommage propagé). */
  amend(state: string): boolean {
    if (state === this.#current) return false;
    if (!this.#undo.length) this.#undo.push(this.#current);
    this.#current = state;
    this.#redo = [];
    return true;
  }

  /** État précédent, ou null. `state` : état courant, s'il a changé sans être enregistré. */
  undo(state = this.#current): string | null {
    this.record(state, Infinity, true);
    const previous = this.#undo.pop();
    if (previous === undefined) return null;
    this.#redo.push(this.#current);
    return this.#moveTo(previous);
  }

  redo(state = this.#current): string | null {
    if (state !== this.#current) return null; // modifié depuis l'annulation : plus rien à rétablir
    const next = this.#redo.pop();
    if (next === undefined) return null;
    this.#undo.push(this.#current);
    return this.#moveTo(next);
  }

  #moveTo(state: string): string {
    this.#current = state;
    this.#last = -Infinity;
    return state;
  }
}
