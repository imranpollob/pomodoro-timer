import json
import os
import platform
import threading
import time
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from io import BytesIO

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FILENAME = "pomodoro_data.json"
MIME_TYPE = "application/json"

EMBEDDED_CLIENT_CONFIG = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID_HERE",
        "client_secret": "YOUR_CLIENT_SECRET_HERE",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


def get_device_id():
    """Returns a unique identifier for this device."""
    return f"{platform.node()}-{platform.system()}"


class GoogleDriveSync:
    """Handles Google Drive sync for settings, todos, and history."""

    def __init__(self, config_dir, on_status_change=None):
        self.config_dir = Path(config_dir)
        self.token_file = self.config_dir / "token.json"
        self.credentials_file = self.config_dir / "credentials.json"
        self.on_status_change = on_status_change

        self._creds = None
        self._service = None
        self._file_id = None
        self._sync_thread = None
        self._sync_queue = []
        self._lock = threading.Lock()
        self._running = True
        self._last_sync_time = None
        self._connected = False

        self._load_credentials()

        self._watchdog = threading.Thread(target=self._sync_watchdog, daemon=True)
        self._watchdog.start()

    @property
    def is_connected(self):
        return self._connected

    @property
    def last_sync_time(self):
        return self._last_sync_time

    def _notify_status(self):
        if self.on_status_change:
            try:
                self.on_status_change(self._connected, self._last_sync_time)
            except Exception:
                pass

    def _load_credentials(self):
        if self.token_file.exists():
            try:
                self._creds = Credentials.from_authorized_user_file(
                    str(self.token_file), SCOPES
                )
            except Exception:
                self._creds = None

        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
                self._save_credentials()
            except Exception:
                self._creds = None

        if self._creds and self._creds.valid:
            self._service = build("drive", "v3", credentials=self._creds)
            self._connected = True
            self._notify_status()

    def _save_credentials(self):
        if self._creds:
            with open(self.token_file, "w") as f:
                f.write(self._creds.to_json())

    def authenticate(self, client_id=None, client_secret=None):
        """Trigger OAuth2 flow. Returns True on success.

        Uses embedded credentials by default. Pass client_id/client_secret
        to override with custom credentials.
        """
        if client_id and client_secret:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        elif self.credentials_file.exists():
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_file), SCOPES
            )
            try:
                self._creds = flow.run_local_server(port=0, open_browser=True)
            except Exception:
                self._creds = flow.run_console()
            self._save_credentials()
            self._service = build("drive", "v3", credentials=self._creds)
            self._connected = True
            self._notify_status()
            return True
        else:
            client_config = EMBEDDED_CLIENT_CONFIG

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        try:
            self._creds = flow.run_local_server(port=0, open_browser=True)
        except Exception:
            self._creds = flow.run_console()

        self._save_credentials()
        self._service = build("drive", "v3", credentials=self._creds)
        self._connected = True
        self._notify_status()
        return True

    def disconnect(self):
        """Disconnect from Google Drive."""
        if self.token_file.exists():
            self.token_file.unlink()
        self._creds = None
        self._service = None
        self._file_id = None
        self._connected = False
        self._notify_status()

    def _find_existing_file(self):
        """Find the existing pomodoro_data.json on Drive."""
        if not self._service:
            return None

        try:
            results = self._service.files().list(
                q=f"name='{DRIVE_FILENAME}' and trashed=false",
                spaces="drive",
                fields="files(id, modifiedTime)",
            ).execute()
            files = results.get("files", [])
            if files:
                return files[0]
        except Exception as e:
            print(f"Error finding file on Drive: {e}")
        return None

    def _ensure_file_exists(self):
        """Ensure the pomodoro_data.json file exists on Drive, return its ID."""
        if self._file_id:
            return self._file_id

        existing = self._find_existing_file()
        if existing:
            self._file_id = existing["id"]
            return self._file_id

        try:
            file_metadata = {"name": DRIVE_FILENAME}
            media = MediaIoBaseUpload(
                BytesIO(b"{}"), mimetype=MIME_TYPE, resumable=False
            )
            file = (
                self._service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            self._file_id = file.get("id")
            return self._file_id
        except Exception as e:
            print(f"Error creating file on Drive: {e}")
        return None

    def upload_data(self, data):
        """Upload consolidated data to Google Drive."""
        if not self._service or not self._connected:
            return False

        file_id = self._ensure_file_exists()
        if not file_id:
            return False

        try:
            data["metadata"]["last_modified"] = datetime.now().isoformat()
            data["metadata"]["device_id"] = get_device_id()

            json_data = json.dumps(data, indent=2).encode("utf-8")
            media = MediaIoBaseUpload(
                BytesIO(json_data), mimetype=MIME_TYPE, resumable=False
            )
            self._service.files().update(
                fileId=file_id, media_body=media
            ).execute()
            self._last_sync_time = datetime.now()
            self._notify_status()
            return True
        except Exception as e:
            print(f"Error uploading to Drive: {e}")
            return False

    def download_data(self):
        """Download consolidated data from Google Drive."""
        if not self._service or not self._connected:
            return None

        file_id = self._ensure_file_exists()
        if not file_id:
            return None

        try:
            request = self._service.files().get_media(fileId=file_id)
            fh = BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            fh.seek(0)
            content = fh.read().decode("utf-8")
            if content.strip():
                data = json.loads(content)
                self._last_sync_time = datetime.now()
                self._notify_status()
                return data
        except Exception as e:
            print(f"Error downloading from Drive: {e}")
        return None

    def _sync_watchdog(self):
        """Background thread that processes sync queue with debouncing."""
        while self._running:
            time.sleep(1)
            if not self._connected:
                continue

            with self._lock:
                if not self._sync_queue:
                    continue
                data = self._sync_queue.pop(0)

            self.upload_data(data)

    def queue_sync(self, data):
        """Queue a sync operation (debounced)."""
        if not self._connected:
            return

        with self._lock:
            self._sync_queue.clear()
            self._sync_queue.append(data)

    def sync_now(self, local_data):
        """Perform immediate sync. Returns True on success."""
        if not self._connected:
            return False
        return self.upload_data(local_data)

    def merge_data(self, local_data, remote_data):
        """Merge local and remote data, preferring newer timestamps."""
        if not remote_data:
            return local_data
        if not local_data:
            return remote_data

        remote_modified = remote_data.get("metadata", {}).get(
            "last_modified", "1970-01-01"
        )
        local_modified = local_data.get("metadata", {}).get(
            "last_modified", "1970-01-01"
        )

        remote_device = remote_data.get("metadata", {}).get("device_id", "")
        local_device = local_data.get("metadata", {}).get("device_id", "")

        if remote_device == local_device:
            if remote_modified > local_modified:
                return remote_data
            return local_data

        if remote_modified > local_modified:
            merged_settings = {**local_data.get("settings", {}), **remote_data.get("settings", {})}
            local_todos = {t["id"]: t for t in local_data.get("todos", [])}
            remote_todos = {t["id"]: t for t in remote_data.get("todos", [])}
            all_todos = {**local_todos, **remote_todos}
            merged_todos = sorted(all_todos.values(), key=lambda t: t["id"])

            local_history = local_data.get("history", [])
            remote_history = remote_data.get("history", [])
            seen_timestamps = set()
            merged_history = []
            for entry in local_history + remote_history:
                ts = entry.get("timestamp", "")
                if ts not in seen_timestamps:
                    seen_timestamps.add(ts)
                    merged_history.append(entry)

            return {
                "settings": merged_settings,
                "todos": merged_todos,
                "history": merged_history,
                "metadata": {
                    "last_modified": max(remote_modified, local_modified),
                    "device_id": get_device_id(),
                    "sync_version": max(
                        local_data.get("metadata", {}).get("sync_version", 0),
                        remote_data.get("metadata", {}).get("sync_version", 0),
                    ) + 1,
                },
            }

        return local_data

    def shutdown(self):
        """Stop the background sync thread."""
        self._running = False
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2)
