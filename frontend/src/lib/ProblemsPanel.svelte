<script lang="ts">
  // Module d'erreurs de la barre du haut : erreurs repérées avant le run, corrections proposées.
  import Icon from "./Icon.svelte";
  import type { Problem } from "./problems";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let launching = $derived(app.problemsOpen === "run");
  // Avant un run, toutes les erreurs ; sinon, rien pendant l'édition d'un bloc.
  let list = $derived(launching ? app.problems : app.shownProblems);
  let open = $derived(app.problemsOpen !== null && (launching || list.length > 0));

  function label(p: Problem): string {
    const block = app.project.blocks.find((b) => b.id === p.blockId);
    if (!block) return "";
    const { command, concept } = app.blockCommand(block);
    return concept ? `${concept} = ${command}` : command || "…";
  }

  function message(p: Problem): string {
    return p.kind === "missing" ? t("Manquant : {keywords}", { keywords: p.message }) : p.message;
  }

  function show(p: Problem) {
    app.selectedId = p.blockId;
    if (!launching) app.problemsOpen = null;
  }

  function toggle(e: MouseEvent) {
    e.stopPropagation();
    app.problemsOpen = app.problemsOpen ? null : "list";
  }
</script>

<svelte:window onclick={() => (app.problemsOpen = null)} />

<div class="wrap">
  {#if list.length}
    <button class="chip" class:active={open} onclick={toggle} title={t("Erreurs repérées par la validation")}>
      <Icon name="alert" size={14} />
      {t("{count} erreur(s)", { count: list.length })}
    </button>
  {/if}
  {#if open}
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="panel" onclick={(e) => e.stopPropagation()}>
      <div class="title">
        {#if !list.length}{t("Erreurs corrigées")}
        {:else if launching}{t("Attention : erreurs repérées avant le lancement")}
        {:else}{t("Erreurs repérées")}{/if}
      </div>
      <ul>
        {#each list as p, i (i)}
          <li>
            <button class="ghost item" onclick={() => show(p)} title={t("Aller au bloc")}>
              <span class="mono block">{label(p)}</span>
              <span class="mono small">{message(p)}</span>
            </button>
            {#if p.fix}
              <button class="small fix" onclick={() => app.fixGroup(p.blockId, p.fix!)}>
                <Icon name="check" size={13} />{t("Corriger en « {name} »", { name: p.fix.to })}
              </button>
            {/if}
          </li>
        {:else}
          <li class="muted none">{t("Plus aucune erreur.")}</li>
        {/each}
      </ul>
      {#if launching}
        <div class="foot">
          <button class="ghost" onclick={() => (app.problemsOpen = null)}>{t("Annuler")}</button>
          <button class="primary" onclick={() => app.startRun(true)}>
            <Icon name="play" filled size={12} />{list.length ? t("Lancer quand même") : t("Lancer")}
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
  }
  .chip {
    gap: 5px;
    color: var(--warn);
    border-color: color-mix(in srgb, var(--warn) 45%, transparent);
    background: color-mix(in srgb, var(--warn) 14%, transparent);
    font-weight: 600;
  }
  .chip:hover,
  .chip.active {
    background: color-mix(in srgb, var(--warn) 24%, transparent) !important;
  }
  .panel {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    z-index: 60;
    width: 460px;
    max-height: 60vh;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid color-mix(in srgb, var(--warn) 45%, var(--border));
    border-radius: 8px;
    box-shadow: var(--shadow);
  }
  .title {
    padding: 8px 12px;
    font-weight: 600;
    color: var(--warn);
    border-bottom: 1px solid var(--border);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 4px;
    overflow: auto;
  }
  li {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 4px;
  }
  .item {
    flex: 1;
    min-width: 0;
    flex-direction: column;
    align-items: flex-start !important;
    gap: 1px !important;
    text-align: left;
    white-space: normal;
    padding: 4px 6px;
  }
  .block {
    font-size: 12px;
    font-weight: 600;
  }
  .small {
    font-size: 11.5px;
  }
  .fix {
    flex: none;
    gap: 4px;
    padding: 3px 8px;
  }
  .none {
    padding: 10px 8px;
  }
  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 8px 12px;
    border-top: 1px solid var(--border);
  }
</style>
