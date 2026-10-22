import { test, expect, type Page } from '@playwright/test';

async function mockDesktop(page: Page, options: { seconds: number; emptyReports?: boolean; recovered?: boolean; interruption?: string | null; opacity?: number; lastRecord?: boolean; platform?: string; failTaskStatusOnce?: boolean; taskTitle?: string; denseHistory?: boolean; extraTasks?: number; resizeDelay?: number; appVersion?: string; updateResponses?: ('current' | 'available' | 'none' | 'error')[]; updateDelay?: number; failOpenReleaseOnce?: boolean; syncConfigured?: boolean; accountEmail?: string; failSyncOnce?: boolean } = { seconds: 1500 }) {
  await page.addInitScript(options => {
    (window as unknown as { isTauri: boolean }).isTauri = true;
    const callbacks = new Map<number, (value: unknown) => void>();
    let callbackId = 0;
    const state = {
      phase: 'focus', status: 'idle', display_seconds: options.seconds, active_ms: 0, duration_ms: 1_500_000,
      selected_task: null as { id: string; title: string } | null, active_task: null as { id: string; title: string } | null,
      cycle: 1, cycle_interval: 4, revision: 0, recovered: options.recovered ?? false, pending_save: false, last_error: null, interruption: options.interruption ?? null,
      settings: { focus_minutes: 25, short_break_minutes: 5, long_break_minutes: 15, long_break_interval: 4, sound_enabled: false, auto_start_next: false }, records: options.lastRecord ? [{ id: 'session-9', phase: 'focus', started_unix_ms: Date.now(), active_ms: 1_500_000, outcome: 'completed', task: { id: 'task-1', title: 'Write tests' } }] : [],
    };
    const desktop = { revision: 0, platform: options.platform ?? 'windows', preferences: { volume: 60, theme: 'dark',
      opacity_percent: options.opacity ?? 100, pinned: true, notifications: true, close_to_tray: true, menu_bar_visible: true, dock_hidden: false },
      audio_status: 'Native playback', notification_status: 'OS controlled', power_status: 'Test adapter' };
    const reportDate = new Date(); reportDate.setHours(9, 0, 0, 0);
    const started = reportDate.getTime();
    const reportRows = [
      { id: 'session-1', phase: 'focus', started_unix_ms: started, active_ms: 1_500_000, outcome: 'completed', task: { id: 'task-1', title: 'Write tests' } },
      { id: 'session-2', phase: 'stopwatch', started_unix_ms: started + 1_800_000, active_ms: 600_000, outcome: 'finished', task: null },
    ];
    const tasks = [
      { id: 'task-1', title: options.taskTitle ?? 'Write tests', status: 'todo', created_unix_ms: started, updated_unix_ms: started },
      { id: 'task-2', title: 'Review requirements', status: 'done', created_unix_ms: started, updated_unix_ms: started },
    ];
    for (let index = 0; index < (options.extraTasks ?? 0); index++) {
      tasks.push({ id: `extra-${index}`, title: `Task ${index + 1}`, status: 'todo', created_unix_ms: started, updated_unix_ms: started });
    }
    const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1); yesterday.setHours(12, 0, 0, 0);
    const today = new Date(); today.setHours(12, 0, 0, 0);
    const taskCompletionEvents = [
      { id: 'event-1', task_id: 'task-2', completed_unix_ms: yesterday.getTime() },
      { id: 'event-2', task_id: 'task-2', completed_unix_ms: today.getTime() },
    ];
    if (options.denseHistory) {
      for (let daysAgo = 0; daysAgo < 180; daysAgo += 1) {
        if (daysAgo % 4 === 1) continue;
        const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - daysAgo, 12).getTime();
        taskCompletionEvents.push({ id: `dense-${daysAgo}`, task_id: 'task-2', completed_unix_ms: day });
        if (daysAgo % 5 === 0) taskCompletionEvents.push({ id: `dense-extra-${daysAgo}`, task_id: 'task-1', completed_unix_ms: day });
      }
    }
    const listeners = new Map<string, number>();
    (window as any).__TAURI_EVENT_PLUGIN_INTERNALS__ = {
      unregisterListener(event: string, id: number) {
        if (listeners.get(event) === id) listeners.delete(event);
        callbacks.delete(id);
      },
    };
    (window as any).__setSeconds = (seconds: number) => {
      state.display_seconds = seconds;
      state.revision++;
      const handler = listeners.get('timer-state');
      if (handler) callbacks.get(handler)?.({ payload: structuredClone(state), id: handler, event: 'timer-state' });
    };
    let finishCount = 0;
    let failTaskStatus = options.failTaskStatusOnce ?? false;
    const updateResponses = [...(options.updateResponses ?? [])];
    let failOpenRelease = options.failOpenReleaseOnce ?? false;
    let failSync = options.failSyncOnce ?? false;
    const account = { revision: 0, configured: options.syncConfigured ?? false, email: options.accountEmail ?? null,
      busy: false, signing_in: false, last_synced_ms: null as number | null,
      message: 'Sign in to sync your tasks across devices.', error: null as string | null };
    function publishAccount() {
      account.revision++;
      const handler = listeners.get('sync-state');
      if (handler) callbacks.get(handler)?.({ payload: structuredClone(account), id: handler, event: 'sync-state' });
    }
    (window as any).__finishBackgroundSync = () => {
      account.error = null; account.message = 'All tasks are synced.'; account.last_synced_ms = Date.now(); publishAccount();
    };
    (window as any).__deliverRemoteTask = () => {
      tasks.push({ id: 'remote-task', title: 'Task from another device', status: 'todo', created_unix_ms: started, updated_unix_ms: started });
      const handler = listeners.get('tasks-synced');
      if (handler) callbacks.get(handler)?.({ payload: null, id: handler, event: 'tasks-synced' });
    };
    (window as any).__deliverRemoteHistory = (deleted = false) => {
      const index = reportRows.findIndex(row => row.id === 'remote-session');
      if (deleted && index >= 0) reportRows.splice(index, 1);
      else if (!deleted && index < 0) reportRows.push({ id: 'remote-session', phase: 'focus', started_unix_ms: started + 3_600_000, active_ms: 600_000, outcome: 'completed', task: { id: 'task-remote', title: 'Focus from another device' } });
      const handler = listeners.get('tasks-synced');
      if (handler) callbacks.get(handler)?.({ payload: null, id: handler, event: 'tasks-synced' });
    };
    (window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = {
      transformCallback(callback: (value: unknown) => void) { callbacks.set(++callbackId, callback); return callbackId; },
      unregisterCallback(id: number) { callbacks.delete(id); },
      metadata: { currentWindow: { label: 'compact' }, currentWebview: { label: 'compact' } },
      async invoke(command: string, args: Record<string, any> = {}) {
        if (command === 'plugin:event|listen') { listeners.set(args.event, args.handler); return args.handler; }
        if (command === 'plugin:event|unlisten') return;
        if (command === 'plugin:window|start_dragging') { (window as any).__dragCalls = ((window as any).__dragCalls ?? 0) + 1; return; }
        if (command === 'open_main') { (window as any).__openMainCalls = ((window as any).__openMainCalls ?? 0) + 1; return; }
        if (command === 'resize_compact') {
          const w = window as any;
          w.__resizesActive = (w.__resizesActive ?? 0) + 1;
          w.__maxResizesActive = Math.max(w.__maxResizesActive ?? 0, w.__resizesActive);
          (w.__resizeRequests ??= []).push(args);
          if (options.resizeDelay) await new Promise(resolve => setTimeout(resolve, options.resizeDelay));
          w.__compactSize = args;
          w.__resizesActive--;
          return;
        }
        if (command === 'compact_menu') {
          const w = window as any; (w.__menuCalls ??= []).push({ x: args.x, y: args.y });
          return new Promise<void>(resolve => { w.__closeMenu = resolve; });
        }
        if (command === 'get_snapshot') return structuredClone(state);
        if (command === 'get_desktop_state') return structuredClone(desktop);
        if (command === 'get_app_version') return options.appVersion ?? '1.2.0';
        if (command === 'get_account_state') return structuredClone(account);
        if (command === 'sign_in_with_google') {
          account.busy = true; account.signing_in = true; account.error = null;
          account.message = 'Finish signing in with Google in your browser.'; publishAccount();
          return new Promise((resolve, reject) => {
            (window as any).__completeGoogleSignIn = () => {
              account.email = 'focus@example.com'; account.busy = false; account.signing_in = false;
              account.message = 'All tasks are synced.'; account.last_synced_ms = Date.now(); publishAccount(); resolve(structuredClone(account));
            };
            (window as any).__cancelGoogleSignIn = () => {
              account.busy = false; account.signing_in = false; account.error = 'Google sign-in was cancelled.';
              publishAccount(); reject(account.error);
            };
          });
        }
        if (command === 'cancel_google_sign_in') { (window as any).__cancelGoogleSignIn?.(); return; }
        if (command === 'sync_tasks_now') {
          account.error = null; account.busy = true; publishAccount();
          await new Promise(resolve => setTimeout(resolve, 150));
          account.busy = false;
          if (failSync) {
            failSync = false; account.error = 'Tasks are saved on this device. Sync will retry when your connection returns.';
            publishAccount(); throw account.error;
          }
          account.message = 'All tasks are synced.'; account.last_synced_ms = Date.now(); publishAccount();
          return structuredClone(account);
        }
        if (command === 'sign_out_account') {
          account.email = null; account.last_synced_ms = null; account.message = 'Signed out. Your tasks and focus history remain on this device.';
          publishAccount(); return structuredClone(account);
        }
        if (command === 'check_for_updates') {
          (window as any).__updateCheckCalls = ((window as any).__updateCheckCalls ?? 0) + 1;
          if (options.updateDelay) await new Promise(resolve => setTimeout(resolve, options.updateDelay));
          const response = updateResponses.shift() ?? 'current';
          if (response === 'error') throw 'Could not check for updates. Check your internet connection and try again.';
          return { current_version: options.appVersion ?? '1.2.0', latest_version: response === 'none' ? null : response === 'available' ? '1.3.0' : options.appVersion ?? '1.2.0', update_available: response === 'available' };
        }
        if (command === 'open_release_page') {
          if (failOpenRelease) { failOpenRelease = false; throw 'Could not open your browser. Please try again.'; }
          (window as any).__releasePageOpens = ((window as any).__releasePageOpens ?? 0) + 1;
          return;
        }
        if (command === 'timer_defaults') return { focus_minutes: 25, short_break_minutes: 5, long_break_minutes: 15, long_break_interval: 4, sound_enabled: true, auto_start_next: false };
        if (command === 'desktop_defaults') return { volume: 60, theme: 'dark', opacity_percent: 100, pinned: true, notifications: true, close_to_tray: true, menu_bar_visible: true, dock_hidden: false };
        if (command === 'list_tasks') return structuredClone(tasks);
        if (command === 'task_completion_events') return structuredClone(taskCompletionEvents);
        if (command === 'rename_task') { const task = tasks.find(item => item.id === args.id)!; task.title = args.title; return structuredClone(task); }
        if (command === 'delete_task') { tasks.splice(tasks.findIndex(item => item.id === args.id), 1); return; }
        if (command === 'set_task_status') {
          if (failTaskStatus) { failTaskStatus = false; throw new Error('Simulated database write failure'); }
          const task = tasks.find(item => item.id === args.id);
          if (!task) throw new Error('Task no longer exists.');
          if (task.status !== 'done' && args.status === 'done') taskCompletionEvents.push({ id: `event-${taskCompletionEvents.length + 1}`, task_id: task.id, completed_unix_ms: Date.now() });
          task.status = args.status; task.updated_unix_ms = Date.now();
          return structuredClone(task);
        }
        if (command === 'daily_totals' && options.emptyReports) return { pomodoro_ms: 0, stopwatch_ms: 0, pomodoro_sessions: 0, stopwatch_sessions: 0 };
        if (command === 'daily_totals') { const pomo = reportRows.filter(row => row.phase === 'focus'); const sw = reportRows.filter(row => row.phase === 'stopwatch'); const sum = (rows: { active_ms: number }[]) => rows.reduce((total, row) => total + row.active_ms, 0); return { pomodoro_ms: sum(pomo), stopwatch_ms: sum(sw), pomodoro_sessions: pomo.length, stopwatch_sessions: sw.length }; }
        if (command === 'reset_reports') { reportRows.length = 0; taskCompletionEvents.length = 0; state.records = []; state.revision++; return structuredClone(state); }
        if (command === 'report_records') { (window as any).__reportRange = args; return options.emptyReports ? [] : structuredClone(reportRows); }
        if (command === 'save_desktop_preferences') {
          desktop.preferences = args.preferences; desktop.revision++;
          const handler = listeners.get('desktop-state');
          if (handler) callbacks.get(handler)?.({ payload: structuredClone(desktop), id: handler, event: 'desktop-state' });
          return structuredClone(desktop);
        }
        if (command === 'timer_command') {
          const action = args.command;
          if (action.type === 'select_task') state.selected_task = action.task;
          if (action.type === 'toggle') {
            if (state.status === 'idle') state.active_task = structuredClone(state.selected_task);
            state.status = state.status === 'running' ? 'paused' : 'running';
          }
          if (action.type === 'finish') { state.status = 'idle'; state.active_ms = 0; state.active_task = null; finishCount++;
            const record = { id: `session-mock-${finishCount}`, phase: 'focus', started_unix_ms: Date.now(), active_ms: 60_000, outcome: 'finished', task: { id: 'task-9', title: 'Fresh mock task' } };
            state.records.unshift(record); reportRows.unshift({ ...record }); }
          if (action.type === 'set_mode') { state.phase = action.mode; state.display_seconds = action.mode === 'stopwatch' ? 0 : 1500; }
          if (action.type === 'configure') state.settings = action.settings;
          state.revision++;
          const handler = listeners.get('timer-state');
          if (handler) callbacks.get(handler)?.({ payload: structuredClone(state), id: handler, event: 'timer-state' });
          return structuredClone(state);
        }
      },
    };
  }, options);
}

