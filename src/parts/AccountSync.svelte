<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke, listen } from '../lib/desktop';
  import Icon from './Icon.svelte';

  interface AccountState {
    revision: number;
    configured: boolean;
    email: string | null;
    busy: boolean;
    signing_in: boolean;
    last_synced_ms: number | null;
    message: string;
    error: string | null;
  }
  let account = $state<AccountState | null>(null);
  let working = $state(false);
  let activeCommand = $state('');
  let error = $state('');
  const busy = $derived(working || account?.busy);

  function accept(incoming: AccountState) {
    if (!account || incoming.revision >= account.revision) { account = incoming; error = ''; }
  }
  onMount(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void (async () => {
      try {
        const stop = await listen<AccountState>('sync-state', event => { if (!disposed) accept(event.payload); });
        if (disposed) { stop(); return; }
        unlisten = stop;
        const initial = await invoke<AccountState>('get_account_state');
        if (!disposed) accept(initial);
      } catch { if (!disposed) error = 'Account settings could not be loaded. Please reopen Settings.'; }
    })();
    return () => { disposed = true; unlisten?.(); };
  });

  async function action(command: string) {
    if (busy) return;
    working = true; activeCommand = command; error = '';
    try { accept(await invoke<AccountState>(command)); }
    catch (cause) { error = String(cause); }
    finally { working = false; activeCommand = ''; }
  }
  async function cancel() {
    try { await invoke('cancel_google_sign_in'); }
    catch (cause) { error = String(cause); }
  }
</script>

<section class="settings-card account-settings" aria-labelledby="account-heading">
  <div class="card-title"><Icon name="account" /><h2 id="account-heading">Account &amp; sync</h2></div>
  <p class="muted">Sync tasks and focus history across devices. App settings stay on this device.</p>
  {#if account?.email}<p class="account-email">Signed in as <strong>{account.email}</strong></p>{/if}
  {#if account && !account.configured}<p class="update-status muted">Google sign-in is not enabled in this build. Your tasks and focus history are saved on this device.</p>
  {:else if account && !account.email && !account.signing_in}<p class="update-status muted">Signing in syncs the tasks and focus history already on this device with your Google account.</p>{/if}
  <div class="form-actions">
    {#if account?.email}
      <button class="secondary" type="button" disabled={busy} onclick={() => void action('sync_tasks_now')}>{busy ? 'Syncing…' : 'Sync now'}</button>
      <button class="secondary" type="button" disabled={busy} onclick={() => void action('sign_out_account')}>Sign out</button>
    {:else}
      <button class="secondary" type="button" disabled={!account?.configured || busy} onclick={() => void action('sign_in_with_google')}>{account?.signing_in || activeCommand === 'sign_in_with_google' ? 'Signing in…' : 'Sign in with Google'}</button>
      {#if account?.signing_in}<button class="secondary" type="button" onclick={() => void cancel()}>Cancel sign-in</button>{/if}
    {/if}
  </div>
  <p class="update-status muted" role="status" aria-live="polite">{account?.configured ? account.message : ''}</p>
  {#if account?.last_synced_ms}<p class="update-status muted">Last synced {new Date(account.last_synced_ms).toLocaleString()}</p>{/if}
  {#if error || account?.error}<p class="update-error" role="alert">{error || account?.error}</p>{/if}
  {#if account?.email}<p class="update-status muted">Signing out keeps your tasks and focus history on this device.</p>{/if}
</section>
