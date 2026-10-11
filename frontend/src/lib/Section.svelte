<script lang="ts">
  // Catégorie repliable d'un formulaire de réglages.
  import type { Snippet } from "svelte";

  let { title, open = false, children }: { title: string; open?: boolean; children: Snippet } = $props();
</script>

<details {open}>
  <summary>{title}</summary>
  <div class="body">{@render children()}</div>
</details>

<style>
  details {
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  summary {
    cursor: pointer;
    padding: 8px 12px;
    font-weight: 600;
    user-select: none;
  }
  summary:hover {
    background: var(--hover);
    border-radius: 8px;
  }
  details[open] > summary {
    border-bottom: 1px solid var(--border);
    border-radius: 8px 8px 0 0;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }
</style>
