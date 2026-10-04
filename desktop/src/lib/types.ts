export type Phase = 'focus' | 'short_break' | 'long_break' | 'stopwatch';
export interface Settings {
  focus_minutes: number; short_break_minutes: number; long_break_minutes: number;
  long_break_interval: number; sound_enabled: boolean;
}
export interface SessionRecord {
  id: string; phase: Phase; started_unix_ms: number; active_ms: number; outcome: string;
}
export interface Snapshot {
  phase: Phase; status: 'idle' | 'running' | 'paused'; display_seconds: number;
  active_ms: number; duration_ms: number | null; cycle: number; cycle_interval: number;
  settings: Settings; revision: number; recovered: boolean; pending_save: boolean;
  last_error: string | null; records: SessionRecord[];
}
export type Command = { type: 'toggle' | 'pause' | 'finish' | 'retry_save' }
  | { type: 'set_mode'; mode: Phase } | { type: 'configure'; settings: Settings };
export interface DesktopInfo { os: string; arch: string; tray: string; data_directory: string }
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
