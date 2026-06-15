import json
import pathlib
import sys
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from drive_sync import GoogleDriveSync, get_device_id


class TestGetDeviceId:
    def test_returns_string(self):
        result = get_device_id()
        assert isinstance(result, str)
        assert "-" in result


class TestGoogleDriveSync:
    def test_init_without_credentials(self, tmp_path):
        sync = GoogleDriveSync(tmp_path)
        assert sync.is_connected is False
        assert sync.last_sync_time is None

    def test_init_with_existing_valid_token(self, tmp_path):
        token_data = {
            "token": "fake_token",
            "refresh_token": "fake_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake_client_id",
            "client_secret": "fake_client_secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        }
        token_file = tmp_path / "token.json"
        token_file.write_text(json.dumps(token_data))

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        with patch("drive_sync.Credentials") as mock_creds_cls, \
             patch("drive_sync.build") as mock_build:
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds
            sync = GoogleDriveSync(tmp_path)
            assert mock_build.called
            assert sync.is_connected is True

    def test_merge_data_prefers_newer_remote(self):
        local_data = {
            "settings": {"work_time": 25},
            "todos": [{"id": 1, "text": "Local", "done": False}],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-01T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }
        remote_data = {
            "settings": {"work_time": 30},
            "todos": [{"id": 2, "text": "Remote", "done": True}],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-02T00:00:00",
                "device_id": "device-b",
                "sync_version": 2,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(local_data, remote_data)

        assert merged["settings"]["work_time"] == 30

    def test_merge_data_merges_todos_by_id(self):
        local_data = {
            "settings": {},
            "todos": [
                {"id": 1, "text": "Local todo", "done": False},
                {"id": 2, "text": "Shared todo - local version", "done": False},
            ],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-01T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }
        remote_data = {
            "settings": {},
            "todos": [
                {"id": 2, "text": "Shared todo - remote version", "done": True},
                {"id": 3, "text": "Remote todo", "done": False},
            ],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-02T00:00:00",
                "device_id": "device-b",
                "sync_version": 2,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(local_data, remote_data)

        todo_ids = [t["id"] for t in merged["todos"]]
        assert 1 in todo_ids
        assert 2 in todo_ids
        assert 3 in todo_ids
        assert len(merged["todos"]) == 3

    def test_merge_data_deduplicates_history_by_timestamp(self):
        history_entry = {
            "date": "2025-01-01",
            "type": "Work",
            "duration_seconds": 1500,
            "timestamp": "2025-01-01T10:00:00",
        }
        local_data = {
            "settings": {},
            "todos": [],
            "history": [history_entry],
            "metadata": {
                "last_modified": "2025-01-01T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }
        remote_data = {
            "settings": {},
            "todos": [],
            "history": [history_entry],
            "metadata": {
                "last_modified": "2025-01-02T00:00:00",
                "device_id": "device-b",
                "sync_version": 2,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(local_data, remote_data)

        assert len(merged["history"]) == 1

    def test_merge_data_returns_local_when_same_device_newer(self):
        local_data = {
            "settings": {"work_time": 25},
            "todos": [],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-02T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }
        remote_data = {
            "settings": {"work_time": 30},
            "todos": [],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-01T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(local_data, remote_data)

        assert merged["settings"]["work_time"] == 25

    def test_merge_data_returns_remote_when_none_local(self):
        remote_data = {
            "settings": {"work_time": 30},
            "todos": [{"id": 1, "text": "Test", "done": False}],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-02T00:00:00",
                "device_id": "device-b",
                "sync_version": 1,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(None, remote_data)

        assert merged == remote_data

    def test_merge_data_returns_local_when_none_remote(self):
        local_data = {
            "settings": {"work_time": 25},
            "todos": [],
            "history": [],
            "metadata": {
                "last_modified": "2025-01-01T00:00:00",
                "device_id": "device-a",
                "sync_version": 1,
            },
        }

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        merged = sync.merge_data(local_data, None)

        assert merged == local_data

    def test_disconnect_clears_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text(json.dumps({"token": "test"}))

        sync = GoogleDriveSync.__new__(GoogleDriveSync)
        sync.config_dir = tmp_path
        sync.token_file = token_file
        sync.credentials_file = tmp_path / "credentials.json"
        sync._creds = MagicMock()
        sync._service = MagicMock()
        sync._file_id = "abc"
        sync._connected = True
        sync.on_status_change = None

        sync.disconnect()

        assert not token_file.exists()
        assert sync._creds is None
        assert sync._service is None
        assert sync._file_id is None
        assert sync._connected is False


class TestStorageSyncHooks:
    def test_trigger_sync_when_connected(self, tmp_path):
        from storage import StorageManager

        storage = StorageManager(
            settings_file=tmp_path / "settings.json",
            todos_file=tmp_path / "todos.json",
            history_file=tmp_path / "history.json",
        )

        mock_sync = MagicMock()
        mock_sync.is_connected = True
        storage.set_drive_sync(mock_sync)

        storage.save_settings()
        mock_sync.queue_sync.assert_called_once()

    def test_trigger_sync_when_disconnected(self, tmp_path):
        from storage import StorageManager

        storage = StorageManager(
            settings_file=tmp_path / "settings.json",
            todos_file=tmp_path / "todos.json",
            history_file=tmp_path / "history.json",
        )

        mock_sync = MagicMock()
        mock_sync.is_connected = False
        storage.set_drive_sync(mock_sync)

        storage.save_settings()
        mock_sync.queue_sync.assert_not_called()

    def test_get_all_data(self, tmp_path):
        from storage import StorageManager

        storage = StorageManager(
            settings_file=tmp_path / "settings.json",
            todos_file=tmp_path / "todos.json",
            history_file=tmp_path / "history.json",
        )
        storage.settings["work_time"] = 30
        storage.todos = [{"id": 1, "text": "Test", "done": False}]

        data = storage.get_all_data()

        assert data["settings"]["work_time"] == 30
        assert len(data["todos"]) == 1
        assert "metadata" in data
        assert "last_modified" in data["metadata"]

    def test_load_all_data(self, tmp_path):
        from storage import StorageManager

        storage = StorageManager(
            settings_file=tmp_path / "settings.json",
            todos_file=tmp_path / "todos.json",
            history_file=tmp_path / "history.json",
        )

        data = {
            "settings": {"work_time": 45, "short_break": 10},
            "todos": [{"id": 1, "text": "Loaded todo", "done": True}],
            "history": [
                {
                    "date": "2025-01-01",
                    "type": "Work",
                    "duration_seconds": 1500,
                    "timestamp": "2025-01-01T10:00:00",
                }
            ],
            "metadata": {"last_modified": "2025-01-01T00:00:00", "device_id": "test", "sync_version": 1},
        }

        result = storage.load_all_data(data)

        assert result is True
        assert storage.settings["work_time"] == 45
        assert len(storage.todos) == 1
        assert storage.todos[0]["text"] == "Loaded todo"
        assert len(storage.load_history()) == 1