test('main timer pauses/resumes and finish dialog preserves keyboard focus', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await expect(page.getByRole('button', { name: 'Start focus', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Start focus', exact: true }).click();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(page.getByText('Paused', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resume', exact: true }).press('Space');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Keep focusing' }).click();
  await expect(page.getByRole('button', { name: 'Finish', exact: true })).toBeFocused();
  await expect(page.getByRole('button', { name: 'Pomodoro', exact: true })).toBeDisabled();
  await page.screenshot({ path: 'test-results/main-timer.png' });
});

test('compact has play and options buttons and fits 170 by 44', async ({ page }) => {
  await mockDesktop(page); await page.setViewportSize({ width: 170, height: 44 }); await page.goto('/?view=compact');
  await expect(page.locator('button')).toHaveCount(2);
  const options = page.getByRole('button', { name: 'Options', exact: true });
  await expect(options).toBeVisible();
  const action = page.locator('.compact-action:not(.compact-options)');
  await expect(action).toHaveAccessibleName('Start focus');
  await action.click(); await expect(action).toHaveAccessibleName('Pause');
  await page.keyboard.press('Space'); await expect(action).toHaveAccessibleName('Resume');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(170);
  const strip = (await page.locator('.compact').boundingBox())!;
  const time = (await page.locator('.compact-time').boundingBox())!;
  const actionBox = (await action.boundingBox())!;
  const box = (await options.boundingBox())!;
  expect(strip.width).toBe(170);
  expect(time.x + time.width + 8).toBeLessThanOrEqual(actionBox.x);
  expect(actionBox.x + actionBox.width + 4).toBeLessThanOrEqual(box.x);
  expect(box.x + box.width).toBeLessThanOrEqual(strip.x + strip.width - 6);
  expect(box.y).toBeGreaterThanOrEqual(strip.y + 1);
  expect(box.y + box.height).toBeLessThanOrEqual(strip.y + strip.height - 1);
  expect(box.width).toBe(actionBox.width);
  await page.screenshot({ path: 'test-results/compact-timer.png' });
});

