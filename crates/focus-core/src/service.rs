//! One serialized owner for timer commands, checkpoints and completion records.
use crate::{
    Command, Engine, Record, Task, TimerView,
    store::{DailyTotals, Store},
};
use serde::Serialize;
use std::{
    sync::{Arc, mpsc},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

#[derive(Debug, Clone, Serialize)]
pub struct Snapshot {
    #[serde(flatten)]
    pub timer: TimerView,
    pub revision: u64,
    pub recovered: bool,
    pub pending_save: bool,
    pub last_error: Option<String>,
    pub records: Vec<Record>,
    pub interruption: Option<String>,
}

pub trait Clock: Send + Sync + 'static {
    fn monotonic_ms(&self) -> u64;
    fn unix_ms(&self) -> u64;
}

pub struct SystemClock {
    origin: Instant,
}
impl Default for SystemClock {
    fn default() -> Self {
        Self {
            origin: Instant::now(),
        }
    }
}
impl Clock for SystemClock {
    fn monotonic_ms(&self) -> u64 {
        self.origin.elapsed().as_millis() as u64
    }
    fn unix_ms(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
    }
}

enum Request {
    Read(mpsc::Sender<Snapshot>),
    Apply(Command, mpsc::Sender<Result<Snapshot, String>>),
    Interrupt(String, u64, mpsc::Sender<Result<Snapshot, String>>),
    ReadPreference(String, mpsc::Sender<Result<Option<String>, String>>),
    SavePreference(String, String, mpsc::Sender<Result<(), String>>),
    ReadTasks(mpsc::Sender<Result<Vec<Task>, String>>),
    CreateTask(String, mpsc::Sender<Result<Task, String>>),
    RenameTask(String, String, mpsc::Sender<Result<Task, String>>),
    CompleteTask(String, bool, mpsc::Sender<Result<(), String>>),
    DeleteTask(String, mpsc::Sender<Result<(), String>>),
    DailyTotals(u64, u64, mpsc::Sender<Result<DailyTotals, String>>),
    ReportRecords(u64, u64, mpsc::Sender<Result<Vec<Record>, String>>),
    ResetReports(mpsc::Sender<Result<Snapshot, String>>),
}

#[derive(Clone)]
pub struct TimerService {
    sender: mpsc::Sender<Request>,
    clock: Arc<dyn Clock>,
}

