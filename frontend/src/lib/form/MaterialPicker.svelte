<script lang="ts">
  // En tête du formulaire DEFI_MATERIAU : remplissage depuis la bibliothèque.
  import { onMount } from "svelte";
  import { api, type Block, type ProjectMaterial } from "../api";
  import Icon from "../Icon.svelte";
  import { app } from "../store.svelte";
  import { i18n, t } from "../i18n.svelte";

  let { block }: { block: Block } = $props();

  let choice = $state("");
  let copies = $state<Record<string, ProjectMaterial>>({});

  let origin = $derived((block.meta?.material as string | undefined) ?? null);
  let copy = $derived(origin ? copies[origin] : undefined);
  let stale = $derived(!!copy && copy.units !== app.project.units);

  async function refresh() {
    if (!app.library.length) await app.loadLibrary();
    copies = app.projectDir ? await api.projectMaterials().catch(() => ({})) : {};
  }

  onMount(refresh);

  async function apply(id: string) {
    if (!id) return;
    await app.applyMaterial(block, id);
    choice = "";
    await refresh();
  }
</script>

<div class="picker">
  <div class="row">
    <Icon name="book" size={14} />
    <select bind:value={choice} onchange={() => apply(choice)}>
      <option value="">{t("Remplir depuis la bibliothèque…")}</option>
      {#each app.library as m (m.id)}
        <option value={m.id}>{m.name} ({m.model})</option>
      {/each}
    </select>
    <button class="ghost small" onclick={() => (app.materialsOpen = true)}>{t("Gérer…")}</button>
  </div>
  {#if origin}
    <div class="origin muted">
      {t("Issu de « {name} »", { name: copy?.material.name ?? origin })}
      {#if copy}
        — {t("copie figée dans materials.json du projet, convertie en {units} le {date}", {
          units: copy.units,
          date: new Date(copy.copied).toLocaleString(i18n.locale),
        })}
        {#if copy.material.source}<br />{t("Source : {source}", { source: copy.material.source })}{/if}
      {/if}
    </div>
    {#if stale}
      <div class="stale">
        <Icon name="alert" size={14} />
        <span>{t("Copie convertie en {units}, le projet est maintenant en {project}.", { units: copy?.units, project: app.project.units })}</span>
        <button class="small" onclick={() => apply(origin!)}>{t("Reconvertir")}</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px;
    margin-bottom: 8px;
    border: 1px dashed var(--border);
    border-radius: 8px;
    background: var(--panel-2);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .row select {
    flex: 1;
  }
  .small {
    font-size: 12px;
    padding: 2px 8px;
  }
  .origin {
    font-size: 11.5px;
    line-height: 1.45;
  }
  .stale {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--warn);
  }
</style>
