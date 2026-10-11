<script lang="ts">
  import CodeEditor from "./CodeEditor.svelte";
  import { editable } from "./editable";
  import { asterCompletion } from "./completion";
  import FormEditor from "./form/FormEditor.svelte";
  import { docUrl } from "./forms";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let block = $derived(app.selected);
  let info = $derived(block ? app.blockInfo.get(block.id) : undefined);
  let messages = $derived(block ? (app.blockMessages.get(block.id) ?? []) : []);
  let missing = $derived(block ? (app.blockMissing.get(block.id) ?? []) : []);
  let command = $derived(block ? (block.mode === "form" ? block.command : info?.command || block.command) : "");
  let concept = $derived(block ? (block.mode === "form" ? block.concept : info?.concept) : null);
  let schema = $derived(app.forms?.schemas[command]);
  let cataInfo = $derived(command ? app.commandInfo(command) : undefined);
  let docRef = $derived(schema?.doc ?? cataInfo?.doc ?? null);
  let validation = $derived(info?.issues ?? []);

  // Autocomplétion : commandes, mots-clés, valeurs permises, concepts définis plus haut.
  const completion = asterCompletion({
    commands: () => app.catalog?.commands ?? [],
    commandDef: (name) => app.commandDef(name),
    concepts: () => (app.selected ? app.conceptsFor(app.selected.id).map((c) => c.name) : []),
  });

  // Curseur dans "NOM_GROUPE" : surbrillance du groupe dans le viewer.
  function onString(value: string | null) {
    const group = value ? app.findGroup(value) : undefined;
    if (group) app.highlight = { entity: group.entity, name: group.name };
  }

  function onText(text: string) {
    if (!block) return;
    block.text = text;
    app.touch();
  }
</script>

<!-- Focus dans l'éditeur : le module d'erreurs attend la fin de la saisie. -->
<section
  onfocusin={(e) => (app.editingId = editable(e.target) ? (block?.id ?? null) : null)}
  onfocusout={(e) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) app.editingId = null;
  }}
>
  {#if block}
    <div class="head">
      <div class="title mono">
        {#if concept}<span class="concept">{concept}</span>{" = "}{/if}<strong>{command || "…"}</strong>
        {#if docRef}
          <a class="doc" href={docUrl(docRef)} target="_blank" rel="noreferrer" title={t("Documentation {ref}", { ref: docRef })}>
            <Icon name="book" size={13} />{docRef}
          </a>
        {/if}
        {#if cataInfo?.fr}<div class="fr">{cataInfo.fr}</div>{/if}
      </div>
      <div class="modes">
        <button
          class="ghost"
          class:on={block.mode === "form"}
          disabled={!schema}
          title={schema ? t("Passer en formulaire") : command ? t("Pas de formulaire pour {command}", { command }) : t("Pas de formulaire pour ce bloc")}
          onclick={() => block.mode === "text" && app.toggleMode(block)}
        >
          <Icon name="form" size={14} />{t("Graphique")}
        </button>
        <button
          class="ghost"
          class:on={block.mode === "text"}
          title={t("Passer en texte")}
          onclick={() => block.mode === "form" && app.toggleMode(block)}
        >
          <Icon name="text" size={14} />{t("Texte")}
        </button>
      </div>
    </div>
    {#if block.mode === "text" && block.fallback_reason && schema}
      <div class="fallback">
        <Icon name="alert" size={14} />
        <span>{t("Reste en texte : {reason}", { reason: block.fallback_reason })}</span>
      </div>
    {/if}
    <div class="body">
      {#key `${block.id}:${block.mode}:${app.revision}`}
        {#if block.mode === "form"}
          <FormEditor {block} />
        {:else}
          <CodeEditor value={block.text} onchange={onText} onstring={onString} {completion} />
        {/if}
      {/key}
    </div>
    {#if info?.error || messages.length || missing.length || validation.length}
      <div class="issues">
        {#each validation as v, i (i)}
          <div class="issue">
            <span class="badge {v.level === 'error' ? 'F' : 'A'}">{v.level === "error" ? t("erreur") : t("attention")}</span>
            <span class="mono small">{v.message}</span>
            {#if v.fix}
              <button class="fix" onclick={() => app.fixGroup(block.id, v.fix!)}>
                <Icon name="check" size={13} />{t("Corriger en « {name} »", { name: v.fix.to })}
              </button>
            {/if}
          </div>
        {/each}
        {#if missing.length}
          <div class="issue"><span class="badge F">{t("incomplet")}</span><span>{t("Manquant :")} <span class="mono">{missing.join(", ")}</span></span></div>
        {/if}
        {#if info?.error}
          <div class="issue"><span class="badge F">{t("syntaxe")}</span><span>{info.error}</span></div>
        {/if}
        {#each messages as m, i (i)}
          <div class="issue">
            <span class="badge {m.level}">&lt;{m.level}&gt;</span>
            <div>
              <div class="mono id">{m.id}{m.count > 1 ? ` ×${m.count}` : ""}</div>
              <pre>{m.text}</pre>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {:else}
    <div class="empty muted">{t("Sélectionne un bloc pour l'éditer.")}</div>
  {/if}
</section>

<style>
  section {
    grid-area: right;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border-left: 1px solid var(--border);
    min-height: 0;
    min-width: 0;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 10px;
    border-bottom: 1px solid var(--border);
  }
  .title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
    min-width: 0;
  }
  .concept {
    color: var(--accent);
  }
  .doc {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 8px;
    font-family: var(--sans);
    font-size: 11px;
    color: var(--muted);
    text-decoration: none;
  }
  .doc:hover {
    color: var(--accent);
  }
  .fr {
    font-family: var(--sans);
    font-size: 11px;
    color: var(--muted);
    white-space: normal;
    font-weight: normal;
  }
  .small {
    font-size: 11.5px;
  }
  .fallback {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    padding: 6px 10px;
    font-size: 12px;
    color: var(--warn);
    background: color-mix(in srgb, var(--warn) 8%, transparent);
    border-bottom: 1px solid var(--border);
  }
  .modes {
    display: flex;
    gap: 2px;
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 2px;
  }
  .modes button {
    padding: 2px 8px;
    font-size: 12px;
  }
  .modes .on {
    background: var(--panel);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
    opacity: 1;
  }
  .body {
    flex: 1;
    min-height: 0;
  }
  .issues {
    max-height: 40%;
    overflow: auto;
    border-top: 1px solid var(--border);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .issue {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .fix {
    flex: none;
    gap: 4px;
    padding: 2px 8px;
    font-size: 11.5px;
  }
  .issue pre {
    margin: 2px 0 0;
    white-space: pre-wrap;
  }
  .id {
    color: var(--muted);
  }
  .empty {
    padding: 20px;
  }
</style>
