//! Clock-injected timer domain and transactional prototype persistence.
pub mod service;
pub mod store;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Focus,
    ShortBreak,
    LongBreak,
    Stopwatch,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Settings {
    pub focus_minutes: u32,
    pub short_break_minutes: u32,
    pub long_break_minutes: u32,
    pub long_break_interval: u32,
    pub sound_enabled: bool,
    #[serde(default)]
    pub auto_start_next: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TaskReference {
    pub id: String,
    pub title: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub title: String,
    pub completed: bool,
    pub created_unix_ms: u64,
    pub updated_unix_ms: u64,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            focus_minutes: 25,
            short_break_minutes: 5,
            long_break_minutes: 15,
            long_break_interval: 4,
            sound_enabled: true,
            auto_start_next: false,
        }
    }
}

impl Settings {
    pub fn validate(&self) -> Result<(), String> {
        if !(1..=60).contains(&self.focus_minutes)
            || !(1..=30).contains(&self.short_break_minutes)
            || !(1..=60).contains(&self.long_break_minutes)
            || !(1..=10).contains(&self.long_break_interval)
        {
            return Err("Durations must be positive and within the editor's ranges.".into());
        }
        Ok(())
    }
    pub fn duration_ms(&self, phase: Phase) -> Option<u64> {
        let minutes = match phase {
            Phase::Focus => self.focus_minutes,
            Phase::ShortBreak => self.short_break_minutes,
            Phase::LongBreak => self.long_break_minutes,
            Phase::Stopwatch => return None,
        };
        Some(u64::from(minutes) * 60_000)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActiveSession {
    id: String,
    phase: Phase,
    started_unix_ms: u64,
    duration_ms: Option<u64>,
    interval: u32,
    elapsed_ms: u64,
    #[serde(default)]
    task: Option<TaskReference>,
    #[serde(skip)]
    started_tick: Option<u64>,
}

impl ActiveSession {
    fn elapsed(&self, now: u64) -> u64 {
        let elapsed = self.elapsed_ms.saturating_add(
            self.started_tick
                .map_or(0, |started| now.saturating_sub(started)),
        );
        self.duration_ms
            .map_or(elapsed, |duration| elapsed.min(duration))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Engine {
    settings: Settings,
    phase: Phase,
    completed_focus: u32,
    active: Option<ActiveSession>,
    #[serde(default)]
    selected_task: Option<TaskReference>,
}

impl Default for Engine {
    fn default() -> Self {
        Self {
            settings: Settings::default(),
            phase: Phase::Focus,
            completed_focus: 0,
            active: None,
            selected_task: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Command {
    Toggle,
    Pause,
    Finish,
    AutoFinish,
    SetMode { mode: Phase },
    Configure { settings: Settings },
    SelectTask { task: Option<TaskReference> },
    RetrySave,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Record {
    pub id: String,
    pub phase: Phase,
    pub started_unix_ms: u64,
    pub active_ms: u64,
    pub outcome: String,
    #[serde(default)]
    pub task: Option<TaskReference>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimerView {
    pub phase: Phase,
    pub status: String,
    pub display_seconds: u64,
    pub active_ms: u64,
    pub duration_ms: Option<u64>,
    pub cycle: u32,
    pub cycle_interval: u32,
    pub settings: Settings,
    pub selected_task: Option<TaskReference>,
    pub active_task: Option<TaskReference>,
}

impl Engine {
    pub fn clear_selected_task_if(&mut self, id: &str) {
        if self
            .selected_task
            .as_ref()
            .is_some_and(|task| task.id == id)
        {
            self.selected_task = None;
        }
    }

    pub fn apply(
        &mut self,
        command: Command,
        now: u64,
        wall: u64,
    ) -> Result<Option<Record>, String> {
        match command {
            Command::Toggle => {
                if self.active.is_none() {
                    self.active = Some(ActiveSession {
                        id: Uuid::new_v4().to_string(),
                        phase: self.phase,
                        started_unix_ms: wall,
                        duration_ms: self.settings.duration_ms(self.phase),
                        interval: self.settings.long_break_interval,
                        elapsed_ms: 0,
                        task: self.selected_task.clone(),
                        started_tick: Some(now),
                    });
                } else if self.running() {
                    self.pause(now);
                } else if let Some(active) = &mut self.active {
                    active.started_tick = Some(now);
                }
            }
            Command::Pause => self.pause(now),
            finish @ (Command::Finish | Command::AutoFinish) => {
                let auto_start = finish == Command::AutoFinish;
                let Some(active) = self.active.take() else {
                    return Ok(None);
                };
                let elapsed = active.elapsed(now);
                let completed = active
                    .duration_ms
                    .is_some_and(|duration| elapsed >= duration);
                let outcome = if active.phase == Phase::Stopwatch {
                    "finished"
                } else if completed {
                    "completed"
                } else if active.phase == Phase::Focus {
                    "interrupted"
                } else {
                    "skipped"
                };
                self.phase = match active.phase {
                    Phase::Focus if completed => {
                        self.completed_focus += 1;
                        if self.completed_focus.is_multiple_of(active.interval) {
                            Phase::LongBreak
                        } else {
                            Phase::ShortBreak
                        }
                    }
                    Phase::Stopwatch => Phase::Stopwatch,
                    Phase::LongBreak if completed => {
                        self.completed_focus = 0;
                        Phase::Focus
                    }
                    _ => Phase::Focus,
                };
                let record = Record {
                    id: active.id,
                    phase: active.phase,
                    started_unix_ms: active.started_unix_ms,
                    active_ms: elapsed,
                    outcome: outcome.into(),
                    task: active.task,
                };
                if auto_start
                    && completed
                    && self.settings.auto_start_next
                    && self.phase != Phase::Stopwatch
                {
                    self.active = Some(ActiveSession {
                        id: Uuid::new_v4().to_string(),
                        phase: self.phase,
                        started_unix_ms: wall,
                        duration_ms: self.settings.duration_ms(self.phase),
                        interval: self.settings.long_break_interval,
                        elapsed_ms: 0,
                        task: self.selected_task.clone(),
                        started_tick: Some(now),
                    });
                }
                return Ok(Some(record));
            }
            Command::SetMode { mode } => {
                if self.active.is_some() {
                    return Err("Finish the current session before changing mode.".into());
                }
                if !matches!(mode, Phase::Focus | Phase::Stopwatch) {
                    return Err("Choose Pomodoro or Stopwatch.".into());
                }
                self.phase = mode;
            }
            Command::Configure { settings } => {
                settings.validate()?;
                self.settings = settings;
            }
            Command::SelectTask { task } => {
                self.selected_task = task;
            }
            Command::RetrySave => return Err("Retry is handled by the persistence service.".into()),
        }
        Ok(None)
    }
    pub fn running(&self) -> bool {
        self.active
            .as_ref()
            .is_some_and(|a| a.started_tick.is_some())
    }
    pub fn has_active(&self) -> bool {
        self.active.is_some()
    }
    pub fn completed(&self, now: u64) -> bool {
        self.active
            .as_ref()
            .is_some_and(|a| a.duration_ms.is_some_and(|d| a.elapsed(now) >= d))
    }
    pub fn pause(&mut self, now: u64) {
        if let Some(active) = &mut self.active {
            active.elapsed_ms = active.elapsed(now);
            active.started_tick = None;
        }
    }
    pub fn checkpoint(&self, now: u64) -> Self {
        let mut copy = self.clone();
        copy.pause(now);
        copy
    }
    pub fn validate(&self) -> Result<(), String> {
        self.settings.validate()?;
        if self.selected_task.as_ref().is_some_and(|task| {
            task.id.trim().is_empty()
                || task.title.trim().is_empty()
                || task.title.chars().count() > 120
        }) {
            return Err("Invalid selected task in timer checkpoint.".into());
        }
        if let Some(a) = &self.active
            && (Uuid::parse_str(&a.id).is_err()
                || a.phase != self.phase
                || !(1..=10).contains(&a.interval)
                || a.duration_ms.is_some_and(|d| d == 0 || d > 3_600_000)
                || (a.phase == Phase::Stopwatch) != a.duration_ms.is_none()
                || a.duration_ms.is_some_and(|d| a.elapsed_ms > d))
        {
            return Err("Invalid saved timer checkpoint; original data was left intact.".into());
        }
        Ok(())
    }
    pub fn view(&self, now: u64) -> TimerView {
        let elapsed = self.active.as_ref().map_or(0, |a| a.elapsed(now));
        let duration = self
            .active
            .as_ref()
            .map_or_else(|| self.settings.duration_ms(self.phase), |a| a.duration_ms);
        let interval = self
            .active
            .as_ref()
            .map_or(self.settings.long_break_interval, |a| a.interval);
        TimerView {
            phase: self.phase,
            status: if self.running() {
                "running"
            } else if self.active.is_some() {
                "paused"
            } else {
                "idle"
            }
            .into(),
            display_seconds: duration
                .map_or(elapsed / 1000, |d| d.saturating_sub(elapsed).div_ceil(1000)),
            active_ms: elapsed,
            duration_ms: duration,
            cycle: self.completed_focus % interval + 1,
            cycle_interval: interval,
            settings: self.settings.clone(),
            selected_task: self.selected_task.clone(),
            active_task: self.active.as_ref().and_then(|active| active.task.clone()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn old_settings_deserialize_with_auto_start_disabled() {
        let old = serde_json::json!({
            "focus_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "long_break_interval": 4,
            "sound_enabled": true
        });
        let settings: Settings = serde_json::from_value(old).unwrap();
        assert!(!settings.auto_start_next);
    }
    #[test]
    fn pauses_and_fractional_segments_share_one_clock() {
        let mut e = Engine::default();
        e.apply(Command::Toggle, 100, 0).unwrap();
        e.apply(Command::Toggle, 850, 0).unwrap();
        e.apply(Command::Toggle, 100_850, 0).unwrap();
        assert_eq!(e.view(101_600).active_ms, 1500);
        assert_eq!(e.view(101_600).display_seconds, 1499);
        let record = e.apply(Command::Finish, 101_600, 0).unwrap().unwrap();
        assert_eq!(record.active_ms, 1500);
        assert!(e.apply(Command::Finish, 101_600, 0).unwrap().is_none());
    }
    #[test]
    fn delayed_completion_clamps_and_uses_original_settings() {
        let mut e = Engine::default();
        e.apply(Command::Toggle, 0, 0).unwrap();
        e.apply(
            Command::Configure {
                settings: Settings {
                    focus_minutes: 30,
                    long_break_interval: 1,
                    ..Settings::default()
                },
            },
            60_000,
            0,
        )
        .unwrap();
        assert_eq!(e.view(60_000).display_seconds, 1440);
        let record = e.apply(Command::Finish, 2_000_000, 0).unwrap().unwrap();
        assert_eq!(record.active_ms, 1_500_000);
        assert_eq!(record.outcome, "completed");
        assert_eq!(e.view(2_000_000).phase, Phase::ShortBreak);
    }
    #[test]
    fn stopwatch_has_hours_and_excludes_pauses() {
        let mut e = Engine::default();
        e.apply(
            Command::SetMode {
                mode: Phase::Stopwatch,
            },
            0,
            0,
        )
        .unwrap();
        e.apply(Command::Toggle, 0, 0).unwrap();
        e.pause(3_600_500);
        e.apply(Command::Toggle, 9_000_000, 0).unwrap();
        assert_eq!(e.view(9_000_500).display_seconds, 3601);
    }
    #[test]
    fn mode_changes_cannot_discard_paused_work() {
        let mut e = Engine::default();
        e.apply(Command::Toggle, 0, 0).unwrap();
        e.pause(1000);
        assert!(
            e.apply(
                Command::SetMode {
                    mode: Phase::Stopwatch
                },
                1000,
                0
            )
            .is_err()
        );
        assert_eq!(e.view(1000).phase, Phase::Focus);
    }
    #[test]
    fn restart_recovers_paused_without_process_down_gap() {
        let mut e = Engine::default();
        e.apply(Command::Toggle, 0, 0).unwrap();
        let recovered: Engine =
            serde_json::from_str(&serde_json::to_string(&e.checkpoint(65_000)).unwrap()).unwrap();
        recovered.validate().unwrap();
        assert_eq!(recovered.view(9_000_000).status, "paused");
        assert_eq!(recovered.view(9_000_000).active_ms, 65_000);
    }
    #[test]
    fn long_break_cycle_and_skip_are_explicit() {
        let mut e = Engine::default();
        for i in 0..4 {
            e.apply(Command::Toggle, 0, 0).unwrap();
            e.apply(Command::Finish, 1_500_000, 0).unwrap();
            assert_eq!(
                e.view(0).phase,
                if i == 3 {
                    Phase::LongBreak
                } else {
                    Phase::ShortBreak
                }
            );
            e.apply(Command::Toggle, 0, 0).unwrap();
            let duration = e.view(0).duration_ms.unwrap();
            e.apply(Command::Finish, duration, 0).unwrap();
        }
        assert_eq!(e.view(0).cycle, 1);
    }
    #[test]
    fn auto_finish_starts_the_next_phase_only_when_preference_is_enabled() {
        let mut engine = Engine::default();
        engine
            .apply(
                Command::Configure {
                    settings: Settings {
                        auto_start_next: true,
                        ..Settings::default()
                    },
                },
                0,
                0,
            )
            .unwrap();
        engine.apply(Command::Toggle, 0, 10_000).unwrap();
        let record = engine
            .apply(Command::AutoFinish, 25 * 60_000, 25 * 60_000 + 10_000)
            .unwrap()
            .unwrap();
        assert_eq!(record.outcome, "completed");
        let next = engine.view(25 * 60_000);
        assert_eq!(next.phase, Phase::ShortBreak);
        assert_eq!(next.status, "running");
        assert_eq!(next.active_ms, 0);
        assert_eq!(next.duration_ms, Some(5 * 60_000));
    }
    #[test]
    fn manual_finish_never_auto_starts_the_following_phase() {
        let mut engine = Engine::default();
        engine
            .apply(
                Command::Configure {
                    settings: Settings {
                        auto_start_next: true,
                        ..Settings::default()
                    },
                },
                0,
                0,
            )
            .unwrap();
        engine.apply(Command::Toggle, 0, 0).unwrap();
        engine
            .apply(Command::Finish, 25 * 60_000, 25 * 60_000)
            .unwrap();
        assert_eq!(engine.view(25 * 60_000).phase, Phase::ShortBreak);
        assert_eq!(engine.view(25 * 60_000).status, "idle");
    }
    #[test]
    fn invalid_settings_cannot_mutate_session() {
        let mut e = Engine::default();
        assert!(
            e.apply(
                Command::Configure {
                    settings: Settings {
                        long_break_interval: 0,
                        ..Settings::default()
                    }
                },
                0,
                0
            )
            .is_err()
        );
        assert_eq!(e.view(0).settings.long_break_interval, 4);
    }
}
