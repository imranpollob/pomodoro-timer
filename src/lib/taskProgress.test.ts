import { describe, expect, it } from 'vitest';
import { buildFocusSummary, focusLevel } from './taskProgress';
import type { SessionRecord } from './types';

function session(id: string, phase: SessionRecord['phase'], year: number, month: number, day: number, activeMinutes: number): SessionRecord {
  return {
    id, phase, started_unix_ms: new Date(year, month, day, 9).getTime(), active_ms: activeMinutes * 60_000,
    outcome: 'finished', task: null,
  };
}
function visibleDays(summary: ReturnType<typeof buildFocusSummary>) {
  return summary.weeks.flatMap(week => week.days).filter((day): day is NonNullable<typeof day> => day !== null);
}

describe('daily focus minutes', () => {
  it('builds a local-calendar six-month grid from saved focus and stopwatch minutes', () => {
    const summary = buildFocusSummary([
      session('old', 'focus', 2025, 11, 4, 30),
      session('focus', 'focus', 2026, 3, 30, 25),
      session('stopwatch', 'stopwatch', 2026, 3, 30, 10),
      session('short-break', 'short_break', 2026, 3, 30, 5),
      session('long-break', 'long_break', 2026, 3, 30, 15),
      session('future', 'focus', 2026, 7, 1, 60),
    ], new Date(2026, 6, 31, 15));
    const days = visibleDays(summary);
    expect(days[0].day).toBe('2026-01-31');
    expect(days.at(-1)?.day).toBe('2026-07-31');
    expect(days.find(day => day.day === '2026-04-30')?.minutes).toBe(35);
    expect(summary.total).toBe(35);
  });

  it('requires strictly more than five total minutes for green cells and streak days', () => {
    expect([0, 4.99, 5, 5.01, 25, 25.01, 60, 60.01, 120, 120.01].map(focusLevel))
      .toEqual([0, 0, 0, 1, 1, 2, 2, 3, 3, 4]);
    const now = new Date(2026, 6, 10, 15);
    const history = [
      session('five', 'focus', 2026, 6, 7, 5),
      session('a', 'focus', 2026, 6, 8, 6),
      session('b', 'focus', 2026, 6, 9, 3),
      session('c', 'stopwatch', 2026, 6, 9, 3),
    ];
    expect(buildFocusSummary(history, now).streak).toBe(2);
    expect(buildFocusSummary([...history, session('today', 'focus', 2026, 6, 10, 5)], now).streak).toBe(2);
    expect(buildFocusSummary([...history, session('today', 'focus', 2026, 6, 10, 5.01)], now).streak).toBe(3);
    expect(buildFocusSummary([history[1]], now).streak).toBe(0);
  });

  it('keeps a streak longer than the graph window', () => {
    const history = Array.from({ length: 200 }, (_, index) => {
      const day = new Date(2026, 6, 9 - (199 - index), 9);
      return session(String(index), 'focus', day.getFullYear(), day.getMonth(), day.getDate(), 6);
    });
    const summary = buildFocusSummary(history, new Date(2026, 6, 9, 15));
    expect(summary.streak).toBe(200);
    expect(summary.total).toBeLessThan(1200);
  });
});
