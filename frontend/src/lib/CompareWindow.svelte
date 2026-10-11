<script lang="ts">
  // Fenêtre de comparaison (ouverte par « Fenêtre » ou un double-clic dans l'onglet Runs).
  import { onMount } from "svelte";
  import CompareView from "./CompareView.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let { ids }: { ids: string[] } = $props();
  let ready = $state(false);

  onMount(async () => {
    await app.initCompare();
    ready = true;
  });
</script>

<svelte:head><title>{t("Comparaison")} — {app.project.name} — Asteroid</title></svelte:head>

<div class="page">
  {#if ready}
    {#key ids.join(",")}<CompareView {ids} wide />{/key}
  {:else}
    <p class="muted">{t("Lecture des résultats…")}</p>
  {/if}
</div>
{#if app.notice}<div class="notice {app.notice.kind}" role="status">{app.notice.text}</div>{/if}

<style>
  .page {
    height: 100%;
    overflow: auto;
    background: var(--panel);
  }
  p {
    padding: 16px;
  }
  .notice {
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    padding: 8px 14px;
    border-radius: 8px;
    background: var(--text);
    color: var(--panel);
  }
  .notice.error {
    background: var(--err);
    color: #fff;
  }
</style>
