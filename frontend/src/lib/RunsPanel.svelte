<script lang="ts">
  // Gestionnaire des runs du projet : tableau, détails d'un run, comparaison de deux runs.
  import { untrack } from "svelte";
  import { api, type Captures, type Headline, type RunFile, type RunSummary } from "./api";
  import CodeEditor from "./CodeEditor.svelte";
  import { formatValue } from "./format";
  import Icon from "./Icon.svelte";
  import ResultPanel from "./ResultPanel.svelte";
  import { app, formatSize, statusLabel } from "./store.svelte";
  import { i18n, t } from "./i18n.svelte";

  const UNIT = { "mm-N-MPa": ["mm", "MPa"], "m-N-Pa": ["m", "Pa"] } as const;
  const fmt = (x: number | null | undefined) => formatValue(x, i18n.locale);
  const units = (r: RunSummary) => UNIT[r.units ?? "mm-N-MPa"];

  // Fichiers texte du run affichables dans l'app.
  const TEXT_FILES = /^(run\.(comm|export|log|sh|json)|message|paraview_open\.py)$/;

  let selected = $state<string | null>(null);
  let checked = $state<string[]>([]);
  let files = $state<RunFile[]>([]);
  let viewing = $state<{ name: string; text: string } | null>(null);
  let comparing = $state<{ a: RunSummary; b: RunSummary; diff: string[] } | null>(null);
  let pair = $state<Record<string, Captures> | null>(null);
  let pairWorking = $state(false);
  let pairStamp = $state(0);
  let note = $state("");

  let current = $derived(app.history.find((r) => r.id === selected) ?? null);
  let allChecked = $derived(app.history.length > 0 && checked.length === app.history.length);

  // Run affiché dans le log (lancé ou choisi) : sélectionné par défaut.
  $effect(() => {
    if (!selected && app.history.length) selected = app.run?.id ?? app.history[0].id;
    // Runs supprimés : retirés de la sélection (réaffectation seulement si elle change, sinon boucle d'effet).
    const kept = checked.filter((id) => app.history.some((r) => r.id === id));
    if (kept.length !== checked.length) checked = kept;
  });

  // Détail rechargé au changement de run seulement : un rafraîchissement du tableau ne doit pas
  // effacer la note en cours de saisie ni le fichier affiché.
  // Identifiant seul (valeur simple) : l'effet ne se relance pas quand l'objet du run est recréé.
  let currentId = $derived(current?.id ?? null);

  $effect(() => {
    const id = currentId;
    untrack(() => {
      viewing = null;
      note = current?.note ?? "";
      files = [];
      if (id) api.runFiles(id).then((f) => selected === id && (files = f)).catch(() => {});
    });
  });

  function select(id: string) {
    selected = id;
    comparing = null;
  }

  async function view(name: string) {
    if (!current) return;
    try {
      viewing = { name, text: await api.runFileText(current.id, name) };
    } catch (e) {
      app.error(e);
    }
  }

  async function compare() {
    // Le plus ancien à gauche : le diff se lit « avant → après ».
    const [a, b] = app.history.filter((r) => checked.includes(r.id)).reverse();
    try {
      comparing = { a, b, diff: (await api.compareRuns(a.id, b.id)).diff };
      pair = null;
    } catch (e) {
      app.error(e);
    }
  }

  /** Captures des deux runs avec les mêmes vues, la même échelle de couleurs et la même amplification. */
  async function compareShots() {
    if (!comparing) return;
    pairWorking = true;
    try {
      pair = await api.compareCaptures(comparing.a.id, comparing.b.id);
      pairStamp = Date.now();
    } catch (e) {
      app.error(e);
    } finally {
      pairWorking = false;
    }
  }

  async function remove(ids: string[]) {
    const msg = ids.length === 1
      ? t("Supprimer définitivement le run {id} et tous ses fichiers ?", { id: ids[0] })
      : t("Supprimer définitivement {count} runs et tous leurs fichiers ?", { count: ids.length });
    if (!confirm(msg)) return;
    await app.deleteRuns(ids);
    checked = checked.filter((id) => !ids.includes(id));
    if (selected && ids.includes(selected)) selected = null;
    comparing = null;
  }

  /** Chiffres d'un run antérieur au résumé, calculés à son ouverture : reportés dans sa ligne. */
  function setHeadline(id: string, headline: Headline | null | undefined) {
    const row = app.history.find((r) => r.id === id);
    if (row && headline && !row.headline) row.headline = headline;
  }

  function saveNote() {
    if (current && note !== (current.note ?? "")) app.setRunNote(current.id, note);
  }

  function formatDate(iso: string): string {
    return iso.replace("T", " ");
  }

  function lineClass(line: string): string {
    if (line.startsWith("@@")) return "hunk";
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "";
  }
