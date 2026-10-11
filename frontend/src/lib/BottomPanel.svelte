<script lang="ts">
  import CodeEditor from "./CodeEditor.svelte";
  import Icon from "./Icon.svelte";
  import RunsPanel from "./RunsPanel.svelte";
  import { app, statusLabel, type BottomTab } from "./store.svelte";
  import { formatValue } from "./format";
  import { i18n, N_, t } from "./i18n.svelte";

  const TABS: { id: BottomTab; label: string }[] = [
    { id: "comm", label: N_("Aperçu .comm") },
    { id: "export", label: ".export" },
    { id: "log", label: N_("Log du run") },
    { id: "history", label: N_("Runs") },
  ];

  let logEl = $state<HTMLPreElement>();
  let follow = $state(true);
  let height = $state(300);

  let selectedLines = $derived.by((): [number, number] | null => {
    const info = app.selected ? app.blockInfo.get(app.selected.id) : undefined;
    return info ? [info.start_line, info.end_line] : null;
  });

  let counts = $derived.by(() => {
    const c = { F: 0, E: 0, A: 0 };
    for (const m of app.run?.messages ?? []) c[m.level] += 1;
    return c;
  });

  $effect(() => {
    void app.log.length;
    if (follow && logEl) queueMicrotask(() => logEl && (logEl.scrollTop = logEl.scrollHeight));
  });

  /** Clic dans l'aperçu : sélectionne le bloc qui a écrit cette ligne. */
  function selectBlockAt(line: number) {
    const info = app.preview?.blocks.find((b) => b.start_line <= line && line <= b.end_line);
    if (info) app.selectedId = info.id;
  }

  function onLogScroll() {
    if (!logEl) return;
    follow = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 30;
  }

  function startResize(e: PointerEvent) {
    const startY = e.clientY;
    const startH = height;
    const move = (ev: PointerEvent) => {
      height = Math.min(Math.max(startH + startY - ev.clientY, 120), window.innerHeight - 200);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function selectTab(id: BottomTab) {
    if (app.bottomTab === id && app.bottomOpen) app.bottomOpen = false;
    else {
      app.bottomTab = id;
      app.bottomOpen = true;
    }
  }
</script>

<section class:closed={!app.bottomOpen} style:height={app.bottomOpen ? `${height}px` : undefined}>
  {#if app.bottomOpen}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="resizer" onpointerdown={startResize}></div>
  {/if}
  <nav>
    {#each TABS as tab (tab.id)}
      <button class="ghost tab" class:active={app.bottomOpen && app.bottomTab === tab.id} onclick={() => selectTab(tab.id)}>
        {t(tab.label)}
        {#if tab.id === "log" && app.run}
          <span class="badge {app.run.status}">{statusLabel(app.run.status)}</span>
        {/if}
        {#if tab.id === "comm" && app.preview?.warnings.length}
          <span class="badge A">{app.preview.warnings.length}</span>
        {/if}
      </button>
    {/each}
    <span class="spacer"></span>
    <button class="ghost icon" onclick={() => (app.bottomOpen = !app.bottomOpen)} title={t("Replier / déplier")}>
      <Icon name={app.bottomOpen ? "chevron" : "chevronUp"} />
    </button>
  </nav>

  {#if app.bottomOpen}
    <div class="content">
      {#if app.bottomTab === "comm"}
        <div class="split">
          <div class="code">
            <CodeEditor
              value={app.preview?.comm ?? ""}
              readonly
              highlightLines={selectedLines}
              onlineclick={selectBlockAt}
            />
          </div>
          {#if app.preview?.warnings.length}
            <ul class="warnings">
              {#each app.preview.warnings as w, i (i)}
                {@const unit = app.preview.unattached.find((u) => w.includes(`UNITE=${u.unit}`) || w.includes(t("unité {unit}", { unit: u.unit })))}
                <li>
                  <Icon name="alert" size={14} />
                  <span>
                    {w}
                    {#if unit}
                      <button class="attach" onclick={() => app.pickAndAttach(unit.unit)}>{t("Rattacher un fichier…")}</button>
                    {/if}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {:else if app.bottomTab === "export"}
        <div class="code">
          <CodeEditor value={app.preview?.export ?? ""} readonly language="plain" />
        </div>
      {:else if app.bottomTab === "log"}
        {#if app.run}
          <div class="log-layout">
            <div class="log-head">
              <span class="mono">{app.run.id}</span>
              <span class="badge {app.run.status}">{statusLabel(app.run.status)}</span>
              {#if app.run.diagnostic}<span class="muted mono">{app.run.diagnostic}</span>{/if}
              {#if app.run.duration != null}<span class="muted">{app.run.duration} s</span>{/if}
              {#if app.run.headline}
                {@const h = app.run.headline}
                {@const [len, stress] = app.run.units === "m-N-Pa" ? ["m", "Pa"] : ["mm", "MPa"]}
                <button class="ghost headline" onclick={() => (app.bottomTab = "history")} title={t("Résumé des résultats (onglet Runs)")}>
                  {t("Dépl. max")} <strong>{formatValue(h.depl_max, i18n.locale)}</strong> {len}
                  · {t("σVM max")} <strong>{formatValue(h.vmis_max, i18n.locale)}</strong> {stress}
                  {#if h.rf_min != null}· {t("RF min")} <strong class:low={h.rf_min < 1}>{formatValue(h.rf_min, i18n.locale)}</strong>{/if}
                </button>
              {/if}
              <span class="spacer"></span>
              {#if app.run.status !== "running"}
                <span class="counts">
                  <span class="badge F">{t("{count} erreur(s)", { count: counts.F + counts.E })}</span>
                  <span class="badge A">{t("{count} alarme(s)", { count: counts.A })}</span>
                </span>
              {/if}
            </div>
            <div class="log-body">
              <pre class="log" bind:this={logEl} onscroll={onLogScroll}>{app.log.join("\n")}</pre>
              {#if app.run.messages.length}
                <ul class="messages">
                  {#each app.run.messages as m, i (i)}
                    <li>
                      <button
                        class="ghost msg"
                        disabled={!m.block_id}
                        onclick={() => m.block_id && (app.selectedId = m.block_id)}
                        title={m.block_id ? t("Aller au bloc") : ""}
                      >
                        <span class="badge {m.level}">&lt;{m.level}&gt;</span>
                        <span class="mono id">{m.id}{m.count > 1 ? ` ×${m.count}` : ""}</span>
                        <span class="text">{m.text}</span>
                      </button>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          </div>
        {:else}
          <div class="empty muted">{t("Aucun run affiché. Lance un calcul (Ctrl+Entrée) ou choisis un run dans l'historique.")}</div>
        {/if}
      {:else if app.bottomTab === "history"}
        <RunsPanel />
      {/if}
    </div>
  {/if}
</section>

<style>
  section {
    grid-area: bottom;
    position: relative;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border-top: 1px solid var(--border);
    min-height: 0;
  }
  .resizer {
    position: absolute;
    top: -3px;
    left: 0;
    right: 0;
    height: 6px;
    cursor: ns-resize;
    z-index: 5;
  }
  nav {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px 6px;
    border-bottom: 1px solid var(--border);
  }
  section.closed nav {
    border-bottom: none;
  }
  .tab {
    font-size: 12px;
    padding: 3px 10px;
    color: var(--muted);
  }
  .tab.active {
    color: var(--text);
    background: var(--hover);
  }
  .spacer {
    flex: 1;
  }
  .content {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .split {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .code {
    flex: 1;
    min-height: 0;
    min-width: 0;
  }
  .warnings {
    width: 320px;
    margin: 0;
    padding: 8px 12px;
    list-style: none;
    border-left: 1px solid var(--border);
    overflow: auto;
    color: var(--warn);
  }
  .warnings li {
    display: flex;
    gap: 6px;
    margin-bottom: 6px;
  }
  .warnings .attach {
    display: inline-flex;
    margin-top: 4px;
    font-size: 11.5px;
    padding: 1px 8px;
    color: var(--text);
  }
  .log-layout {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
  .log-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 10px;
    border-bottom: 1px solid var(--border);
  }
  .headline {
    font-size: 12px;
    padding: 1px 8px;
    gap: 4px;
  }
  .headline .low {
    color: var(--err);
  }
  .counts {
    display: flex;
    gap: 6px;
  }
  .log-body {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .log {
    flex: 1;
    margin: 0;
    padding: 8px 10px;
    overflow: auto;
    background: var(--code-bg);
    white-space: pre;
    font-size: 11.5px;
    line-height: 1.45;
  }
  .messages {
    width: 42%;
    max-width: 560px;
    margin: 0;
    padding: 6px;
    list-style: none;
    overflow: auto;
    border-left: 1px solid var(--border);
  }
  .msg {
    width: 100%;
    align-items: flex-start;
    justify-content: flex-start;
    text-align: left;
    white-space: normal;
    padding: 6px;
    opacity: 1 !important;
  }
  .msg .id {
    color: var(--muted);
    flex: none;
  }
  .msg .text {
    white-space: pre-wrap;
    font-size: 12px;
  }
  .empty {
    padding: 16px;
  }
</style>
