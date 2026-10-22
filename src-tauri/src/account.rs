//! Google OAuth and sync run in Rust; credentials never enter the webview.
use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use focus_core::{service::TimerService, sync::SyncReply};
use reqwest::{Client, Url};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{Emitter, Manager};
use tauri_plugin_opener::OpenerExt;

const CALLBACK_PORT: u16 = 43821;
const EXPIRED: &str = "Your sign-in session expired. Sign in with Google again.";

#[derive(Clone)]
struct Config {
    url: String,
    key: String,
}

impl Config {
    fn load() -> Result<Option<Self>, String> {
        Self::parse(env!("SUPABASE_URL"), env!("SUPABASE_PUBLISHABLE_KEY"))
    }
    fn parse(url: &str, key: &str) -> Result<Option<Self>, String> {
        if url.is_empty() && key.is_empty() {
            return Ok(None);
        }
        let parsed =
            Url::parse(url).map_err(|_| "The Supabase project URL is invalid.".to_string())?;
        if parsed.scheme() != "https"
            || parsed.host_str().is_none()
            || !parsed.username().is_empty()
            || parsed.password().is_some()
            || parsed.query().is_some()
            || parsed.fragment().is_some()
            || parsed.path() != "/"
        {
            return Err("Use the HTTPS Supabase project URL without a path.".into());
        }
        let legacy_anon = key
            .split('.')
            .nth(1)
            .and_then(|part| URL_SAFE_NO_PAD.decode(part).ok())
            .and_then(|bytes| serde_json::from_slice::<serde_json::Value>(&bytes).ok())
            .is_some_and(|claims| claims["role"] == "anon");
        if !(key.starts_with("sb_publishable_") || legacy_anon) || key.contains(['\r', '\n']) {
            return Err("Configure a Supabase publishable key or legacy anon key. Secret and service-role keys must not be used in the app.".into());
        }
        Ok(Some(Self {
            url: url.trim_end_matches('/').into(),
            key: key.into(),
        }))
    }
}

#[derive(Clone, Serialize)]
pub struct AccountState {
    revision: u64,
    configured: bool,
    email: Option<String>,
    busy: bool,
    signing_in: bool,
    last_synced_ms: Option<u64>,
    message: String,
    error: Option<String>,
}

#[derive(Deserialize)]
struct User {
    id: String,
    email: Option<String>,
}

#[derive(Deserialize)]
struct Session {
    access_token: String,
    refresh_token: String,
    expires_in: u64,
    user: User,
    #[serde(skip)]
    expires_at: u64,
}

enum Action {
    Restore,
    SignIn,
    Sync,
    SignOut,
}

pub struct AccountService {
    config: Option<Config>,
    client: Client,
    app: tauri::AppHandle,
    timer: TimerService,
    state: Mutex<AccountState>,
    session: Mutex<Option<Session>>,
    operation: Mutex<()>,
    cancelled: AtomicBool,
    wake: mpsc::Sender<()>,
    credential_user: String,
    restore_pending: AtomicBool,
}

impl AccountService {
    pub fn start(
        app: tauri::AppHandle,
        timer: TimerService,
        profile: &Path,
    ) -> Result<Arc<Self>, String> {
        let (config, config_error) = match Config::load() {
            Ok(value) => (value, None),
            Err(error) => (None, Some(error)),
        };
        let scope = format!(
            "{}:{}",
            config.as_ref().map(|c| c.url.as_str()).unwrap_or_default(),
            profile.canonicalize().map_err(|e| e.to_string())?.display()
        );
        let (wake, receiver) = mpsc::channel();
        let configured = config.is_some();
        let service = Arc::new(Self {
            config,
            client: Client::builder()
                .https_only(true)
                .connect_timeout(Duration::from_secs(5))
                .timeout(Duration::from_secs(20))
                .redirect(reqwest::redirect::Policy::none())
                .build()
                .map_err(|_| "Could not initialize account services.".to_string())?,
            app,
            timer,
            state: Mutex::new(AccountState {
                revision: 0,
                configured,
                email: None,
                busy: false,
                signing_in: false,
                last_synced_ms: None,
                message: "Sign in to sync your tasks across devices.".into(),
                error: config_error,
            }),
            session: Mutex::new(None),
            operation: Mutex::new(()),
            cancelled: AtomicBool::new(false),
            wake,
            credential_user: URL_SAFE_NO_PAD.encode(Sha256::digest(scope.as_bytes())),
            restore_pending: AtomicBool::new(true),
        });
        if configured {
            let worker = service.clone();
            std::thread::spawn(move || {
                let _ = worker.run(Action::Restore);
                loop {
                    let _ = receiver.recv_timeout(Duration::from_secs(30));
                    // Coalesce rapid edits into one upload.
                    while receiver.try_recv().is_ok() {}
                    if worker.session.lock().unwrap().is_some() {
                        let _ = worker.run(Action::Sync);
                    } else if worker.restore_pending.load(Ordering::SeqCst) {
                        let _ = worker.run(Action::Restore);
                    }
                }
            });
        }
        Ok(service)
    }