test('compact zero timer keeps both controls clickable at desktop display scales', async ({ browser }) => {
  for (const scale of [1, 1.25, 1.5, 2]) {
    const context = await browser.newContext({ viewport: { width: 170, height: 44 }, deviceScaleFactor: scale });
    try {
      const page = await context.newPage();
      await mockDesktop(page, { seconds: 0, platform: 'linux' });
      await page.goto('/?view=compact');
      await expect(page.locator('.compact')).toHaveAttribute('data-compact-ui', '2');
      await expect(page.locator('.compact-time')).toHaveText('00:00');
      const group = (await page.locator('.compact-controls').boundingBox())!;
      expect(group.width).toBe(68);
      for (const [selector, x, width] of [
        ['.compact-action:not(.compact-options)', 96, 32],
        ['.compact-options', 132, 32],
      ] as const) {
        const button = page.locator(selector);
        await expect(button).toBeVisible();
        const box = (await button.boundingBox())!;
        // Fractional display scales can round a border to a device pixel.
        expect(box.x).toBeCloseTo(x, 0);
        expect({ y: box.y, width: box.width, height: box.height }).toEqual({ y: 6, width, height: 32 });
        expect(box.x).toBeGreaterThanOrEqual(group.x);
        expect(box.x + box.width).toBeLessThanOrEqual(group.x + group.width);
        expect(await button.evaluate(element => {
          const box = element.getBoundingClientRect();
          return element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
        })).toBe(true);
      }
      await page.getByRole('button', { name: 'Start focus', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Options', exact: true }).click();
      await expect.poll(() => page.evaluate(() => (window as any).__menuCalls?.length ?? 0)).toBe(1);
      await page.evaluate(() => (window as any).__closeMenu());
      await page.waitForTimeout(350);
      await page.getByRole('button', { name: 'Options', exact: true }).focus();
      await page.keyboard.press('Space');
      await expect.poll(() => page.evaluate(() => (window as any).__menuCalls?.length ?? 0)).toBe(2);
      await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
      if (scale === 1) await page.screenshot({ path: 'test-results/compact-zero.png' });
    } finally { await context.close(); }
  }
});

test('compact options button opens the menu at a fixed spot and right-click does not', async ({ page }) => {
  await mockDesktop(page); await page.setViewportSize({ width: 170, height: 44 }); await page.goto('/?view=compact');
  const calls = () => page.evaluate(() => (window as any).__menuCalls ?? []);
  await page.locator('.compact').click({ button: 'right', position: { x: 5, y: 5 } });
  await page.locator('.compact-time').click({ button: 'right' });
  expect(await calls()).toHaveLength(0);
  const options = page.getByRole('button', { name: 'Options', exact: true });
  const box = (await options.boundingBox())!;
  await options.click();
  await expect.poll(calls).toHaveLength(1);
  expect((await calls())[0]).toEqual({ x: box.x, y: 44 });
  await options.click(); // already open: no second menu
  expect(await calls()).toHaveLength(1);
  await page.evaluate(() => (window as any).__closeMenu());
  await page.waitForTimeout(350);
  await options.click({ position: { x: 4, y: 4 } });
  await expect.poll(calls).toHaveLength(2);
  expect((await calls())[1]).toEqual({ x: box.x, y: 44 });
});

test('Linux compact time and background drag without selecting text or activating buttons', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, platform: 'linux' });
  await page.setViewportSize({ width: 170, height: 44 }); await page.goto('/?view=compact');
  const time = page.locator('.compact-time');
  const dragCalls = () => page.evaluate(() => (window as any).__dragCalls ?? 0);
  const openCalls = () => page.evaluate(() => (window as any).__openMainCalls ?? 0);
  await expect(time).toHaveCSS('user-select', 'none');
  await expect(time).toHaveCSS('line-height', '32px');
  const timeBox = (await time.boundingBox())!;
  await page.mouse.move(timeBox.x + 4, timeBox.y + 16);
  await page.mouse.down();
  await page.mouse.move(timeBox.x + timeBox.width - 4, timeBox.y + 16, { steps: 5 });
  await page.mouse.up();
  await expect.poll(dragCalls).toBe(1);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe('');
  expect(await openCalls()).toBe(0);
  await page.locator('.compact').click({ position: { x: 3, y: 3 } });
  await expect.poll(dragCalls).toBe(2);
  await time.click({ button: 'right' });
  expect(await dragCalls()).toBe(2);
  const action = page.getByRole('button', { name: 'Start focus', exact: true });
  await action.locator('svg').click();
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  expect(await dragCalls()).toBe(2);
  await time.dblclick();
  await expect.poll(openCalls).toBe(1);
  await time.focus(); await time.press('Enter');
  await expect.poll(openCalls).toBe(2);
  for (const selector of ['.compact-time', '.compact-action:not(.compact-options)', '.compact-options']) {
    const box = (await page.locator(selector).boundingBox())!;
    expect(box.y).toBe(6);
    expect(box.height).toBe(32);
    expect(box.x + box.width).toBeLessThanOrEqual(170);
  }
  await page.screenshot({ path: 'test-results/linux-compact.png' });
});

