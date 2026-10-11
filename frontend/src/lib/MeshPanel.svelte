<script lang="ts">
  import type { MeshGroup } from "./api";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import Viewer3D from "./Viewer3D.svelte";
  import { i18n, N_, t } from "./i18n.svelte";

  const SECTIONS: { title: string; match: (g: MeshGroup) => boolean }[] = [
    { title: N_("Volumes"), match: (g) => g.entity === "GROUP_MA" && g.dim === 3 },
    { title: N_("Faces"), match: (g) => g.entity === "GROUP_MA" && g.dim === 2 },
    { title: N_("Arêtes"), match: (g) => g.entity === "GROUP_MA" && g.dim === 1 },
    { title: N_("Points"), match: (g) => g.entity === "GROUP_MA" && g.dim === 0 },
    { title: N_("Nœuds"), match: (g) => g.entity === "GROUP_NO" },
  ];

  let lengthUnit = $derived(app.project.units === "m-N-Pa" ? "m" : "mm");

  function fmt(x: number): string {
    return x.toLocaleString(i18n.locale, { maximumSignificantDigits: 5 });
  }

  function measure(g: MeshGroup): string {
    if (g.measure == null || g.entity === "GROUP_NO") return "";
    const dim = g.dim ?? 0;
    const exp = ["", "", "²", "³"][dim];
    const value = fmt(g.measure * app.meshScale ** dim);
    // Unité douteuse tant que l'avertissement d'unités est affiché.
    return app.unitWarning ? value : `${value} ${lengthUnit}${exp}`;
  }

  function countLabel(g: MeshGroup): string {
    const count = fmt(g.count);
    return g.entity === "GROUP_NO" ? t("{count} nœuds", { count }) : t("{count} mailles", { count });
  }

  let cellSummary = $derived(
    app.mesh
      ? Object.entries(app.mesh.cells)
          .map(([t, n]) => `${fmt(n)} ${t}`)
          .join(" · ")
      : "",
  );
</script>

<main>
  {#if app.mesh}
    <div class="view">
      <Viewer3D />
      {#if app.unitWarning}
        {@const w = app.unitWarning}
        <div class="unit-warning">
          <Icon name="alert" size={16} />
          <div>
            <strong>
              {w.kind === "meters" ? t("Le maillage semble être en mètres") : t("Le maillage semble être en millimètres")}
            </strong>
            <span class="muted">
              {t("(dimensions {size}), alors que le projet est en {units}.", { size: w.size, units: app.project.units })}
            </span>
            <div class="fix">
              {#if w.kind === "meters"}
                <button onclick={() => app.addScaleBlock(1000)}>{t("Ajouter MODI_MAILLAGE(ECHELLE=1000) — calcul en mm")}</button>
                <button onclick={() => app.setUnits("m-N-Pa")}>{t("Passer le projet en m-N-Pa")}</button>
              {:else}
                <button onclick={() => app.addScaleBlock(0.001)}>{t("Ajouter MODI_MAILLAGE(ECHELLE=0.001) — calcul en m")}</button>
                <button onclick={() => app.setUnits("mm-N-MPa")}>{t("Passer le projet en mm-N-MPa")}</button>
              {/if}
            </div>
          </div>
        </div>
      {/if}
      <div class="info muted">
        {#if app.meshSize}{app.meshSize.map(fmt).join(" × ")}{app.unitWarning ? "" : ` ${lengthUnit}`}{#if app.meshScale !== 1}&nbsp;{t("(échelle ×{scale})", { scale: fmt(app.meshScale) })}{/if} · {/if}{t("{count} nœuds", { count: fmt(app.mesh.nodes) })} · {cellSummary}
      </div>
    </div>
    <aside class="groups">
      <div class="head">
        <span class="title">{t("Groupes")}</span>
        {#if app.highlight}
          <button class="ghost small" onclick={() => (app.highlight = null)}>{t("Effacer")}</button>
        {/if}
      </div>
      <div class="list">
        {#each SECTIONS as section (section.title)}
          {@const items = app.mesh.groups.filter(section.match)}
          {#if items.length}
            <div class="section">{t(section.title)}</div>
            {#each items as g (g.entity + g.name)}
              {@const on = app.highlight?.entity === g.entity && app.highlight.name === g.name}
              <button class="ghost group" class:on onclick={() => app.toggleHighlight(g)} title="{g.entity} {g.name}">
                <span class="name mono">{g.name}</span>
                <span class="meta">
                  <span>{countLabel(g)}</span>
                  {#if measure(g)}<span class="measure">{measure(g)}</span>{/if}
                </span>
              </button>
            {/each}
          {/if}
        {:else}
          <div class="muted empty">{t("Aucun groupe dans ce maillage.")}</div>
        {/each}
      </div>
    </aside>
  {:else}
    <div class="placeholder">
      <img class="logo" src="/logo.png" alt="" />
      {#if app.meshLoading}
        <p>{t("Lecture du maillage…")}</p>
      {:else if app.meshError}
        <p class="error">{app.meshError}</p>
        <button onclick={() => app.chooseMesh()}><Icon name="folder" />{t("Choisir un autre fichier")}</button>
      {:else}
        <p>{t("Aucun maillage")}</p>
        <button class="primary" onclick={() => app.chooseMesh()}><Icon name="folder" />{t("Choisir un fichier .med")}</button>
      {/if}
    </div>
  {/if}
</main>

<style>
  main {
    grid-area: center;
    display: flex;
    min-width: 0;
    min-height: 0;
    background: radial-gradient(circle at 50% 40%, var(--panel-2), var(--bg));
  }
  .view {
    position: relative;
    flex: 1;
    display: flex;
    min-width: 0;
  }
  .info {
    position: absolute;
    right: 10px;
    bottom: 8px;
    font-size: 11px;
    pointer-events: none;
  }
  .unit-warning {
    position: absolute;
    top: 48px;
    left: 8px;
    right: 8px;
    max-width: 640px;
    display: flex;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--warn) 50%, transparent);
    background: color-mix(in srgb, var(--panel) 92%, var(--warn));
    color: var(--text);
    box-shadow: var(--shadow);
  }
  .unit-warning :global(svg) {
    color: var(--warn);
    flex: none;
    margin-top: 2px;
  }
  .fix {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }
  .fix button {
    font-size: 12px;
  }
  .groups {
    width: 230px;
    flex: none;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
    background: var(--panel);
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    min-height: 39px;
    border-bottom: 1px solid var(--border);
  }
  .title {
    font-weight: 600;
  }
  .small {
    padding: 1px 6px;
    font-size: 12px;
  }
  .list {
    flex: 1;
    overflow: auto;
    padding: 4px 6px 10px;
  }
  .section {
    margin: 10px 4px 4px;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .group {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
    gap: 1px;
    padding: 5px 8px;
    border-left: 3px solid transparent;
    border-radius: 4px;
  }
  .group.on {
    background: color-mix(in srgb, #ff7a1a 14%, transparent);
    border-left-color: #ff7a1a;
  }
  .name {
    font-weight: 600;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta {
    display: flex;
    gap: 8px;
    font-size: 11px;
    color: var(--muted);
  }
  .measure {
    color: var(--text);
  }
  .empty {
    padding: 10px 4px;
  }
  .placeholder {
    margin: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: var(--muted);
  }
  .placeholder .logo {
    width: 96px;
    height: 96px;
    border-radius: 20px;
    margin-bottom: 6px;
    box-shadow: var(--shadow);
  }
  .placeholder p {
    margin: 0;
  }
  .error {
    color: var(--err);
    max-width: 420px;
    text-align: center;
  }
</style>
