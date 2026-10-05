export type Phase = 'focus' | 'short_break' | 'long_break' | 'stopwatch';
export interface Settings {
  focus_minutes: number; short_break_minutes: number; long_break_minutes: number;
  long_break_interval: number; sound_enabled: boolean; auto_start_next: boolean;
}
export interface SessionRecord {
  id: string; phase: Phase; started_unix_ms: number; active_ms: number; outcome: string; task?: TaskReference | null;
}
export interface TaskReference { id: string; title: string }
export interface Task extends TaskReference { completed: boolean; created_unix_ms: number; updated_unix_ms: number }
export interface DailyTotals { pomodoro_ms: number; stopwatch_ms: number; pomodoro_sessions: number; stopwatch_sessions: number }
export interface Snapshot {
  phase: Phase; status: 'idle' | 'running' | 'paused'; display_seconds: number;
  active_ms: number; duration_ms: number | null; cycle: number; cycle_interval: number;
  settings: Settings; revision: number; recovered: boolean; pending_save: boolean;
  last_error: string | null; records: SessionRecord[];
  interruption?: string | null;
  selected_task: TaskReference | null; active_task: TaskReference | null;
}
export type Command = { type: 'toggle' | 'pause' | 'finish' | 'retry_save' }
  | { type: 'set_mode'; mode: Phase } | { type: 'configure'; settings: Settings }
  | { type: 'select_task'; task: TaskReference | null };
export interface DesktopPreferences {
  volume: number; theme: 'dark' | 'light';
  opacity_percent: number; pinned: boolean; notifications: boolean; close_to_tray: boolean;
}
export interface DesktopState {
  revision: number; preferences: DesktopPreferences;
  notification_status: string; audio_status: string; power_status: string;
}
export const phaseLabel: Record<Phase, string> = {
  focus: 'Focus', short_break: 'Short break', long_break: 'Long break', stopwatch: 'Stopwatch',
};
export function formatTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = String(safe % 60).padStart(2, '0');
  return minutes >= 60 ? `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}:${remainder}`
    : `${String(minutes).padStart(2, '0')}:${remainder}`;
}
export function actionLabel(snapshot: Snapshot): string {
  if (snapshot.pending_save) return 'Retry save';
  return snapshot.status === 'running' ? 'Pause' : snapshot.status === 'paused' ? 'Resume'
    : snapshot.phase === 'focus' ? 'Start focus' : snapshot.phase === 'stopwatch' ? 'Start stopwatch' : 'Start break';
}