test('compact time opens main through assistive activation without dragging', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, platform: 'windows' });
  await page.setViewportSize({ width: 170, height: 44 }); await page.goto('/?view=compact');
  const time = page.getByRole('button', { name: 'Focus, 25:00. Open main window', exact: true });
  await expect(time).toBeVisible();
  await time.evaluate(element => {
    // Chromium UIA Invoke sends mousedown with detail 0, then click with
    // detail 1 and the primary button still marked as pressed.
    for (const [type, detail, buttons] of [
      ['mousedown', 0, 1], ['mouseup', 0, 0], ['click', 1, 1],
    ] as const) {
      element.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, button: 0, detail, buttons }));
    }
  });
  await expect.poll(() => page.evaluate(() => (window as any).__openMainCalls ?? 0)).toBe(1);
  expect(await page.evaluate(() => (window as any).__dragCalls ?? 0)).toBe(0);
  // Other assistive tools can activate the element directly without mouse events.
  await time.evaluate(element => (element as HTMLElement).click());
  await expect.poll(() => page.evaluate(() => (window as any).__openMainCalls ?? 0)).toBe(2);
});

test('timer preferences autosave and invalid values are skipped', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const timerCard = page.locator('.timer-settings');
  await page.getByLabel('Focus duration').fill('0');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Focus duration')).toHaveValue('25');
  await page.getByLabel('Focus duration').fill('30');
  await page.getByLabel('Automatically start the next focus or break after a session completes').check();
  await expect(timerCard.getByRole('status')).toHaveText('Saved');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Focus duration')).toHaveValue('30');
  await expect(page.getByLabel('Automatically start the next focus or break after a session completes')).toBeChecked();
  await page.screenshot({ path: 'test-results/settings.png' });
});

test('empty reports and missing desktop connection provide clear feedback', async ({ page }) => {
  await page.goto('/'); await expect(page.getByText('Desktop connection unavailable')).toBeVisible();
  await mockDesktop(page, { seconds: 1500, emptyReports: true }); await page.reload();
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  await expect(page.getByText('No sessions in this range')).toBeVisible();
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Start focus', exact: true })).toBeVisible();
});

test('navigation holds three pages with settings in the footer and compact on the timer', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await expect(page.getByRole('navigation').getByRole('button')).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Sessions', exact: true })).toHaveCount(0);
  await expect(page.getByText(/YOUR FOCUS SPACE|Make time for what matters|BETA PROTOTYPE|A little space for deep work/)).toHaveCount(0);
  for (const name of ['Timer', 'Tasks', 'Reports']) {
    await page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
    await expect(page.locator('.page-header')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
  }
  await page.getByRole('navigation').getByRole('button', { name: 'Timer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Compact mode', exact: true })).toBeVisible();
  await page.getByRole('navigation').getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Compact mode', exact: true })).toHaveCount(0);
});

test('reports default to today with active preset states and inclusive ranges', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-05T12:00:00Z'));
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible();
  const today = page.getByRole('button', { name: 'Today', exact: true });
  const week = page.getByRole('button', { name: 'Last week', exact: true });
  const month = page.getByRole('button', { name: 'Last month', exact: true });
  await expect(page.getByLabel('Report start date')).toHaveCount(0);
  await expect(today).toHaveAttribute('aria-pressed', 'true');
  await expect(week).toHaveAttribute('aria-pressed', 'false');
  await expect(month).toHaveAttribute('aria-pressed', 'false');
  await week.click();
  await expect.poll(() => page.evaluate(() => (window as any).__reportRange.startUnixMs)).toBe(await page.evaluate(() => new Date('2026-09-29T00:00:00').getTime()));
  await expect(week).toHaveAttribute('aria-pressed', 'true');
  await expect(today).toHaveAttribute('aria-pressed', 'false');
  await month.click();
  await expect(month).toHaveAttribute('aria-pressed', 'true');
  await expect(week).toHaveAttribute('aria-pressed', 'false');
  await expect.poll(() => page.evaluate(() => (window as any).__reportRange.startUnixMs)).toBe(await page.evaluate(() => new Date('2026-09-06T00:00:00').getTime()));
  expect(await page.evaluate(() => (window as any).__reportRange.endUnixMs)).toBe(await page.evaluate(() => new Date('2026-10-06T00:00:00').getTime()));
  await page.getByRole('button', { name: 'Custom', exact: true }).click();
  await page.getByLabel('Report start date').fill('2026-09-01');
  await page.getByRole('button', { name: 'Apply dates' }).click();
  await expect(today).toHaveAttribute('aria-pressed', 'false');
  await expect(week).toHaveAttribute('aria-pressed', 'false');
  await expect(month).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('region', { name: 'Focus by month' })).toContainText('min');
  await expect(page.locator('table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Export CSV' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  await expect(page.locator('thead th')).toHaveCount(4);
});

test('each page uses shared typography and fits the fixed window in both themes', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  for (const theme of ['dark', 'light']) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByLabel('Appearance theme').selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    for (const name of ['Timer', 'Tasks', 'Reports', 'Settings']) {
      await page.getByRole('button', { name, exact: true }).click();
      await expect(page.getByRole('button', { name, exact: true })).toHaveCSS('font-size', '16px');
      if (name !== 'Timer') await expect(page.locator('.card-title h2').first()).toHaveCSS('font-size', '20px');
      await page.setViewportSize({ width: 960, height: 680 });
      await page.screenshot({ path: `test-results/review-${name.toLowerCase()}-${theme}.png`, fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(960);
    }
  }
});

test('desktop preferences autosave pinning, tray, notifications and appearance', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const desktopCard = page.locator('.desktop-settings');
  await expect(page.getByLabel('Close to system tray instead of exiting')).toBeChecked();
  await expect(page.getByLabel('Send completion notifications')).toBeChecked();
  await page.getByLabel('Appearance theme').selectOption('light');
  await page.getByLabel('Compact mode background opacity').fill('85');
  await page.getByLabel('Keep compact timer on top').uncheck();
  await page.getByLabel('Send completion notifications').uncheck();
  await page.getByLabel('Close to system tray instead of exiting').uncheck();
  await expect(desktopCard.getByRole('status')).toHaveText('Saved');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Appearance theme')).toHaveValue('light');
  await expect(page.getByLabel('Compact mode background opacity')).toHaveValue('85');
  await expect(page.getByLabel('Keep compact timer on top')).not.toBeChecked();
  await expect(page.getByLabel('Send completion notifications')).not.toBeChecked();
  await expect(page.getByLabel('Close to system tray instead of exiting')).not.toBeChecked();
});

