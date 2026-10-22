<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '../lib/desktop';
  import Icon from './Icon.svelte';

  interface UpdateInfo {
    current_version: string;
    latest_version: string | null;
    update_available: boolean;
  }

  let version = $state<string | null>(null);
  let loadingVersion = $state(true);
  let checking = $state(false);
  let opening = $state(false);
  let result = $state<UpdateInfo | null>(null);
  let error = $state('');

  onMount(() => {
    void invoke<string>('get_app_version')
      .then(value => { version = value; })
      .catch(() => { error = 'Could not read the installed version. Please try checking for updates.'; })
      .finally(() => { loadingVersion = false; });
  });

  async function checkForUpdates() {
    if (checking) return;
    checking = true; result = null; error = '';
    try {
      result = await invoke<UpdateInfo>('check_for_updates');
      version = result.current_version;
    } catch (cause) { error = String(cause); }
    finally { checking = false; }
  }

  async function openRelease() {
    if (opening) return;
    opening = true; error = '';
    try { await invoke('open_release_page'); }
    catch (cause) { error = String(cause); }
    finally { opening = false; }
  }
</script>

<section class="settings-card about-settings" aria-labelledby="about-heading">
  <div class="card-title"><Icon name="info" /><h2 id="about-heading">About</h2></div>
  <p class="muted">{version ? `Version ${version}` : loadingVersion ? 'Loading version…' : 'Version unavailable'}</p>
  <div class="form-actions">
    <button class="secondary" type="button" disabled={checking} onclick={() => void checkForUpdates()}>
      {checking ? 'Checking…' : 'Check for updates'}
    </button>
    {#if result?.update_available}
      <button class="secondary" type="button" disabled={opening || checking} onclick={() => void openRelease()}>{opening ? 'Opening…' : 'View release'}</button>
      <span class="muted">Download the installer from GitHub.</span>
    {/if}
  </div>
  <p class="update-status muted" role="status" aria-live="polite">
    {#if checking}Checking for updates…
    {:else if result?.update_available}Version {result.latest_version} is available.
    {:else if result?.latest_version}You’re up to date.
    {:else if result}No published releases are available yet.{/if}
  </p>
  {#if error}<p class="update-error" role="alert">{error}</p>{/if}
</section>
