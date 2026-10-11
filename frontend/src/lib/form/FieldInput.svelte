<script lang="ts">
  // Un champ simple (tout sauf les mots-clés facteurs).
  import type { MeshGroup } from "../api";
  import { isRef, unitLabel, type Field, type Params } from "../forms";
  import Icon from "../Icon.svelte";
  import { app } from "../store.svelte";
  import { t } from "../i18n.svelte";

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

  let value = $derived(owner[field.kw]);
  let unit = $derived(unitLabel(field.unit, app.project.units));
  let missing = $derived(
    field.required && (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)),
  );

  function set(v: unknown) {
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) delete owner[field.kw];
    else owner[field.kw] = v;
    onchange();
  }

  // ------------------------------------------------------------------ nombres

  function parseNumber(text: string): number | null | undefined {
    const t = text.trim().replace(",", ".");
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : undefined; // undefined : saisie invalide
  }

  function formatNumber(v: unknown): string {
    return typeof v === "number" ? String(v) : "";
  }

  function setNumber(text: string, index?: number) {
    const n = parseNumber(text);
    if (n === undefined) return;
    const stored = field.type === "int" && n !== null ? Math.round(n) : n;
    if (index === undefined) {
      set(stored);
    } else {
      const size = field.size ?? 1;
      const arr = Array.isArray(value) ? [...value] : Array(size).fill(null);
      arr[index] = stored;
      set(arr.every((x) => x === null) ? null : arr);
    }
  }

  function invalid(text: string): boolean {
    return parseNumber(text) === undefined;
  }

  // ------------------------------------------------------------------ concepts

  let candidates = $derived(concepts.filter((c) => field.ctypes?.includes(c.type)));
  let others = $derived(concepts.filter((c) => !field.ctypes?.includes(c.type) && c.type === "?"));
  let refs = $derived(
    (Array.isArray(value) ? value : value ? [value] : []).filter(isRef).map((r) => r.$ref),
  );

  function known(name: string): boolean {
    return concepts.some((c) => c.name === name);
  }

  // ------------------------------------------------------------------ groupes

  let groupNames = $derived((Array.isArray(value) ? value : typeof value === "string" ? [value] : []) as string[]);
  let meshGroups = $derived(
    (app.mesh?.groups ?? []).filter(
      (g: MeshGroup) =>
        g.entity === field.entity && (!field.dims || g.dim === null || field.dims.includes(g.dim)),
    ),
  );
  let otherGroups = $derived(
    (app.mesh?.groups ?? []).filter((g) => g.entity === field.entity && !meshGroups.includes(g)),
  );

  function groupExists(name: string): boolean {
    return !app.mesh || app.mesh.groups.some((g) => g.name === name && g.entity === field.entity);
  }

  function highlight(name: string) {
    const g = app.findGroup(name, field.entity);
    if (g) app.highlight = { entity: g.entity, name: g.name };
  }

  function addGroup(name: string) {
    if (!name || groupNames.includes(name)) return;
    set([...groupNames, name]);
    highlight(name);
  }

  let freeGroup = $state("");
</script>

