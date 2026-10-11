<script lang="ts">
  // Comparaison de plusieurs runs : chiffres clés (écart à la référence), captures avec mêmes vues
  // et même échelle, différences du .comm. Dans le panneau des runs (compact) ou dans sa fenêtre (wide).
  import { onMount, untrack } from "svelte";
  import { api, type Captures, type ResultSummary, type RunSummary } from "./api";
  import { formatValue } from "./format";
  import Icon from "./Icon.svelte";
  import { app, statusLabel } from "./store.svelte";
  import { i18n, t } from "./i18n.svelte";

  let { ids, wide = false, onclose }: { ids: string[]; wide?: boolean; onclose?: () => void } = $props();

  const VIEWS = ["iso", "x", "y", "z"];
  const UNIT = { "mm-N-MPa": ["mm", "MPa"], "m-N-Pa": ["m", "Pa"] } as const;

  let summaries = $state<Record<string, ResultSummary | null>>({});
  let diffs = $state<Record<string, string[]>>({});
  let shots = $state<{ key: string; runs: Record<string, Captures> } | null>(null);
  let working = $state(false);
  let stamp = $state(0);
  let zoomed = $state<{ id: string; view: string } | null>(null);

  // Ordre des colonnes, réglable (glisser un en-tête, ou ‹ ›) ; la première sert de référence.
  let order = $state<string[]>(untrack(() => [...ids]));
  let dragFrom = $state<number | null>(null);
  let runs = $derived(order.map((id) => app.history.find((r) => r.id === id)).filter((r): r is RunSummary => !!r));
  let referenceId = $derived(order[0]);
  let reference = $derived(runs[0]);
  const fmt = (x: number | null | undefined) => formatValue(x, i18n.locale);
  const units = (r: RunSummary) => UNIT[r.units ?? "mm-N-MPa"];

  type Key = "depl_max" | "vmis_max" | "rf_min";
  function value(r: RunSummary, key: Key): number | null {
    return summaries[r.id]?.headline?.[key] ?? r.headline?.[key] ?? null;
  }

  /** Écart à la référence, en % (vide pour la référence elle-même). */
  function delta(r: RunSummary, key: Key): string {
    if (!reference || r.id === reference.id) return "";
    const ref = value(reference, key);
    const v = value(r, key);
    if (ref === null || v === null || ref === 0) return "";
    const d = (100 * (v - ref)) / Math.abs(ref);
    return `${d >= 0 ? "+" : ""}${formatValue(d, i18n.locale)} %`;
  }

  // Différences du .comm par rapport à la référence : recalculées quand la première colonne change.
  $effect(() => {
    const ref = referenceId;
    untrack(() => {
      api.compareRuns([ref, ...order.filter((id) => id !== ref)])
        .then((res) => ref === referenceId && (diffs = res.diffs))
        .catch((e) => app.error(e));
    });
  });

  function move(from: number, to: number) {
    if (to < 0 || to >= order.length || from === to) return;
    const next = [...order];
    const [id] = next.splice(from, 1);
    next.splice(to, 0, id);
    order = next;
  }

  onMount(async () => {
    for (const id of ids) {
      api.runSummary(id).then((res) => (summaries[id] = res.summary)).catch(() => (summaries[id] = null));
    }
    // Dans sa fenêtre, la comparaison montre tout de suite les captures (reprises si déjà faites).
    if (wide && app.settings?.capture_command) await capture();
  });

  async function capture() {
    working = true;
    try {
      shots = await api.compareCaptures(ids);
      stamp = Date.now();
    } catch (e) {
      app.error(e);
    } finally {
      working = false;
    }
  }

  function lineClass(line: string): string {
    if (line.startsWith("@@")) return "hunk";
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "";
  }

  let errors = $derived(shots ? Object.values(shots.runs).map((c) => c.error).filter(Boolean) : []);
</script>

