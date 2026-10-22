//! Manual checks against published GitHub releases; installation stays with the user.
use reqwest::{Client, StatusCode};
use semver::Version;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri_plugin_opener::OpenerExt;

const LATEST_RELEASE_API: &str =
    "https://api.github.com/repos/imranpollob/pomodoro-timer/releases/latest";
const RELEASE_PAGE: &str = "https://github.com/imranpollob/pomodoro-timer/releases/latest";

#[derive(Debug, Serialize)]
pub struct UpdateInfo {
    current_version: String,
    latest_version: Option<String>,
    update_available: bool,
}

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
}

#[tauri::command]
pub fn get_app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
pub async fn check_for_updates(app: tauri::AppHandle) -> Result<UpdateInfo, String> {
    let current_version = get_app_version(app);
    let client = Client::builder()
        .https_only(true)
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(15))
        .user_agent(format!("pomodoro-desktop/{current_version}"))
        .build()
        .map_err(|_| "Could not start the update check. Please try again.".to_string())?;
    fetch_release(&client, LATEST_RELEASE_API, &current_version).await
}

#[tauri::command]
pub fn open_release_page(app: tauri::AppHandle) -> Result<(), String> {
    // The renderer cannot supply an arbitrary URL or executable to the opener.
    app.opener()
        .open_url(RELEASE_PAGE, None::<&str>)
        .map_err(|_| "Could not open your browser. Please try again.".to_string())
}

async fn fetch_release(client: &Client, url: &str, current: &str) -> Result<UpdateInfo, String> {
    let response = client
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .header("X-GitHub-Api-Version", "2022-11-28")
        .send()
        .await
        .map_err(|_| {
            "Could not check for updates. Check your internet connection and try again.".to_string()
        })?;
    match response.status() {
        StatusCode::NOT_FOUND => return release_info(current, None),
        StatusCode::FORBIDDEN | StatusCode::TOO_MANY_REQUESTS => {
            return Err("GitHub is limiting update checks. Please try again later.".into());
        }
        status if !status.is_success() => {
            return Err("GitHub is unavailable. Please try again later.".into());
        }
        _ => {}
    }
    let release: Release = response.json().await.map_err(|_| {
        "Could not read the latest release information. Please try again.".to_string()
    })?;
    release_info(current, Some(release))
}

fn release_info(current: &str, release: Option<Release>) -> Result<UpdateInfo, String> {
    let mut info = UpdateInfo {
        current_version: current.into(),
        latest_version: None,
        update_available: false,
    };
    if let Some(release) = release.filter(|release| !release.draft && !release.prerelease) {
        let tag = release
            .tag_name
            .strip_prefix(['v', 'V'])
            .unwrap_or(&release.tag_name);
        let latest = Version::parse(tag)
            .map_err(|_| "The latest release has an unsupported version number.".to_string())?;
        // Also ignore prerelease tags if the publisher omitted GitHub's prerelease flag.
        if !latest.pre.is_empty() {
            return Ok(info);
        }
        let current = Version::parse(current)
            .map_err(|_| "The installed app has an unsupported version number.".to_string())?;
        info.update_available = latest.cmp_precedence(&current).is_gt();
        info.latest_version = Some(latest.to_string());
    }
    Ok(info)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn release(tag: &str) -> Release {
        Release {
            tag_name: tag.into(),
            draft: false,
            prerelease: false,
        }
    }

    #[test]
    fn compares_versions_numerically_without_offering_downgrades() {
        for (current, tag, available) in [
            ("1.2.0", "v1.2.1", true),
            ("1.9.0", "v1.10.0", true),
            ("1.2.0", "V2.0.0", true),
            ("1.2.0", "1.2.0", false),
            ("1.2.0", "v1.1.1", false),
            ("1.2.0+local", "v1.2.0+release", false),
            ("1.3.0-beta.1", "v1.3.0", true),
        ] {
            let result = release_info(current, Some(release(tag))).unwrap();
            assert_eq!(result.update_available, available, "{current} -> {tag}");
            assert_eq!(result.current_version, current);
        }
    }

    #[test]
    fn ignores_unpublished_and_prerelease_versions_and_rejects_invalid_tags() {
        let draft = Release {
            draft: true,
            ..release("v2.0.0")
        };
        let prerelease = Release {
            prerelease: true,
            ..release("v2.0.0")
        };
        for release in [
            None,
            Some(draft),
            Some(prerelease),
            Some(release("v2.0.0-beta.1")),
        ] {
            let result = release_info("1.2.0", release).unwrap();
            assert!(!result.update_available);
            assert!(result.latest_version.is_none());
        }
        assert!(release_info("1.2.0", Some(release("latest"))).is_err());
    }

    #[test]
    fn handles_github_responses_and_sends_required_headers() {
        use std::{
            io::{Read, Write},
            net::TcpListener,
        };

        for (status, body, expected) in [
            (
                200,
                r#"{"tag_name":"v1.3.0","draft":false,"prerelease":false}"#,
                "update",
            ),
            (404, "{}", "none"),
            (403, "{}", "limiting"),
            (429, "{}", "limiting"),
            (503, "{}", "unavailable"),
            (200, "not json", "Could not read"),
        ] {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let url = format!("http://{}/latest", listener.local_addr().unwrap());
            let server = std::thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                socket
                    .set_read_timeout(Some(Duration::from_secs(5)))
                    .unwrap();
                let mut request = String::new();
                let mut buffer = [0; 1024];
                while !request.contains("\r\n\r\n") {
                    let count = socket.read(&mut buffer).unwrap();
                    assert_ne!(count, 0);
                    request.push_str(std::str::from_utf8(&buffer[..count]).unwrap());
                }
                let headers = request.to_ascii_lowercase();
                assert!(headers.contains("accept: application/vnd.github+json"));
                assert!(headers.contains("x-github-api-version: 2022-11-28"));
                write!(socket, "HTTP/1.1 {status} Response\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
            });
            let client = Client::builder()
                .no_proxy()
                .timeout(Duration::from_secs(5))
                .build()
                .unwrap();
            let result = tauri::async_runtime::block_on(fetch_release(&client, &url, "1.2.0"));
            server.join().unwrap();
            match expected {
                "update" => assert!(result.unwrap().update_available),
                "none" => assert!(result.unwrap().latest_version.is_none()),
                error => assert!(result.unwrap_err().contains(error)),
            }
        }
    }
}
