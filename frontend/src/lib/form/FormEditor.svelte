<script lang="ts">
  // Formulaire d'un bloc graphique, construit à partir du schéma de la commande.
  import type { Block } from "../api";
  import { isRef, type Params } from "../forms";
  import { app } from "../store.svelte";
  import FactorField from "./FactorField.svelte";
  import FieldInput from "./FieldInput.svelte";
  import MaterialPicker from "./MaterialPicker.svelte";
  import { t } from "../i18n.svelte";

  let { block }: { block: Block } = $props();

  let schema = $derived(app.forms?.schemas[block.command]);
  let concepts = $derived(app.conceptsFor(block.id));
  let exclusive = $derived(schema?.exclusive ?? []);
  let active = $derived(exclusive.find((k) => k in block.params) ?? exclusive[0]);
  let visible = $derived(
    (schema?.fields ?? []).filter((f) => !f.hidden && (!exclusive.includes(f.kw) || f.kw === active)),
  );
  let produces = $derived(!!app.forms?.concept_types[block.command]);

  function onchange() {
    // Commande réentrante (reuse) : le concept suit le concept modifié.
    const reuse = schema?.reuse;
    if (reuse) {
      const target = block.params[reuse];
      if (isRef(target)) block.concept = target.$ref;
    }
    app.touch();
  }

  function chooseExclusive(kw: string) {
    if (kw === active) return;
    for (const k of exclusive) delete block.params[k];
    const field = schema!.fields.find((f) => f.kw === kw)!;
    const item: Params = {};
    for (const f of field.fields ?? []) if (f.required) item[f.kw] = null;
    block.params[kw] = item;
    app.touch();
  }

  // Nom au début de la saisie : à la validation (Entrée ou sortie du champ), les blocs
  // suivants qui l'utilisaient sont mis à jour.
  let renameFrom: string | null = null;

  function renameConcept(name: string) {
    block.concept = name.trim() || null;
    app.touch();
  }

  async function commitRename() {
    await app.renameConcept(block.id, renameFrom, block.concept);
    renameFrom = block.concept;
  }
</script>

{#if schema}
  <div class="form">
    {#if produces && !schema.reuse}
      <div class="concept-row">
        <label class="mono" for="concept-name">Concept</label>
        <input
          id="concept-name"
          class="mono"
          value={block.concept ?? ""}
          onfocus={() => (renameFrom = block.concept)}
          oninput={(e) => renameConcept(e.currentTarget.value)}
          onchange={commitRename}
          spellcheck="false"
        />
        <span class="muted small">{t("nom à gauche du « = »")}</span>
      </div>
    {:else if schema.reuse}
      <p class="muted small">{t("Modifie")} <span class="mono">{block.concept ?? "?"}</span> {t("en place (reuse).")}</p>
    {/if}

    {#if block.command === "DEFI_MATERIAU"}
      <MaterialPicker {block} />
    {/if}

    {#if exclusive.length}
      <div class="seg">
        {#each exclusive as kw (kw)}
          <button class:on={kw === active} onclick={() => chooseExclusive(kw)}>{kw}</button>
        {/each}
      </div>
    {/if}

    {#each visible as f (f.kw)}
      {#if f.type === "factor"}
        <FactorField field={f} owner={block.params} {concepts} {onchange} />
      {:else}
        <FieldInput field={f} owner={block.params} {concepts} {onchange} />
      {/if}
    {/each}
  </div>
{/if}

<style>
  .form {
    padding: 8px 12px 16px;
    overflow: auto;
    height: 100%;
  }
  .concept-row {
    display: grid;
    grid-template-columns: 130px 160px 1fr;
    gap: 8px;
    align-items: center;
    padding-bottom: 8px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
  }
  .concept-row label {
    font-weight: 600;
    font-size: 12px;
  }
  .concept-row input {
    color: var(--accent);
    font-size: 12.5px;
  }
  .small {
    font-size: 11px;
  }
  p {
    margin: 0 0 8px;
  }
  .seg {
    display: inline-flex;
    margin: 4px 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .seg button {
    border: none;
    border-radius: 0;
    font-family: var(--mono);
    font-size: 12px;
    padding: 3px 12px;
    color: var(--muted);
  }
  .seg button + button {
    border-left: 1px solid var(--border);
  }
  .seg .on {
    background: var(--accent-soft);
    color: var(--accent);
  }
</style>
