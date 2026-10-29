import { localDate, type SessionRecord } from './types';

export interface FocusDay {
  day: string;
  minutes: number;
  date: Date;
}

export interface FocusWeek {
  days: (FocusDay | null)[];
  month: string;
}

export interface FocusSummary {
  weeks: FocusWeek[];
  streak: number;
  total: number;
}

export function buildFocusSummary(sessions: SessionRecord[], now = new Date()): FocusSummary {
  const minutes = new Map<string, number>();
  for (const record of sessions) {
    if (record.phase !== 'focus' && record.phase !== 'stopwatch') continue;
    const day = localDate(new Date(record.started_unix_ms));
    minutes.set(day, (minutes.get(day) ?? 0) + record.active_ms / 60_000);
  }

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(today);
  const dayOfMonth = start.getDate();
  start.setDate(1);
  start.setMonth(start.getMonth() - 6);
  start.setDate(Math.min(dayOfMonth, new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate()));

  const cells: (FocusDay | null)[] = Array(start.getDay()).fill(null);
  const cursor = new Date(start);
  while (cursor <= today) {
    const day = localDate(cursor);
    cells.push({ day, minutes: minutes.get(day) ?? 0, date: new Date(cursor) });
    cursor.setDate(cursor.getDate() + 1);
  }
  while (cells.length % 7) cells.push(null);

  const weeks = Array.from({ length: cells.length / 7 }, (_, index) => {
    const days = cells.slice(index * 7, (index + 1) * 7);
    const monthStart = days.find(day => day?.date.getDate() === 1);
    return { days, month: monthStart?.date.toLocaleDateString(undefined, { month: 'short' }) ?? '' };
  });

  let streak = 0;
  const streakCursor = new Date(today);
  if ((minutes.get(localDate(streakCursor)) ?? 0) <= 5) streakCursor.setDate(streakCursor.getDate() - 1);
  while ((minutes.get(localDate(streakCursor)) ?? 0) > 5) {
    streak += 1;
    streakCursor.setDate(streakCursor.getDate() - 1);
  }

  const startDay = localDate(start);
  const todayDay = localDate(today);
  const total = [...minutes].reduce((sum, [day, value]) => day >= startDay && day <= todayDay ? sum + value : sum, 0);
  return { weeks, streak, total };
}

// The same strict threshold drives both green cells and streak eligibility.
export function focusLevel(minutes: number): number {
  return minutes <= 5 ? 0 : minutes <= 25 ? 1 : minutes <= 60 ? 2 : minutes <= 120 ? 3 : 4;
}
