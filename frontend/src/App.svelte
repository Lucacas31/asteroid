<script lang="ts">
  import { onMount } from "svelte";
  import BlockEditor from "./lib/BlockEditor.svelte";
  import BlockList from "./lib/BlockList.svelte";
  import CompareWindow from "./lib/CompareWindow.svelte";
  import BottomPanel from "./lib/BottomPanel.svelte";
  import FilePicker from "./lib/FilePicker.svelte";
  import ImportDialog from "./lib/ImportDialog.svelte";
  import MaterialLibrary from "./lib/MaterialLibrary.svelte";
  import MeshPanel from "./lib/MeshPanel.svelte";
  import ProfilesDialog from "./lib/ProfilesDialog.svelte";
  import SettingsDialog from "./lib/SettingsDialog.svelte";
  import SetupDialog from "./lib/SetupDialog.svelte";
  import StatusBar from "./lib/StatusBar.svelte";
  import TopBar from "./lib/TopBar.svelte";
  import { editable } from "./lib/editable";
  import { t } from "./lib/i18n.svelte";
  import { app } from "./lib/store.svelte";

  // /?compare=a,b,c : fenêtre de comparaison de runs, sans le reste de l'interface.
  const compareIds = new URLSearchParams(location.search).get("compare")?.split(",").filter(Boolean) ?? null;

  onMount(() => {
    if (!compareIds) app.init();
  });

  function onKey(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    if (mod && (key === "z" || key === "y") && !editable(e.target)) {
      e.preventDefault();
      if (key === "y" || e.shiftKey) app.redo();
      else app.undo();
    } else if (mod && key === "s") {
      e.preventDefault();
      app.save();
    } else if (mod && e.key === "Enter") {
      e.preventDefault();
      app.startRun();
    } else if (e.key === "Escape") {
      app.settingsOpen = false;
      app.importOpen = false;
      app.materialsOpen = false;
      app.problemsOpen = null;
      app.profilesOpen = false;
    }
  }
</script>

<!-- Raccourcis et titre de la fenêtre principale ; la fenêtre de comparaison a les siens. -->
<svelte:window onkeydown={(e) => !compareIds && onKey(e)} onfocus={() => !compareIds && app.refreshMesh()} />
<svelte:head>{#if !compareIds}<title>{t(app.project.name)} — Asteroid</title>{/if}</svelte:head>

{#if compareIds}
  <CompareWindow ids={compareIds} />
{:else}

  <div class="layout">
    <TopBar />
    <BlockList />
    <MeshPanel />
    <BlockEditor />
    <BottomPanel />
    <StatusBar />
  </div>

  {#if app.settingsOpen && app.settings}<SettingsDialog />{/if}
  {#if app.importOpen}<ImportDialog />{/if}
  {#if app.materialsOpen}<MaterialLibrary />{/if}
  {#if app.profilesOpen && app.settings}<ProfilesDialog />{/if}
  {#if app.settings && !app.settings.configured}<SetupDialog />{/if}
  {#if app.picker}<FilePicker />{/if}
  {#if app.notice}
    <div class="notice {app.notice.kind}" role="status">{app.notice.text}</div>
  {/if}
{/if}

<style>
  .layout {
    height: 100%;
    display: grid;
    /* Minimums réduits : dans une fenêtre étroite, rien ne sort à droite (bouton Run compris). */
    grid-template-columns: minmax(200px, 260px) minmax(300px, 1fr) minmax(320px, 30%);
    grid-template-rows: auto minmax(0, 1fr) auto auto;
    grid-template-areas:
      "top top top"
      "left center right"
      "bottom bottom bottom"
      "status status status";
  }
  .notice {
    position: fixed;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 200;
    max-width: 70vw;
    padding: 8px 14px;
    border-radius: 8px;
    background: var(--text);
    color: var(--panel);
    box-shadow: var(--shadow);
    white-space: pre-wrap;
  }
  .notice.error {
    background: var(--err);
    color: #fff;
  }
</style>
