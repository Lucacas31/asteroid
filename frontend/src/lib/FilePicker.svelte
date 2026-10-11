<script lang="ts">
  // Explorateur de secours, utilisé seulement si zenity n'est pas installé.
  import { onMount } from "svelte";
  import { api, type DirListing } from "./api";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let req = $derived(app.picker!);
  let listing = $state<DirListing | null>(null);
  let pathInput = $state("");

  async function go(path: string) {
    try {
      listing = await api.listDir(path);
      pathInput = listing.path;
    } catch (e) {
      app.error(e);
    }
  }

  onMount(() => go(app.projectDir ?? "~"));

  function visible(name: string, dir: boolean): boolean {
    if (dir) return true;
    if (req.mode === "dir") return false;
    return !req.extensions.length || req.extensions.some((ext) => name.toLowerCase().endsWith(ext));
  }

  function join(name: string): string {
    return `${listing!.path.replace(/\/$/, "")}/${name}`;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={() => app.closePicker(null)}>
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-label={req.title}>
    <header>
      <strong>{req.title}</strong>
      <button class="ghost icon" onclick={() => app.closePicker(null)}><Icon name="close" /></button>
    </header>
    <div class="path">
      <button class="icon" onclick={() => listing && go(listing.parent)} title={t("Dossier parent")}><Icon name="up" /></button>
      <input bind:value={pathInput} onkeydown={(e) => e.key === "Enter" && go(pathInput)} spellcheck="false" />
    </div>
    <ul>
      {#each listing?.entries.filter((e) => visible(e.name, e.dir)) ?? [] as entry (entry.name)}
        <li>
          <button
            class="ghost"
            ondblclick={() => (entry.dir ? go(join(entry.name)) : app.closePicker(join(entry.name)))}
            onclick={() => entry.dir && go(join(entry.name))}
          >
            <Icon name={entry.dir ? "folder" : "file"} size={14} />{entry.name}
          </button>
        </li>
      {/each}
    </ul>
    <footer>
      {#if req.mode === "dir"}
        <button class="primary" onclick={() => listing && app.closePicker(listing.path)}>{t("Choisir ce dossier")}</button>
      {:else}
        <span class="muted">{t("Double-clic sur un fichier pour le choisir.")}</span>
      {/if}
    </footer>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 110;
    background: rgba(10, 12, 18, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dialog {
    width: min(620px, 92vw);
    height: min(560px, 85vh);
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
  }
  header,
  footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
  }
  header {
    border-bottom: 1px solid var(--border);
  }
  footer {
    border-top: 1px solid var(--border);
  }
  .path {
    display: flex;
    gap: 6px;
    padding: 8px 12px;
  }
  .path input {
    flex: 1;
    font-family: var(--mono);
    font-size: 12px;
  }
  ul {
    flex: 1;
    overflow: auto;
    list-style: none;
    margin: 0;
    padding: 0 8px;
  }
  li button {
    width: 100%;
    justify-content: flex-start;
  }
</style>