    pub fn state(&self) -> AccountState {
        self.state.lock().unwrap().clone()
    }
    pub fn wake(&self) {
        let _ = self.wake.send(());
    }
    fn publish(&self, change: impl FnOnce(&mut AccountState)) {
        let state = {
            let mut state = self.state.lock().unwrap();
            change(&mut state);
            state.revision += 1;
            state.clone()
        };
        let _ = self.app.emit("sync-state", state);
    }
    fn credential(&self) -> Result<keyring::Entry, String> {
        keyring::Entry::new(
            "com.imranpollob.pomodoro-timer.supabase",
            &self.credential_user,
        )
        .map_err(|_| "Could not access the system credential store.".into())
    }
    fn forget_credential(&self) -> Result<(), String> {
        match self.credential()?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(_) => {
                Err("Could not remove the saved sign-in from the system credential store.".into())
            }
        }
    }
    fn run(&self, action: Action) -> Result<AccountState, String> {
        let _operation = self
            .operation
            .try_lock()
            .map_err(|_| "Another account action is in progress. Please wait.".to_string())?;
        if self.config.is_none() {
            return Err("Cloud sync has not been configured for this build.".into());
        }
        if matches!(action, Action::SignIn) {
            self.cancelled.store(false, Ordering::SeqCst);
        }
        self.publish(|state| {
            state.busy = true;
            state.signing_in = matches!(action, Action::SignIn);
            state.error = None;
        });
        let result = match action {
            Action::Restore => self.restore(),
            Action::SignIn => self.sign_in(),
            Action::Sync => self.sync(),
            Action::SignOut => self.sign_out(),
        };
        self.publish(|state| {
            state.busy = false;
            state.signing_in = false;
            if let Err(error) = &result {
                state.error = Some(error.clone());
            }
        });
        result.map(|()| self.state())
    }
    fn account_id(&self, user_id: &str) -> String {
        format!("{}:{user_id}", self.config.as_ref().unwrap().url)
    }
    fn save_session(&self, mut session: Session) -> Result<(), String> {
        uuid::Uuid::parse_str(&session.user.id)
            .map_err(|_| "Supabase returned an invalid account.".to_string())?;
        self.timer.sync_batch(self.account_id(&session.user.id))?;
        self.credential()?.set_password(&session.refresh_token)
            .map_err(|_| "Could not save sign-in in the system credential store. Check that your keychain is unlocked and try again.".to_string())?;
        session.expires_at = seconds().saturating_add(session.expires_in);
        let email = session
            .user
            .email
            .clone()
            .unwrap_or_else(|| "Google account".into());
        *self.session.lock().unwrap() = Some(session);
        self.restore_pending.store(false, Ordering::SeqCst);
        self.publish(|state| {
            state.email = Some(email);
            state.message = "Signed in. Syncing tasks and focus history…".into();
        });
        Ok(())
    }
    fn token(&self, grant: &str, body: serde_json::Value) -> Result<Session, String> {
        let config = self.config.as_ref().unwrap();
        tauri::async_runtime::block_on(async {
            let response = self
                .client
                .post(format!("{}/auth/v1/token", config.url))
                .query(&[("grant_type", grant)])
                .header("apikey", &config.key)
                .json(&body)
                .send()
                .await
                .map_err(|_| {
                    "Could not reach Supabase. Check your internet connection and try again."
                        .to_string()
                })?;
            match response.status().as_u16() {
                400 | 401 => return Err(EXPIRED.into()),
                429 => return Err("Too many sign-in attempts. Please try again later.".into()),
                status if !(200..300).contains(&status) => return Err("Google sign-in could not complete. Check the Supabase Google provider configuration.".into()),
                _ => {}
            }
            response
                .json()
                .await
                .map_err(|_| "Supabase returned an invalid sign-in response.".into())
        })
    }
    fn restore(&self) -> Result<(), String> {
        let refresh = match self.credential()?.get_password() {
            Ok(refresh) => refresh,
            Err(keyring::Error::NoEntry) => {
                self.restore_pending.store(false, Ordering::SeqCst);
                return Ok(());
            }
            Err(_) => {
                return Err(
                    "Could not restore sign-in. Unlock your system keychain and sign in again."
                        .into(),
                );
            }
        };
        match self.token(
            "refresh_token",
            serde_json::json!({"refresh_token": refresh}),
        ) {
            Ok(session) => {
                self.save_session(session)?;
                self.sync()
            }
            Err(error) => {
                if error == EXPIRED {
                    self.forget_credential()?;
                    self.restore_pending.store(false, Ordering::SeqCst);
                }
                Err(error)
            }
        }
    }
    fn sign_in(&self) -> Result<(), String> {
        let listener = TcpListener::bind(("127.0.0.1", CALLBACK_PORT))
            .map_err(|_| "The sign-in callback port is busy. Close another Pomodoro sign-in window and try again.".to_string())?;
        listener.set_nonblocking(true).map_err(|e| e.to_string())?;
        let nonce = uuid::Uuid::new_v4().simple().to_string();
        let path = format!("/auth/callback/{nonce}");
        let verifier = format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        );
        let challenge = URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()));
        let mut url = Url::parse(&format!(
            "{}/auth/v1/authorize",
            self.config.as_ref().unwrap().url
        ))
        .map_err(|e| e.to_string())?;
        url.query_pairs_mut()
            .append_pair("provider", "google")
            .append_pair(
                "redirect_to",
                &format!("http://127.0.0.1:{CALLBACK_PORT}{path}"),
            )
            .append_pair("code_challenge", &challenge)
            .append_pair("code_challenge_method", "s256");
        self.publish(|state| {
            state.message = "Finish signing in with Google in your browser.".into();
        });
        self.app
            .opener()
            .open_url(url.as_str(), None::<&str>)
            .map_err(|_| "Could not open your browser for Google sign-in.".to_string())?;
        let deadline = Instant::now() + Duration::from_secs(120);
        let code = loop {
            if self.cancelled.load(Ordering::SeqCst) {
                return Err("Google sign-in was cancelled.".into());
            }
            if Instant::now() >= deadline {
                return Err("Google sign-in timed out. Please try again.".into());
            }
            match listener.accept() {
                Ok((mut stream, _)) => {
                    if let Some(code) = callback(&mut stream, &path)? {
                        break code;
                    }
                }
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    std::thread::sleep(Duration::from_millis(75))
                }
                Err(_) => return Err("Could not receive the Google sign-in callback.".into()),
            }
        };
        drop(listener);
        let session = self.token(
            "pkce",
            serde_json::json!({"auth_code": code, "code_verifier": verifier}),
        )?;
        if self.cancelled.load(Ordering::SeqCst) {
            return Err("Google sign-in was cancelled.".into());
        }
        self.save_session(session)?;
        if self.cancelled.load(Ordering::SeqCst) {
            self.sign_out()?;
            return Err("Google sign-in was cancelled.".into());
        }
        self.sync()
    }
    fn sync(&self) -> Result<(), String> {
        let refresh = {
            let session = self.session.lock().unwrap();
            let session = session
                .as_ref()
                .ok_or_else(|| "Sign in with Google before syncing.".to_string())?;
            (session.expires_at <= seconds() + 60).then(|| session.refresh_token.clone())
        };
        if let Some(refresh) = refresh {
            match self.token(
                "refresh_token",
                serde_json::json!({"refresh_token": refresh}),
            ) {
                Ok(session) => self.save_session(session)?,
                Err(error) => {
                    if error == EXPIRED {
                        self.forget_credential()?;
                        *self.session.lock().unwrap() = None;
                        self.publish(|state| {
                            state.email = None;
                            state.message = "Sign in to resume sync.".into();
                        });
                    }
                    return Err(error);
                }
            }
        }
        let (token, account) = {
            let session = self.session.lock().unwrap();
            let session = session.as_ref().unwrap();
            (
                session.access_token.clone(),
                self.account_id(&session.user.id),
            )
        };
        let config = self.config.as_ref().unwrap();
        self.publish(|state| state.message = "Syncing tasks and focus history…".into());
        let mut conflicts = 0;
        // Bound a pass so heavy editing cannot monopolize the worker forever.
        for _ in 0..100 {
            let batch = self.timer.sync_batch(account.clone())?;
            let reply: SyncReply = tauri::async_runtime::block_on(async {
                let response = self.client.post(format!("{}/rest/v1/rpc/sync_app_data", config.url))
                    .header("apikey", &config.key).bearer_auth(&token)
                    .json(&serde_json::json!({"p_changes": batch.changes, "p_after_version": batch.cursor, "p_history_changes": batch.history_changes, "p_history_after_version": batch.history_cursor})).send().await
                    .map_err(|_| "Tasks are saved on this device. Sync will retry when your connection returns.".to_string())?;
                match response.status().as_u16() {
                    401 => {
                        if let Some(session) = self.session.lock().unwrap().as_mut() { session.expires_at = 0; }
                        return Err("Reconnecting your account. Try syncing again.".into());
                    }
                    404 => return Err("Cloud sync needs the latest Supabase migration (202610220001_focus_history_sync.sql). Apply it in the SQL Editor.".into()),
                    status if !(200..300).contains(&status) => return Err("Could not sync tasks and focus history. Your local changes are saved; please try again later.".into()),
                    _ => {}
                }
                response.json::<SyncReply>().await.map_err(|_| {
                    "Supabase returned invalid sync data. Local tasks and focus history were preserved.".to_string()
                })
            })?;
            conflicts += reply.conflicts;
            let more = reply.has_more || reply.history.has_more;
            self.timer.apply_task_sync(account.clone(), reply)?;
            let _ = self.app.emit("tasks-synced", ());
            let remaining = self.timer.sync_batch(account.clone())?;
            if !more && remaining.changes.is_empty() && remaining.history_changes.is_empty() {
                self.publish(|state| { state.last_synced_ms = Some(seconds() * 1000); state.message = if conflicts == 0 { "Tasks and focus history are synced.".into() } else { format!("Tasks synced. {conflicts} conflicting change(s) kept the copy already saved on the server.") }; });
                return Ok(());
            }
        }
        self.wake();
        self.publish(|state| {
            state.message = "More data is waiting to sync. Sync will continue shortly.".into()
        });
        Ok(())
    }
    fn sign_out(&self) -> Result<(), String> {
        self.forget_credential()?;
        self.restore_pending.store(false, Ordering::SeqCst);
        let session = self.session.lock().unwrap().take();
        self.publish(|state| {
            state.email = None;
            state.last_synced_ms = None;
            state.message =
                "Signed out. Your tasks and focus history remain on this device.".into();
        });
        if let Some(session) = session {
            let config = self.config.as_ref().unwrap();
            let _ = tauri::async_runtime::block_on(
                self.client
                    .post(format!("{}/auth/v1/logout?scope=local", config.url))
                    .header("apikey", &config.key)
                    .bearer_auth(session.access_token)
                    .timeout(Duration::from_secs(5))
                    .send(),
            );
        }
        Ok(())
    }
}

