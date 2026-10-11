<script lang="ts">
  // Mot-clé facteur : une ou plusieurs occurrences de _F(...).
  import { unitLabel, type Field, type Params } from "../forms";
  import Icon from "../Icon.svelte";
  import { app } from "../store.svelte";
  import FactorField from "./FactorField.svelte";
  import FieldInput from "./FieldInput.svelte";
  import { i18n, t } from "../i18n.svelte";

  let {
    field,
    owner,
    concepts,
    onchange,
  }: {
    field: Field;
    owner: Params;
    concepts: { name: string; type: string }[];
    onchange: () => void;
  } = $props();

  let single = $derived(field.max === 1);
  let value = $derived(owner[field.kw]);
  let items = $derived((Array.isArray(value) ? value : value ? [value] : []) as Params[]);
  let fields = $derived(field.fields ?? []);

  // Zone d'application : TOUT, GROUP_MA ou GROUP_NO, un seul à la fois.
  let whereFields = $derived(fields.filter((f) => f.kw === "TOUT" || f.type === "groups"));
  let hasWhereChoice = $derived(whereFields.length > 1);
  let otherFields = $derived(hasWhereChoice ? fields.filter((f) => !whereFields.includes(f)) : fields);

  function whereOf(item: Params): string {
    return whereFields.find((f) => f.kw in item)?.kw ?? whereFields.find((f) => f.type === "groups")?.kw ?? "TOUT";
  }

  function setWhere(item: Params, kw: string) {
    for (const f of whereFields) delete item[f.kw];
    if (kw === "TOUT") item.TOUT = "OUI";
    else item[kw] = [];
    onchange();
  }

  function addItem() {
    const item: Params = {};
    if (hasWhereChoice && whereFields.some((f) => f.kw === "TOUT") && !app.mesh?.groups.length) item.TOUT = "OUI";
    for (const f of fields) if (f.default !== undefined) item[f.kw] = f.default;
    if (single) owner[field.kw] = item;
    else owner[field.kw] = [...items, item];
    onchange();
  }

  function removeItem(i: number) {
    if (single) delete owner[field.kw];
    else {
      const next = items.filter((_, j) => j !== i);
      if (next.length) owner[field.kw] = next;
      else delete owner[field.kw];
    }
    onchange();
  }

  // ------------------------------------------------------------------ aide aire / résultante

  function area(item: Params): number | null {
    const names = (Array.isArray(item.GROUP_MA) ? item.GROUP_MA : []) as string[];
    if (!names.length || !app.mesh) return null;
    let total = 0;
    for (const n of names) {
      const g = app.mesh.groups.find((x) => x.name === n && x.entity === "GROUP_MA");
      if (!g || g.measure == null || g.dim !== 2) return null;
      total += g.measure * app.meshScale ** 2;
    }
    return total;
  }

  function fmt(x: number): string {
    return x.toLocaleString(i18n.locale, { maximumSignificantDigits: 4 });
  }

  function resultant(item: Params, s: number): string {
    const force = unitLabel("force", app.project.units);
    if (field.kw === "PRES_REP") {
      const p = typeof item.PRES === "number" ? item.PRES : null;
      return p === null ? "" : `|F| = PRES × S = ${fmt(p * s)} ${force} ${t("(normale aux faces)")}`;
    }
    const comps = ["FX", "FY", "FZ"].map((k) => (typeof item[k] === "number" ? (item[k] as number) : 0));
    if (comps.every((c) => c === 0)) return "";
    return `F = (${comps.map((c) => fmt(c * s)).join(" ; ")}) ${force}`;
  }

  let enabled = $derived(items.length > 0);
</script>

<fieldset class:single>
  <legend>
    {#if !field.required && single}
      <input type="checkbox" checked={enabled} onchange={() => (enabled ? removeItem(0) : addItem())} />
    {/if}
    <span class="mono">{field.kw}</span>
    {#if field.label}<span class="muted">{field.label}</span>{/if}
    {#if !single}<span class="count muted">{items.length}</span>{/if}
    {#if field.required && !items.length}<span class="req">{t("obligatoire")}</span>{/if}
  </legend>
  {#if field.help}<p class="help muted">{field.help}</p>{/if}

  {#each items as item, i (i)}
    <div class="item">
      {#if !single}
        <div class="item-head">
          <span class="muted">{t("_F n°{n}", { n: i + 1 })}</span>
          <button class="ghost icon" title={t("Supprimer cette occurrence")} onclick={() => removeItem(i)}>
            <Icon name="trash" size={13} />
          </button>
        </div>
      {/if}
      {#if hasWhereChoice}
        {@const where = whereOf(item)}
        <div class="where">
          <span class="where-label muted">{t("Zone")}</span>
          <div class="seg">
            {#each whereFields as f (f.kw)}
              <button class:on={where === f.kw} onclick={() => setWhere(item, f.kw)}>{f.kw}</button>
            {/each}
          </div>
        </div>
        {#if where !== "TOUT"}
          {@const wf = whereFields.find((f) => f.kw === where)!}
          <FieldInput field={wf} owner={item} {concepts} {onchange} />
        {/if}
      {/if}
      {#each otherFields as f (f.kw)}
        {#if f.type === "factor"}
          <FactorField field={f} owner={item} {concepts} {onchange} />
        {:else if !f.hidden}
          <FieldInput field={f} owner={item} {concepts} {onchange} />
        {/if}
      {/each}
      {#if field.area}
        {@const s = area(item)}
        {#if s !== null}
          <div class="area">
            <Icon name="cube" size={13} />
            S = {fmt(s)} {unitLabel("length", app.project.units)}²
            {#if resultant(item, s)}<span class="sep">·</span><span>{resultant(item, s)}</span>{/if}
          </div>
        {/if}
      {/if}
    </div>
  {/each}

  {#if !single || (!items.length && field.required)}
    <button class="ghost add" onclick={addItem}><Icon name="plus" size={13} />{single ? t("Ajouter") : t("Ajouter une occurrence")}</button>
  {/if}
</fieldset>

<style>
  fieldset {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 4px 10px 8px;
    margin: 8px 0;
    min-width: 0;
  }
  legend {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 4px;
  }
  legend .mono {
    font-weight: 700;
    font-size: 12px;
  }
  .count {
    font-size: 11px;
    background: var(--panel-2);
    border-radius: 8px;
    padding: 0 6px;
  }
  .req {
    font-size: 11px;
    color: var(--err);
  }
  .help {
    margin: 2px 0 6px;
    font-size: 11px;
  }
  .item {
    padding: 4px 0;
  }
  .item + .item {
    border-top: 1px dashed var(--border);
  }
  .item-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
  }
  .where {
    display: grid;
    grid-template-columns: 130px 1fr;
    gap: 8px;
    align-items: center;
    padding: 3px 0;
  }
  .where-label {
    font-size: 12px;
  }
  .seg {
    display: inline-flex;
    width: fit-content;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .seg button {
    border: none;
    border-radius: 0;
    padding: 2px 10px;
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--muted);
  }
  .seg button + button {
    border-left: 1px solid var(--border);
  }
  .seg .on {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .area {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 6px 0 2px;
    padding: 4px 8px;
    border-radius: 6px;
    background: color-mix(in srgb, #ff7a1a 10%, transparent);
    font-size: 12px;
  }
  .sep {
    color: var(--muted);
  }
  .add {
    margin-top: 4px;
    font-size: 12px;
    color: var(--accent);
  }
</style>
