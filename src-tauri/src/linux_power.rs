//! logind sleep and lid notifications, independent of webview visibility.
//! Protocol: https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
use focus_core::service::TimerService;
use std::collections::HashMap;
use tauri::{Emitter, Manager};
use zbus::{
    MatchRule,
    blocking::{Connection, MessageIterator, Proxy},
    zvariant::{OwnedFd, OwnedValue},
};

const DESTINATION: &str = "org.freedesktop.login1";
const PATH: &str = "/org/freedesktop/login1";
const MANAGER: &str = "org.freedesktop.login1.Manager";

pub fn start(app: tauri::AppHandle, service: TimerService) {
    std::thread::spawn(move || {
        loop {
            let result = Connection::system().and_then(|connection| {
                listen(connection, &service, || {
                    app.state::<crate::Controls>().power_status(
                        "Linux sleep/lid listener active; interrupted sessions stay paused.".into(),
                    );
                    let _ = app.emit("desktop-state", app.state::<crate::Controls>().snapshot());
                })
            });
            app.state::<crate::Controls>().power_status(format!(
                "Linux sleep/lid listener unavailable: {}. Retrying.",
                result
                    .err()
                    .map_or_else(|| "connection closed".into(), |e| e.to_string())
            ));
            let _ = app.emit("desktop-state", app.state::<crate::Controls>().snapshot());
            std::thread::sleep(std::time::Duration::from_secs(5));
        }
    });
}

fn delay_sleep(manager: &Proxy<'_>) -> zbus::Result<OwnedFd> {
    // A delay inhibitor lets the checkpoint finish before suspend, then is
    // released immediately. It never blocks the user's request to sleep.
    manager.call(
        "Inhibit",
        &("sleep", "Pomodoro", "Pause the active timer", "delay"),
    )
}