fn seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn callback(stream: &mut TcpStream, expected_path: &str) -> Result<Option<String>, String> {
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let mut bytes = Vec::new();
    let mut buffer = [0; 1024];
    while bytes.len() < 8192 && !bytes.windows(4).any(|part| part == b"\r\n\r\n") {
        match stream.read(&mut buffer) {
            Ok(0) | Err(_) => break,
            Ok(count) => bytes.extend_from_slice(&buffer[..count]),
        }
    }
    let request = String::from_utf8_lossy(&bytes);
    let mut first_line = request
        .lines()
        .next()
        .unwrap_or_default()
        .split_whitespace();
    let method = first_line.next().unwrap_or_default();
    let target = first_line.next().unwrap_or_default();
    let result = if method == "GET" {
        callback_code(target, expected_path)
    } else {
        Ok(None)
    };
    let body = if matches!(&result, Ok(Some(_))) {
        "Sign-in received. You can close this tab and return to Pomodoro."
    } else {
        "Return to Pomodoro to continue or retry sign-in."
    };
    let status = if matches!(&result, Ok(Some(_))) {
        "200 OK"
    } else {
        "400 Bad Request"
    };
    let _ = write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nContent-Security-Policy: default-src 'none'\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{body}",
        body.len()
    );
    result
}

