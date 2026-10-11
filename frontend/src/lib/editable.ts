/** Champ de saisie (texte, nombre, éditeur de code) : il gère lui-même Ctrl+Z et compte comme « en édition ». */
export function editable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.closest("textarea, select, .cm-editor")) return true;
  return target instanceof HTMLInputElement && !["checkbox", "radio", "button"].includes(target.type);
}
