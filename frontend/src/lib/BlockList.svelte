<script lang="ts">
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  // Commandes courantes, proposées juste après celles qui ont un formulaire.
  const COMMON = [
    "LIRE_MAILLAGE",
    "MODI_MAILLAGE",
    "AFFE_MODELE",
    "DEFI_MATERIAU",
    "AFFE_MATERIAU",
    "AFFE_CARA_ELEM",
    "AFFE_CHAR_MECA",
    "MECA_STATIQUE",
    "MACRO_ELAS_MULT",
    "CALC_CHAMP",
    "IMPR_RESU",
    "TEST_RESU",
    "DEFI_FONCTION",
    "DEFI_LIST_REEL",
    "DEFI_GROUP",
    "CREA_MAILLAGE",
    "POST_RELEVE_T",
    "IMPR_TABLE",
    "STAT_NON_LINE",
  ];

  let adding = $state(false);
  let query = $state("");
  let highlighted = $state(0);
  let dragFrom = $state<number | null>(null);
  let dropAt = $state<number | null>(null);
  let searchEl = $state<HTMLInputElement>();

  $effect(() => {
    if (adding) searchEl?.focus();
  });

  interface Choice {
    name: string;
    fr: string;
    form: boolean;
    known: boolean;
  }

  let matches = $derived.by((): Choice[] => {
    const q = query.trim();
    const upper = q.toUpperCase();
    const all = app.catalog?.commands ?? COMMON.map((name) => ({ name, fr: "", form: false, doc: null, produces: true }));
    const rank = (c: { name: string; form: boolean }) =>
      c.form ? 0 : COMMON.includes(c.name) ? 1 + COMMON.indexOf(c.name) / 100 : 2;
    const list: Choice[] = all
      .filter((c) => !q || c.name.includes(upper) || c.fr.toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => {
        // Le nom qui commence par la saisie passe devant, puis formulaires, courantes, reste.
        const pa = a.name.startsWith(upper) ? 0 : 1;
        const pb = b.name.startsWith(upper) ? 0 : 1;
        return pa - pb || rank(a) - rank(b) || a.name.localeCompare(b.name);
      })
      .map((c) => ({ name: c.name, fr: c.fr, form: c.form, known: true }));
    if (upper && /^[A-Z_][A-Z0-9_]*$/.test(upper) && !list.some((c) => c.name === upper)) {
      list.push({ name: upper, fr: t("absente du catalogue"), form: false, known: false });
    }
    return list;
  });

  function openAdd(e: MouseEvent) {
    e.stopPropagation();
    adding = !adding;
    query = "";
    highlighted = 0;
  }

  function add(command: string) {
    adding = false;
    app.addBlock(command);
  }

  function onAddKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") highlighted = Math.min(highlighted + 1, matches.length - 1);
    else if (e.key === "ArrowUp") highlighted = Math.max(highlighted - 1, 0);
    else if (e.key === "Enter" && matches[highlighted]) add(matches[highlighted].name);
    else if (e.key === "Escape") adding = false;
    else return;
    e.preventDefault();
  }

  function status(id: string): "error" | "alarm" | "ok" {
    const info = app.blockInfo.get(id);
    const msgs = app.blockMessages.get(id) ?? [];
    const issues = info?.issues ?? [];
    if (info?.error || msgs.some((m) => m.level !== "A") || app.blockMissing.has(id)) return "error";
    if (issues.some((i) => i.level === "error")) return "error";
    if (msgs.length || issues.length) return "alarm";
    return "ok";
  }

  function tooltip(id: string): string {
    const info = app.blockInfo.get(id);
    const msgs = app.blockMessages.get(id) ?? [];
    const missing = app.blockMissing.get(id);
    const lines = [
      info?.error,
      missing && t("Manquant : {keywords}", { keywords: missing.join(", ") }),
      ...(info?.issues ?? []).map((i) => i.message),
      ...msgs.map((m) => `<${m.level}> ${m.id} ${m.text.split("\n")[0]}`),
    ];
    return lines.filter(Boolean).join("\n");
  }

  function onDragOver(e: DragEvent, i: number) {
    if (dragFrom === null) return;
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    dropAt = e.clientY < rect.top + rect.height / 2 ? i : i + 1;
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    if (dragFrom !== null && dropAt !== null) app.moveBlock(dragFrom, dropAt);
    dragFrom = dropAt = null;
  }

  function onKey(e: KeyboardEvent, i: number) {
    if (e.altKey && e.key === "ArrowUp" && i > 0) app.moveBlock(i, i - 1);
    else if (e.altKey && e.key === "ArrowDown" && i < app.project.blocks.length - 1) app.moveBlock(i, i + 2);
    else if (e.key === "ArrowUp" && i > 0) app.selectedId = app.project.blocks[i - 1].id;
    else if (e.key === "ArrowDown" && i < app.project.blocks.length - 1) app.selectedId = app.project.blocks[i + 1].id;
    else return;
    e.preventDefault();
  }
