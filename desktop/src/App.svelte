<script lang="ts">
  import { onMount } from 'svelte';
  import { TimerClient } from './lib/client';
  import { mergeUnedited } from './lib/drafts';
  import { transport, invoke, listen } from './lib/desktop';
  import { actionLabel, formatTime, phaseLabel, type Snapshot, type Command, type DesktopState, type DesktopPreferences, type Settings, type Task, type DailyTotals, type SessionRecord } from './lib/types';
  import Compact from './parts/Compact.svelte';
  import Icon from './parts/Icon.svelte';

  const compact = new URLSearchParams(location.search).get('view') === 'compact';
  let snapshot = $state<Snapshot | null>(null);
  let error = $state('');
  let busy = $state(false);
  let page = $state('timer');
  let draft = $state<Settings | null>(null);
  let finishDialog = $state<HTMLDialogElement>(null!);
  let confirmDialog = $state<HTMLDialogElement>(null!);
  let pendingConfirm = $state<{ heading: string; message: string; confirmLabel: string; action: () => void } | null>(null);
  function askConfirm(heading: string, message: string, confirmLabel: string, action: () => void) {
    if (!confirmDialog || confirmDialog.open) return;
    pendingConfirm = { heading, message, confirmLabel, action };
    confirmDialog.showModal();
  }
  function resolveConfirm(confirmed: boolean) {
    const pending = pendingConfirm;
    pendingConfirm = null;
    confirmDialog?.close();
    if (confirmed) pending?.action();
  }
  let desktop = $state<DesktopState | null>(null);
  let desktopDraft = $state<DesktopPreferences | null>(null);
  let desktopDirty = $state(false);
  let timerDirty = $state(false);
  let timerSaveStatus = $state('');
  let desktopSaveStatus = $state('');
  let timerSaveTimer: ReturnType<typeof setTimeout> | null = null;
  let desktopSaveTimer: ReturnType<typeof setTimeout> | null = null;
  let tasks = $state<Task[]>([]);
  let today = $state<DailyTotals | null>(null);
  let reportRows = $state<SessionRecord[]>([]);
  let reportTotals = $state<DailyTotals | null>(null);
  let reportFrom = $state('');
  let reportTo = $state('');
  let reportLoaded = $state(false);
  let reportDays = $derived.by(() => {
    const groups = new Map<string, { day: string; minutes: number; sessions: number }>();
    for (const record of reportRows) {
      if (record.phase !== 'focus' && record.phase !== 'stopwatch') continue;
      const day = localDate(new Date(record.started_unix_ms));
      const group = groups.get(day) ?? { day, minutes: 0, sessions: 0 };
      group.minutes += record.active_ms / 60_000; group.sessions += 1; groups.set(day, group);
    }
    return [...groups.values()].sort((a, b) => a.day.localeCompare(b.day));
  });
  let sortedReportRows = $derived([...reportRows].sort((a, b) => b.started_unix_ms - a.started_unix_ms));
  let maxReportDay = $derived(Math.max(1, ...reportDays.map(day => day.minutes)));
  let newTaskTitle = $state('');
  let editingTaskId = $state<string | null>(null);
  let editingTaskTitle = $state('');
  let lastRecordId: string | null = null;
  let dismissedRecovery = $state(false);
  let dismissedInterruption = $state(false);
  let lastInterruption = $state<string | null>(null);
  async function loadTasks() { tasks = await invoke<Task[]>('list_tasks'); }
  async function loadToday() {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime();
    today = await invoke<DailyTotals>('daily_totals', { startUnixMs: start, endUnixMs: end });
  }
  function localDate(date: Date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
  function localMidnight(value: string) { return new Date(`${value}T00:00:00`).getTime(); }
  function refreshReportIfVisible() {
    if (page !== 'reports' || !reportLoaded || !reportFrom || !reportTo || reportFrom > reportTo) return;
    void loadReport();
  }
  async function loadReport() {
    if (!reportFrom || !reportTo || reportFrom > reportTo) { reportError('Choose a valid report date range.'); return; }
    const start = localMidnight(reportFrom);
    const endDate = new Date(`${reportTo}T00:00:00`); endDate.setDate(endDate.getDate() + 1);
    const end = endDate.getTime();
    try {
      const [rows, totals] = await Promise.all([
        invoke<SessionRecord[]>('report_records', { startUnixMs: start, endUnixMs: end }),
        invoke<DailyTotals>('daily_totals', { startUnixMs: start, endUnixMs: end }),
      ]);
      reportRows = rows; reportTotals = totals; reportLoaded = true; error = '';
    } catch (e) { reportError(String(e)); }
  }
  function matchPreset(from: string, to: string): 'today' | 'week' | 'month' | null {
    if (!from || !to) return null;
    const now = new Date();
    const end = localDate(now);
    if (to !== end) return null;
    if (from === end) return 'today';
    const week = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    week.setDate(week.getDate() - 6);
    if (from === localDate(week)) return 'week';
    const month = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    month.setDate(month.getDate() - 29);
    if (from === localDate(month)) return 'month';
    return null;
  }
  let reportPreset = $derived(matchPreset(reportFrom, reportTo));
  function setReportPreset(days: 1 | 7 | 30) {
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    start.setDate(start.getDate() - days + 1);
    reportFrom = localDate(start); reportTo = localDate(today); void loadReport();
  }
  async function taskRequest(command: string, args: Record<string, unknown> = {}) {
    try { await invoke(command, args); await loadTasks(); return true; }
    catch (e) { reportError(String(e)); return false; }
  }
  async function addTask(event: SubmitEvent) {
    event.preventDefault();
    const title = newTaskTitle.trim();
    if (!title) return;
    if (await taskRequest('create_task', { title })) newTaskTitle = '';
  }
  async function saveTask(id: string) {
    try {
      const updated = await invoke<Task>('rename_task', { id, title: editingTaskTitle });
      await loadTasks();
      if (snapshot?.selected_task?.id === id) await send({ type: 'select_task', task: { id, title: updated.title } });
      editingTaskId = null;
    } catch (e) { reportError(String(e)); }
  }
  async function completeTask(id: string, completed: boolean) {
    if (completed && snapshot?.selected_task?.id === id) await send({ type: 'select_task', task: null });
    await taskRequest('complete_task', { id, completed });
  }
  async function removeTask(id: string) {
    const task = tasks.find(item => item.id === id);
    if (!task) return;
    askConfirm('Remove task?', `Remove “${task.title}” from your task list? Saved sessions will keep its title.`, 'Remove', async () => {
      if (snapshot?.selected_task?.id === id) await send({ type: 'select_task', task: null });
      await taskRequest('delete_task', { id });
    });
  }
  async function setTask(taskId: string) {
    const task = tasks.find(item => item.id === taskId);
    await send({ type: 'select_task', task: task ? { id: task.id, title: task.title } : null });
  }
  function acceptDesktop(incoming: DesktopState) {
    if (!desktop || incoming.revision >= desktop.revision) {
      if (desktopDraft && desktop) desktopDraft = mergeUnedited(desktopDraft, desktop.preferences, incoming.preferences);
      desktop = incoming;
      if (!desktopDirty) desktopDraft = { ...incoming.preferences };
    }
  }
  $effect(() => {
    const root = document.documentElement;
    const preferences = desktop?.preferences;
    root.style.setProperty('--compact-opacity', String((preferences?.opacity_percent ?? 100) / 100));
    root.dataset.theme = preferences?.theme ?? 'dark';
  });
  $effect(() => {
    if (!snapshot?.recovered && dismissedRecovery) dismissedRecovery = false;
    const interruption = snapshot?.interruption ?? null;
    if (interruption !== lastInterruption) {
      lastInterruption = interruption;
      if (dismissedInterruption) dismissedInterruption = false;
    }
  });
  $effect(() => {
    if (!draft || !snapshot || !timerDirty || busy || snapshot.pending_save || error || !validTimerDraft(draft)) return;
    timerSaveTimer = setTimeout(() => { timerSaveTimer = null; void persistTimerDraft(); }, 500);
    return () => { if (timerSaveTimer !== null) { clearTimeout(timerSaveTimer); timerSaveTimer = null; } };
  });
  $effect(() => {
    if (!desktopDraft || !desktop || !desktopDirty || busy || error) return;
    desktopSaveTimer = setTimeout(() => { desktopSaveTimer = null; void persistDesktopDraft(); }, 500);
    return () => { if (desktopSaveTimer !== null) { clearTimeout(desktopSaveTimer); desktopSaveTimer = null; } };
  });
  const client = new TimerClient(transport, incoming => {
    if (draft && snapshot) draft = mergeUnedited(draft, snapshot.settings, incoming.settings);
    const latestRecordId = incoming.records[0]?.id ?? null;
    if (latestRecordId && latestRecordId !== lastRecordId) { void loadToday().catch(e => reportError(String(e))); refreshReportIfVisible(); }
    lastRecordId = latestRecordId;
    snapshot = incoming;
  });
  let progress = $derived(snapshot?.duration_ms ? Math.min(1, snapshot.active_ms / snapshot.duration_ms) : 0);

  async function send(command: Command) {
    if (busy) return;
    busy = true; error = '';
    try { await client.send(command); } catch (e) { reportError(String(e)); }
    finally { busy = false; }
  }
  async function native(command: string) {
    try { await invoke(command); } catch (e) { error = String(e); }
  }
  function reportError(message: string) {
    error = message;
    if (compact) void invoke('report_desktop_error', { message }).catch(() => {});
  }
  function validTimerDraft(value: Settings) {
    const checks: [number, number, number][] = [
      [value.focus_minutes, 1, 60],
      [value.short_break_minutes, 1, 30],
      [value.long_break_minutes, 1, 60],
      [value.long_break_interval, 1, 10],
    ];
    return checks.every(([v, min, max]) => Number.isInteger(v) && v >= min && v <= max);
  }
  async function persistTimerDraft() {
    if (!draft || !snapshot || !timerDirty || busy || snapshot.pending_save || error || !validTimerDraft(draft)) return;
    timerDirty = false;
    timerSaveStatus = 'Saving…';
    await send({ type: 'configure', settings: { ...draft } });
    timerSaveStatus = error ? '' : 'Saved';
  }
  async function persistDesktopDraft() {
    if (!desktopDraft || !desktop || !desktopDirty || busy || error) return;
    desktopSaveStatus = 'Saving…';
    await saveDesktop();
    desktopSaveStatus = error ? '' : 'Saved';
  }
  async function restoreTimerDefaults() {
    if (!snapshot || busy) return;
    askConfirm('Restore default timer settings?', 'Your current durations and options will be replaced.', 'Restore defaults', async () => {
      try {
        const defaults = await invoke<Settings>('timer_defaults');
        draft = { ...defaults }; timerDirty = true; timerSaveStatus = ''; error = '';
        flushTimerSave();
      } catch (e) { reportError(String(e)); }
    });
  }
  async function restoreDesktopDefaults() {
    if (!desktop || busy) return;
    askConfirm('Restore default desktop settings?', 'Your current appearance and behavior options will be replaced.', 'Restore desktop defaults', async () => {
      try {
        const defaults = await invoke<DesktopPreferences>('desktop_defaults');
        desktopDraft = { ...defaults }; desktopDirty = true; desktopSaveStatus = ''; error = '';
        flushDesktopSave();
      } catch (e) { reportError(String(e)); }
    });
  }
  function flushTimerSave() {
    if (timerSaveTimer !== null) { clearTimeout(timerSaveTimer); timerSaveTimer = null; }
    void persistTimerDraft();
  }
  function flushDesktopSave() {
    if (desktopSaveTimer !== null) { clearTimeout(desktopSaveTimer); desktopSaveTimer = null; }
    void persistDesktopDraft();
  }
  async function saveDesktop() {
    if (!desktopDraft || busy) return;
    busy = true; error = '';
    try {
      const saved = await invoke<DesktopState>('save_desktop_preferences', { preferences: { ...desktopDraft } });
      desktopDirty = false; acceptDesktop(saved);
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }
  async function resetReports() {
    askConfirm('Reset reports?', 'Delete every recorded session? Totals, reports, and the last-session summary will be cleared. This cannot be undone.', 'Reset reports', async () => {
      try {
        snapshot = await invoke<Snapshot>('reset_reports');
        lastRecordId = snapshot.records[0]?.id ?? null;
        await loadToday();
        error = '';
      } catch (e) { reportError(String(e)); }
    });
  }
  function navigate(destination: string) {
    page = destination;
    window.scrollTo(0, 0);
    if (destination === 'settings' && snapshot) { draft = { ...snapshot.settings }; timerDirty = false; timerSaveStatus = ''; }
    if (destination === 'reports') {
      if (!reportLoaded) setReportPreset(1);
      else void loadReport();
    }
  }
  function primary() {
    if (snapshot?.pending_save) void send({ type: 'retry_save' });
    else void send({ type: 'toggle' });
  }
  function keyboard(event: KeyboardEvent) {
    if (compact || !snapshot || event.target instanceof HTMLInputElement || finishDialog?.open || confirmDialog?.open) return;
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
        const desktopStop = await listen<DesktopState>('desktop-state', event => acceptDesktop(event.payload));
        if (disposed) { desktopStop(); return; } else listeners.push(desktopStop);
        acceptDesktop(await invoke<DesktopState>('get_desktop_state'));
        if (!compact) {
          const stop = await listen('finish-requested', () => { if (snapshot?.status !== 'idle' && !snapshot?.pending_save) finishDialog?.showModal(); });
          if (disposed) stop(); else listeners.push(stop);
          const errorStop = await listen<string>('desktop-error', event => { error = event.payload; });
          if (disposed) errorStop(); else listeners.push(errorStop);
        try { await Promise.all([loadTasks(), loadToday()]); } catch (e) { reportError(String(e)); }
        const completedStop = await listen('session-completed', () => { void loadToday().catch(e => reportError(String(e))); refreshReportIfVisible(); });
        if (disposed) completedStop(); else listeners.push(completedStop);
        }
      } catch (e) { if (!disposed) error = String(e); }
    }
    void register();
    return () => { disposed = true; client.dispose(); listeners.forEach(stop => stop()); };
  });
