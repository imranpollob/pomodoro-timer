//! One serialized owner for timer commands, checkpoints and completion records.
use crate::{Command, Engine, Record, TimerView, store::Store};
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
}

#[derive(Clone)]
pub struct TimerService {
    sender: mpsc::Sender<Request>,
}

impl TimerService {
    pub fn spawn(
        mut store: Store,
        clock: Arc<dyn Clock>,
        publish: impl Fn(Snapshot) + Send + 'static,
        completed: impl Fn(Record) + Send + 'static,
    ) -> Result<Self, String> {
        let mut engine = store.load()?;
        let mut recovered = engine.has_active();
        let mut records = store.records()?;
        let (sender, receiver) = mpsc::channel();
        thread::Builder::new()
            .name("focus-authority".into())
            .spawn(move || {
                let mut revision = 0;
                let mut last_error = None;
                let mut pending: Option<Command> = None;
                let mut checkpoint_at = clock.monotonic_ms();
                let mut published_at = checkpoint_at;
                loop {
                    let request = match receiver.recv_timeout(Duration::from_millis(100)) {
                        Ok(r) => Some(r),
                        Err(mpsc::RecvTimeoutError::Timeout) => None,
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    };
                    let now = clock.monotonic_ms();
                    let snapshot =
                        |engine: &Engine,
                         revision,
                         recovered,
                         pending: &Option<Command>,
                         last_error: &Option<String>,
                         records: &Vec<Record>| Snapshot {
                            timer: engine.view(now),
                            revision,
                            recovered,
                            pending_save: pending.is_some(),
                            last_error: last_error.clone(),
                            records: records.clone(),
                        };
                    if let Some(Request::Read(reply)) = &request {
                        let _ = reply.send(snapshot(
                            &engine,
                            revision,
                            recovered,
                            &pending,
                            &last_error,
                            &records,
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
                        Some(Command::Finish)
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
                        // A checkpoint saves a paused copy without pausing the live timer.
                        let transition = if periodic {
                            Ok(None)
                        } else {
                            candidate.apply(command.clone(), now, clock.unix_ms())
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
                                    if let Some(record) = record {
                                        records.insert(0, record.clone());
                                        records.truncate(20);
                                        if record.outcome == "completed" {
                                            completed(record);
                                        }
                                    }
                                }
                                Err(error) => {
                                    engine.pause(now);
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
                        ));
                        published_at = now;
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        Ok(Self { sender })
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