test('compact fits long stopwatch hours beside both buttons', async ({ page }) => {
  await mockDesktop(page, { seconds: 36_000_001 });
  await page.setViewportSize({ width: 170, height: 44 }); await page.goto('/?view=compact');
  const time = page.locator('.compact-time');
  await expect(time).toHaveText('10000:00:01');
  await expect(time).toHaveCSS('font-size', '25px');
  await expect.poll(() => page.evaluate(() => (window as any).__compactSize?.width ?? 0)).toBeGreaterThan(170);
  const requested = await page.evaluate(() => (window as any).__compactSize);
  await page.setViewportSize(requested);
  const digits = (await page.locator('.compact-digits').boundingBox())!;
  const button = (await page.locator('button').first().boundingBox())!;
  const options = (await page.getByRole('button', { name: 'Options', exact: true }).boundingBox())!;
  expect(digits.x + digits.width + 8).toBeLessThanOrEqual(button.x);
  expect(options.x + options.width).toBe(requested.width - 6);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(requested.width);
});

test('compact serializes delayed native resizes and finishes at the latest digit width', async ({ page }) => {
  await mockDesktop(page, { seconds: 0, resizeDelay: 250 });
  await page.setViewportSize({ width: 170, height: 44 });
  await page.goto('/?view=compact');
  await expect(page.locator('.compact-time')).toHaveText('00:00');
  await page.evaluate(() => (window as any).__setSeconds(36_000_001));
  await expect.poll(() => page.evaluate(() => ((window as any).__resizeRequests ?? []).some((size: any) => size.width > 170))).toBe(true);
  await page.evaluate(() => (window as any).__setSeconds(0));
  await expect(page.locator('.compact-time')).toHaveText('00:00');
  await expect.poll(() => page.evaluate(() => ({ width: (window as any).__compactSize?.width, active: (window as any).__resizesActive }))).toEqual({ width: 170, active: 0 });
  expect(await page.evaluate(() => (window as any).__maxResizesActive)).toBe(1);
});

test('compact background follows the opacity setting', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, opacity: 60 });
  await page.goto('/?view=compact');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgba(20, 29, 43, 0.6)');
});

test('removed system, shortcut and motion settings stay absent', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'System', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Test notification', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Test sound', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Reduce motion and transitions')).toHaveCount(0);
  await expect(page.getByLabel('Enable global shortcuts')).toHaveCount(0);
  await expect(page.getByLabel('Global timer shortcut')).toHaveCount(0);
  await expect(page.getByLabel('Open main shortcut')).toHaveCount(0);
});

test('removed text-size settings stay absent and opacity targets compact', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Compact text size')).toHaveCount(0);
  await expect(page.getByLabel('Main text size')).toHaveCount(0);
  await expect(page.getByLabel('Window background opacity')).toHaveCount(0);
  await expect(page.getByLabel('Compact mode background opacity')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save preferences', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Save desktop preferences', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Reset changes', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Reset desktop changes', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Restore defaults', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Restore desktop defaults', exact: true })).toBeVisible();
});

test('settings restore buttons bring back defaults', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const timerCard = page.locator('.timer-settings');
  const desktopCard = page.locator('.desktop-settings');
  const dialog = page.getByRole('dialog');
  await page.getByLabel('Focus duration').fill('30');
  await expect(timerCard.getByRole('status')).toHaveText('Saved');
  await page.getByRole('button', { name: 'Restore defaults' }).click();
  await expect(dialog.getByRole('heading', { name: 'Restore default timer settings?' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Restore defaults' }).click();
  await expect(timerCard.getByRole('status')).toHaveText('Saved');
  await expect(page.getByLabel('Focus duration')).toHaveValue('25');
  await expect(page.getByLabel('Play a completion tone')).toBeChecked();
  await page.getByLabel('Appearance theme').selectOption('light');
  await expect(desktopCard.getByRole('status')).toHaveText('Saved');
  await page.getByRole('button', { name: 'Restore desktop defaults' }).click();
  await expect(dialog.getByRole('heading', { name: 'Restore default desktop settings?' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByLabel('Appearance theme')).toHaveValue('light');
  await page.getByRole('button', { name: 'Restore desktop defaults' }).click();
  await dialog.getByRole('button', { name: 'Restore desktop defaults' }).click();
  await expect(desktopCard.getByRole('status')).toHaveText('Saved');
  await expect(page.getByLabel('Appearance theme')).toHaveValue('dark');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Focus duration')).toHaveValue('25');
  await expect(page.getByLabel('Appearance theme')).toHaveValue('dark');
});

test('settings checkboxes only toggle on their own text', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const label = page.getByText('Send completion notifications', { exact: true });
  await label.scrollIntoViewIfNeeded();
  await label.click();
  await expect(page.getByLabel('Send completion notifications')).not.toBeChecked();
  const cardBox = await page.locator('.sound-settings').boundingBox();
  const labelBox = await label.boundingBox();
  await page.mouse.click(cardBox!.x + cardBox!.width - 30, labelBox!.y + labelBox!.height / 2);
  await expect(page.getByLabel('Send completion notifications')).not.toBeChecked();
});

test('timer New task button opens the tasks page with the title field focused', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'New task', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'New task' })).toBeFocused();
});

test('focus task picker only shows when the timer is idle', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  const taskSelect = page.getByLabel('Task for the next session');
  await expect(taskSelect).toBeVisible();
  await page.getByRole('button', { name: 'Start focus', exact: true }).click();
  await expect(taskSelect).toHaveCount(0);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(taskSelect).toHaveCount(0);
  await page.getByRole('button', { name: 'Resume', exact: true }).click();
  await expect(taskSelect).toHaveCount(0);
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.getByRole('button', { name: 'Finish and save' }).click();
  await expect(taskSelect).toBeVisible();
});