fn callback_code(target: &str, expected_path: &str) -> Result<Option<String>, String> {
    let Ok(url) = Url::parse(&format!("http://127.0.0.1:{CALLBACK_PORT}{target}")) else {
        return Ok(None);
    };
    if url.path() != expected_path {
        return Ok(None);
    }
    if url
        .query_pairs()
        .any(|(key, _)| key == "error" || key == "error_description")
    {
        return Err("Google sign-in was declined or could not complete. Please try again.".into());
    }
    Ok(url
        .query_pairs()
        .find(|(key, value)| key == "code" && !value.is_empty())
        .map(|(_, code)| code.into_owned()))
}

#[tauri::command]
pub fn get_account_state(app: tauri::AppHandle) -> AccountState {
    app.state::<Arc<AccountService>>().state()
}

async fn action(app: tauri::AppHandle, action: Action) -> Result<AccountState, String> {
    let service = app.state::<Arc<AccountService>>().inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.run(action))
        .await
        .map_err(|_| "The account action could not finish.".to_string())?
}
#[tauri::command]
pub async fn sign_in_with_google(app: tauri::AppHandle) -> Result<AccountState, String> {
    action(app, Action::SignIn).await
}
#[tauri::command]
pub async fn sync_tasks_now(app: tauri::AppHandle) -> Result<AccountState, String> {
    action(app, Action::Sync).await
}
#[tauri::command]
pub async fn sign_out_account(app: tauri::AppHandle) -> Result<AccountState, String> {
    action(app, Action::SignOut).await
}
#[tauri::command]
pub fn cancel_google_sign_in(app: tauri::AppHandle) {
    app.state::<Arc<AccountService>>()
        .cancelled
        .store(true, Ordering::SeqCst);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_accepts_only_public_keys_and_https_project_urls() {
        assert!(Config::parse("", "").unwrap().is_none());
        assert!(
            Config::parse("https://example.supabase.co", "sb_publishable_example")
                .unwrap()
                .is_some()
        );
        assert!(Config::parse("http://example.supabase.co", "sb_publishable_example").is_err());
        assert!(
            Config::parse("https://example.supabase.co/path", "sb_publishable_example").is_err()
        );
        assert!(Config::parse("https://example.supabase.co", "sb_secret_example").is_err());
        let admin = URL_SAFE_NO_PAD.encode(br#"{"role":"service_role"}"#);
        assert!(
            Config::parse(
                "https://example.supabase.co",
                &format!("header.{admin}.sig")
            )
            .is_err()
        );
        let anon = URL_SAFE_NO_PAD.encode(br#"{"role":"anon"}"#);
        assert!(
            Config::parse("https://example.supabase.co", &format!("header.{anon}.sig")).is_ok()
        );
    }

    #[test]
    fn callback_accepts_only_the_current_nonce_and_handles_denial() {
        let path = "/auth/callback/current-nonce";
        assert_eq!(
            callback_code("/auth/callback/current-nonce?code=test%2Bcode", path)
                .unwrap()
                .as_deref(),
            Some("test+code")
        );
        assert!(
            callback_code("/auth/callback/old-nonce?code=stolen", path)
                .unwrap()
                .is_none()
        );
        assert!(callback_code("/favicon.ico", path).unwrap().is_none());
        assert!(
            callback_code("/auth/callback/current-nonce?code=", path)
                .unwrap()
                .is_none()
        );
        assert!(callback_code("/auth/callback/current-nonce?error=access_denied", path).is_err());
    }

    #[test]
    fn pkce_matches_the_rfc7636_test_vector() {
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        assert_eq!(
            URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes())),
            "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        );
    }
}
