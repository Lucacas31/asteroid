<script lang="ts">
  import { api, type ImportResult } from "./api";
  import CodeEditor from "./CodeEditor.svelte";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let text = $state("");
  let result = $state<ImportResult | null>(null);
  let error = $state<string | null>(null);
  let mode = $state<"replace" | "append">("replace");
  let attachments = $state<Record<number, string>>({}); // unité → chemin choisi

  async function attach(unit: number) {
    const path = await app.pick("file", t("Fichier pour l'unité {unit}", { unit }));
    if (path) attachments[unit] = path;
  }
  let timer: ReturnType<typeof setTimeout> | undefined;

  function close() {
    app.importOpen = false;
  }

  function analyse(value: string) {
    text = value;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!text.trim()) {
        result = null;
        error = null;
        return;
      }
      try {
        result = await api.importComm({ text });
        error = null;
      } catch (e) {
        result = null;
        error = e instanceof Error ? e.message : String(e);
      }
    }, 250);
  }

  async function openFile() {
    const path = await app.pick("file", t("Importer un fichier .comm"), [`${t("Fichier de commandes")} | *.comm *.py *.com`]);
    if (!path) return;
    try {
      const res = await api.importComm({ path });
      text = res.text;
      result = res;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  function apply() {
    if (!result) return;
    app.applyImport(result.blocks, mode);
    for (const [unit, path] of Object.entries(attachments)) app.attachFile(Number(unit), path);
    close();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={close}>
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-label={t("Importer un .comm")}>
    <header>
      <strong>{t("Importer un .comm")}</strong>
      <button class="ghost icon" onclick={close} title={t("Fermer")}><Icon name="close" /></button>
    </header>
    <div class="body">
      <div class="editor">
        <div class="hint muted">
          {t("Colle le fichier entier ici, ou")}
          <button class="link" onclick={openFile}><Icon name="folder" size={14} />{t("ouvre un fichier…")}</button>
        </div>
        <div class="code">
          <CodeEditor value={text} onchange={analyse} />
        </div>
      </div>
      <aside>
        {#if error}
          <p class="error">{error}</p>
        {:else if result}
          <p><strong>{result.blocks.length}</strong> {t("bloc(s) détecté(s)")}</p>
          <ol class="blocks mono">
            {#each result.blocks as b (b.id)}
              <li>
                {#if b.command}
                  {#if b.concept}<span class="concept">{b.concept}</span>{" = "}{/if}{b.command}
                {:else}
                  <span class="muted">python : {b.text.split("\n")[0]}</span>
                {/if}
              </li>
            {/each}
          </ol>
          {#if result.units.length}
            <p class="muted">{t("Fichiers rattachés automatiquement :")}</p>
            <ul class="mono small">
              {#each result.units as u (u)}<li>{u}</li>{/each}
            </ul>
          {/if}
          {#if result.unattached.length}
            <p class="muted">{t("Unités à rattacher à un fichier :")}</p>
            <ul class="attach">
              {#each result.unattached as u (u.unit)}
                <li>
                  <span class="mono">{u.command} · UNITE={u.unit}</span>
                  {#if attachments[u.unit]}
                    <span class="mono path" title={attachments[u.unit]}>{attachments[u.unit].split("/").at(-1)}</span>
                  {/if}
                  <button class="small" onclick={() => attach(u.unit)}>
                    <Icon name="folder" size={13} />{attachments[u.unit] ? t("Changer") : t("Rattacher…")}
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
          {#each result.warnings.filter((w) => !result!.unattached.some((u) => w.includes(`UNITE=${u.unit}`) || w.includes(t("unité {unit}", { unit: u.unit })))) as w (w)}
            <p class="warn"><Icon name="alert" size={14} />{w}</p>
          {/each}
        {:else}
          <p class="muted">
            {t("Un bloc par commande, texte d'origine conservé (commentaires compris). DEBUT et FIN sont retirés : l'app les ajoute elle-même.")}
          </p>
        {/if}
      </aside>
    </div>
    <footer>
      <label><input type="radio" bind:group={mode} value="replace" />{t("Remplacer les blocs existants")}</label>
      <label><input type="radio" bind:group={mode} value="append" />{t("Ajouter à la suite")}</label>
      <span class="spacer"></span>
      <button onclick={close}>{t("Annuler")}</button>
      <button class="primary" disabled={!result?.blocks.length} onclick={apply}>
        {t("Importer {count} bloc(s)", { count: result?.blocks.length ?? "" })}
      </button>
    </footer>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(10, 12, 18, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dialog {
    width: min(1100px, 94vw);
    height: min(720px, 88vh);
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
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
  }
  header {
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
  }
  footer {
    border-top: 1px solid var(--border);
  }
  footer label {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .spacer {
    flex: 1;
  }
  .body {
    flex: 1;
    display: flex;
    min-height: 0;
  }
  .editor {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .hint {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
  }
  .link {
    border: none;
    background: none;
    color: var(--accent);
    padding: 0 2px;
  }
  .code {
    flex: 1;
    min-height: 0;
    border-top: 1px solid var(--border);
  }
  aside {
    width: 320px;
    padding: 10px 14px;
    overflow: auto;
    border-left: 1px solid var(--border);
  }
  aside p {
    margin: 0 0 8px;
  }
  .blocks {
    margin: 0 0 12px;
    padding-left: 22px;
    font-size: 12px;
  }
  .blocks li {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .concept {
    color: var(--accent);
  }
  .small {
    font-size: 12px;
    margin: 0 0 10px;
    padding-left: 18px;
  }
  .attach {
    list-style: none;
    margin: 0 0 10px;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .attach li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }
  .attach .path {
    color: var(--ok);
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
  }
  .attach button {
    margin-left: auto;
    font-size: 12px;
    padding: 2px 8px;
  }
  .warn {
    display: flex;
    gap: 6px;
    color: var(--warn);
  }
  .error {
    color: var(--err);
  }
</style>