test('Linux focus task menu has bounded sizing and supports mouse and keyboard selection', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, platform: 'linux', taskTitle: 'A very long focus task title '.repeat(8), extraTasks: 12 });
  await page.goto('/');
  const picker = page.getByRole('combobox', { name: 'Task for the next session' });
  for (const theme of ['dark', 'light']) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByLabel('Appearance theme').selectOption(theme);
    await page.getByRole('button', { name: 'Timer', exact: true }).click();
    await picker.click();
    const menu = page.getByRole('listbox', { name: 'Focus task' });
    const controlBox = (await picker.boundingBox())!;
    const menuBox = (await menu.boundingBox())!;
    expect(controlBox.height).toBe(36);
    expect(menuBox.width).toBe(controlBox.width);
    expect(menuBox.height).toBeLessThanOrEqual(224);
    expect(await menu.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
    expect(await page.getByRole('option').count()).toBe(14); // Done tasks are excluded.
    expect((await page.getByRole('option').first().boundingBox())!.height).toBe(36);
    await page.screenshot({ path: `test-results/focus-task-menu-${theme}.png` });
    await picker.press('ArrowDown');
    await picker.press('Enter');
    await expect(picker).toContainText('A very long focus task title');
    await expect(menu).toHaveCount(0);
    await expect(picker).toBeFocused();
    await picker.press('ArrowDown');
    await picker.press('End');
    await picker.press('Escape');
    await expect(picker).toContainText('A very long focus task title');
    await picker.click();
    await page.getByRole('option', { name: 'No task selected', exact: true }).click();
    await expect(picker).toContainText('No task selected');
    await picker.click();
    await picker.press('Tab');
    await expect(menu).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'New task', exact: true })).toBeFocused();
    await picker.click();
    await page.getByRole('heading', { name: 'Timer', exact: true }).click();
    await expect(menu).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(960);
  }
});

test('recovery and interruption banners dismiss without losing the timer', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, recovered: true, interruption: 'sleep' });
  await page.goto('/');
  await expect(page.getByText('Your previous session was restored.')).toBeVisible();
  await page.getByRole('button', { name: 'Dismiss recovery notice' }).click();
  await expect(page.getByText('Your previous session was restored.')).toHaveCount(0);
  await expect(page.getByText('Paused before Windows suspended.')).toBeVisible();
  await page.getByRole('button', { name: 'Dismiss interruption notice' }).click();
  await expect(page.getByText('Paused before Windows suspended.')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Start focus', exact: true })).toBeVisible();
});

test('last session card summarizes the most recent record', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  const empty = page.locator('section', { has: page.getByRole('heading', { name: 'Last session' }) });
  await expect(empty.getByText('No sessions yet.')).toBeVisible();
  await mockDesktop(page, { seconds: 1500, lastRecord: true }); await page.reload();
  const filled = page.locator('section', { has: page.getByRole('heading', { name: 'Last session' }) });
  await expect(filled.getByText('Write tests')).toBeVisible();
  await expect(filled.getByText('Focus \u00b7 25:00 \u00b7 completed')).toBeVisible();
});

test('six-month heatmap keeps every week column the same width with a full history', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, denseHistory: true }); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  const weeks = page.locator('.heatmap-week');
  await expect(weeks).toHaveCount(27);
  const widths = await weeks.evaluateAll(elements => elements.map(element => Math.round(element.getBoundingClientRect().width)));
  expect(new Set(widths).size).toBe(1);
  const cells = await page.locator('button.heatmap-cell').evaluateAll(elements => elements.map(element => Math.round(element.getBoundingClientRect().height)));
  expect(new Set(cells).size).toBe(1);
  await page.screenshot({ path: 'test-results/heatmap-dense.png', fullPage: true });
});

test('heatmap day tooltip appears immediately with focus time and tasks done', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  const cell = page.locator('button.heatmap-cell:not([data-level="0"])').first();
  await cell.hover();
  const tip = page.getByRole('tooltip');
  await expect(tip).toBeVisible({ timeout: 300 });
  await expect(tip).toContainText(/\d+ min focused · \d+ tasks? done/);
  await page.screenshot({ path: 'test-results/heatmap-tooltip.png' });
  await expect(cell).toHaveAttribute('aria-label', /min focused · \d+ tasks? done/);
  await page.mouse.move(0, 0);
  await expect(tip).toHaveCount(0);
});

test('last 6 months and last year show a monthly focus chart', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-05T12:00:00Z'));
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Last 6 months', exact: true }).click();
  const chart = page.getByRole('region', { name: 'Focus by month' });
  await expect(chart).toBeVisible();
  await expect(chart.locator('.month-column')).toHaveCount(6);
  await page.screenshot({ path: 'test-results/reports-last-6-months.png', fullPage: true });
  await page.getByRole('button', { name: 'Last year', exact: true }).click();
  await expect(chart.locator('.month-column')).toHaveCount(12);
  await page.getByRole('button', { name: 'Last week', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Focus by month' })).toHaveCount(0);
});

test('reports table refreshes when a session lands while viewing reports', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  const table = page.locator('.report-card table');
  await expect(table.getByRole('row')).toHaveCount(3);
  await page.evaluate(() => (window as any).__TAURI_INTERNALS__.invoke('timer_command', { command: { type: 'finish' } }));
  await expect(table.getByRole('row')).toHaveCount(4);
  await expect(table.getByText('Fresh mock task')).toBeVisible();
});

test('report table leads with start time and sorts newest first', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  await expect(page.locator('.report-card thead th')).toHaveText(['When', 'Type', 'Task', 'Focus time']);
  const rows = page.locator('.report-card tbody tr');
  await expect(rows.nth(0).locator('td').nth(1)).toHaveText('Stopwatch');
  await expect(rows.nth(0).locator('td').nth(3)).toHaveText('10:00');
  await expect(rows.nth(1).locator('td').nth(1)).toHaveText('Focus');
  await expect(rows.nth(1).locator('td').nth(2)).toHaveText('Write tests');
});

test('tasks move across the board and completion feedback updates the report heatmap', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await page.screenshot({ path: 'test-results/tasks-board.png', fullPage: true });
  const task = page.locator('.task-item-card').filter({ hasText: 'Write tests' });
  await task.hover();
  await expect(task.locator('.task-card-controls')).toHaveCSS('opacity', '1');
  await page.screenshot({ path: 'test-results/tasks-hover.png', fullPage: true });
  await task.locator('.task-card-title').dragTo(page.locator('.column-in_progress'));
  await expect(page.locator('.column-in_progress')).toContainText('Write tests');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByLabel('Task for the next session').click();
  await expect(page.getByRole('option', { name: 'In progress · Write tests', exact: true })).toBeAttached();
  await expect(page.getByRole('option', { name: /Review requirements/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await task.locator('.task-card-title').dragTo(page.locator('.column-done'));
  await expect(page.locator('.column-done')).toContainText('Write tests');
  await expect(page.getByRole('status')).toContainText('Nice work!');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.getByText('Last six months · 3 completions')).toBeVisible();
  await expect(page.locator('.streak-card strong')).toHaveText('2');
  const heatmap = page.getByRole('group', { name: 'Task completions over the last six months' });
  await expect(heatmap).toBeVisible();
  const day = heatmap.locator('.heatmap-cell[aria-label]').first();
  await day.focus(); await expect(day).toBeFocused();
  await page.screenshot({ path: 'test-results/task-reports.png', fullPage: true });
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByLabel('Task for the next session').click();
  await expect(page.getByRole('option', { name: /Write tests/ })).toHaveCount(0);
});

test('settings reset reports clears recorded sessions everywhere', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  await expect(page.locator('.report-card tbody tr')).toHaveCount(2);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Reset reports', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Delete every recorded session and task completion');
  await dialog.getByRole('button', { name: 'Reset reports' }).click();
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.getByText('No sessions in this range')).toBeVisible();
  await expect(page.locator('.streak-card strong')).toHaveText('0');
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await expect(page.getByText('No sessions yet.')).toBeVisible();
  await expect(page.locator('.summary-card .summary-row').first()).toContainText('0 min · 0');
});

