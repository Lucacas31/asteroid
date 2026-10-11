<script lang="ts">
  // Bibliothèque de matériaux, commune à tous les projets. Stockage en SI ; saisie en
  // unités lisibles (GPa, MPa, kg/m³), converties à l'enregistrement.
  import { onMount } from "svelte";
  import { api, type Material, type MaterialModel } from "./api";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { N_, t } from "./i18n.svelte";

  const MODELS: Record<MaterialModel, { label: string; keys: string[] }> = {
    ELAS: { label: N_("Isotrope"), keys: ["E", "NU", "ALPHA"] },
    ELAS_ISTR: { label: N_("Isotrope transverse"), keys: ["E_L", "E_N", "NU_LT", "NU_LN", "G_LN"] },
    ELAS_ORTH: {
      label: N_("Orthotrope"),
      keys: ["E_L", "E_T", "E_N", "NU_LT", "NU_LN", "NU_TN", "G_LT", "G_LN", "G_TN"],
    },
  };

  // Unité d'affichage par constante : [libellé, facteur SI → affichage].
  function displayUnit(key: string): [string, number] {
    if (key.startsWith("E") || key.startsWith("G_")) return ["GPa", 1e-9];
    if (key === "ALPHA") return ["1/K", 1];
    return ["", 1];
  }

  let selectedId = $state<string | null>(null);
  let draft = $state<Material | null>(null);
  let dirty = $state(false);

  onMount(async () => {
    await app.loadLibrary();
    select(app.library[0]?.id ?? null);
  });

  function select(id: string | null) {
    if (dirty && !confirm(t("Modifications non enregistrées. Continuer ?"))) return;
    selectedId = id;
    const m = app.library.find((x) => x.id === id);
    draft = m ? structuredClone($state.snapshot(m)) as Material : null;
    dirty = false;
  }

  function fmt(x: number | null | undefined, factor: number): string {
    return x === null || x === undefined ? "" : String(Number((x * factor).toPrecision(10)));
  }

  function parse(text: string, factor: number): number | null | undefined {
    const t = text.trim().replace(",", ".");
    if (!t) return null;
    const n = Number(t);
    // 2,3 GPa / 1e-9 = 2299999999.9999995 : arrondi à 12 chiffres significatifs.
    return Number.isFinite(n) ? Number((n / factor).toPrecision(12)) : undefined;
  }

  function setConstant(key: string, text: string) {
    const [, factor] = displayUnit(key);
    const v = parse(text, factor);
    if (v === undefined || !draft) return;
    if (v === null) delete draft.constants[key];
    else draft.constants[key] = v;
    dirty = true;
  }

  function setModel(model: MaterialModel) {
    if (!draft) return;
    draft.model = model;
    dirty = true;
  }

  async function save() {
    if (!draft) return;
    try {
      // Les constantes d'un autre modèle ne sont pas gardées.
      const keys = MODELS[draft.model].keys;
      draft.constants = Object.fromEntries(Object.entries(draft.constants).filter(([k]) => keys.includes(k)));
      const saved = await api.updateMaterial($state.snapshot(draft) as Material);
      await app.loadLibrary();
      dirty = false;
      select(saved.id);
      app.info(t("« {name} » enregistré", { name: saved.name }));
    } catch (e) {
      app.error(e);
    }
  }

  async function create() {
    if (dirty && !confirm(t("Modifications non enregistrées. Continuer ?"))) return;
    dirty = false;
    try {
      const m = await api.createMaterial({ name: t("Nouveau matériau"), model: "ELAS", constants: {}, strengths: [] });
      await app.loadLibrary();
      select(m.id);
    } catch (e) {
      app.error(e);
    }
  }

  async function duplicate() {
    if (!selectedId) return;
    try {
      const m = await api.duplicateMaterial(selectedId);
      await app.loadLibrary();
      dirty = false;
      select(m.id);
    } catch (e) {
      app.error(e);
    }
  }

  async function remove() {
    if (!draft || !confirm(t("Supprimer « {name} » de la bibliothèque ? Les projets gardent leur copie.", { name: draft.name }))) return;
    try {
      await api.deleteMaterial(draft.id);
      await app.loadLibrary();
      dirty = false;
      select(app.library[0]?.id ?? null);
    } catch (e) {
      app.error(e);
    }
  }

  async function importFile() {
    const path = await app.pick("file", t("Importer des matériaux"), [`${t("Matériaux JSON")} | *.json`]);
    if (!path) return;
    try {
      const added = await api.importMaterials(path);
      await app.loadLibrary();
      if (added.length) select(added[0].id);
      app.info(t("{count} matériau(x) importé(s) : {names}", { count: added.length, names: added.map((m) => m.name).join(", ") }));
    } catch (e) {
      app.error(e);
    }
  }

  async function openFolder() {
    try {
      await api.openMaterialsFolder();
    } catch (e) {
      app.error(e);
    }
  }

  function close() {
    if (dirty && !confirm(t("Modifications non enregistrées. Fermer quand même ?"))) return;
    app.materialsOpen = false;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={close}>
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-label={t("Bibliothèque matériaux")}>
    <header>
      <div class="title">
        <strong>{t("Bibliothèque matériaux")}</strong>
        <span class="muted small">{t("commune à tous les projets · un fichier JSON en SI par matériau dans")}
          <code>{app.libraryDir}</code></span>
      </div>
      <span class="spacer"></span>
      <button class="ghost" onclick={importFile} title={t("Copier dans la bibliothèque les matériaux d'un fichier JSON")}
        ><Icon name="file" size={14} />{t("Importer…")}</button>
      <button class="ghost" onclick={openFolder} title={t("Ouvrir le dossier dans le gestionnaire de fichiers")}
        ><Icon name="folder" size={14} />{t("Ouvrir le dossier")}</button>
      <button class="ghost icon" onclick={close} title={t("Fermer")}><Icon name="close" /></button>
    </header>
    {#if app.libraryErrors.length}
      <div class="errors">
        <strong>{t("Fichiers ignorés")}</strong>
        {#each app.libraryErrors as err (err)}<div class="mono small">{err}</div>{/each}
      </div>
    {/if}
    <div class="body">
      <aside>
        <ul>
          {#each app.library as m (m.id)}
            <li>
              <button class="ghost item" class:on={m.id === selectedId} onclick={() => select(m.id)}>
                <span class="name">{m.name}</span>
                <span class="muted small">{m.model}{m.rho ? ` · ${m.rho} kg/m³` : ""}</span>
              </button>
            </li>
          {/each}
        </ul>
        <div class="list-actions">
          <button onclick={create}><Icon name="plus" size={14} />{t("Nouveau")}</button>
          <button onclick={duplicate} disabled={!selectedId}><Icon name="copy" size={14} />{t("Dupliquer")}</button>
        </div>
      </aside>

      {#if draft}
        <section class="editor">
          <label class="wide">
            <span>{t("Nom")}</span>
            <input bind:value={draft.name} oninput={() => (dirty = true)} />
          </label>
          <label class="wide">
            <span>{t("Description")}</span>
            <input bind:value={draft.description} oninput={() => (dirty = true)} />
          </label>
          <label class="wide">
            <span>{t("Source")}</span>
            <input
              bind:value={draft.source}
              oninput={() => (dirty = true)}
              placeholder={t("fiche technique, article, essai perso…")}
            />
          </label>

          <div class="models">
            {#each Object.entries(MODELS) as [model, def] (model)}
              <button class:on={draft.model === model} onclick={() => setModel(model as MaterialModel)}>
                <span class="mono">{model}</span>
                <span class="small">{t(def.label)}</span>
              </button>
            {/each}
          </div>

          <div class="grid">
            {#each MODELS[draft.model].keys as key (key)}
              {@const [unit, factor] = displayUnit(key)}
              <label>
                <span class="mono">{key}</span>
                <span class="input">
                  <input
                    class="mono"
                    value={fmt(draft.constants[key], factor)}
                    oninput={(e) => setConstant(key, e.currentTarget.value)}
                    inputmode="decimal"
                  />
                  <span class="unit">{unit}</span>
                </span>
              </label>
            {/each}
            <label>
              <span class="mono">RHO</span>
              <span class="input">
                <input
                  class="mono"
                  value={fmt(draft.rho, 1)}
                  oninput={(e) => {
                    const v = parse(e.currentTarget.value, 1);
                    if (v !== undefined && draft) {
                      draft.rho = v;
                      dirty = true;
                    }
                  }}
                  inputmode="decimal"
                />
                <span class="unit">{t("kg/m³")}</span>
              </span>
            </label>
          </div>

          <div class="strengths">
            <div class="sub-head">
              <strong>{t("Résistances")}</strong>
              <span class="muted small">{t("non utilisées par Code_Aster en élasticité linéaire — pour un futur calcul de marges")}</span>
            </div>
            {#each draft.strengths as s, i (i)}
              <div class="strength">
                <input bind:value={s.name} oninput={() => (dirty = true)} placeholder={t("Traction XY, Traction Z…")} />
                <span class="input">
                  <input
                    class="mono"
                    value={fmt(s.value, 1e-6)}
                    oninput={(e) => {
                      const v = parse(e.currentTarget.value, 1e-6);
                      if (v !== undefined && v !== null) {
                        s.value = v;
                        dirty = true;
                      }
                    }}
                    inputmode="decimal"
                  />
                  <span class="unit">{t("MPa")}</span>
                </span>
                <button
                  class="ghost icon"
                  title={t("Retirer")}
                  onclick={() => {
                    draft!.strengths.splice(i, 1);
                    dirty = true;
                  }}
                >
                  <Icon name="trash" size={13} />
                </button>
              </div>
            {/each}
            <button
              class="ghost add"
              onclick={() => {
                draft!.strengths.push({ name: "", value: 0 });
                dirty = true;
              }}
            >
              <Icon name="plus" size={13} />{t("Ajouter une résistance")}
            </button>
          </div>

          <footer>
            <button class="ghost danger" onclick={remove}><Icon name="trash" size={14} />{t("Supprimer")}</button>
            <span class="spacer"></span>
            {#if dirty}<span class="muted small">{t("modifié")}</span>{/if}
            <button class="primary" onclick={save} disabled={!dirty}><Icon name="save" size={14} />{t("Enregistrer")}</button>
          </footer>
        </section>
      {:else}
        <section class="editor muted">{t("Aucun matériau. Crée-en un avec « Nouveau ».")}</section>
      {/if}
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(10, 12, 18, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dialog {
    width: min(980px, 94vw);
    height: min(680px, 88vh);
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
  }
  header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  .spacer {
    flex: 1;
  }
  .title {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  header code {
    font-size: 11px;
    word-break: break-all;
  }
  .errors {
    padding: 6px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--err);
  }
  .small {
    font-size: 11px;
  }
  .body {
    flex: 1;
    display: flex;
    min-height: 0;
  }
  aside {
    width: 240px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border);
  }
  ul {
    flex: 1;
    overflow: auto;
    list-style: none;
    margin: 0;
    padding: 6px;
  }
  .item {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
    gap: 0;
    padding: 6px 8px;
  }
  .item.on {
    background: var(--accent-soft);
  }
  .item .name {
    font-weight: 600;
  }
  .list-actions {
    display: flex;
    gap: 6px;
    padding: 8px;
    border-top: 1px solid var(--border);
  }
  .editor {
    flex: 1;
    overflow: auto;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  label > span:first-child {
    font-size: 12px;
    font-weight: 500;
  }
  .models {
    display: flex;
    gap: 6px;
  }
  .models button {
    flex-direction: column;
    gap: 0;
    padding: 4px 12px;
    color: var(--muted);
  }
  .models .on {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 8px 14px;
  }
  .input {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .input input {
    width: 110px;
  }
  .unit {
    font-size: 12px;
    color: var(--muted);
  }
  .strengths {
    border-top: 1px solid var(--border);
    padding-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sub-head {
    display: flex;
    gap: 10px;
    align-items: baseline;
  }
  .strength {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .strength > input {
    flex: 1;
  }
  .add {
    align-self: flex-start;
    color: var(--accent);
    font-size: 12px;
  }
  footer {
    margin-top: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
  .danger {
    color: var(--err);
  }
</style>
