<script lang="ts">
  import { app } from "./store.svelte";
  import { N_, t } from "./i18n.svelte";

  const SAVE_LABELS = {
    saved: N_("Enregistré"),
    dirty: N_("Modifié…"),
    saving: N_("Enregistrement…"),
    nodir: N_("Non enregistré (Ctrl+S)"),
    error: N_("Erreur d'enregistrement"),
  };
</script>

<footer>
  <span class="path mono" title={app.projectDir ?? ""}>{app.projectDir ?? t("Projet non enregistré")}</span>
  <span class="save" class:warn={app.saveState === "nodir" || app.saveState === "error"}>
    {t(SAVE_LABELS[app.saveState])}
  </span>
  <span class="spacer"></span>
  {#if app.running}<span class="running">{t("● Run en cours")}</span>{/if}
  <span>Code_Aster {app.settings?.aster_version ?? "?"}</span>
  <span class="units" title={t("Système d'unités du projet (Réglages → Projet)")}>{app.project.units}</span>
</footer>

<style>
  footer {
    grid-area: status;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 2px 10px;
    font-size: 11.5px;
    color: var(--muted);
    background: var(--panel);
    border-top: 1px solid var(--border);
  }
  .path {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
  }
  .warn {
    color: var(--warn);
  }
  .spacer {
    flex: 1;
  }
  .running {
    color: var(--accent);
  }
  .units {
    font-weight: 600;
    color: var(--text);
  }
</style>