</script>

<svelte:window onclick={() => (adding = false)} />

<aside>
  <div class="head">
    <span class="title">{t("Blocs")}</span>
    <div class="add-wrap">
      <button class="ghost small" onclick={() => (app.importOpen = true)} title={t("Coller ou ouvrir un .comm complet")}>
        <Icon name="text" size={14} />{t("Importer")}
      </button>
      <button class="primary small" onclick={openAdd} title={t("Ajouter une commande après le bloc sélectionné")}>
        <Icon name="plus" size={14} />{t("Ajouter")}
      </button>
      {#if adding}
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
        <div class="add-menu" onclick={(e) => e.stopPropagation()}>
          <input
            bind:this={searchEl}
            placeholder={t("Commande Code_Aster…")}
            bind:value={query}
            oninput={() => (highlighted = 0)}
            onkeydown={onAddKey}
            spellcheck="false"
          />
          <div class="list">
            {#each matches as choice, i (choice.name)}
              <button
                class="ghost choice"
                class:hl={i === highlighted}
                onmouseenter={() => (highlighted = i)}
                onclick={() => add(choice.name)}
                title={choice.fr}
              >
                <span class="cmd">
                  {choice.name}
                  {#if choice.form}<span class="tag">{t("formulaire")}</span>{:else if !choice.known}<span class="tag warn">?</span>{/if}
                </span>
                {#if choice.fr}<span class="fr">{choice.fr}</span>{/if}
              </button>
            {:else}
              <div class="muted empty">{t("Nom de commande invalide")}</div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <ol ondrop={onDrop} ondragover={(e) => e.preventDefault()}>
    {#each app.project.blocks as block, i (block.id)}
      {@const info = app.blockInfo.get(block.id)}
      {@const st = status(block.id)}
      <li
        class:selected={app.selectedId === block.id}
        class:drop-before={dropAt === i}
        class:drop-after={dropAt === i + 1 && i === app.project.blocks.length - 1}
        class:dragging={dragFrom === i}
        draggable="true"
        ondragstart={(e) => {
          dragFrom = i;
          e.dataTransfer?.setData("text/plain", block.id);
        }}
        ondragend={() => (dragFrom = dropAt = null)}
        ondragover={(e) => onDragOver(e, i)}
      >
        <button
          class="item"
          onclick={() => (app.selectedId = block.id)}
          onkeydown={(e) => onKey(e, i)}
          title={tooltip(block.id)}
        >
          <span class="grip"><Icon name="grip" size={14} /></span>
          <span class="mode" title={block.mode === "text" ? t("Mode texte") : t("Mode graphique")}>
            <Icon name={block.mode === "text" ? "text" : "form"} size={14} />
          </span>
          <span class="label">
            {#if info?.concept ?? block.concept}
              <span class="concept">{block.mode === "form" ? block.concept : (info?.concept ?? block.concept)}</span>
              <span class="muted">=</span>
            {/if}
            <span class="command">{info?.command || block.command || "…"}</span>
          </span>
          <span class="dot {st}"></span>
        </button>
        <span class="actions">
          <button class="ghost icon" title={t("Dupliquer")} onclick={() => app.duplicateBlock(block.id)}>
            <Icon name="copy" size={14} />
          </button>
          <button class="ghost icon" title={t("Supprimer")} onclick={() => app.removeBlock(block.id)}>
            <Icon name="trash" size={14} />
          </button>
        </span>
      </li>
    {:else}
      <li class="placeholder muted">
        {#if app.project.mesh}
          {t("Aucun bloc. Ajoute une commande avec « Ajouter ».")}
        {:else}
          {t("Commence par choisir un maillage (barre du haut) : les blocs de base seront créés.")}
        {/if}
      </li>
    {/each}
  </ol>
  <div class="foot muted">{t("DEBUT() et FIN() sont ajoutés automatiquement.")}</div>
</aside>

<style>
  aside {
    grid-area: left;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border-right: 1px solid var(--border);
    min-height: 0;
  }
  .head {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }
  .title {
    font-weight: 600;
  }
  .small {
    padding: 3px 8px;
  }
  .add-wrap {
    display: flex;
    gap: 4px;
  }
  .add-menu {
    position: absolute;
    left: 6px;
    right: 6px;
    top: calc(100% + 2px);
    z-index: 40;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow);
    padding: 6px;
  }
  .add-menu input {
    width: 100%;
    font-family: var(--mono);
  }
  .add-menu .list {
    max-height: 420px;
    overflow: auto;
    margin-top: 6px;
    display: flex;
    flex-direction: column;
  }
  .add-menu .list button {
    justify-content: flex-start;
  }
  .choice {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 0 !important;
    padding: 4px 8px;
    white-space: normal;
    text-align: left;
  }
  .choice .cmd {
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 600;
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .choice .fr {
    font-size: 11px;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
  }
  .tag {
    font-family: var(--sans);
    font-size: 10px;
    font-weight: 500;
    padding: 0 5px;
    border-radius: 6px;
    background: var(--accent-soft);
    color: var(--accent);
  }
  .tag.warn {
    background: color-mix(in srgb, var(--warn) 20%, transparent);
    color: var(--warn);
  }
  .add-menu .hl {
    background: var(--accent-soft);
  }
  .empty {
    padding: 6px;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 6px;
    overflow: auto;
    flex: 1;
  }
  li {
    position: relative;
    display: flex;
    align-items: center;
    border-radius: 6px;
    margin-bottom: 2px;
  }
  li.drop-before::before,
  li.drop-after::after {
    content: "";
    position: absolute;
    left: 4px;
    right: 4px;
    height: 2px;
    background: var(--accent);
    border-radius: 2px;
  }
  li.drop-before::before {
    top: -2px;
  }
  li.drop-after::after {
    bottom: -2px;
  }
  li.dragging {
    opacity: 0.4;
  }
  .item {
    flex: 1;
    min-width: 0;
    border: none;
    background: transparent;
    padding: 6px 6px 6px 2px;
    justify-content: flex-start;
    gap: 6px;
  }
  li:hover {
    background: var(--hover);
  }
  li.selected {
    background: var(--accent-soft);
  }
  .grip {
    color: var(--muted);
    opacity: 0.5;
    cursor: grab;
    display: flex;
  }
  .mode {
    color: var(--muted);
    display: flex;
  }
  .label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: left;
    font-family: var(--mono);
    font-size: 12px;
  }
  .concept {
    color: var(--accent);
  }
  .command {
    font-weight: 600;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex: none;
  }
  .dot.ok {
    background: color-mix(in srgb, var(--ok) 60%, transparent);
  }
  .dot.alarm {
    background: var(--warn);
  }
  .dot.error {
    background: var(--err);
  }
  .actions {
    display: none;
    padding-right: 4px;
  }
  li:hover .actions,
  li.selected .actions {
    display: flex;
  }
  .placeholder {
    padding: 14px 10px;
    line-height: 1.5;
  }
  .foot {
    padding: 6px 10px;
    font-size: 11px;
    border-top: 1px solid var(--border);
  }
</style>