test('reports tab and page use the chart icon', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  const chart = 'M4 4v16h16M8 20v-9M12 20V8M16 20v-7';
  await expect(page.getByRole('navigation').getByRole('button', { name: 'Reports', exact: true }).locator('path')).toHaveAttribute('d', chart);
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.locator('.report-card .card-title path')).toHaveAttribute('d', chart);
});

test('macOS settings show menu bar and dock options instead of tray close', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, platform: 'macos' }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const desktopCard = page.locator('.desktop-settings');
  await expect(page.getByLabel('Show in menu bar')).toBeChecked();
  const dock = page.getByLabel('Hide Dock icon');
  await expect(dock).not.toBeChecked();
  await expect(dock).toBeEnabled();
  await expect(page.getByLabel('Close to system tray instead of exiting')).toHaveCount(0);
  await expect(page.getByText('macOS notification settings and Focus modes')).toBeVisible();
  await expect(page.getByText('Closing the main window always keeps the app running.')).toBeVisible();
  await page.getByLabel('Show in menu bar').uncheck();
  await expect(dock).toBeDisabled();
  await page.getByLabel('Show in menu bar').check();
  await expect(dock).toBeEnabled();
  await dock.check();
  await expect(desktopCard.getByRole('status')).toHaveText('Saved');
  await expect(dock).toBeChecked();
});

test('Linux settings show tray close and desktop notification hint', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, platform: 'linux' }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Close to system tray instead of exiting')).toBeChecked();
  await expect(page.getByText("your Linux desktop's notification settings")).toBeVisible();
  await expect(page.getByText('Windows notification settings')).toHaveCount(0);
  await expect(page.getByLabel('Show in menu bar')).toHaveCount(0);
});

test('timer controls stay inside the fixed window in both themes and all timer states', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, taskTitle: 'Review the release notes and confirm keyboard access for every control. '.repeat(2).slice(0, 120) }); await page.goto('/');
  await page.getByLabel('Task for the next session').click();
  await page.getByRole('option', { name: /Review the release notes/ }).click();
  for (const theme of ['dark', 'light']) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByLabel('Appearance theme').selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await page.getByRole('button', { name: 'Timer', exact: true }).click();
    await page.setViewportSize({ width: 960, height: 680 });
    for (const label of ['Start focus', 'Pause', 'Resume']) {
      const button = page.getByRole('button', { name: label, exact: true });
      await expect(button).toBeInViewport({ ratio: 1 });
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(960);
      if (label !== 'Start focus') await expect(page.getByRole('button', { name: 'Finish', exact: true })).toBeInViewport({ ratio: 1 });
      await button.click();
    }
    await page.getByRole('button', { name: 'Finish', exact: true }).click();
    await page.getByRole('button', { name: 'Finish and save', exact: true }).click();
    await page.screenshot({ path: `test-results/timer-${theme}.png` });
  }
});

test('task board exposes every status without horizontal scrolling', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.setViewportSize({ width: 960, height: 680 });
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  expect(await page.locator('.task-board').evaluate(element => element.scrollWidth === element.clientWidth)).toBe(true);
  for (const label of ['To do', 'In progress', 'Done']) {
    const heading = page.getByRole('heading', { name: label, exact: true });
    await heading.scrollIntoViewIfNeeded();
    await expect(heading).toBeInViewport({ ratio: 1 });
  }
  await page.screenshot({ path: 'test-results/task-board.png', fullPage: true });
});

test('a rejected task move stays in its column and can be retried', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, failTaskStatusOnce: true }); await page.goto('/');
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  const task = page.locator('.task-item-card').filter({ hasText: 'Write tests' });
  await task.locator('.task-card-title').dragTo(page.locator('.column-done'));
  await expect(page.getByRole('alert')).toContainText('Simulated database write failure');
  await expect(page.locator('.column-todo')).toContainText('Write tests');
  await task.locator('.task-card-title').dragTo(page.locator('.column-done'));
  await expect(page.locator('.column-done')).toContainText('Write tests');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.getByText('Last six months · 3 completions')).toBeVisible();
});

test('task cards edit inline and remove only after confirmation', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await page.getByRole('button', { name: 'Edit Write tests', exact: true }).click();
  await page.getByRole('textbox', { name: 'Edit task title' }).fill('Review the release');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Remove Review the release', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Saved sessions will keep its title.');
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.task-card-title')).toContainText(['Review the release', 'Review requirements']);
  await page.getByRole('button', { name: 'Remove Review the release', exact: true }).click();
  await dialog.getByRole('button', { name: 'Remove', exact: true }).click();
  await expect(page.locator('.task-item-card').filter({ hasText: 'Review the release' })).toHaveCount(0);
});

test('reports roll forward after midnight and refresh on resume without changing custom dates', async ({ page }) => {
  await page.clock.install({ time: new Date(2026, 9, 20, 12) });
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(page.locator('.streak-card strong')).toHaveText('2');
  await page.clock.setSystemTime(new Date(2026, 9, 22, 12));
  await page.clock.fastForward(30_000);
  await expect(page.locator('.heatmap-cell[aria-label]').last()).toHaveAttribute('aria-label', /October 22, 2026/);
  await expect(page.locator('.streak-card strong')).toHaveText('0');
  await expect(page.getByRole('button', { name: 'Today', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Custom', exact: true }).click();
  await page.getByLabel('Report start date').fill('2026-10-01');
  await page.getByLabel('Report end date').fill('2026-10-05');
  await page.getByRole('button', { name: 'Apply dates', exact: true }).click();
  await page.clock.setSystemTime(new Date(2026, 9, 25, 12));
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.locator('.heatmap-cell[aria-label]').last()).toHaveAttribute('aria-label', /October 25, 2026/);
  await expect(page.getByLabel('Report start date')).toHaveValue('2026-10-01');
  await expect(page.getByLabel('Report end date')).toHaveValue('2026-10-05');
});

test('settings groups put About last after data and reset', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.locator('.settings-card h2')).toHaveText(['Timer', 'Sound & notifications', 'Appearance & compact', 'Account & sync', 'Data & reset', 'About']);
  await page.getByLabel('Play a completion tone').check();
  await expect(page.locator('.sound-settings').getByRole('status')).toHaveText('Saved');
  await page.getByRole('button', { name: 'Reset reports', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Reset reports', exact: true })).toHaveClass(/danger/);
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
});

test('settings shows the installed version and checks for updates only on request', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, appVersion: '7.4.2', updateDelay: 500 }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const about = page.getByRole('region', { name: 'About', exact: true });
  await expect(about.getByText('Version 7.4.2', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).__updateCheckCalls ?? 0)).toBe(0);
  await about.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await expect(about.getByRole('button', { name: 'Checking…', exact: true })).toBeDisabled();
  await expect(about.getByRole('status')).toHaveText('Checking for updates…');
  await expect(about.getByRole('status')).toHaveText('You’re up to date.');
  await expect(about.getByRole('button', { name: 'Check for updates', exact: true })).toBeEnabled();
  await expect(about.getByRole('button', { name: 'View release', exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__updateCheckCalls)).toBe(1);
});

