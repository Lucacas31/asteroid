<script lang="ts">
  // Commandes externes (Code_Aster, arrêt, ParaView) : partagées par l'écran de premier
  // lancement et les réglages globaux. L'app ne devine rien : elle exécute ces commandes.
  import { api, type Settings } from "./api";
  import { N_, t } from "./i18n.svelte";

  let { draft }: { draft: Settings } = $props();

  async function suggest() {
    draft.capture_command = (await api.captureSuggestion(draft.paraview_command)).command;
  }

  const RUN_VARS: [string, string][] = [
    ["{run_dir}", N_("chemin absolu du dossier du run (dossier courant de la commande)")],
    ["{export}", N_("fichier .export du run, relatif au dossier du run")],
    ["{comm}", N_("fichier .comm du run")],
    ["{mesh}", N_("maillage copié dans le run")],
    ["{run_id}", N_("identifiant du run (horodatage), utile pour nommer un conteneur")],
    ["{image}", N_("image Docker ci-dessous")],
  ];
</script>

<label>
  <span>{t("Commande de lancement")}</span>
  <textarea rows="4" bind:value={draft.run_command} spellcheck="false"></textarea>
  <small class="muted">
    {t("Exécutée par bash depuis le dossier du run ; elle doit lancer")} <code>run_aster</code> {t("sur le .export. Exemples : Docker (valeur par défaut), Apptainer, ou")} <code>run_aster {"{export}"}</code> {t("pour une installation locale.")}
  </small>
</label>
<table class="vars">
  <tbody>
    {#each RUN_VARS as [name, help] (name)}
      <tr><td><code>{name}</code></td><td class="muted">{t(help)}</td></tr>
    {/each}
  </tbody>
</table>
<label>
  <span>{t("Image Docker")}</span>
  <input bind:value={draft.docker_image} spellcheck="false" />
  <small class="muted">{t("Variable")} <code>{"{image}"}</code> {t("des commandes ; inutile sans Docker.")}</small>
</label>
<label>
  <span>{t("Commande d'arrêt")}</span>
  <input bind:value={draft.stop_command} spellcheck="false" />
  <small class="muted">{t("Bouton Stop, mêmes variables. Vide : le processus de la commande de lancement est tué.")}</small>
</label>
<label>
  <span>{t("Commande ParaView")}</span>
  <input bind:value={draft.paraview_command} spellcheck="false" />
  <small class="muted">
    {t("Chemin complet si")} <code>paraview</code> {t("n'est pas dans le PATH. Variables :")} <code>{"{script}"}</code> {t("(script qui charge le plugin MEDReader et ouvre les .rmed),")} <code>{"{rmed}"}</code>, <code>{"{run_dir}"}</code>
  </small>
</label>

<label>
  <span>{t("Commande des captures (pvbatch)")}</span>
  <div class="with-button">
    <input bind:value={draft.capture_command} spellcheck="false" placeholder={t("vide : pas de captures")} />
    <button type="button" onclick={suggest} title={t("pvbatch est livré avec ParaView, dans le même dossier bin/")}>
      {t("Déduire de la commande ParaView")}
    </button>
  </div>
  <small class="muted">
    {t("Images du résultat (déformée, Von Mises) à la fin de chaque run, dans l'onglet Runs. Variable :")} <code>{"{script}"}</code>
  </small>
</label>

<style>
  .with-button {
    display: flex;
    gap: 6px;
  }
  .with-button input {
    flex: 1;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  label > span {
    font-weight: 500;
  }
  textarea,
  input {
    font-family: var(--mono);
    font-size: 12px;
  }
  .vars {
    margin-top: -6px;
    border-collapse: collapse;
    font-size: 11.5px;
  }
  .vars td {
    padding: 1px 10px 1px 0;
    vertical-align: top;
  }
</style>