<div class="field" class:missing>
  <label class="kw" for={`${field.kw}-input`} title={field.help ?? ""}>
    <span class="mono">{field.kw}</span>
    {#if field.label}<span class="label">{field.label}</span>{/if}
  </label>

  <div class="control">
    {#if field.type === "float" || field.type === "int"}
      {#if (field.size ?? 1) > 1}
        <div class="vector">
          {#each Array(field.size) as _, i (i)}
            {@const text = formatNumber(Array.isArray(value) ? value[i] : null)}
            <input
              class="num"
              value={text}
              oninput={(e) => setNumber(e.currentTarget.value, i)}
              class:invalid={invalid(text)}
              inputmode="decimal"
              spellcheck="false"
            />
          {/each}
        </div>
      {:else}
        <input
          id={`${field.kw}-input`}
          class="num"
          value={formatNumber(value)}
          oninput={(e) => {
            e.currentTarget.classList.toggle("invalid", invalid(e.currentTarget.value));
            setNumber(e.currentTarget.value);
          }}
          inputmode="decimal"
          spellcheck="false"
          placeholder={field.required ? t("obligatoire") : ""}
        />
      {/if}
      {#if unit}<span class="unit">{unit}</span>{/if}
    {:else if field.type === "text"}
      <input id={`${field.kw}-input`} value={(value as string) ?? ""} oninput={(e) => set(e.currentTarget.value)} />
    {:else if field.type === "enum"}
      <select id={`${field.kw}-input`} value={(value as string) ?? ""} onchange={(e) => set(e.currentTarget.value)}>
        {#if !field.required && !field.default}<option value=""></option>{/if}
        {#each field.into ?? [] as v (v)}<option value={v}>{v}</option>{/each}
      </select>
    {:else if field.type === "multienum"}
      {@const selected = (Array.isArray(value) ? value : value ? [value] : []) as string[]}
      <div class="chips">
        {#each field.into ?? [] as v (v)}
          <button
            class="chip toggle"
            class:on={selected.includes(v)}
            onclick={() => set(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])}
          >
            {v}
          </button>
        {/each}
      </div>
    {:else if field.type === "flag"}
      <label class="check">
        <input type="checkbox" checked={value === "OUI"} onchange={(e) => set(e.currentTarget.checked ? "OUI" : null)} />
        OUI
      </label>
    {:else if field.type === "concept"}
      {#if field.multiple}
        <div class="chips">
          {#each refs as name (name)}
            <span class="chip" class:bad={!known(name)}>
              {name}
              <button class="x" onclick={() => set(refs.filter((r) => r !== name).map((r) => ({ $ref: r })))}>
                <Icon name="close" size={11} />
              </button>
            </span>
          {/each}
          <select
            class="add"
            value=""
            onchange={(e) => {
              const v = e.currentTarget.value;
              if (v && !refs.includes(v)) set([...refs, v].map((r) => ({ $ref: r })));
              e.currentTarget.value = "";
            }}
          >
            <option value="">{t("+ ajouter…")}</option>
            {#each candidates.filter((c) => !refs.includes(c.name)) as c (c.name)}<option value={c.name}>{c.name}</option>{/each}
          </select>
        </div>
      {:else}
        <select
          id={`${field.kw}-input`}
          class="mono"
          class:bad={refs[0] && !known(refs[0])}
          value={refs[0] ?? ""}
          onchange={(e) => set(e.currentTarget.value ? { $ref: e.currentTarget.value } : null)}
        >
          <option value="">{candidates.length ? "" : t("aucun concept compatible plus haut")}</option>
          {#each candidates as c (c.name)}<option value={c.name}>{c.name}</option>{/each}
          {#if others.length}
            <optgroup label={t("Type inconnu")}>
              {#each others as c (c.name)}<option value={c.name}>{c.name}</option>{/each}
            </optgroup>
          {/if}
          {#if refs[0] && !known(refs[0])}<option value={refs[0]}>{t("{name} (non défini plus haut)", { name: refs[0] })}</option>{/if}
        </select>
      {/if}
    {:else if field.type === "groups"}
      <div class="chips">
        {#each groupNames as name (name)}
          <span class="chip group" class:bad={!groupExists(name)} class:lit={app.highlight?.name === name}>
            <button class="name" onclick={() => highlight(name)} title={t("Mettre en surbrillance")}>{name}</button>
            <button class="x" onclick={() => set(groupNames.filter((g) => g !== name))} title={t("Retirer")}>
              <Icon name="close" size={11} />
            </button>
          </span>
        {/each}
        {#if app.mesh}
          <select
            class="add"
            value=""
            onchange={(e) => {
              addGroup(e.currentTarget.value);
              e.currentTarget.value = "";
            }}
          >
            <option value="">{t("+ groupe…")}</option>
            {#each meshGroups.filter((g) => !groupNames.includes(g.name)) as g (g.name)}
              <option value={g.name}>{g.name}</option>
            {/each}
            {#if otherGroups.length}
              <optgroup label={t("Autres dimensions")}>
                {#each otherGroups.filter((g) => !groupNames.includes(g.name)) as g (g.name)}
                  <option value={g.name}>{g.name}</option>
                {/each}
              </optgroup>
            {/if}
          </select>
        {:else}
          <input
            class="add mono"
            placeholder={t("nom du groupe ↵")}
            bind:value={freeGroup}
            onkeydown={(e) => {
              if (e.key === "Enter") {
                addGroup(freeGroup.trim());
                freeGroup = "";
              }
            }}
          />
        {/if}
      </div>
    {/if}
    {#if field.help && field.type !== "float"}<small class="help muted">{field.help}</small>{/if}
  </div>
</div>

<style>
  .field {
    display: grid;
    grid-template-columns: 130px 1fr;
    gap: 8px;
    align-items: start;
    padding: 3px 0;
  }
  .kw {
    display: flex;
    flex-direction: column;
    padding-top: 5px;
    min-width: 0;
  }
  .kw .mono {
    font-weight: 600;
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .label {
    font-size: 11px;
    color: var(--muted);
  }
  .missing .kw .mono {
    color: var(--err);
  }
  .control {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  input.num {
    width: 130px;
    font-family: var(--mono);
    font-size: 12px;
  }
  .vector {
    display: flex;
    gap: 4px;
  }
  .vector input.num {
    width: 80px;
  }
  :global(input.invalid),
  input.invalid {
    border-color: var(--err);
    outline-color: color-mix(in srgb, var(--err) 25%, transparent);
  }
  .unit {
    font-size: 12px;
    color: var(--muted);
    min-width: 40px;
  }
  select {
    max-width: 100%;
  }
  select.bad {
    border-color: var(--err);
  }
  .check {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-top: 4px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 1px 4px 1px 8px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--panel-2);
    font-family: var(--mono);
    font-size: 12px;
  }
  .chip.toggle {
    padding: 2px 9px;
    color: var(--muted);
  }
  .chip.toggle.on {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }
  .chip.group.lit {
    border-color: #ff7a1a;
    background: color-mix(in srgb, #ff7a1a 14%, transparent);
  }
  .chip.bad {
    border-color: var(--err);
    color: var(--err);
  }
  .chip button {
    border: none;
    background: none;
    padding: 1px 2px;
    font: inherit;
    color: inherit;
  }
  .chip .x {
    opacity: 0.6;
  }
  .chip .x:hover {
    opacity: 1;
  }
  select.add,
  input.add {
    font-size: 12px;
    padding: 2px 6px;
    width: auto;
    max-width: 160px;
  }
  .help {
    flex-basis: 100%;
    font-size: 11px;
  }
</style>