</script>

{#if app.history.length}
  <div class="runs">
    <div class="list">
      <!-- Barre toujours affichée : cocher un run ne décale pas les lignes sous le curseur. -->
      <div class="bulk" class:on={checked.length > 0}>
        <span class="muted">
          {checked.length ? t("{count} sélectionné(s)", { count: checked.length }) : t("Cocher deux runs pour les comparer")}
        </span>
        <button class="small" disabled={checked.length !== 2} onclick={compare} title={t("Comparer deux runs")}>
          {t("Comparer")}
        </button>
        <button class="small danger" disabled={!checked.length} onclick={() => remove(checked)}>
          <Icon name="trash" size={13} />{t("Supprimer")}
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th class="check">
              <input type="checkbox" checked={allChecked} onchange={() => (checked = allChecked ? [] : app.history.map((r) => r.id))} />
            </th>
            <th>Run</th>
            <th>{t("Note")}</th>
            <th>{t("Profil")}</th>
            <th>{t("Statut")}</th>
            <th>{t("Durée")}</th>
            <th class="num">{t("Dépl. max")}</th>
            <th class="num">{t("σVM max")}</th>
            <th class="num" title={t("Plus petite marge : résistance / Von Mises max")}>{t("RF min")}</th>
            <th>{t("Taille")}</th>
          </tr>
        </thead>
        <tbody>
          {#each app.history as r (r.id)}
            <tr class:current={selected === r.id} onclick={() => select(r.id)} ondblclick={() => app.showRun(r.id)}>
              <td class="check" onclick={(e) => e.stopPropagation()}>
                <input type="checkbox" bind:group={checked} value={r.id} />
              </td>
              <td class="mono">{formatDate(r.started)}</td>
              <td class="note" title={r.note}>{r.note}</td>
              <td>{app.profileLabel(r.profile)}</td>
              <td><span class="badge {r.status}">{statusLabel(r.status)}</span></td>
              <td>{r.duration != null ? `${r.duration} s` : "—"}</td>
              <td class="num">{fmt(r.headline?.depl_max)}{#if r.headline?.depl_max != null}<span class="muted unit">{units(r)[0]}</span>{/if}</td>
              <td class="num">{fmt(r.headline?.vmis_max)}{#if r.headline?.vmis_max != null}<span class="muted unit">{units(r)[1]}</span>{/if}</td>
              <td class="num" class:low={r.headline?.rf_min != null && r.headline.rf_min < 1}>{fmt(r.headline?.rf_min)}</td>
              <td class="muted">{formatSize(r.size)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="detail">
      {#if comparing}
        <div class="head">
          <strong class="mono">{comparing.a.id} → {comparing.b.id}</strong>
          <span class="spacer"></span>
          <button class="ghost icon" onclick={() => (comparing = null)} title={t("Fermer")}><Icon name="close" size={14} /></button>
        </div>
        <table class="pair">
          <tbody>
            <tr><th>{t("Note")}</th><td>{comparing.a.note}</td><td>{comparing.b.note}</td></tr>
            <tr><th>{t("Profil")}</th><td>{app.profileLabel(comparing.a.profile)}</td><td>{app.profileLabel(comparing.b.profile)}</td></tr>
            <tr>
              <th>{t("Statut")}</th>
              <td><span class="badge {comparing.a.status}">{statusLabel(comparing.a.status)}</span></td>
              <td><span class="badge {comparing.b.status}">{statusLabel(comparing.b.status)}</span></td>
            </tr>
            <tr><th>{t("Durée")}</th><td>{comparing.a.duration ?? "—"} s</td><td>{comparing.b.duration ?? "—"} s</td></tr>
            <tr>
              <th>{t("Dépl. max")}</th>
              <td>{fmt(comparing.a.headline?.depl_max)} {units(comparing.a)[0]}</td>
              <td>{fmt(comparing.b.headline?.depl_max)} {units(comparing.b)[0]}</td>
            </tr>
            <tr>
              <th>{t("σVM max")}</th>
              <td>{fmt(comparing.a.headline?.vmis_max)} {units(comparing.a)[1]}</td>
              <td>{fmt(comparing.b.headline?.vmis_max)} {units(comparing.b)[1]}</td>
            </tr>
            <tr><th>{t("RF min")}</th><td>{fmt(comparing.a.headline?.rf_min)}</td><td>{fmt(comparing.b.headline?.rf_min)}</td></tr>
          </tbody>
        </table>
        <div class="section">
          {t("Captures")}
          <span class="spacer"></span>
          <button class="ghost small" onclick={compareShots} disabled={pairWorking || !app.settings?.capture_command}
                  title={app.settings?.capture_command ? "" : t("Captures : régler la commande pvbatch dans les réglages globaux.")}>
            {pairWorking ? t("Captures en cours…") : t("Mêmes vues, même échelle")}
          </button>
        </div>
        {#if pair}
          {@const ca = pair[comparing.a.id]}
          {@const cb = pair[comparing.b.id]}
          {#if ca?.error || cb?.error}<p class="warn pad small">{ca?.error ?? cb?.error}</p>{/if}
          <div class="pairs">
            {#each ca?.views ?? [] as v (v)}
              <img src={api.captureUrl(comparing.a.id, "cmp", v, pairStamp)} alt={`${comparing.a.id} ${v}`} />
              <img src={api.captureUrl(comparing.b.id, "cmp", v, pairStamp)} alt={`${comparing.b.id} ${v}`} />
            {/each}
          </div>
        {/if}
        <div class="section">{t("Différences du .comm")}</div>
        {#if comparing.diff.length}
          <div class="diff mono">
            {#each comparing.diff as line, i (i)}<div class={lineClass(line)}>{line || " "}</div>{/each}
          </div>
        {:else}
          <p class="muted pad">{t("Les deux .comm sont identiques.")}</p>
        {/if}
      {:else if current}
        <div class="head">
          <strong class="mono">{current.id}</strong>
          <span class="badge {current.status}">{statusLabel(current.status)}</span>
          <span class="muted small">{app.profileLabel(current.profile)} · {app.limitsLabel(current.time_limit, current.memory_limit)}</span>
        </div>
        <div class="actions">
          <button class="small" onclick={() => app.showRun(current!.id)}><Icon name="file" size={13} />{t("Log")}</button>
          <button class="small" onclick={() => app.openParaview(current!.id)}><Icon name="eye" size={13} />ParaView</button>
          <button class="small" onclick={() => app.openRunDir(current!.id)}><Icon name="folder" size={13} />{t("Ouvrir le dossier")}</button>
          {#if current.status !== "running"}
            <button class="small danger" onclick={() => remove([current!.id])}><Icon name="trash" size={13} />{t("Supprimer")}</button>
          {/if}
        </div>
        <textarea
          class="note-input"
          rows="2"
          placeholder={t("Note : ce qui change dans ce run (matériau, charge, maillage…)")}
          bind:value={note}
          onblur={saveNote}
        ></textarea>
        {#if current.status === "ok" || current.status === "alarm"}
          <div class="section">{t("Résumé des résultats")}</div>
          <!-- currentId (valeur simple) : recréer l'objet du run ne relance pas la lecture du résumé. -->
          {#key currentId}<ResultPanel runId={currentId!} onheadline={setHeadline} />{/key}
        {/if}
        {#if viewing}
          <div class="section">
            <button class="ghost small" onclick={() => (viewing = null)}><Icon name="up" size={12} />{t("Fichiers")}</button>
            <span class="mono">{viewing.name}</span>
          </div>
          <div class="viewer">
            <CodeEditor value={viewing.text} readonly language={viewing.name.endsWith(".comm") || viewing.name.endsWith(".py") ? "python" : "plain"} />
          </div>
        {:else}
          <div class="section">{t("Fichiers")}</div>
          <ul class="files">
            {#each files as f (f.name)}
              <li>
                {#if TEXT_FILES.test(f.name)}
                  <button class="ghost link mono" onclick={() => view(f.name)}>{f.name}</button>
                {:else}
                  <span class="mono">{f.name}</span>
                {/if}
                <span class="muted">{formatSize(f.size)}</span>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>
  </div>
{:else}
  <div class="empty muted">{t("Aucun run pour ce projet.")}</div>
{/if}

<style>
  .runs {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .list {
    flex: 1.4;
    min-width: 0;
    overflow: auto;
  }
  .detail {
    flex: 1;
    min-width: 320px;
    max-width: 640px;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
    overflow: auto;
  }
  .bulk {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .bulk.on {
    background: var(--accent-soft);
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th,
  td {
    text-align: left;
    padding: 4px 10px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  th {
    font-weight: 500;
    color: var(--muted);
    font-size: 12px;
    position: sticky;
    top: 0;
    background: var(--panel);
  }
  .bulk + table th {
    top: 31px;
  }
  tbody tr {
    cursor: pointer;
  }
  tbody tr:hover {
    background: var(--hover);
  }
  tr.current {
    background: var(--accent-soft) !important;
  }
  .check {
    width: 24px;
    padding-right: 0;
  }
  .note {
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .spacer {
    flex: 1;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 6px 10px;
  }
  .small {
    font-size: 11.5px;
    padding: 2px 8px;
    gap: 4px;
  }
  .danger {
    color: var(--err);
  }
  .detail > * {
    flex: none;
  }
  .detail > .viewer,
  .detail > .diff {
    flex: 1;
  }
  .note-input {
    margin: 0 10px 6px;
    resize: vertical;
    font-size: 12px;
  }
  .section {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-top: 1px solid var(--border);
  }
  .files {
    list-style: none;
    margin: 0;
    padding: 2px 10px 8px;
  }
  .files li {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
    padding: 1px 0;
  }
  .link {
    padding: 0;
    color: var(--accent);
    font-size: 12px;
  }
  .viewer {
    flex: 1;
    min-height: 160px;
  }
  .pair th {
    position: static;
    width: 80px;
  }
  .pair td {
    white-space: normal;
  }
  .diff {
    white-space: pre;
    padding: 6px 10px;
    font-size: 11.5px;
    line-height: 1.45;
    background: var(--code-bg);
    overflow: auto;
    flex: 1;
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
  .pad {
    padding: 0 10px;
  }
  .num {
    text-align: right;
  }
  .unit {
    margin-left: 3px;
  }
  td.low {
    color: var(--err);
    font-weight: 600;
  }
  .warn {
    color: var(--warn);
  }
  .pairs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    padding: 4px 10px 10px;
  }
  .pairs img {
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fff;
  }
  .empty {
    padding: 16px;
  }
</style>
