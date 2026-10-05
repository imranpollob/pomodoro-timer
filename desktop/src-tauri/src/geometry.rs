//! Debounced window placement, stored in the isolated profile's SQLite database.
use focus_core::service::TimerService;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, sync::mpsc, time::Duration};
use tauri::{PhysicalPosition, WebviewWindow};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Placement {
    pub x: i32,
    pub y: i32,
    pub width: f64,
    pub height: f64,
}
impl Placement {
    fn validate(&self, label: &str) -> Result<(), String> {
        let (min_w, min_h, max_w, max_h) = if label == "compact" {
            (200.0, 44.0, 1200.0, 300.0)
        } else if label == "main" {
            (660.0, 520.0, 8192.0, 8192.0)
        } else {
            return Err("Unknown window in saved placement.".into());
        };
        if !(min_w..=max_w).contains(&self.width)
            || !(min_h..=max_h).contains(&self.height)
            || self.x.unsigned_abs() > 1_000_000
            || self.y.unsigned_abs() > 1_000_000
        {
            return Err("Invalid saved window placement; data was preserved.".into());
        }
        Ok(())
    }
}

/// Full monitor bounds are the portable fallback; Windows uses its work area.
pub fn clamp_position(
    x: i32,
    y: i32,
    width: i32,
    height: i32,
    areas: &[(i32, i32, i32, i32)],
) -> Option<(i32, i32)> {
    let area = areas
        .iter()
        .find(|&&(ax, ay, aw, ah)| x >= ax && x < ax + aw && y >= ay && y < ay + ah)
        .or_else(|| areas.first())?;
    let &(ax, ay, aw, ah) = area;
    Some((
        x.clamp(ax, ax + (aw - width).max(0)),
        y.clamp(ay, ay + (ah - height).max(0)),
    ))
}

enum Request {
    Observe(String, Placement),
    Flush(mpsc::Sender<Result<(), String>>),
}
#[derive(Clone)]
pub struct GeometryService(mpsc::Sender<Request>);
impl GeometryService {
    pub fn start(service: TimerService) -> Result<(Self, BTreeMap<String, Placement>), String> {
        let initial: BTreeMap<String, Placement> = service
            .preference("windows")?
            .map(|raw| serde_json::from_str(&raw))
            .transpose()
            .map_err(|e| format!("Invalid window settings: {e}"))?
            .unwrap_or_default();
        for (label, placement) in &initial {
            placement.validate(label)?;
        }
        let mut placements = initial.clone();
        let (sender, receiver) = mpsc::channel();
        std::thread::Builder::new()
            .name("focus-placement".into())
            .spawn(move || {
                let mut dirty = false;
                let save = |values: &BTreeMap<String, Placement>| {
                    service.save_preference(
                        "windows",
                        &serde_json::to_string(values).map_err(|e| e.to_string())?,
                    )
                };
                loop {
                    match receiver.recv_timeout(Duration::from_millis(500)) {
                        Ok(Request::Observe(label, placement)) => {
                            if placement.validate(&label).is_ok() {
                                placements.insert(label, placement);
                                dirty = true;
                            }
                        }
                        Ok(Request::Flush(reply)) => {
                            let result = if dirty { save(&placements) } else { Ok(()) };
                            if result.is_ok() {
                                dirty = false;
                            }
                            let _ = reply.send(result);
                        }
                        Err(mpsc::RecvTimeoutError::Timeout) => {
                            if dirty && save(&placements).is_ok() {
                                dirty = false;
                            }
                        }
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        Ok((Self(sender), initial))
    }
    pub fn observe(&self, window: &tauri::Window) {
        if window.is_minimized().unwrap_or(true) || window.is_maximized().unwrap_or(true) {
            return;
        }
        if let (Ok(position), Ok(size), Ok(scale)) = (
            window.outer_position(),
            window.inner_size(),
            window.scale_factor(),
        ) {
            let logical = size.to_logical::<f64>(scale);
            let _ = self.0.send(Request::Observe(
                window.label().into(),
                Placement {
                    x: position.x,
                    y: position.y,
                    width: logical.width,
                    height: logical.height,
                },
            ));
        }
    }
    pub fn flush(&self) -> Result<(), String> {
        let (send, receive) = mpsc::channel();
        self.0
            .send(Request::Flush(send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    }
}

pub fn restore(window: &WebviewWindow, placement: &Placement) -> Result<(), String> {
    placement.validate(window.label())?;
    window
        .set_size(tauri::LogicalSize::new(placement.width, placement.height))
        .map_err(|e| e.to_string())?;
    ensure_visible(window, Some((placement.x, placement.y)))
}
pub fn ensure_visible(window: &WebviewWindow, position: Option<(i32, i32)>) -> Result<(), String> {
    let monitors = window.available_monitors().map_err(|e| e.to_string())?;
    let areas: Vec<_> = monitors
        .iter()
        .map(|m| {
            let p = m.position();
            let s = m.size();
            #[cfg(windows)]
            if let Some(area) = crate::power::work_area(p.x, p.y) {
                return area;
            }
            (p.x, p.y, s.width as i32, s.height as i32)
        })
        .collect();
    let p = window.outer_position().map_err(|e| e.to_string())?;
    let s = window.outer_size().map_err(|e| e.to_string())?;
    let (x, y) = position.unwrap_or((p.x, p.y));
    if let Some((x, y)) = clamp_position(x, y, s.width as i32, s.height as i32, &areas) {
        window
            .set_position(PhysicalPosition::new(x, y))
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn negative_monitor_coordinates_and_removed_monitor_are_safe() {
        let areas = [(-1920, 0, 1920, 1040), (0, 0, 1920, 1040)];
        assert_eq!(
            clamp_position(-100, 1000, 200, 44, &areas),
            Some((-200, 996))
        );
        assert_eq!(
            clamp_position(4000, 3000, 200, 44, &areas[1..]),
            Some((1720, 996))
        );
        assert_eq!(clamp_position(0, 0, 200, 44, &[]), None);
    }
    #[test]
    fn scaled_compact_stays_in_work_area() {
        assert_eq!(
            clamp_position(1850, 1000, 400, 88, &[(0, 0, 1920, 1040)]),
            Some((1520, 952))
        );
    }
    #[test]
    fn invalid_saved_geometry_is_rejected() {
        assert!(
            Placement {
                x: 0,
                y: 0,
                width: f64::NAN,
                height: 44.0
            }
            .validate("compact")
            .is_err()
        );
        assert!(
            Placement {
                x: 0,
                y: 0,
                width: 1.0,
                height: 1.0
            }
            .validate("main")
            .is_err()
        );
    }
}
