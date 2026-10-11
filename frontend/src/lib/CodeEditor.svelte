<script lang="ts">
  import { onMount } from "svelte";
  import { EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection } from "@codemirror/view";
  import { EditorState, type Extension } from "@codemirror/state";
  import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
  import { python } from "@codemirror/lang-python";
  import {
    bracketMatching,
    defaultHighlightStyle,
    indentOnInput,
    syntaxHighlighting,
  } from "@codemirror/language";
  import {
    autocompletion,
    closeBrackets,
    closeBracketsKeymap,
    completionKeymap,
    type CompletionSource,
  } from "@codemirror/autocomplete";

  let {
    value,
    onchange,
    readonly = false,
    language = "python",
    highlightLines = null,
    onstring,
    onlineclick,
    completion,
  }: {
    value: string;
    onchange?: (value: string) => void;
    readonly?: boolean;
    language?: "python" | "plain";
    highlightLines?: [number, number] | null;
    /** Contenu de la chaîne littérale sous le curseur, ou null. */
    onstring?: (value: string | null) => void;
    /** Numéro de ligne (1-indexé) cliquée. */
    onlineclick?: (line: number) => void;
    /** Source d'autocomplétion (catalogue Code_Aster). */
    completion?: CompletionSource;
  } = $props();

  function stringAtCursor(state: EditorState): string | null {
    const pos = state.selection.main.head;
    const line = state.doc.lineAt(pos);
    const col = pos - line.from;
    for (const m of line.text.matchAll(/"([^"\\]*)"|'([^'\\]*)'/g)) {
      const start = m.index ?? 0;
      if (col > start && col < start + m[0].length) return m[1] ?? m[2] ?? null;
    }
    return null;
  }

  let host: HTMLDivElement;
  let view: EditorView | undefined;

  const theme = EditorView.theme({
    "&": { height: "100%", fontSize: "12.5px", backgroundColor: "var(--code-bg)", color: "var(--text)" },
    ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.55" },
    ".cm-gutters": { backgroundColor: "var(--code-bg)", color: "var(--muted)", border: "none" },
    ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--accent) 6%, transparent)" },
    ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--text)" },
    "&.cm-focused": { outline: "none" },
    ".cm-cursor": { borderLeftColor: "var(--text)" },
    ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
      backgroundColor: "color-mix(in srgb, var(--accent) 25%, transparent) !important",
    },
  });

  onMount(() => {
    const extensions: Extension[] = [
      lineNumbers(),
      drawSelection(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      bracketMatching(),
      theme,
      EditorView.lineWrapping,
    ];
    if (language === "python") extensions.push(python());
    if (onlineclick) {
      extensions.push(
        EditorView.domEventHandlers({
          click: (event, v) => {
            const pos = v.posAtCoords({ x: event.clientX, y: event.clientY });
            if (pos !== null) onlineclick(v.state.doc.lineAt(pos).number);
            return false;
          },
        }),
      );
    }
    if (readonly) {
      extensions.push(EditorState.readOnly.of(true), EditorView.editable.of(false));
    } else {
      extensions.push(
        history(),
        highlightActiveLine(),
        indentOnInput(),
        closeBrackets(),
        ...(completion ? [autocompletion({ override: [completion], activateOnTyping: true })] : []),
        keymap.of([...closeBracketsKeymap, ...completionKeymap, ...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) onchange?.(u.state.doc.toString());
          if (u.selectionSet && onstring) onstring(stringAtCursor(u.state));
        }),
      );
    }
    view = new EditorView({ parent: host, state: EditorState.create({ doc: value, extensions }) });
    return () => view?.destroy();
  });

  // Mise à jour quand la valeur change de l'extérieur (aperçu, changement de bloc).
  $effect(() => {
    const next = value;
    if (view && view.state.doc.toString() !== next) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next } });
    }
  });

  // Défile jusqu'aux lignes demandées (bloc sélectionné dans l'aperçu du .comm).
  $effect(() => {
    const range = highlightLines;
    if (!view || !range) return;
    const doc = view.state.doc;
    if (range[0] < 1 || range[0] > doc.lines) return;
    const from = doc.line(range[0]).from;
    const to = doc.line(Math.min(range[1], doc.lines)).to;
    // Pas de défilement si le bloc est déjà visible (clic dans l'aperçu).
    const rect = view.scrollDOM.getBoundingClientRect();
    const top = view.coordsAtPos(from);
    const visible = top !== null && top.top >= rect.top && top.bottom <= rect.bottom;
    view.dispatch({
      selection: { anchor: from, head: to },
      effects: visible ? [] : EditorView.scrollIntoView(from, { y: "center" }),
    });
  });

  export function focus() {
    view?.focus();
  }
</script>

<div class="editor" bind:this={host}></div>

<style>
  .editor {
    height: 100%;
    overflow: hidden;
  }
  .editor :global(.cm-editor) {
    height: 100%;
  }
</style>
