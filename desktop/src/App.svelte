<script lang="ts">
  import { onMount } from 'svelte';
  import { TimerClient } from './lib/client';
  import { transport, invoke, listen } from './lib/desktop';
  import { actionLabel, formatTime, phaseLabel, type Snapshot, type Command, type DesktopInfo, type Settings } from './lib/types';
  import Compact from './parts/Compact.svelte';
  import Icon from './parts/Icon.svelte';

  const compact = new URLSearchParams(location.search).get('view') === 'compact';
  let snapshot = $state<Snapshot | null>(null);
  let info = $state<DesktopInfo | null>(null);
  let error = $state('');
  let busy = $state(false);
  let page = $state('timer');
  let draft = $state<Settings | null>(null);
  let finishDialog = $state<HTMLDialogElement>(null!);
  let audio: AudioContext | undefined;
  const client = new TimerClient(transport, incoming => { snapshot = incoming; });
  let progress = $derived(snapshot?.duration_ms ? Math.min(1, snapshot.active_ms / snapshot.duration_ms) : 0);
  let recentFocus = $derived(snapshot?.records.filter(record => ['focus', 'stopwatch'].includes(record.phase)).reduce((sum, record) => sum + record.active_ms, 0) ?? 0);

  async function send(command: Command) {
    if (busy) return;
    busy = true; error = '';
    try { await client.send(command); } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function native(command: string) {
    try { await invoke(command); } catch (e) { error = String(e); }
  }
  async function playSound() {
    try {
      audio ??= new AudioContext(); await audio.resume();
      const oscillator = audio.createOscillator(); const gain = audio.createGain();
      oscillator.frequency.value = 660; gain.gain.setValueAtTime(0.08, audio.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.3);
      oscillator.connect(gain); gain.connect(audio.destination); oscillator.start(); oscillator.stop(audio.currentTime + 0.3);
    } catch (e) { error = `Audio unavailable: ${String(e)}`; }
  }
  function navigate(destination: string) { page = destination; if (destination === 'settings' && snapshot) draft = { ...snapshot.settings }; }
  function primary() {
    if (snapshot?.pending_save) void send({ type: 'retry_save' });
    else { if (!compact && snapshot?.settings.sound_enabled) { audio ??= new AudioContext(); void audio.resume(); } void send({ type: 'toggle' }); }
  }
  function keyboard(event: KeyboardEvent) {
    if (compact || !snapshot || event.target instanceof HTMLInputElement || finishDialog?.open) return;
    if (event.code === 'Space' && (event.target === document.body || event.target instanceof HTMLElement && event.target.classList.contains('timer-face'))) {
      event.preventDefault(); primary();
    }
  }
  onMount(() => {
    document.documentElement.classList.toggle('compact-document', compact);
    let disposed = false;
    const listeners: (() => void)[] = [];
    async function register() {
      try {
        await client.start();
        info = await invoke<DesktopInfo>('desktop_info');
        if (!compact) {
          for (const [event, callback] of [
            ['finish-requested', () => finishDialog?.showModal()],
            ['session-completed', () => { if (snapshot?.settings.sound_enabled) void playSound(); }],
          ] as const) {
            const stop = await listen(event, callback); if (disposed) stop(); else listeners.push(stop);
          }
        }
      } catch (e) { if (!disposed) error = String(e); }
    }
    void register();
    return () => { disposed = true; client.dispose(); listeners.forEach(stop => stop()); void audio?.close(); };
  });
</script>

<svelte:window onkeydown={keyboard} />
{#if compact && snapshot}
  <Compact state={snapshot} {busy} send={primary} error={message => { error = message; void invoke('open_main'); }} />
{:else if compact}
  <div class="compact-loading" role="status">{error ? 'Needs attention' : 'Connecting…'}</div>
{:else}
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><Icon name="timer" size={22} /></span><strong>Pomodoro<span>Find your focus.</span></strong></div>
      <nav aria-label="Main navigation">
        {#each [{ id: 'timer', label: 'Timer', icon: 'timer' }, { id: 'history', label: 'Sessions', icon: 'history' }, { id: 'settings', label: 'Settings', icon: 'settings' }] as item}
          <button class:active={page === item.id} aria-current={page === item.id ? 'page' : undefined} disabled={!snapshot && item.id !== 'timer'} onclick={() => navigate(item.id)}><Icon name={item.icon} />{item.label}</button>
        {/each}
      </nav>
      <div class="sidebar-footer"><span class="beta-badge">BETA PROTOTYPE</span><p>A little space for deep work.</p><span class="local-status"><i></i> {snapshot?.last_error ? 'Needs attention' : snapshot ? 'Saved on this device' : 'Connecting'}</span></div>
    </aside>
    <main>
      <header class="page-header"><div><p class="eyebrow">YOUR FOCUS SPACE</p><h1>{page === 'timer' ? 'Make time for what matters.' : page === 'history' ? 'Your recent sessions.' : 'Make it your own.'}</h1></div>
        <button class="secondary compact-entry" onclick={() => void native('open_compact')} disabled={!snapshot}><Icon name="compact" />Compact mode</button></header>
      {#if error || snapshot?.last_error}
        <div class="error-banner" role="alert"><strong>Needs attention</strong><p>{error || snapshot?.last_error}</p>{#if snapshot?.pending_save}<button onclick={() => void send({ type: 'retry_save' })} disabled={busy}>Retry save</button>{/if}</div>
      {/if}
      {#if !snapshot}
        <div class="empty-state"><Icon name="timer" size={40} /><h2>{error ? 'Desktop connection unavailable' : 'Connecting to your timer…'}</h2><p>{error ? 'Launch the installed app or use npm run tauri dev.' : 'Your session is managed on this device.'}</p></div>
      {:else if page === 'timer'}
        {#if snapshot.recovered}<div class="recovery-banner" role="status">Your previous session was restored paused. Resume when you’re ready; time while the app was closed is excluded.</div>{/if}
        <div class="timer-layout">
          <section class="timer-card" aria-label="Timer">
            <div class="mode-switch" role="group" aria-label="Timer mode">
              <button aria-pressed={snapshot.phase !== 'stopwatch'} disabled={snapshot.status !== 'idle' || busy} onclick={() => void send({ type: 'set_mode', mode: 'focus' })}>Pomodoro</button>
              <button aria-pressed={snapshot.phase === 'stopwatch'} disabled={snapshot.status !== 'idle' || busy} onclick={() => void send({ type: 'set_mode', mode: 'stopwatch' })}>Stopwatch</button>
            </div>
            <div class="timer-face" class:break-phase={snapshot.phase.includes('break')} role="group" aria-label={`${phaseLabel[snapshot.phase]} timer`}>
              <svg class="timer-ring" viewBox="0 0 300 300" aria-hidden="true"><circle class="ring-track" cx="150" cy="150" r="138" /><circle class="ring-progress" cx="150" cy="150" r="138" pathLength="100" stroke-dasharray={`${snapshot.phase === 'stopwatch' ? 0 : 100 * (1 - progress)} 100`} /></svg>
              <div class="timer-inner"><p class="phase-label">{phaseLabel[snapshot.phase]}</p><span class="time-digits" role="timer">{formatTime(snapshot.display_seconds)}</span>
                <span class="state-label" class:paused={snapshot.status === 'paused'}>{snapshot.status === 'running' ? 'One thing at a time.' : snapshot.status === 'paused' ? 'Paused · take a breath' : 'Ready when you are.'}</span>
                {#if snapshot.phase !== 'stopwatch'}<p class="cycle-label">Session {snapshot.cycle} of {snapshot.cycle_interval}</p><div class="cycle-dots" aria-hidden="true">{#each Array(snapshot.cycle_interval) as _, i}<i class:filled={i < snapshot.cycle}></i>{/each}</div>{/if}
              </div>
            </div>
            <div class="timer-actions"><button class="primary" onclick={primary} disabled={busy}><Icon name={snapshot.status === 'running' ? 'pause' : 'play'} />{actionLabel(snapshot)}</button>
              {#if snapshot.status !== 'idle'}<button class="secondary" onclick={() => finishDialog.showModal()} disabled={busy || snapshot.pending_save}><Icon name="finish" />{snapshot.phase.includes('break') ? 'Skip break' : 'Finish'}</button>{/if}</div>
            <p class="keyboard-hint">Space to activate the focused timer control</p>
          </section>
          <aside class="focus-aside">
            <section class="note-card"><p class="eyebrow">A MOMENT TO BEGIN</p><h2>Less switching.<br />More doing.</h2><p>Pick one thing to work on. Give it your attention, then make room for a break.</p><div class="note-line"></div><span>Progress happens one session at a time.</span></section>
            <section class="summary-card"><div class="card-title"><Icon name="history" /><h2>Recent focus</h2></div><strong>{Math.floor(recentFocus / 60_000)}<small> min</small></strong><p>Across your latest 20 saved sessions</p><div class="summary-row"><span>Saved sessions</span><b>{snapshot.records.length}</b></div></section>
            <section class="next-card"><span class="phase-dot"></span><div><h2>{snapshot.phase === 'stopwatch' ? 'Your pace, your choice' : snapshot.phase === 'focus' ? 'Then, a well-earned break' : 'Next, a fresh focus session'}</h2><p>{snapshot.phase === 'stopwatch' ? 'Finish whenever you’re ready.' : snapshot.phase === 'focus' ? `${snapshot.cycle === snapshot.cycle_interval ? snapshot.settings.long_break_minutes : snapshot.settings.short_break_minutes} minute ${snapshot.cycle === snapshot.cycle_interval ? 'long' : 'short'} break · starts when you choose` : `${snapshot.settings.focus_minutes} minutes to focus`}</p></div></section>
          </aside>
        </div>
      {:else if page === 'history'}
        <section class="history-card"><div class="card-title"><Icon name="history" /><h2>Saved on this device</h2></div><p class="muted">Latest 20 sessions. Active time excludes pauses.</p>
          {#if snapshot.records.length === 0}<div class="empty-state"><h3>Your first session starts here.</h3><p>Finish a focus session or stopwatch to see it here.</p><button class="primary" onclick={() => navigate('timer')}>Open timer</button></div>
          {:else}<div class="table-wrap"><table><thead><tr><th>Session</th><th>Started</th><th>Active time</th><th>Outcome</th></tr></thead><tbody>{#each snapshot.records as record (record.id)}<tr><td>{phaseLabel[record.phase]}</td><td>{new Date(record.started_unix_ms).toLocaleString()}</td><td>{formatTime(Math.floor(record.active_ms / 1000))}</td><td><span class="outcome">{record.outcome}</span></td></tr>{/each}</tbody></table></div>{/if}
        </section>
      {:else if draft}
        <section class="settings-card"><div class="card-title"><Icon name="settings" /><h2>Timer preferences</h2></div><p class="muted">Duration changes apply to the next session.</p>
          <form onsubmit={event => { event.preventDefault(); if (draft) void send({ type: 'configure', settings: { ...draft } }); }}>
            <div class="settings-grid">{#each [{ key: 'focus_minutes', label: 'Focus duration', max: 60 }, { key: 'short_break_minutes', label: 'Short break', max: 30 }, { key: 'long_break_minutes', label: 'Long break', max: 60 }, { key: 'long_break_interval', label: 'Sessions before a long break', max: 10 }] as field}<label>{field.label}<span class="input-unit"><input type="number" min="1" max={field.max} step="1" required value={draft[field.key as keyof Settings] as number} oninput={event => { if (draft) draft = { ...draft, [field.key]: event.currentTarget.valueAsNumber }; }} />{field.key.includes('minutes') ? 'min' : 'sessions'}</span></label>{/each}</div>
            <label class="checkbox-row"><input type="checkbox" bind:checked={draft.sound_enabled} />Play a completion tone</label><div class="form-actions"><button class="primary" type="submit" disabled={busy || snapshot.pending_save}>Save preferences</button><button class="secondary" type="button" onclick={() => { draft = { ...snapshot!.settings }; }}>Reset changes</button></div>
          </form>
        </section>
        <section class="settings-card desktop-checks"><div class="card-title"><Icon name="check" /><h2>Desktop checks</h2></div><p class="muted">Use these on your native platform while we validate the beta.</p><div class="form-actions"><button class="secondary" onclick={() => void native('test_notification')}>Test notification</button><button class="secondary" onclick={() => void playSound()}>Test sound</button></div>
          {#if info}<dl><dt>Platform</dt><dd>{info.os} · {info.arch}</dd><dt>Tray</dt><dd>{info.tray}</dd><dt>Beta data</dt><dd class="data-path">{info.data_directory}</dd></dl>{/if}
          <p class="muted">Closing the app checkpoints an active session for paused recovery. Existing Python data stays in its own profile.</p>
        </section>
      {/if}
    </main>
  </div>
  <dialog bind:this={finishDialog}><div class="dialog-content"><p class="eyebrow">{snapshot?.phase.includes('break') ? 'SKIP BREAK' : 'FINISH SESSION'}</p><h2>{snapshot?.phase.includes('break') ? 'Ready to focus again?' : 'Finish this session?'}</h2><p>Your active time will be saved on this device.</p><div class="form-actions"><button class="secondary" onclick={() => finishDialog.close()}>Keep {snapshot?.phase.includes('break') ? 'resting' : 'focusing'}</button><button class="primary" onclick={() => { finishDialog.close(); void send({ type: 'finish' }); }}>Finish and save</button></div></div></dialog>
{/if}