fn listen(
    connection: Connection,
    service: &TimerService,
    ready: impl FnOnce(),
) -> zbus::Result<()> {
    let rule = MatchRule::builder()
        .msg_type(zbus::message::Type::Signal)
        .sender(DESTINATION)?
        .path(PATH)?
        .build();
    let messages = MessageIterator::for_match_rule(rule, &connection, Some(64))?;
    let manager = Proxy::new(&connection, DESTINATION, PATH, MANAGER)?;
    // Subscribe before taking the lock so no sleep notification can be missed.
    let mut inhibitor = Some(delay_sleep(&manager)?);
    ready();
    for message in messages {
        let message = message?;
        let header = message.header();
        match (
            header.interface().map(|v| v.as_str()),
            header.member().map(|v| v.as_str()),
        ) {
            (Some(MANAGER), Some("PrepareForSleep")) => {
                let sleeping: bool = message.body().deserialize()?;
                if sleeping {
                    let paused = service.interrupt("sleep");
                    drop(inhibitor.take());
                    paused.map_err(zbus::Error::Failure)?;
                } else {
                    // Waking only arms the next notification; resuming the
                    // timer always requires an explicit user action.
                    inhibitor = Some(delay_sleep(&manager)?);
                }
            }
            (Some("org.freedesktop.DBus.Properties"), Some("PropertiesChanged")) => {
                let (interface, changed, invalidated): (
                    String,
                    HashMap<String, OwnedValue>,
                    Vec<String>,
                ) = message.body().deserialize()?;
                if interface == MANAGER {
                    let closed = match changed.get("LidClosed") {
                        Some(value) => bool::try_from(value).unwrap_or(false),
                        None if invalidated.iter().any(|name| name == "LidClosed") => {
                            manager.get_property::<bool>("LidClosed")?
                        }
                        None => false,
                    };
                    if closed {
                        service.interrupt("sleep").map_err(zbus::Error::Failure)?;
                    }
                }
            }
            _ => {}
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use focus_core::{Command, service::Clock, store::Store};
    use std::{
        io::{BufRead, BufReader},
        process::{Child, Command as ProcessCommand, Stdio},
        sync::{
            Arc,
            atomic::{AtomicU64, Ordering},
            mpsc,
        },
        time::{Duration, Instant},
    };

    struct Bus(Child);
    impl Drop for Bus {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    struct Manager(Arc<AtomicU64>);
    #[zbus::interface(name = "org.freedesktop.login1.Manager")]
    impl Manager {
        fn inhibit(&self, _what: &str, _who: &str, _why: &str, _mode: &str) -> OwnedFd {
            self.0.fetch_add(1, Ordering::SeqCst);
            std::os::fd::OwnedFd::from(std::fs::File::open("/dev/null").unwrap()).into()
        }
    }
    struct TestClock(AtomicU64);
    impl Clock for TestClock {
        fn monotonic_ms(&self) -> u64 {
            self.0.load(Ordering::SeqCst)
        }
        fn unix_ms(&self) -> u64 {
            self.monotonic_ms()
        }
    }

    #[test]
    fn logind_signals_pause_sleep_and_lid_without_resuming_on_wake() {
        // A private bus exercises the actual D-Bus subscription and decoding;
        // it cannot suspend the host or send signals to the user's apps.
        let mut bus = Bus(ProcessCommand::new("dbus-daemon")
            .args(["--session", "--nofork", "--print-address=1"])
            .stdout(Stdio::piped())
            .spawn()
            .unwrap());
        let mut address = String::new();
        BufReader::new(bus.0.stdout.take().unwrap())
            .read_line(&mut address)
            .unwrap();
        let inhibitors = Arc::new(AtomicU64::new(0));
        let server = zbus::blocking::connection::Builder::address(address.trim())
            .unwrap()
            .name(DESTINATION)
            .unwrap()
            .serve_at(PATH, Manager(inhibitors.clone()))
            .unwrap()
            .build()
            .unwrap();
        let connection = zbus::blocking::connection::Builder::address(address.trim())
            .unwrap()
            .build()
            .unwrap();
        let clock = Arc::new(TestClock(AtomicU64::new(0)));
        let service = TimerService::spawn(
            Store::open(std::path::Path::new(":memory:")).unwrap(),
            clock.clone(),
            |_| {},
            |_| {},
        )
        .unwrap();
        let (send, receive) = mpsc::channel();
        let worker_service = service.clone();
        let worker = std::thread::spawn(move || {
            listen(connection, &worker_service, || send.send(()).unwrap())
        });
        receive.recv_timeout(Duration::from_secs(5)).unwrap();

        for phase in [focus_core::Phase::Focus, focus_core::Phase::Stopwatch] {
            service.command(Command::SetMode { mode: phase }).unwrap();
            service.command(Command::Toggle).unwrap();
            clock.0.fetch_add(5500, Ordering::SeqCst);
            server
                .emit_signal(None::<&str>, PATH, MANAGER, "PrepareForSleep", &true)
                .unwrap();
            wait_paused(&service);
            let before = service.snapshot().unwrap().timer.active_ms;
            clock.0.fetch_add(3_600_000, Ordering::SeqCst);
            let count = inhibitors.load(Ordering::SeqCst);
            server
                .emit_signal(None::<&str>, PATH, MANAGER, "PrepareForSleep", &false)
                .unwrap();
            let deadline = Instant::now() + Duration::from_secs(5);
            while inhibitors.load(Ordering::SeqCst) == count {
                assert!(
                    Instant::now() < deadline,
                    "wake did not re-arm the listener"
                );
                std::thread::sleep(Duration::from_millis(10));
            }
            assert_eq!(service.snapshot().unwrap().timer.status, "paused");
            assert_eq!(service.snapshot().unwrap().timer.active_ms, before);
            service.command(Command::Toggle).unwrap();
            let changed = HashMap::from([("LidClosed", zbus::zvariant::Value::from(true))]);
            server
                .emit_signal(
                    None::<&str>,
                    PATH,
                    "org.freedesktop.DBus.Properties",
                    "PropertiesChanged",
                    &(MANAGER, changed, Vec::<String>::new()),
                )
                .unwrap();
            wait_paused(&service);
            assert_eq!(service.snapshot().unwrap().timer.active_ms, before);
            service.command(Command::Finish).unwrap();
        }
        drop(server);
        drop(bus);
        let _ = worker.join().unwrap();
    }

    fn wait_paused(service: &TimerService) {
        let deadline = Instant::now() + Duration::from_secs(5);
        while service.snapshot().unwrap().timer.status != "paused" {
            assert!(
                Instant::now() < deadline,
                "logind notification did not pause the timer"
            );
            std::thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(
            service.snapshot().unwrap().interruption.as_deref(),
            Some("sleep")
        );
    }
}