</script>

<svelte:window onkeydown={keyboard} />
{#if compact && snapshot}
  <Compact state={snapshot} {busy} send={primary} error={reportError} />
{:else if compact}
  <div class="compact-loading" role="status">{error ? 'Needs attention' : 'Connecting…'}</div>
{:else}
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><Icon name="timer" size={22} /></span><strong>Pomodoro</strong></div>
      <nav aria-label="Main navigation">
        {#each [{ id: 'timer', label: 'Timer', icon: 'timer' }, { id: 'tasks', label: 'Tasks', icon: 'check' }, { id: 'reports', label: 'Reports', icon: 'chart' }] as item}
          <button class:active={page === item.id} aria-current={page === item.id ? 'page' : undefined} disabled={!snapshot && item.id !== 'timer'} onclick={() => navigate(item.id)}><Icon name={item.icon} />{item.label}</button>
        {/each}
      </nav>
      <div class="sidebar-footer"><button class="settings-entry" class:active={page === 'settings'} aria-current={page === 'settings' ? 'page' : undefined} disabled={!snapshot} onclick={() => navigate('settings')}><Icon name="settings" />Settings</button>{#if snapshot?.last_error}<span class="local-status attention"><i></i>Needs attention</span>{:else if !snapshot}<span class="local-status"><i></i>Connecting</span>{/if}</div>
    </aside>
    <main>
      {#if error || snapshot?.last_error}
        <div class="error-banner" role="alert"><strong>Needs attention</strong><p>{error || snapshot?.last_error}</p>{#if snapshot?.pending_save}<button onclick={() => void send({ type: 'retry_save' })} disabled={busy}>Retry save</button>{/if}</div>
      {/if}
      {#if !snapshot}
        <div class="empty-state"><Icon name="timer" size={40} /><h2>{error ? 'Desktop connection unavailable' : 'Connecting to your timer…'}</h2><p>{error ? 'Launch the installed app or use npm run tauri dev.' : 'Your session is managed on this device.'}</p></div>
      {:else if page === 'timer'}
        {#if snapshot.recovered && !dismissedRecovery}<div class="recovery-banner" role="status"><span>Your previous session was restored.</span><button class="secondary banner-dismiss" onclick={() => dismissedRecovery = true} aria-label="Dismiss recovery notice">Dismiss</button></div>{/if}
        {#if snapshot.interruption && !dismissedInterruption}<div class="recovery-banner" role="status"><span>Paused before {snapshot.interruption === 'sleep' ? 'Windows suspended' : 'Windows locked'}. Resume when you’re ready; time while paused is excluded.</span><button class="secondary banner-dismiss" onclick={() => dismissedInterruption = true} aria-label="Dismiss interruption notice">Dismiss</button></div>{/if}
        <div class="timer-layout">
          <section class="timer-card" aria-label="Timer">
            <div class="mode-switch" role="group" aria-label="Timer mode">
              <button aria-pressed={snapshot.phase !== 'stopwatch'} disabled={snapshot.status !== 'idle' || busy} onclick={() => void send({ type: 'set_mode', mode: 'focus' })}>Pomodoro</button>
              <button aria-pressed={snapshot.phase === 'stopwatch'} disabled={snapshot.status !== 'idle' || busy} onclick={() => void send({ type: 'set_mode', mode: 'stopwatch' })}>Stopwatch</button>
            </div>
            <div class="timer-face" class:break-phase={snapshot.phase.includes('break')} role="group" aria-label={`${phaseLabel[snapshot.phase]} timer`}>
              <svg class="timer-ring" viewBox="0 0 300 300" aria-hidden="true"><circle class="ring-track" cx="150" cy="150" r="138" /><circle class="ring-progress" cx="150" cy="150" r="138" pathLength="100" stroke-dasharray={`${snapshot.phase === 'stopwatch' ? 0 : 100 * (1 - progress)} 100`} /></svg>
              <div class="timer-inner"><p class="phase-label">{phaseLabel[snapshot.phase]}</p><span class="time-digits" role="timer">{formatTime(snapshot.display_seconds)}</span>
                <span class="state-label" class:paused={snapshot.status === 'paused'}>{snapshot.status === 'running' ? 'Running' : snapshot.status === 'paused' ? 'Paused' : 'Ready'}</span>
                {#if snapshot.phase !== 'stopwatch'}<p class="cycle-label">Session {snapshot.cycle} of {snapshot.cycle_interval}</p><div class="cycle-dots" aria-hidden="true">{#each Array(snapshot.cycle_interval) as _, i}<i class:filled={i < snapshot.cycle}></i>{/each}</div>{/if}
              </div>
            </div>
            {#if snapshot.active_task}<p class="active-task">Current session: <strong>{snapshot.active_task.title}</strong></p>{/if}
            {#if snapshot.status === 'idle'}<label class="task-select">Focus task
              <select aria-label="Task for the next session" value={snapshot.selected_task?.id ?? ''} disabled={busy} onchange={event => void setTask(event.currentTarget.value)}>
                <option value="">No task selected</option>
                {#each tasks.filter(task => !task.completed) as task (task.id)}<option value={task.id}>{task.title}</option>{/each}
              </select>
            </label>{/if}
            <div class="timer-actions"><button class="primary" onclick={primary} disabled={busy}><Icon name={snapshot.status === 'running' ? 'pause' : 'play'} />{actionLabel(snapshot)}</button>
              {#if snapshot.status !== 'idle'}<button class="secondary" onclick={() => finishDialog.showModal()} disabled={busy || snapshot.pending_save}><Icon name="finish" />{snapshot.phase.includes('break') ? 'Skip break' : 'Finish'}</button>{/if}</div>
          </section>
          <aside class="focus-aside">
            <div class="compact-row"><button class="secondary compact-entry" onclick={() => void native('open_compact')} disabled={!snapshot}><Icon name="compact" />Compact mode</button></div>
            <section class="summary-card"><div class="card-title"><Icon name="history" /><h2>Today</h2></div><strong>{Math.floor(((today?.pomodoro_ms ?? 0) + (today?.stopwatch_ms ?? 0)) / 60_000)}<small> min focused</small></strong><div class="summary-row"><span>Pomodoro</span><b>{Math.floor((today?.pomodoro_ms ?? 0) / 60_000)} min · {today?.pomodoro_sessions ?? 0}</b></div><div class="summary-row"><span>Stopwatch</span><b>{Math.floor((today?.stopwatch_ms ?? 0) / 60_000)} min · {today?.stopwatch_sessions ?? 0}</b></div></section>
            <section class="next-card"><div><h2>{snapshot.phase === 'stopwatch' ? 'Stopwatch' : 'Next session'}</h2><p>{snapshot.phase === 'stopwatch' ? 'Finish to save your session.' : snapshot.phase === 'focus' ? `${snapshot.cycle === snapshot.cycle_interval ? snapshot.settings.long_break_minutes : snapshot.settings.short_break_minutes} minute ${snapshot.cycle === snapshot.cycle_interval ? 'long' : 'short'} break` : `${snapshot.settings.focus_minutes} minute focus`}</p>{#if snapshot.phase !== 'stopwatch'}<p>{snapshot.settings.auto_start_next ? 'Starts automatically on completion' : 'Start when ready'}</p>{/if}</div></section>
            {#if snapshot.records[0]}<section class="next-card"><div><h2>Last session</h2><p><strong>{snapshot.records[0].task?.title ?? 'No task'}</strong></p><p>{phaseLabel[snapshot.records[0].phase]} · {formatTime(Math.floor(snapshot.records[0].active_ms / 1000))} · {snapshot.records[0].outcome}</p></div></section>
            {:else}<section class="next-card"><div><h2>Last session</h2><p>No sessions yet.</p></div></section>{/if}
          </aside>
        </div>
      {:else if page === 'tasks'}
        <section class="content-card task-card"><div class="card-title"><Icon name="check" /><h2>Tasks</h2></div><p class="muted">Select a task on the timer before starting a session.</p>
          <form class="new-task-form" onsubmit={addTask}><label for="new-task-title">New task</label><div class="input-unit"><input id="new-task-title" class="task-title-input" type="text" maxlength="120" required bind:value={newTaskTitle} placeholder="What will you focus on?" /><button class="primary" type="submit" disabled={!newTaskTitle.trim()}>Add task</button></div></form>
          {#if tasks.length === 0}<div class="empty-state"><h3>No tasks yet</h3><p>Add a task, then select it on the timer screen.</p></div>
          {:else}<div class="task-list">{#each tasks as task (task.id)}<article class="task-row" class:task-completed={task.completed}>
            {#if editingTaskId === task.id}<form class="task-edit" onsubmit={event => { event.preventDefault(); void saveTask(task.id); }}><input aria-label="Edit task title" maxlength="120" required bind:value={editingTaskTitle} /><button class="secondary" type="submit">Save</button><button class="secondary" type="button" onclick={() => editingTaskId = null}>Cancel</button></form>
            {:else}<label class="task-name"><input type="checkbox" checked={task.completed} onchange={event => void completeTask(task.id, event.currentTarget.checked)} /><span>{task.title}</span></label><div class="task-actions"><button class="secondary" onclick={() => { editingTaskId = task.id; editingTaskTitle = task.title; }}>Edit</button><button class="secondary" onclick={() => void removeTask(task.id)}>Remove</button></div>{/if}
          </article>{/each}</div>{/if}
        </section>
      {:else if page === 'reports'}
        <section class="content-card report-card"><div class="card-title"><Icon name="chart" /><h2>Reports</h2></div>
          <div class="report-toolbar"><div class="report-presets"><button class="secondary" aria-pressed={reportPreset === 'today'} onclick={() => setReportPreset(1)}>Today</button><button class="secondary" aria-pressed={reportPreset === 'week'} onclick={() => setReportPreset(7)}>Last 7 days</button><button class="secondary" aria-pressed={reportPreset === 'month'} onclick={() => setReportPreset(30)}>Last 30 days</button></div>
            <label>From<input aria-label="Report start date" type="date" bind:value={reportFrom} /></label><label>To<input aria-label="Report end date" type="date" bind:value={reportTo} /></label>
            <button class="primary" onclick={() => void loadReport()}>Apply dates</button>
          </div>
          {#if reportTotals}
            <div class="report-totals"><article><span>Focus time</span><strong>{Math.floor((reportTotals.pomodoro_ms + reportTotals.stopwatch_ms) / 3_600_000)}h {Math.floor(((reportTotals.pomodoro_ms + reportTotals.stopwatch_ms) % 3_600_000) / 60_000)}m</strong></article><article><span>Pomodoro sessions</span><strong>{reportTotals.pomodoro_sessions}</strong></article><article><span>Stopwatch sessions</span><strong>{reportTotals.stopwatch_sessions}</strong></article></div>
            {#if reportDays.length}<section class="report-days" aria-label="Daily focus summary"><h3>Focus by day</h3>{#each reportDays as day (day.day)}<div class="report-day"><time datetime={day.day}>{new Date(`${day.day}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</time><span class="report-bar-track"><i style={`width:${Math.max(2, day.minutes / maxReportDay * 100)}%`}></i></span><strong>{Math.floor(day.minutes)} min · {day.sessions}</strong></div>{/each}</section>{/if}
            {#if reportRows.length === 0}<div class="empty-state"><h3>No sessions in this range</h3><p>Try a wider date range.</p></div>
            {:else}<div class="table-wrap"><table><thead><tr><th>Start time</th><th>Session</th><th>Task</th><th>Active time</th><th>Outcome</th></tr></thead><tbody>{#each sortedReportRows as record (record.id)}<tr><td>{new Date(record.started_unix_ms).toLocaleString()}</td><td>{phaseLabel[record.phase]}</td><td>{record.task?.title ?? '—'}</td><td>{formatTime(Math.floor(record.active_ms / 1000))}</td><td><span class="outcome">{record.outcome}</span></td></tr>{/each}</tbody></table></div>{/if}
          {/if}
        </section>
      {:else if draft}
        <section class="settings-card"><div class="card-title"><Icon name="settings" /><h2>Timer preferences</h2></div><p class="muted">Duration changes apply to the next session.</p>
          <form onsubmit={event => { event.preventDefault(); flushTimerSave(); }} oninput={() => { timerDirty = true; timerSaveStatus = ''; error = ''; }}>
            <div class="settings-grid">{#each [{ key: 'focus_minutes', label: 'Focus duration', max: 60 }, { key: 'short_break_minutes', label: 'Short break', max: 30 }, { key: 'long_break_minutes', label: 'Long break', max: 60 }, { key: 'long_break_interval', label: 'Sessions before a long break', max: 10 }] as field}<label>{field.label}<span class="input-unit"><input type="number" min="1" max={field.max} step="1" required value={draft[field.key as keyof Settings] as number} oninput={event => { if (draft) draft = { ...draft, [field.key]: event.currentTarget.valueAsNumber }; }} />{field.key.includes('minutes') ? 'min' : 'sessions'}</span></label>{/each}</div>
            <label class="checkbox-row"><input type="checkbox" bind:checked={draft.sound_enabled} />Play a completion tone</label>
            <label class="checkbox-row"><input type="checkbox" bind:checked={draft.auto_start_next} />Automatically start the next focus or break after a session completes</label>
            <div class="form-actions"><span class="save-status" role="status">{timerSaveStatus}</span><button class="secondary" type="button" onclick={() => void restoreTimerDefaults()}>Restore defaults</button></div>
          </form>
        </section>
        <section class="settings-card"><div class="card-title"><Icon name="history" /><h2>Session data</h2></div>
          <p class="muted">Delete every recorded session. Totals, reports, and the last-session summary will be cleared. This cannot be undone.</p>
          <div class="form-actions"><button class="secondary" type="button" onclick={() => void resetReports()}>Reset reports</button></div>
        </section>
        {#if desktopDraft && desktop}
        <section class="settings-card"><div class="card-title"><Icon name="compact" /><h2>Desktop preferences</h2></div>
          <form onsubmit={event => { event.preventDefault(); flushDesktopSave(); }} oninput={() => { desktopDirty = true; desktopSaveStatus = ''; error = ''; }}>
            <div class="settings-grid"><label>Tone volume<span class="input-unit"><input type="range" min="0" max="100" step="5" bind:value={desktopDraft.volume} />{desktopDraft.volume}%</span></label>
              <label>Appearance theme<span class="input-unit"><select bind:value={desktopDraft.theme}><option value="dark">Dark</option><option value="light">Light</option></select></span></label>
              <label>Compact mode background opacity<span class="input-unit"><input aria-label="Compact mode background opacity" type="range" min="60" max="100" step="5" bind:value={desktopDraft.opacity_percent} />{desktopDraft.opacity_percent}%</span></label></div>
            <label class="checkbox-row"><input type="checkbox" bind:checked={desktopDraft.pinned} />Keep compact timer on top</label>
            <label class="checkbox-row"><input type="checkbox" bind:checked={desktopDraft.notifications} />Send completion notifications</label>
            {#if desktop.platform === 'macos'}
              <p class="muted">Notification delivery also depends on macOS notification settings and Focus modes.</p>
              <label class="checkbox-row"><input type="checkbox" bind:checked={desktopDraft.menu_bar_visible} />Show in menu bar</label>
              <label class="checkbox-row"><input type="checkbox" bind:checked={desktopDraft.dock_hidden} disabled={!desktopDraft.menu_bar_visible} />Hide Dock icon</label>
              <p class="muted">Hiding the Dock icon requires the menu bar icon so the app stays reachable. Closing the main window always keeps the app running.</p>
            {:else}
              <p class="muted">Notification delivery also depends on Windows notification settings and Focus Assist. </p>
              <label class="checkbox-row"><input type="checkbox" bind:checked={desktopDraft.close_to_tray} />Close to system tray instead of exiting</label>
            {/if}
            <div class="form-actions"><span class="save-status" role="status">{desktopSaveStatus}</span><button class="secondary" type="button" onclick={() => void restoreDesktopDefaults()}>Restore desktop defaults</button></div>
          </form>
        </section>
        {/if}
      {/if}
    </main>
  </div>
  <dialog bind:this={finishDialog}><div class="dialog-content"><h2>{snapshot?.phase.includes('break') ? 'Ready to focus again?' : 'Finish this session?'}</h2><p>Your active time will be saved on this device.</p><div class="form-actions"><button class="secondary" onclick={() => finishDialog.close()}>Keep {snapshot?.phase.includes('break') ? 'resting' : 'focusing'}</button><button class="primary" onclick={() => { finishDialog.close(); void send({ type: 'finish' }); }}>Finish and save</button></div></div></dialog>
  <dialog bind:this={confirmDialog} oncancel={() => pendingConfirm = null}><div class="dialog-content"><h2>{pendingConfirm?.heading}</h2><p>{pendingConfirm?.message}</p><div class="form-actions"><button class="secondary" onclick={() => resolveConfirm(false)}>Cancel</button><button class="primary" onclick={() => resolveConfirm(true)}>{pendingConfirm?.confirmLabel ?? 'Confirm'}</button></div></div></dialog>
{/if}
