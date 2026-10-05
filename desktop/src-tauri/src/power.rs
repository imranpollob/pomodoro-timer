//! Windows broadcasts are observed by a hidden top-level window, never a message-only window.
use focus_core::service::TimerService;
use std::{ptr::null_mut, sync::mpsc};
use windows_sys::Win32::{
    Foundation::{HWND, LPARAM, LRESULT, POINT, WPARAM},
    Graphics::Gdi::{GetMonitorInfoW, MONITOR_DEFAULTTONEAREST, MONITORINFO, MonitorFromPoint},
    System::{
        LibraryLoader::GetModuleHandleW,
        RemoteDesktop::{
            NOTIFY_FOR_THIS_SESSION, WTSRegisterSessionNotification,
            WTSUnRegisterSessionNotification,
        },
    },
    UI::WindowsAndMessaging::*,
};

pub struct PowerListener {
    hwnd: isize,
}
struct Context {
    service: TimerService,
    app: tauri::AppHandle,
}
impl PowerListener {
    pub fn start(app: tauri::AppHandle, service: TimerService) -> Result<Self, String> {
        let (send, receive) = mpsc::channel();
        std::thread::Builder::new()
            .name("focus-power-events".into())
            .spawn(move || {
                let mut context = Box::new(Context { service, app });
                let class: Vec<u16> = "PomodoroBetaPowerEvents\0".encode_utf16().collect();
                // This thread owns the window and the boxed context throughout its message loop.
                unsafe {
                    let instance = GetModuleHandleW(std::ptr::null());
                    let mut wc: WNDCLASSW = std::mem::zeroed();
                    wc.lpfnWndProc = Some(window_proc);
                    wc.hInstance = instance;
                    wc.lpszClassName = class.as_ptr();
                    if RegisterClassW(&wc) == 0 {
                        let _ = send.send(Err(format!(
                            "Windows power listener: {}",
                            std::io::Error::last_os_error()
                        )));
                        return;
                    }
                    let hwnd = CreateWindowExW(
                        0,
                        class.as_ptr(),
                        class.as_ptr(),
                        0,
                        0,
                        0,
                        0,
                        0,
                        null_mut(),
                        null_mut(),
                        instance,
                        (&mut *context as *mut Context).cast(),
                    );
                    if hwnd.is_null()
                        || WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION) == 0
                    {
                        let error = std::io::Error::last_os_error();
                        if !hwnd.is_null() {
                            DestroyWindow(hwnd);
                        }
                        UnregisterClassW(class.as_ptr(), instance);
                        let _ = send.send(Err(format!(
                            "Windows suspend/lock listener unavailable: {error}"
                        )));
                        return;
                    }
                    let _ = send.send(Ok(hwnd as isize));
                    let mut message: MSG = std::mem::zeroed();
                    while GetMessageW(&mut message, null_mut(), 0, 0) > 0 {
                        TranslateMessage(&message);
                        DispatchMessageW(&message);
                    }
                    UnregisterClassW(class.as_ptr(), instance);
                }
            })
            .map_err(|e| e.to_string())?;
        let hwnd = receive
            .recv_timeout(std::time::Duration::from_secs(5))
            .map_err(|e| e.to_string())??;
        Ok(Self { hwnd })
    }
    #[cfg(feature = "smoke-test")]
    pub fn simulate_lock(&self) {
        // Send the same message as Windows, only in the nondistributed test executable.
        unsafe {
            SendMessageW(
                self.hwnd as HWND,
                WM_WTSSESSION_CHANGE,
                WTS_SESSION_LOCK as WPARAM,
                0,
            );
        }
    }
    #[cfg(feature = "smoke-test")]
    pub fn simulate_suspend(&self) {
        unsafe {
            SendMessageW(
                self.hwnd as HWND,
                WM_POWERBROADCAST,
                PBT_APMSUSPEND as WPARAM,
                0,
            );
        }
    }
}
impl Drop for PowerListener {
    fn drop(&mut self) {
        unsafe {
            PostMessageW(self.hwnd as HWND, WM_CLOSE, 0, 0);
        }
    }
}

unsafe extern "system" fn window_proc(
    hwnd: HWND,
    message: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    // All pointer access is confined to the owning thread, between creation and destruction.
    unsafe {
        if message == WM_NCCREATE {
            let creation = &*(lparam as *const CREATESTRUCTW);
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, creation.lpCreateParams as isize);
        }
        let pointer = GetWindowLongPtrW(hwnd, GWLP_USERDATA) as *const Context;
        let reason = if message == WM_POWERBROADCAST && wparam == PBT_APMSUSPEND as usize {
            Some("sleep")
        } else if message == WM_WTSSESSION_CHANGE && wparam == WTS_SESSION_LOCK as usize {
            Some("lock")
        } else {
            None
        };
        if let Some(reason) = reason
            && !pointer.is_null()
        {
            let context = &*pointer;
            if let Err(error) = context.service.interrupt(reason) {
                let app = context.app.clone();
                tauri::async_runtime::spawn_blocking(move || {
                    crate::report_error(&app, &format!("Windows interruption checkpoint: {error}"))
                });
            }
            return 1;
        }
        if message == WM_CLOSE {
            WTSUnRegisterSessionNotification(hwnd);
            DestroyWindow(hwnd);
            return 0;
        }
        if message == WM_DESTROY {
            PostQuitMessage(0);
            return 0;
        }
        DefWindowProcW(hwnd, message, wparam, lparam)
    }
}

pub fn work_area(x: i32, y: i32) -> Option<(i32, i32, i32, i32)> {
    unsafe {
        let monitor = MonitorFromPoint(POINT { x, y }, MONITOR_DEFAULTTONEAREST);
        let mut info: MONITORINFO = std::mem::zeroed();
        info.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
        if GetMonitorInfoW(monitor, &mut info) == 0 {
            return None;
        }
        let r = info.rcWork;
        Some((r.left, r.top, r.right - r.left, r.bottom - r.top))
    }
}
