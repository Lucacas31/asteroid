<script lang="ts">
  // Résumé des résultats d'un run : chiffres clés, marges, équilibre, captures pvbatch.
  import { untrack } from "svelte";
  import { api, type Captures, type Note, type ResultSummary } from "./api";
  import { formatValue, formatVector } from "./format";
  import { app } from "./store.svelte";
  import { i18n, t } from "./i18n.svelte";

  let { runId, onheadline }: { runId: string; onheadline?: (id: string, h: ResultSummary["headline"]) => void } = $props();

  let summary = $state<ResultSummary | null>(null);
  let shots = $state<Captures | null>(null);
  let error = $state<string | null>(null);
  let stamp = $state(Date.now());
  let zoomed = $state<string | null>(null);
  let working = $state(false);

  const fmt = (x: number | null | undefined) => formatValue(x, i18n.locale);
  const note = (n: Note) => t(n.template, n.vars);

  async function load(id: string) {
    try {
      const res = await api.runSummary(id);
      if (id !== runId) return;
      summary = res.summary;
      shots = res.captures;
      onheadline?.(id, res.summary.headline);
      error = null;
      stamp = Date.now();
      // Captures lancées à la fin du run : on revient voir tant qu'elles sont en cours.
      if (res.captures.state === "pending") setTimeout(() => id === runId && load(id), 1500);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => {
    const id = runId;
    untrack(() => {
      summary = shots = null;
      load(id);
    });
  });

  async function capture() {
    working = true;
    try {
      const res = await api.makeCaptures(runId);
      shots = { ...res, state: res.error ? "error" : "ok" };
      stamp = Date.now();
    } catch (e) {
      app.error(e);
    } finally {
      working = false;
    }
  }

  function rfClass(rf: number | null): string {
    return rf !== null && rf < 1 ? "low" : "";
  }
</script>

{#if error}
  <p class="muted pad">{error}</p>
{:else if summary}
  {@const u = summary.units}
  {#if summary.note}<p class="muted pad">{note(summary.note)}</p>{/if}
  {#each summary.results as r (r.concept + r.order)}
    <div class="card">
      {#if summary.results.length > 1}<div class="muted small mono">{r.concept} · {t("ordre")} {r.order}</div>{/if}
      <div class="keys">
        <div>
          <span class="label">{t("Déplacement max")}</span>
          <strong>{fmt(r.depl?.max)}</strong> <span class="muted">{u.length}</span>
          {#if r.depl}<span class="muted small">{t("nœud")} {r.depl.node}</span>{/if}
        </div>
        <div>
          <span class="label">{t("Von Mises max")}</span>
          <strong>{fmt(r.vmis?.max)}</strong> <span class="muted">{u.stress}</span>
          {#if r.vmis}
            <span class="muted small" title={r.vmis.source === "SIGM_NOEU" ? t("calculé par Asteroid depuis SIGM_NOEU") : "SIEQ_NOEU"}>
              {t("nœud")} {r.vmis.node}{r.vmis.source === "SIGM_NOEU" ? " · SIGM_NOEU" : ""}
            </span>
          {/if}
        </div>
      </div>

      {#if r.margins?.length}
        <table class="margins">
          <thead>
            <tr>
              <th>{t("Zone")}</th><th>{t("Matériau")}</th><th>{t("Résistance")}</th>
              <th class="num">R ({u.stress})</th><th class="num" title={t("R / σVM max de la zone")}>RF</th>
            </tr>
          </thead>
          <tbody>
            {#each r.margins as m, i (i)}
              {#if m.strengths?.length}
                {#each m.strengths as s, j (j)}
                  <tr>
                    <td class="mono">{j === 0 ? m.zone : ""}</td>
                    <td>{j === 0 ? m.material : ""}</td>
                    <td>{s.name}</td>
                    <td class="num">{fmt(s.value)}</td>
                    <td class="num rf {rfClass(s.rf)}">{fmt(s.rf)}</td>
                  </tr>
                {/each}
              {:else}
                <tr><td class="mono">{m.zone}</td><td class="mono">{m.concept}</td><td colspan="3" class="muted">{m.note ? note(m.note) : ""}</td></tr>
              {/if}
            {/each}
          </tbody>
        </table>
        {#if r.margins.some((m) => m.model && m.model !== "ELAS")}
          <p class="muted small">{t("Matériau anisotrope : la comparaison au Von Mises n'est qu'indicative.")}</p>
        {/if}
      {/if}

      <!-- Contrôle d'équilibre, discret : charge recalculée par Asteroid face aux réactions de Code_Aster. -->
      <div class="check small">
        {#if r.equilibrium !== undefined}
          <span class:ok={r.equilibrium < 1e-3} class:warn={r.equilibrium >= 1e-3}>
            {t("Équilibre")} : {t("écart {gap} %", { gap: formatValue(100 * r.equilibrium, i18n.locale) })}
          </span>
        {:else}
          <span class="muted">{t("Équilibre")} :</span>
        {/if}
        <span class="muted">
          {t("charge appliquée")} {r.applied ? `${formatVector(r.applied, i18n.locale)} ${u.force}` : "—"}
          {#if r.reactions} · Σ REAC_NODA {formatVector(r.reactions, i18n.locale)} {u.force}{/if}
        </span>
        {#if r.applied_note}<span class="muted">· {note(r.applied_note)}</span>{/if}
      </div>
      {#each r.notes as n, i (i)}<div class="muted small">{note(n)}</div>{/each}
    </div>
  {/each}

  {#if shots && summary.results.length}
    <div class="shots">
      {#if shots.state === "ok" && shots.views}
        {#each shots.views as v (v)}
          <button class="thumb" onclick={() => (zoomed = v)} title={v}>
            <img src={api.captureUrl(runId, "run", v, stamp)} alt={v} />
          </button>
        {/each}
      {:else if shots.state === "pending" || working}
        <span class="muted small">{t("Captures en cours…")}</span>
      {:else if shots.state === "error"}
        <span class="warn small">{shots.error}</span>
        <button class="small" onclick={capture}>{t("Réessayer")}</button>
      {:else if shots.state === "none"}
        <button class="small" onclick={capture}>{t("Générer les captures")}</button>
      {:else}
        <span class="muted small">{t("Captures : régler la commande pvbatch dans les réglages globaux.")}</span>
      {/if}
    </div>
  {/if}
{:else}
  <p class="muted pad small">{t("Lecture des résultats…")}</p>
{/if}

{#if zoomed}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="overlay" onclick={() => (zoomed = null)}>
    <img src={api.captureUrl(runId, "run", zoomed, stamp)} alt={zoomed} />
  </div>
{/if}

<style>
  .pad {
    padding: 0 10px;
  }
  .card {
    padding: 6px 10px 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .keys {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }
  .keys > div {
    display: flex;
    align-items: baseline;
    gap: 5px;
  }
  .label {
    color: var(--muted);
    font-size: 12px;
  }
  .keys strong {
    font-size: 15px;
  }
  .small {
    font-size: 11.5px;
  }
  .margins {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .margins th,
  .margins td {
    padding: 2px 6px;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }
  .margins th {
    color: var(--muted);
    font-weight: 500;
  }
  .num {
    text-align: right !important;
  }
  .rf {
    font-weight: 600;
  }
  .rf.low {
    color: var(--err);
  }
  .check {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .ok {
    color: var(--ok);
  }
  .warn {
    color: var(--warn);
  }
  .shots {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 4px 10px 10px;
    align-items: center;
  }
  .thumb {
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: #fff;
  }
  .thumb img {
    display: block;
    width: 132px;
    height: 99px;
    object-fit: contain;
  }
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 300;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
  }
  .overlay img {
    max-width: 90vw;
    max-height: 90vh;
    border-radius: 8px;
    background: #fff;
  }
</style>
