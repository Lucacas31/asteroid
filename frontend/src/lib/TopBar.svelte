<script lang="ts">
  import Icon from "./Icon.svelte";
  import ProblemsPanel from "./ProblemsPanel.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let menuOpen = $state(false);
  let profilesOpen = $state(false);

  function launch(profile: string | null) {
    profilesOpen = false;
    app.startRun(false, profile);
  }

  function act(fn: () => unknown) {
    menuOpen = false;
    profilesOpen = false;
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

<svelte:window
  onclick={() => {
    menuOpen = false;
    profilesOpen = false;
  }}
/>

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
    <div class="history">
      <button class="ghost icon" disabled={!app.canUndo} onclick={() => app.undo()} title={t("Annuler (Ctrl+Z)")}>
        <Icon name="undo" />
      </button>
      <button class="ghost icon" disabled={!app.canRedo} onclick={() => app.redo()} title={t("Rétablir (Ctrl+Maj+Z)")}>
        <Icon name="redo" />
      </button>
    </div>
  </div>

  <div class="right">
    <ProblemsPanel />
    {#if app.running}
      <button class="stop" onclick={() => app.stopRun()} title={t("Arrêter le run")}>
        <Icon name="stop" filled size={12} />Stop
      </button>
    {:else}
      <div class="run-wrap">
        <button
          class="primary run"
          onclick={() => app.startRun()}
          title={t("Lancer le calcul (Ctrl+Entrée) avec le profil « {profile} »", { profile: app.profileLabel(app.currentProfile) })}
        >
          <Icon name="play" filled size={12} />Run
        </button>
        <button
          class="primary profile"
          title={t("Choisir le profil et lancer")}
          onclick={(e) => {
            e.stopPropagation();
            profilesOpen = !profilesOpen;
          }}
        >
          <Icon name="chevron" size={12} />
        </button>
        {#if profilesOpen}
          <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
          <div class="menu profiles" onclick={(e) => e.stopPropagation()}>
            <div class="sep first">{t("Lancer avec le profil")}</div>
            {#if app.projectLimits}
              <button class="ghost choice" onclick={() => launch(null)} title={t("Limites définies dans les réglages du projet")}>
                <span class="tick">{#if app.currentProfile === null}<Icon name="check" size={13} />{/if}</span>
                <span class="name">{t("Projet")}</span>
                <span class="muted small">{app.projectLimitsLabel}</span>
              </button>
            {/if}
            {#each app.settings?.run_profiles ?? [] as p (p.name)}
              <button class="ghost choice" onclick={() => launch(p.name)}>
                <span class="tick">{#if app.currentProfile === p.name}<Icon name="check" size={13} />{/if}</span>
                <span class="name">{app.profileLabel(p.name)}</span>
                <span class="muted small">{app.limitsLabel(p.time_limit, p.memory_limit)}</span>
              </button>
            {/each}
            <div class="sep"></div>
            <button class="ghost" onclick={() => act(() => (app.profilesOpen = true))}><Icon name="settings" />{t("Modifier les profils…")}</button>
          </div>
        {/if}
      </div>
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
  .history {
    display: flex;
    gap: 2px;
  }
  .run-wrap {
    position: relative;
    display: flex;
  }
  .run {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
  }
  .profile {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: 1px solid color-mix(in srgb, #fff 35%, transparent);
    padding-left: 5px;
    padding-right: 5px;
  }
  .profiles {
    left: auto;
    right: 0;
    min-width: 300px;
  }
  .choice {
    gap: 8px !important;
  }
  .choice .tick {
    width: 14px;
    display: flex;
    color: var(--accent);
  }
  .choice .name {
    flex: 1;
    text-align: left;
  }
  .small {
    font-size: 11.5px;
  }
  .sep.first {
    border-top: none;
    margin-top: 0;
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
