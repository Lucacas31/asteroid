<script lang="ts">
  // Premier lancement : l'utilisateur indique comment lancer Code_Aster et ParaView.
  // Rien n'est détecté automatiquement ; les valeurs proposées sont des exemples.
  import type { Settings } from "./api";
  import CommandSettings from "./CommandSettings.svelte";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { i18n, t } from "./i18n.svelte";

  let draft = $state<Settings>($state.snapshot(app.settings!) as Settings);

  async function save() {
    await app.saveSettings({ ...($state.snapshot(draft) as Settings), configured: true });
  }
</script>

<div class="backdrop">
  <div class="dialog" role="dialog" aria-label={t("Premiers réglages")}>
    <header>
      <img src="/logo.png" alt="" width="40" height="40" />
      <div>
        <strong>{t("Bienvenue dans Asteroid")}</strong>
        <div class="muted small">
          {t("Asteroid prépare les fichiers du calcul puis exécute vos commandes : indiquez comment lancer Code_Aster et ParaView sur cette machine. Tout reste modifiable dans Réglages → Réglages globaux.")}
        </div>
      </div>
    </header>
    <div class="form">
      <label class="lang">
        <span>{t("Langue de l'interface")}</span>
        <select
          value={draft.language}
          onchange={(e) => {
            draft.language = e.currentTarget.value;
            app.setLanguage(draft.language);
          }}
        >
          {#each i18n.languages as lang (lang.code)}<option value={lang.code}>{lang.name}</option>{/each}
        </select>
      </label>
      <CommandSettings {draft} />
      <p class="muted small">
        {t("Réglages enregistrés dans")} <code>{app.paths?.config}</code>{t(", bibliothèque de matériaux dans")}
        <code>{app.paths?.materials}</code>.
      </p>
    </div>
    <footer>
      <button class="primary" onclick={save}><Icon name="check" />{t("Enregistrer et commencer")}</button>
    </footer>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 150;
    background: rgba(10, 12, 18, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dialog {
    width: min(760px, 92vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
  }
  header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
  }
  header strong {
    font-size: 15px;
  }
  .form {
    overflow: auto;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .lang {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-weight: 500;
  }
  .lang select {
    align-self: flex-start;
  }
  .small {
    font-size: 12px;
  }
  p {
    margin: 0;
  }
  code {
    word-break: break-all;
  }
  footer {
    display: flex;
    justify-content: flex-end;
    padding: 10px 16px;
    border-top: 1px solid var(--border);
  }
</style>
