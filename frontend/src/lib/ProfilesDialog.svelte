<script lang="ts">
  // Profils de run (communs à tous les projets), ouverts depuis le menu à côté de Run.
  import type { RunProfile, Settings } from "./api";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  let profiles = $state<RunProfile[]>(
    ($state.snapshot(app.settings!.run_profiles) as RunProfile[]).map((p) => ({ ...p, name: app.profileLabel(p.name) })),
  );

  function close() {
    app.profilesOpen = false;
  }

  async function save() {
    const kept = profiles.filter((p) => p.name.trim()).map((p) => ({ ...p, name: p.name.trim() }));
    await app.saveSettings({ ...($state.snapshot(app.settings!) as Settings), run_profiles: kept });
    close();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={close}>
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-label={t("Profils de run")}>
    <header>
      <strong>{t("Profils de run")}</strong>
      <button class="ghost icon" onclick={close} title={t("Fermer")}><Icon name="close" /></button>
    </header>
    <div class="body">
      <small class="muted">
        {t("Choisis au lancement (menu à côté de Run) : P time_limit et P memory_limit du .export. Temps vide : illimité. Le premier profil sert par défaut.")}
      </small>
      <div class="row head muted">
        <span>{t("Nom")}</span><span>{t("Temps limite (s)")}</span><span>{t("Mémoire limite (Mo)")}</span><span></span>
      </div>
      {#each profiles as p, i (i)}
        <div class="row">
          <input bind:value={p.name} />
          <input
            type="number"
            min="1"
            placeholder={t("illimité")}
            value={p.time_limit ?? ""}
            oninput={(e) => (p.time_limit = e.currentTarget.value === "" ? null : Number(e.currentTarget.value))}
          />
          <input type="number" min="128" step="128" bind:value={p.memory_limit} />
          <button class="ghost icon" title={t("Retirer")} onclick={() => profiles.splice(i, 1)}>
            <Icon name="trash" size={13} />
          </button>
        </div>
      {/each}
      <button class="ghost add" onclick={() => profiles.push({ name: t("Nouveau profil"), time_limit: 600, memory_limit: 4096 })}>
        <Icon name="plus" size={13} />{t("Ajouter un profil")}
      </button>
    </div>
    <footer>
      <button class="ghost" onclick={close}>{t("Annuler")}</button>
      <button class="primary" onclick={save}><Icon name="save" />{t("Enregistrer")}</button>
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
    width: min(560px, 92vw);
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
  }
  header,
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
  }
  header {
    border-bottom: 1px solid var(--border);
  }
  footer {
    justify-content: flex-end;
    gap: 8px;
    border-top: 1px solid var(--border);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 14px;
  }
  .row {
    display: grid;
    grid-template-columns: 1fr 130px 130px 28px;
    gap: 6px;
    align-items: center;
  }
  .row.head {
    font-size: 11px;
  }
  .add {
    align-self: flex-start;
  }
</style>