impl TimerService {
    pub fn spawn(
        mut store: Store,
        clock: Arc<dyn Clock>,
        publish: impl Fn(Snapshot) + Send + 'static,
        completed: impl Fn(Record) + Send + 'static,
    ) -> Result<Self, String> {
        let mut engine = store.load()?;
        if let Some(task) = engine.view(clock.monotonic_ms()).selected_task
            && store.selectable_task(&task.id)?.is_none()
        {
            engine.clear_selected_task_if(&task.id);
            store.save(&engine, clock.monotonic_ms(), None)?;
        }
        let mut recovered = engine.has_active();
        let mut records = store.records()?;
        let (sender, receiver) = mpsc::channel();
        let client_clock = clock.clone();
        thread::Builder::new()
            .name("focus-authority".into())
            .spawn(move || {
                let mut revision = 0;
                let mut last_error = None;
                let mut pending: Option<Command> = None;
                let mut interruption = None;
                let mut checkpoint_at = clock.monotonic_ms();
                let mut published_at = checkpoint_at;
                loop {
                    let mut request = match receiver.recv_timeout(Duration::from_millis(100)) {
                        Ok(r) => Some(r),
                        Err(mpsc::RecvTimeoutError::Timeout) => None,
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    };
                    let mut interrupted_at = None;
                    match request.take() {
                        Some(Request::ReadPreference(key, reply)) => {
                            let _ = reply.send(store.preference(&key));
                            continue;
                        }
                        Some(Request::SavePreference(key, payload, reply)) => {
                            let _ = reply.send(store.save_preference(&key, &payload));
                            continue;
                        }
                        Some(Request::ReadTasks(reply)) => {
                            let _ = reply.send(store.tasks());
                            continue;
                        }
                        Some(Request::CreateTask(title, reply)) => {
                            let _ = reply.send(store.create_task(&title, clock.unix_ms()));
                            continue;
                        }
                        Some(Request::RenameTask(id, title, reply)) => {
                            let _ = reply.send(store.rename_task(&id, &title, clock.unix_ms()));
                            continue;
                        }
                        Some(Request::CompleteTask(id, completed, reply)) => {
                            let _ = reply.send(store.set_task_completed(
                                &id,
                                completed,
                                clock.unix_ms(),
                            ));
                            continue;
                        }
                        Some(Request::DeleteTask(id, reply)) => {
                            if pending.is_some() {
                                let _ = reply.send(Err(
                                    "Retry the pending session save before removing a task.".into(),
                                ));
                                continue;
                            }
                            let mut candidate = engine.clone();
                            candidate.clear_selected_task_if(&id);
                            let result = store
                                .delete_task(&id, &candidate, clock.unix_ms(), clock.monotonic_ms())
                                .map(|()| {
                                    engine = candidate;
                                });
                            let _ = reply.send(result);
                            continue;
                        }
                        Some(Request::DailyTotals(start, end, reply)) => {
                            let _ = reply.send(store.daily_totals(start, end));
                            continue;
                        }
                        Some(Request::ReportRecords(start, end, reply)) => {
                            let _ = reply.send(store.records_between(start, end));
                            continue;
                        }
                        Some(Request::ResetReports(reply)) => {
                            match store.clear_sessions() {
                                Ok(()) => {
                                    records.clear();
                                    revision += 1;
                                    let state = Snapshot {
                                        timer: engine.view(clock.monotonic_ms()),
                                        revision,
                                        recovered,
                                        pending_save: pending.is_some(),
                                        last_error: last_error.clone(),
                                        records: Vec::new(),
                                        interruption: interruption.clone(),
                                    };
                                    publish(state.clone());
                                    let _ = reply.send(Ok(state));
                                }
                                Err(error) => {
                                    let _ = reply.send(Err(error));
                                }
                            }
                            continue;
                        }
                        Some(Request::Interrupt(reason, observed, reply)) => {
                            interrupted_at = Some(observed);
                            if engine.running() {
                                interruption = Some(reason);
                            }
                            request = Some(Request::Apply(Command::Pause, reply));
                        }
                        other => request = other,
                    }
                    let now = clock.monotonic_ms();
                    let snapshot =
                        |engine: &Engine,
                         revision,
                         recovered,
                         pending: &Option<Command>,
                         last_error: &Option<String>,
                         records: &Vec<Record>,
                         interruption: &Option<String>| Snapshot {
                            timer: engine.view(now),
                            revision,
                            recovered,
                            pending_save: pending.is_some(),
                            last_error: last_error.clone(),
                            records: records.clone(),
                            interruption: interruption.clone(),
                        };
                    if let Some(Request::Read(reply)) = &request {
                        let _ = reply.send(snapshot(
                            &engine,
                            revision,
                            recovered,
                            &pending,
                            &last_error,
                            &records,
                            &interruption,
                        ));
                    }
                    let automatic = request.is_none()
                        && pending.is_none()
                        && engine.running()
                        && engine.completed(now);
                    let periodic = request.is_none()
                        && pending.is_none()
                        && engine.running()
                        && now.saturating_sub(checkpoint_at) >= 15_000;
                    let mut reply = None;
                    let mut action = if automatic {
                        Some(Command::AutoFinish)
                    } else if periodic {
                        Some(Command::Pause)
                    } else {
                        None
                    };
                    if let Some(Request::Apply(command, response)) = request {
                        reply = Some(response);
                        if command == Command::RetrySave {
                            action = Some(pending.clone().unwrap_or(Command::Pause));
                        } else if pending.is_some() {
                            if let Some(response) = reply {
                                let _ = response.send(Err(
                                    "Retry the pending save before changing this session.".into(),
                                ));
                            }
                            continue;
                        } else {
                            action = Some(command);
                        }
                    }
                    if let Some(command) = action {
                        let mut candidate = engine.clone();
                        let command = match command {
                            Command::SelectTask {
                                task: Some(reference),
                            } => match store.selectable_task(&reference.id) {
                                Ok(Some(task)) => Command::SelectTask {
                                    task: Some(crate::TaskReference {
                                        id: task.id,
                                        title: task.title,
                                    }),
                                },
                                Ok(None) => {
                                    if let Some(response) = reply {
                                        let _ = response
                                            .send(Err("That task is no longer available.".into()));
                                    }
                                    continue;
                                }
                                Err(error) => {
                                    if let Some(response) = reply {
                                        let _ = response.send(Err(error));
                                    }
                                    continue;
                                }
                            },
                            other => other,
                        };
                        // A checkpoint saves a paused copy without pausing the live timer.
                        let transition = if periodic {
                            Ok(None)
                        } else {
                            candidate.apply(
                                command.clone(),
                                interrupted_at.map_or(now, |at| at.min(now)),
                                clock.unix_ms(),
                            )
                        };
                        match transition {
                            Err(error) => {
                                if let Some(response) = reply {
                                    let _ = response.send(Err(error));
                                }
                                continue;
                            }
                            Ok(record) => match store.save(&candidate, now, record.as_ref()) {
                                Ok(()) => {
                                    engine = candidate;
                                    recovered = false;
                                    pending = None;
                                    last_error = None;
                                    checkpoint_at = now;
                                    if engine.running() || !engine.has_active() {
                                        interruption = None;
                                    }
                                    if let Some(record) = record {
                                        records.insert(0, record.clone());
                                        records.truncate(20);
                                        if record.outcome == "completed" {
                                            completed(record);
                                        }
                                    }
                                }
                                Err(error) => {
                                    engine.pause(interrupted_at.map_or(now, |at| at.min(now)));
                                    pending = Some(command);
                                    last_error =
                                        Some(format!("Could not save on this device: {error}"));
                                }
                            },
                        }
                        revision += 1;
                        let state = snapshot(
                            &engine,
                            revision,
                            recovered,
                            &pending,
                            &last_error,
                            &records,
                            &interruption,
                        );
                        publish(state.clone());
                        published_at = now;
                        if let Some(response) = reply {
                            let _ = response.send(Ok(state));
                        }
                    } else if engine.running() && now.saturating_sub(published_at) >= 1000 {
                        revision += 1;
                        publish(snapshot(
                            &engine,
                            revision,
                            recovered,
                            &pending,
                            &last_error,
                            &records,
                            &interruption,
                        ));
                        published_at = now;
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        Ok(Self {
            sender,
            clock: client_clock,
        })
    }
    pub fn snapshot(&self) -> Result<Snapshot, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::Read(send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())
    }
    pub fn command(&self, command: Command) -> Result<Snapshot, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::Apply(command, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn interrupt(&self, reason: &str) -> Result<Snapshot, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::Interrupt(
                reason.into(),
                self.clock.monotonic_ms(),
                send,
            ))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(1))
            .map_err(|e| e.to_string())?
    }
    pub fn preference(&self, key: &str) -> Result<Option<String>, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::ReadPreference(key.into(), send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn save_preference(&self, key: &str, payload: &str) -> Result<(), String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::SavePreference(key.into(), payload.into(), send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn tasks(&self) -> Result<Vec<Task>, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::ReadTasks(send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn create_task(&self, title: String) -> Result<Task, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::CreateTask(title, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn rename_task(&self, id: String, title: String) -> Result<Task, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::RenameTask(id, title, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn complete_task(&self, id: String, completed: bool) -> Result<(), String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::CompleteTask(id, completed, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn delete_task(&self, id: String) -> Result<(), String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::DeleteTask(id, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn daily_totals(&self, start: u64, end: u64) -> Result<DailyTotals, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::DailyTotals(start, end, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
    pub fn reset_reports(&self) -> Result<Snapshot, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::ResetReports(send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }

    pub fn report_records(&self, start: u64, end: u64) -> Result<Vec<Record>, String> {
        let (send, receive) = mpsc::channel();
        self.sender
            .send(Request::ReportRecords(start, end, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        path::Path,
        sync::atomic::{AtomicU64, Ordering},
    };
    struct FakeClock(AtomicU64);
    impl Clock for FakeClock {
        fn monotonic_ms(&self) -> u64 {
            self.0.load(Ordering::SeqCst)
        }
        fn unix_ms(&self) -> u64 {
            1000
        }
    }
    #[test]
    fn reset_reports_clears_cached_records_and_published_snapshot() {
        let clock = Arc::new(FakeClock(AtomicU64::new(0)));
        let service = TimerService::spawn(
            Store::open(Path::new(":memory:")).unwrap(),
            clock.clone(),
            |_| {},
            |_| {},
        )
        .unwrap();
        service.command(Command::Toggle).unwrap();
        clock.0.store(60_000, Ordering::SeqCst);
        let finished = service.command(Command::Finish).unwrap();
        assert_eq!(finished.records.len(), 1);
        let reset = service.reset_reports().unwrap();
        assert!(reset.records.is_empty());
        assert!(service.report_records(0, 5000).unwrap().is_empty());
        assert_eq!(service.daily_totals(0, 5000).unwrap().pomodoro_sessions, 0);
    }

    #[test]
    fn suspend_and_lock_freeze_time_until_explicit_resume() {
        let clock = Arc::new(FakeClock(AtomicU64::new(0)));
        let service = TimerService::spawn(
            Store::open(Path::new(":memory:")).unwrap(),
            clock.clone(),
            |_| {},
            |_| {},
        )
        .unwrap();
        service.command(Command::Toggle).unwrap();
        clock.0.store(5500, Ordering::SeqCst);
        let paused = service.interrupt("sleep").unwrap();
        assert_eq!(paused.interruption.as_deref(), Some("sleep"));
        assert_eq!(paused.timer.active_ms, 5500);
        clock.0.store(3_600_000, Ordering::SeqCst);
        assert_eq!(service.snapshot().unwrap().timer.active_ms, 5500);
        assert!(
            service
                .command(Command::Toggle)
                .unwrap()
                .interruption
                .is_none()
        );
        clock.0.store(3_602_000, Ordering::SeqCst);
        let locked = service.interrupt("lock").unwrap();
        assert_eq!(locked.timer.active_ms, 7500);
        assert_eq!(locked.interruption.as_deref(), Some("lock"));
        assert_eq!(
            service.command(Command::Finish).unwrap().records[0].active_ms,
            7500
        );
    }
    #[test]
    fn delayed_suspend_processing_uses_notification_time_not_wake_time() {
        let clock = Arc::new(FakeClock(AtomicU64::new(0)));
        let service = TimerService::spawn(
            Store::open(Path::new(":memory:")).unwrap(),
            clock.clone(),
            |_| {},
            |_| {},
        )
        .unwrap();
        service.command(Command::Toggle).unwrap();
        clock.0.store(3_600_000, Ordering::SeqCst);
        let (send, receive) = mpsc::channel();
        service
            .sender
            .send(Request::Interrupt("sleep".into(), 5500, send))
            .unwrap();
        let paused = receive
            .recv_timeout(Duration::from_secs(1))
            .unwrap()
            .unwrap();
        assert_eq!(paused.timer.active_ms, 5500);
        assert_eq!(paused.timer.status, "paused");
        assert!(paused.records.is_empty());
    }
    #[test]
    fn desktop_preferences_use_the_same_serialized_store() {
        let service = TimerService::spawn(
            Store::open(Path::new(":memory:")).unwrap(),
            Arc::new(FakeClock(AtomicU64::new(0))),
            |_| {},
            |_| {},
        )
        .unwrap();
        assert!(service.preference("desktop").unwrap().is_none());
        service
            .save_preference("desktop", "{\"pinned\":false}")
            .unwrap();
        assert!(service.save_preference("desktop", "broken").is_err());
        assert_eq!(
            service.preference("desktop").unwrap().as_deref(),
            Some("{\"pinned\":false}")
        );
    }
    #[test]
    fn failed_finalization_freezes_duration_and_blocks_new_sessions() {
        let mut store = Store::open(Path::new(":memory:")).unwrap();
        let mut engine = Engine::default();
        engine.apply(Command::Toggle, 0, 0).unwrap();
        store.save(&engine, 5000, None).unwrap();
        store.reject_records();
        let clock = Arc::new(FakeClock(AtomicU64::new(0)));
        let service = TimerService::spawn(store, clock.clone(), |_| {}, |_| {}).unwrap();
        service.command(Command::Toggle).unwrap();
        clock.0.store(60_000, Ordering::SeqCst);
        let failed = service.command(Command::Finish).unwrap();
        assert!(failed.pending_save);
        assert!(failed.last_error.is_some());
        assert_eq!(failed.timer.status, "paused");
        assert_eq!(failed.timer.active_ms, 65_000);
        clock.0.store(9_000_000, Ordering::SeqCst);
        assert!(service.command(Command::Toggle).is_err());
        assert_eq!(service.snapshot().unwrap().timer.active_ms, 65_000);
        assert!(service.command(Command::RetrySave).unwrap().pending_save);
        assert!(service.snapshot().unwrap().records.is_empty());
    }
    #[test]
    fn shared_commands_keep_one_session_and_one_record() {
        let clock = Arc::new(FakeClock(AtomicU64::new(0)));
        let service = TimerService::spawn(
            Store::open(Path::new(":memory:")).unwrap(),
            clock.clone(),
            |_| {},
            |_| {},
        )
        .unwrap();
        service.command(Command::Toggle).unwrap();
        clock.0.store(65_000, Ordering::SeqCst);
        let second_window = service.clone();
        assert_eq!(
            second_window
                .command(Command::Pause)
                .unwrap()
                .timer
                .active_ms,
            65_000
        );
        clock.0.store(9_000_000, Ordering::SeqCst);
        assert_eq!(service.snapshot().unwrap().timer.active_ms, 65_000);
        assert_eq!(service.command(Command::Finish).unwrap().records.len(), 1);
        assert_eq!(
            second_window
                .command(Command::Finish)
                .unwrap()
                .records
                .len(),
            1
        );
    }
}