<div class="compare" class:wide style:--n={runs.length}>
  <div class="bar">
    <strong>{t("Comparaison de {count} runs", { count: runs.length })}</strong>
    <span class="muted small">{t("référence : {id}", { id: reference?.id ?? "?" })}</span>
    <span class="spacer"></span>
    <button
      class="small"
      onclick={capture}
      disabled={working || !app.settings?.capture_command}
      title={app.settings?.capture_command ? t("Mêmes vues, même échelle de couleurs, même amplification") : t("Captures : régler la commande pvbatch dans les réglages globaux.")}
    >
      {working ? t("Captures en cours…") : shots ? t("Recalculer les captures") : t("Mêmes vues, même échelle")}
    </button>
    {#if !wide}
      <button class="small" onclick={() => app.openCompare(order)} title={t("Comparer dans une grande fenêtre")}>
        <Icon name="eye" size={13} />{t("Ouvrir dans une fenêtre")}
      </button>
      {#if onclose}<button class="ghost icon" onclick={onclose} title={t("Fermer")}><Icon name="close" size={14} /></button>{/if}
    {/if}
  </div>

  <div class="grid">
    <div class="label"></div>
    {#each runs as r, i (r.id)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="head mono"
        class:ref={i === 0}
        class:dragging={dragFrom === i}
        draggable="true"
        title={t("Glisser pour déplacer la colonne ; la première sert de référence")}
        ondragstart={(e) => {
          dragFrom = i;
          e.dataTransfer?.setData("text/plain", r.id);
        }}
        ondragend={() => (dragFrom = null)}
        ondragover={(e) => dragFrom !== null && e.preventDefault()}
        ondrop={(e) => {
          e.preventDefault();
          if (dragFrom !== null) move(dragFrom, i);
          dragFrom = null;
        }}
      >
        <button class="ghost arrow" disabled={i === 0} onclick={() => move(i, i - 1)} title={t("Vers la gauche")}>‹</button>
        <span class="id">{r.id}</span>
        <button class="ghost arrow" disabled={i === runs.length - 1} onclick={() => move(i, i + 1)} title={t("Vers la droite")}>›</button>
      </div>
    {/each}

    <div class="label">{t("Note")}</div>
    {#each runs as r (r.id)}<div class="cell note">{r.note || "—"}</div>{/each}

    <div class="label">{t("Profil")}</div>
    {#each runs as r (r.id)}<div class="cell">{app.profileLabel(r.profile)} · {app.limitsLabel(r.time_limit, r.memory_limit)}</div>{/each}

    <div class="label">{t("Statut")}</div>
    {#each runs as r (r.id)}
      <div class="cell"><span class="badge {r.status}">{statusLabel(r.status)}</span> {r.duration != null ? `${r.duration} s` : ""}</div>
    {/each}

    {#each [["depl_max", t("Dépl. max")], ["vmis_max", t("σVM max")], ["rf_min", t("RF min")]] as [key, label] (key)}
      <div class="label">{label}</div>
      {#each runs as r (r.id)}
        {@const v = value(r, key as Key)}
        <div class="cell num">
          <strong class:low={key === "rf_min" && v !== null && v < 1}>{fmt(v)}</strong>
          {#if v !== null && key !== "rf_min"}<span class="muted">{units(r)[key === "depl_max" ? 0 : 1]}</span>{/if}
          <span class="delta muted">{delta(r, key as Key)}</span>
        </div>
      {/each}
    {/each}

    {#if shots}
      {#each VIEWS as view (view)}
        <div class="label">{view}</div>
        {#each runs as r (r.id)}
          <div class="cell shot">
            {#if shots.runs[r.id]?.views?.includes(view)}
              <button class="thumb" onclick={() => (zoomed = { id: r.id, view })} title={t("Agrandir")}>
                <img src={api.captureUrl(r.id, shots.key, view, stamp)} alt={`${r.id} ${view}`} />
              </button>
            {/if}
          </div>
        {/each}
      {/each}
    {/if}
  </div>
  {#if errors.length}<p class="warn small pad">{errors[0]}</p>{/if}

  <div class="diffs">
    {#each runs.slice(1) as r (r.id)}
      <details open={wide && runs.length <= 3}>
        <summary class="small">{t("Différences du .comm")} : <span class="mono">{reference?.id} → {r.id}</span></summary>
        {#if diffs[r.id]?.length}
          <div class="diff mono">
            {#each diffs[r.id] as line, i (i)}<div class={lineClass(line)}>{line || " "}</div>{/each}
          </div>
        {:else}
          <p class="muted small pad">{t("Les deux .comm sont identiques.")}</p>
        {/if}
      </details>
    {/each}
  </div>
</div>

{#if zoomed && shots}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="overlay" onclick={() => (zoomed = null)}>
    <figure>
      <img src={api.captureUrl(zoomed.id, shots.key, zoomed.view, stamp)} alt={zoomed.view} />
      <figcaption class="mono">{zoomed.id} · {zoomed.view}</figcaption>
    </figure>
  </div>
{/if}

<style>
  .compare {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .bar {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 6px 10px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .spacer {
    flex: 1;
  }
  .small {
    font-size: 11.5px;
  }
  button.small {
    padding: 2px 8px;
    gap: 4px;
  }
  .grid {
    display: grid;
    grid-template-columns: 80px repeat(var(--n), minmax(150px, 1fr));
    overflow-x: auto;
    font-size: 12px;
  }
  .wide .grid {
    grid-template-columns: 90px repeat(var(--n), minmax(260px, 1fr));
    font-size: 13px;
  }
  .grid > div {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
    min-width: 0;
  }
  .label {
    color: var(--muted);
    font-size: 11.5px;
  }
  .head {
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 2px;
    cursor: grab;
  }
  .head .id {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .head.dragging {
    opacity: 0.4;
  }
  .arrow {
    padding: 0 5px;
    font-size: 14px;
    line-height: 1;
  }
  .head.ref .id::after {
    content: " ★";
    color: var(--accent);
  }
  .note {
    white-space: pre-wrap;
  }
  .num strong {
    font-size: 13px;
  }
  .wide .num strong {
    font-size: 16px;
  }
  .delta {
    margin-left: 6px;
    font-size: 11px;
  }
  .low {
    color: var(--err);
  }
  .shot {
    padding: 4px !important;
  }
  .thumb {
    padding: 0;
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: #fff;
  }
  .thumb img {
    display: block;
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: contain;
  }
  .warn {
    color: var(--warn);
  }
  .pad {
    padding: 0 10px;
  }
  .diffs details {
    border-bottom: 1px solid var(--border);
  }
  .diffs summary {
    cursor: pointer;
    padding: 6px 10px;
    color: var(--muted);
  }
  .diff {
    white-space: pre;
    padding: 6px 10px;
    font-size: 11.5px;
    line-height: 1.45;
    background: var(--code-bg);
    overflow: auto;
  }
  .diff .add {
    color: var(--ok);
    background: color-mix(in srgb, var(--ok) 10%, transparent);
  }
  .diff .del {
    color: var(--err);
    background: color-mix(in srgb, var(--err) 10%, transparent);
  }
  .diff .hunk {
    color: var(--muted);
  }
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 300;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
  }
  figure {
    margin: 0;
    text-align: center;
    color: #fff;
  }
  figure img {
    max-width: 92vw;
    max-height: 86vh;
    border-radius: 8px;
    background: #fff;
  }
</style>
