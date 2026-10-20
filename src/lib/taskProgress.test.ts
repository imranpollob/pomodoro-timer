import { describe, expect, it } from 'vitest';
import { buildCompletionSummary } from './taskProgress';
import type { TaskCompletionEvent } from './types';

function completion(id: string, year: number, month: number, day: number): TaskCompletionEvent {
  return { id, task_id: `task-${id}`, completed_unix_ms: new Date(year, month, day, 12).getTime() };
}

function visibleDays(summary: ReturnType<typeof buildCompletionSummary>) {
  return summary.weeks.flatMap(week => week.days).filter((day): day is NonNullable<typeof day> => day !== null);
}

describe('task completion reports', () => {
  it('builds a local-calendar three-month grid with daily counts', () => {
    const summary = buildCompletionSummary([
      completion('old', 2026, 0, 4),
      completion('one', 2026, 3, 30),
      completion('two', 2026, 3, 30),
      completion('future', 2026, 7, 1),
    ], new Date(2026, 6, 31, 15));
    const days = visibleDays(summary);
    expect(days[0].day).toBe('2026-04-30');
    expect(days.at(-1)?.day).toBe('2026-07-31');
    expect(days.find(day => day.day === '2026-04-30')?.count).toBe(2);
    expect(summary.total).toBe(2);
  });

  it('keeps a streak alive through today or yesterday and stops at a gap', () => {
    const now = new Date(2026, 6, 10, 15);
    expect(buildCompletionSummary([
      completion('a', 2026, 6, 8), completion('b', 2026, 6, 9),
    ], now).streak).toBe(2);
    expect(buildCompletionSummary([
      completion('a', 2026, 6, 7), completion('b', 2026, 6, 9),
    ], now).streak).toBe(1);
    expect(buildCompletionSummary([completion('a', 2026, 6, 8)], now).streak).toBe(0);
  });

  it('counts repeated completions and keeps a streak longer than the graph window', () => {
    const events = Array.from({ length: 100 }, (_, index) => {
      const day = new Date(2026, 3, 1 + index, 12);
      return { id: String(index), task_id: 'task-repeat', completed_unix_ms: day.getTime() };
    });
    const now = new Date(2026, 6, 9, 15);
    const summary = buildCompletionSummary(events, now);
    expect(summary.streak).toBe(100);
    expect(summary.total).toBeLessThan(100);
  });
});
