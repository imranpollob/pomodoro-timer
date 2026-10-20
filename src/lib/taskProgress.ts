import type { TaskCompletionEvent } from './types';

export interface CompletionDay {
  day: string;
  count: number;
  date: Date;
}

export interface CompletionWeek {
  days: (CompletionDay | null)[];
  month: string;
}

export interface CompletionSummary {
  weeks: CompletionWeek[];
  streak: number;
  total: number;
}

function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function buildCompletionSummary(events: TaskCompletionEvent[], now = new Date()): CompletionSummary {
  const counts = new Map<string, number>();
  for (const event of events) {
    const day = localDate(new Date(event.completed_unix_ms));
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(today);
  const dayOfMonth = start.getDate();
  start.setDate(1);
  start.setMonth(start.getMonth() - 3);
  start.setDate(Math.min(dayOfMonth, new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate()));

  const cells: (CompletionDay | null)[] = Array(start.getDay()).fill(null);
  const cursor = new Date(start);
  while (cursor <= today) {
    const day = localDate(cursor);
    cells.push({ day, count: counts.get(day) ?? 0, date: new Date(cursor) });
    cursor.setDate(cursor.getDate() + 1);
  }
  while (cells.length % 7) cells.push(null);

  const weeks = Array.from({ length: cells.length / 7 }, (_, index) => {
    const days = cells.slice(index * 7, (index + 1) * 7);
    const monthStart = days.find(day => day?.date.getDate() === 1);
    const firstDay = days.find(day => day !== null);
    return {
      days,
      month: monthStart?.date.toLocaleDateString(undefined, { month: 'short' })
        ?? (index === 0 ? firstDay?.date.toLocaleDateString(undefined, { month: 'short' }) ?? '' : ''),
    };
  });

  let streak = 0;
  const streakCursor = new Date(today);
  if (!counts.has(localDate(streakCursor))) streakCursor.setDate(streakCursor.getDate() - 1);
  while (counts.has(localDate(streakCursor))) {
    streak += 1;
    streakCursor.setDate(streakCursor.getDate() - 1);
  }

  const startDay = localDate(start);
  const todayDay = localDate(today);
  const total = [...counts].reduce((sum, [day, count]) => day >= startDay && day <= todayDay ? sum + count : sum, 0);
  return { weeks, streak, total };
}