test('an available update opens its release page and browser errors can be retried', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, updateResponses: ['available'], failOpenReleaseOnce: true }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const about = page.getByRole('region', { name: 'About', exact: true });
  await about.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await expect(about.getByRole('status')).toHaveText('Version 1.3.0 is available.');
  await expect(about.getByText('Version 1.2.0', { exact: true })).toBeVisible();
  for (const theme of ['dark', 'light']) {
    await page.getByLabel('Appearance theme').selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await about.screenshot({ path: `test-results/settings-about-${theme}.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(960);
  }
  await about.getByRole('button', { name: 'View release', exact: true }).click();
  await expect(about.getByRole('alert')).toHaveText('Could not open your browser. Please try again.');
  await about.getByRole('button', { name: 'View release', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as any).__releasePageOpens ?? 0)).toBe(1);
  await expect(about.getByRole('alert')).toHaveCount(0);
});

test('failed update checks can be retried without blocking settings autosave', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, updateResponses: ['error', 'current'] }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const about = page.getByRole('region', { name: 'About', exact: true });
  await about.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await expect(about.getByRole('alert')).toContainText('Check your internet connection and try again.');
  await page.getByLabel('Keep compact timer on top').uncheck();
  await expect(page.locator('.desktop-settings').getByRole('status')).toHaveText('Saved');
  await about.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await expect(about.getByRole('status')).toHaveText('You’re up to date.');
  await expect(about.getByRole('alert')).toHaveCount(0);
});

test('update checks explain when no stable release is published', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, updateResponses: ['none'] }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const about = page.getByRole('region', { name: 'About', exact: true });
  await about.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await expect(about.getByRole('status')).toHaveText('No published releases are available yet.');
  await expect(about.getByRole('button', { name: 'View release', exact: true })).toHaveCount(0);
});

test('unconfigured cloud sync keeps tasks local and sign-in disabled', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const account = page.getByRole('region', { name: 'Account & sync', exact: true });
  await expect(account.getByRole('button', { name: 'Sign in with Google', exact: true })).toBeDisabled();
  await expect(account).toContainText('Google sign-in is not enabled in this build.');
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await expect(page.locator('.task-item-card').filter({ hasText: 'Write tests' })).toBeVisible();
});

test('Google sign-in can be cancelled, retried and completed', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, syncConfigured: true }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const account = page.getByRole('region', { name: 'Account & sync', exact: true });
  await account.getByRole('button', { name: 'Sign in with Google', exact: true }).click();
  await expect(account.getByRole('status')).toContainText('Finish signing in with Google in your browser.');
  await account.getByRole('button', { name: 'Cancel sign-in', exact: true }).click();
  await expect(account.getByRole('alert')).toHaveText('Google sign-in was cancelled.');
  await account.getByRole('button', { name: 'Sign in with Google', exact: true }).click();
  await page.evaluate(() => (window as any).__completeGoogleSignIn());
  await expect(account).toContainText('Signed in as focus@example.com');
  await expect(account.getByRole('alert')).toHaveCount(0);
  await expect(account.getByRole('button', { name: 'Sync now', exact: true })).toBeEnabled();
  for (const theme of ['dark', 'light']) {
    await page.getByLabel('Appearance theme').selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await account.screenshot({ path: `test-results/settings-account-${theme}.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(960);
  }
});

test('task sync errors are retryable and do not block preference saves', async ({ page }) => {
  await mockDesktop(page, { seconds: 1500, syncConfigured: true, accountEmail: 'focus@example.com', failSyncOnce: true }); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const account = page.getByRole('region', { name: 'Account & sync', exact: true });
  await account.getByRole('button', { name: 'Sync now', exact: true }).click();
  await expect(account.getByRole('button', { name: 'Syncing…', exact: true })).toBeDisabled();
  await expect(account.getByRole('alert')).toContainText('Tasks are saved on this device.');
  await page.getByLabel('Keep compact timer on top').uncheck();
  await expect(page.locator('.desktop-settings').getByRole('status')).toHaveText('Saved');
  await page.evaluate(() => (window as any).__finishBackgroundSync());
  await expect(account.getByRole('alert')).toHaveCount(0);
  await account.getByRole('button', { name: 'Sync now', exact: true }).click();
  await expect(account.getByRole('status')).toHaveText('All tasks are synced.');
  await expect(account.getByRole('alert')).toHaveCount(0);
  await expect(account).toContainText('Last synced');
});

test('signing out retains local tasks and synced changes refresh the task board', async ({ page }) => {
  const browserErrors: Error[] = [];
  page.on('pageerror', error => browserErrors.push(error));
  await mockDesktop(page, { seconds: 1500, syncConfigured: true, accountEmail: 'focus@example.com' }); await page.goto('/');
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await page.evaluate(() => (window as any).__deliverRemoteTask());
  await expect(page.locator('.task-item-card').filter({ hasText: 'Task from another device' })).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const account = page.getByRole('region', { name: 'Account & sync', exact: true });
  await account.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(account.getByRole('status')).toHaveText('Signed out. Your tasks and focus history remain on this device.');
  await expect(account.getByRole('button', { name: 'Sign in with Google', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await expect(page.locator('.task-item-card').filter({ hasText: 'Write tests' })).toBeVisible();
  await expect(page.locator('.task-item-card').filter({ hasText: 'Task from another device' })).toBeVisible();
  expect(browserErrors).toEqual([]);
});


test('synced focus history refreshes visible reports for additions and deletions', async ({ page }) => {
  await mockDesktop(page, { syncConfigured: true, accountEmail: 'focus@example.com' }); await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: 'Show sessions', exact: true }).click();
  const table = page.locator('.report-card table');
  await expect(table.getByRole('row')).toHaveCount(3);
  await page.evaluate(() => (window as any).__deliverRemoteHistory());
  await expect(table.getByRole('row')).toHaveCount(4);
  await expect(table.getByText('Focus from another device')).toBeVisible();
  await page.evaluate(() => (window as any).__deliverRemoteHistory(true));
  await expect(table.getByRole('row')).toHaveCount(3);
  await expect(table.getByText('Focus from another device')).toHaveCount(0);
});
