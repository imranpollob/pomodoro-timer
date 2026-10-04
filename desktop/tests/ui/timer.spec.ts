import { test, expect, type Page } from '@playwright/test';

async function mockDesktop(page: Page) {
  await page.addInitScript(() => {
    (window as unknown as { isTauri: boolean }).isTauri = true;
    const callbacks = new Map<number, (value: unknown) => void>();
    let callbackId = 0;
    const state = {
      phase: 'focus', status: 'idle', display_seconds: 1500, active_ms: 0, duration_ms: 1_500_000,
      cycle: 1, cycle_interval: 4, revision: 0, recovered: false, pending_save: false, last_error: null,
      settings: { focus_minutes: 25, short_break_minutes: 5, long_break_minutes: 15, long_break_interval: 4, sound_enabled: false }, records: [],
    };
    const listeners = new Map<string, number>();
    (window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = {
      transformCallback(callback: (value: unknown) => void) { callbacks.set(++callbackId, callback); return callbackId; },
      unregisterCallback(id: number) { callbacks.delete(id); },
      metadata: { currentWindow: { label: 'compact' }, currentWebview: { label: 'compact' } },
      async invoke(command: string, args: Record<string, any> = {}) {
        if (command === 'plugin:event|listen') { listeners.set(args.event, args.handler); return args.handler; }
        if (command === 'plugin:event|unlisten') return;
        if (command === 'get_snapshot') return structuredClone(state);
        if (command === 'desktop_info') return { os: 'test', arch: 'test', tray: 'Test transport', data_directory: '/temporary/test-profile' };
        if (command === 'timer_command') {
          const action = args.command;
          if (action.type === 'toggle') state.status = state.status === 'running' ? 'paused' : 'running';
          if (action.type === 'finish') { state.status = 'idle'; state.active_ms = 0; }
          if (action.type === 'set_mode') { state.phase = action.mode; state.display_seconds = action.mode === 'stopwatch' ? 0 : 1500; }
          if (action.type === 'configure') state.settings = action.settings;
          state.revision++;
          const handler = listeners.get('timer-state');
          if (handler) callbacks.get(handler)?.({ payload: structuredClone(state), id: handler, event: 'timer-state' });
          return structuredClone(state);
        }
      },
    };
  });
}

test('main timer pauses/resumes and finish dialog preserves keyboard focus', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await expect(page.getByRole('button', { name: 'Start focus', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Start focus', exact: true }).click();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(page.getByText('Paused · take a breath')).toBeVisible();
  await page.getByRole('button', { name: 'Resume', exact: true }).press('Space');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Keep focusing' }).click();
  await expect(page.getByRole('button', { name: 'Finish', exact: true })).toBeFocused();
  await expect(page.getByRole('button', { name: 'Pomodoro', exact: true })).toBeDisabled();
  await page.screenshot({ path: 'test-results/main-timer.png' });
});

test('compact has one action button and fits 200 by 44', async ({ page }) => {
  await mockDesktop(page); await page.setViewportSize({ width: 200, height: 44 }); await page.goto('/?view=compact');
  const action = page.locator('button');
  await expect(action).toHaveCount(1);
  await expect(action).toHaveAccessibleName('Start focus');
  await action.click(); await expect(action).toHaveAccessibleName('Pause');
  await page.keyboard.press('Space'); await expect(action).toHaveAccessibleName('Resume');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(200);
  const box = await action.boundingBox(); expect(box!.x + box!.width).toBeLessThanOrEqual(200);
  await page.screenshot({ path: 'test-results/compact-timer.png' });
});

test('preferences save through backend and invalid fields block submission', async ({ page }) => {
  await mockDesktop(page); await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByLabel('Focus duration').fill('0');
  await page.getByRole('button', { name: 'Save preferences' }).click();
  expect(await page.getByLabel('Focus duration').evaluate((input: HTMLInputElement) => input.validity.rangeUnderflow)).toBe(true);
  await page.getByLabel('Focus duration').fill('30'); await page.getByRole('button', { name: 'Save preferences' }).click();
  await page.getByRole('button', { name: 'Timer', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByLabel('Focus duration')).toHaveValue('30');
  await page.screenshot({ path: 'test-results/settings.png' });
});

test('empty history and missing desktop connection have honest recovery paths', async ({ page }) => {
  await page.goto('/'); await expect(page.getByText('Desktop connection unavailable')).toBeVisible();
  await mockDesktop(page); await page.reload();
  await page.getByRole('button', { name: 'Sessions', exact: true }).click();
  await expect(page.getByText('Your first session starts here.')).toBeVisible();
  await page.getByRole('button', { name: 'Open timer' }).click();
  await expect(page.getByRole('button', { name: 'Start focus', exact: true })).toBeVisible();
});
