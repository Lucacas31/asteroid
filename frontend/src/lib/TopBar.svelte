<script lang="ts">
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let menuOpen = $state(false);

  function act(fn: () => unknown) {
    menuOpen = false;
    fn();
  }

  function shortPath(p: string): string {
    const parts = p.split("/").filter(Boolean);
    return parts.length > 3 ? "…/" + parts.slice(-3).join("/") : p;
  }

  async function newProject() {
    if (!app.projectDir && app.project.blocks.length && !confirm(t("Le projet actuel n'est pas enregistré. Continuer ?"))) {
      return;
    }
    await app.newProject();
  }
</script>

<svelte:window onclick={() => (menuOpen = false)} />

<header>
  <div class="left">
    <div class="menu-wrap">
      <button
        class="ghost brand"
        title={t("Menu projet")}
        onclick={(e) => {
          e.stopPropagation();
          menuOpen = !menuOpen;
        }}
      >
        <img class="logo" src="/logo.png" alt="Asteroid" />
        <Icon name="chevron" size={14} />
      </button>
      {#if menuOpen}
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
        <div class="menu" onclick={(e) => e.stopPropagation()}>
          <button class="ghost" onclick={() => act(newProject)}><Icon name="file" />{t("Nouveau projet")}</button>
          <button class="ghost" onclick={() => act(() => app.openProject())}><Icon name="folder" />{t("Ouvrir…")}</button>
          <button class="ghost" onclick={() => act(() => app.saveAs())}><Icon name="save" />{t("Enregistrer sous…")}</button>
          <button class="ghost" onclick={() => act(() => (app.importOpen = true))}><Icon name="text" />{t("Importer un .comm…")}</button>
          <button class="ghost" onclick={() => act(() => (app.materialsOpen = true))}><Icon name="book" />{t("Bibliothèque matériaux…")}</button>
          {#if app.settings?.recent_projects.length}
            <div class="sep">{t("Récents")}</div>
            {#each app.settings.recent_projects as dir (dir)}
              <button class="ghost recent" title={dir} onclick={() => act(() => app.openProject(dir))}>
                <span class="name">{dir.split("/").filter(Boolean).at(-1)}</span>
                <span class="muted">{shortPath(dir)}</span>
              </button>
            {/each}
          {/if}
          <div class="sep"></div>
          <button class="ghost" onclick={() => act(() => (app.settingsOpen = true))}><Icon name="settings" />{t("Réglages…")}</button>
        </div>
      {/if}
    </div>
    <input
      class="name"
      bind:value={app.project.name}
      oninput={() => app.touch()}
      spellcheck="false"
      title={t("Nom du projet")}
    />
    <button class="mesh" onclick={() => app.chooseMesh()} title={t("Choisir le fichier de maillage (.med)")}>
      <Icon name="cube" />
      {app.project.mesh ?? t("Choisir un maillage…")}
    </button>
  </div>

  <div class="right">
    {#if app.running}
      <button class="stop" onclick={() => app.stopRun()} title={t("Arrêter le run")}>
        <Icon name="stop" filled size={12} />Stop
      </button>
    {:else}
      <button class="primary" onclick={() => app.startRun()} title={t("Lancer le calcul (Ctrl+Entrée)")}>
        <Icon name="play" filled size={12} />Run
      </button>
    {/if}
    <button
      onclick={() => app.openParaview()}
      disabled={!app.run && !app.history.length}
      title={t("Ouvrir le résultat du run affiché (ou du dernier run) dans ParaView")}
    >
      <Icon name="eye" />ParaView
    </button>
  </div>
</header>

<style>
  header {
    grid-area: top;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 6px 10px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .left,
  .right {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .brand {
    padding: 3px 6px;
  }
  .logo {
    width: 22px;
    height: 22px;
    border-radius: 5px;
    display: block;
  }
  input.name {
    font-weight: 600;
    font-size: 14px;
    border-color: transparent;
    background: transparent;
    width: 220px;
  }
  input.name:hover {
    border-color: var(--border);
  }
  .mesh {
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--muted);
  }
  .stop {
    background: var(--err);
    border-color: var(--err);
    color: #fff;
  }
  .stop:hover {
    filter: brightness(1.08);
    background: var(--err) !important;
  }
  .menu-wrap {
    position: relative;
  }
  .menu {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 50;
    min-width: 260px;
    max-width: 420px;
    padding: 6px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
  }
  .menu button {
    justify-content: flex-start;
    padding: 6px 8px;
  }
  .recent {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 0 !important;
  }
  .recent .muted {
    font-size: 11px;
  }
  .sep {
    border-top: 1px solid var(--border);
    margin: 6px 0 2px;
    padding: 4px 8px 0;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
</style>
