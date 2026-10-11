<script lang="ts">
  import type { Settings } from "./api";
  import CommandSettings from "./CommandSettings.svelte";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { i18n, t } from "./i18n.svelte";

  let tab = $state<"project" | "global">("project");
  let draft = $state<Settings>($state.snapshot(app.settings!) as Settings);

  function close() {
    app.settingsOpen = false;
  }

  let updating = $state(false);

  async function addFile() {
    const path = await app.pick("file", t("Fichier de données à rattacher"));
    if (!path) return;
    const used = new Set((app.project.files ?? []).map((f) => f.unit));
    let unit = 40;
    while (used.has(unit)) unit += 1;
    app.attachFile(unit, path);
  }

  async function updateCatalog() {
    updating = true;
    await app.updateCatalog();
    updating = false;
  }

  async function saveGlobal() {
    await app.saveSettings($state.snapshot(draft) as Settings);
    app.info(t("Réglages enregistrés"));
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={close}>
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-label={t("Réglages")}>
    <header>
      <nav>
        <button class="ghost" class:active={tab === "project"} onclick={() => (tab = "project")}>{t("Projet")}</button>
        <button class="ghost" class:active={tab === "global"} onclick={() => (tab = "global")}>{t("Réglages globaux")}</button>
      </nav>
      <button class="ghost icon" onclick={close} title={t("Fermer")}><Icon name="close" /></button>
    </header>

    {#if tab === "project"}
      <div class="form">
        <label>
          <span>{t("Nom")}</span>
          <input bind:value={app.project.name} oninput={() => app.touch()} />
        </label>
        <label>
          <span>{t("Système d'unités")}</span>
          <select bind:value={app.project.units} onchange={() => app.touch()}>
            <option value="mm-N-MPa">{t("mm – N – MPa (t/mm³)")}</option>
            <option value="m-N-Pa">{t("m – N – Pa (SI, kg/m³)")}</option>
          </select>
        </label>
        <label>
          <span>{t("Dossier des runs")}</span>
          <input bind:value={app.project.runs_dir} oninput={() => app.touch()} />
        </label>
        <div class="row">
          <label>
            <span>{t("Temps limite (s)")}</span>
            <input type="number" min="1" bind:value={app.project.time_limit} oninput={() => app.touch()} />
          </label>
          <label>
            <span>{t("Mémoire limite (Mo)")}</span>
            <input type="number" min="128" step="128" bind:value={app.project.memory_limit} oninput={() => app.touch()} />
          </label>
        </div>
        <div class="files">
          <span class="files-title">{t("Fichiers rattachés aux unités")}</span>
          <small class="muted">
            {t("Déclarés dans le .export. En entrée (D), le fichier est copié dans le dossier du run ; en sortie (R), le run l'écrit sous ce nom.")}
          </small>
          {#each app.project.files ?? [] as f, i (i)}
            <div class="file">
              <span class="mono">UNITE</span>
              <input
                class="unit mono"
                type="number"
                min="1"
                value={f.unit}
                oninput={(e) => {
                  f.unit = Number(e.currentTarget.value);
                  app.touch();
                }}
              />
              <select bind:value={f.mode} onchange={() => app.touch()}>
                <option value="D">{t("entrée (D)")}</option>
                <option value="R">{t("sortie (R)")}</option>
              </select>
              <input class="path mono" bind:value={f.path} oninput={() => app.touch()} spellcheck="false" />
              <button
                class="ghost icon"
                title={t("Retirer")}
                onclick={() => {
                  app.project.files.splice(i, 1);
                  app.touch();
                }}
              >
                <Icon name="trash" size={13} />
              </button>
            </div>
          {/each}
          <button class="ghost add" onclick={addFile}><Icon name="plus" size={13} />{t("Rattacher un fichier…")}</button>
        </div>
        <p class="muted">{t("Dossier du projet :")} <code>{app.projectDir ?? t("non enregistré")}</code></p>
        <p class="muted">{t("Enregistrement automatique.")}</p>
      </div>
    {:else}
      <div class="form">
        <label>
          <span>{t("Langue de l'interface")}</span>
          <select bind:value={draft.language}>
            {#each i18n.languages as lang (lang.code)}<option value={lang.code}>{lang.name}</option>{/each}
          </select>
          <small class="muted">
            {t("Fichiers de langue :")} <code>{app.paths?.languages}/&lt;code&gt;.json</code>
          </small>
        </label>
        <CommandSettings {draft} />
        <div class="catalog">
          <div>
            <strong>{t("Catalogue des commandes")}</strong>
            <div class="muted small">
              Code_Aster {app.catalog?.version ?? "?"} · {t("{count} commandes", { count: app.catalog?.commands.length ?? 0 })}
              <br /><code>{app.catalog?.source ?? ""}</code>
            </div>
          </div>
          <button onclick={updateCatalog} disabled={updating}>
            {updating ? t("Export en cours…") : t("Mettre à jour le catalogue")}
          </button>
        </div>
        <label>
          <span>{t("Commande d'export du catalogue")}</span>
          <textarea rows="3" bind:value={draft.catalog_command} spellcheck="false"></textarea>
          <small class="muted">{t("Variables :")} <code>{"{out_dir} {script} {image}"}</code></small>
        </label>
        <p class="muted small">{t("Réglages :")} <code>{app.paths?.config}</code></p>
        <div class="actions">
          <button class="primary" onclick={saveGlobal}><Icon name="save" />{t("Enregistrer")}</button>
        </div>
      </div>
    {/if}
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
    width: min(720px, 92vw);
    max-height: 88vh;
    overflow: auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }
  nav {
    display: flex;
    gap: 4px;
  }
  nav .active {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .form {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  label > span {
    font-weight: 500;
  }
  textarea,
  label input:not([type="checkbox"]) {
    font-family: var(--mono);
    font-size: 12px;
  }
  .row {
    display: flex;
    gap: 12px;
  }
  .row label {
    flex: 1;
  }
  p {
    margin: 0;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
  }
  .files {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .files-title {
    font-weight: 500;
  }
  .file {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .file .unit {
    width: 70px;
  }
  .file .path {
    flex: 1;
  }
  .files .add {
    align-self: flex-start;
    color: var(--accent);
    font-size: 12px;
  }
  .catalog {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--panel-2);
  }
  .catalog code {
    font-size: 11px;
    word-break: break-all;
  }
  .small {
    font-size: 11.5px;
  }
</style>
