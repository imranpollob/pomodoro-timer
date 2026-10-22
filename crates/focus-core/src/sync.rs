//! Durable task changes. All reads and merges run on the timer authority thread.
use crate::{Command, Engine, TaskReference, TaskStatus, store::Store};
use rusqlite::{OptionalExtension, params};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloudTask {
    pub id: String,
    pub title: String,
    pub status: TaskStatus,
    pub deleted: bool,
    pub created_unix_ms: i64,
    pub updated_unix_ms: i64,
    pub server_version: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskChange {
    #[serde(flatten)]
    pub task: CloudTask,
    pub change_id: String,
}

#[derive(Debug, Serialize)]
pub struct SyncBatch {
    pub changes: Vec<TaskChange>,
    pub cursor: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AcknowledgedTask {
    pub change_id: String,
    pub task: CloudTask,
    pub applied: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SyncReply {
    pub acknowledged: Vec<AcknowledgedTask>,
    pub changes: Vec<CloudTask>,
    pub cursor: i64,
    pub has_more: bool,
    pub conflicts: usize,
}

impl Store {
    fn check_sync_account(&self, account: &str) -> Result<(), String> {
        match self.preference("task_sync_account")? {
            Some(saved) if serde_json::from_str::<String>(&saved).map_err(|e| e.to_string())? != account => {
                Err("These local tasks belong to a different account. Sign in with the original Google account or use a separate app profile.".into())
            }
            Some(_) => Ok(()),
            None => self.save_preference("task_sync_account", &serde_json::to_string(account).map_err(|e| e.to_string())?),
        }
    }

    pub fn sync_batch(&self, account: &str) -> Result<SyncBatch, String> {
        self.check_sync_account(account)?;
        let cursor = self
            .preference("task_sync_cursor")?
            .map(|value| serde_json::from_str(&value))
            .transpose()
            .map_err(|e| e.to_string())?
            .unwrap_or(0);
        let mut query = self.connection.prepare(
            "SELECT id,title,status,deleted,created_unix_ms,updated_unix_ms,sync_version,sync_change_id
             FROM tasks WHERE sync_dirty=1 ORDER BY rowid LIMIT 100"
        ).map_err(|e| e.to_string())?;
        let changes = query
            .query_map([], |row| {
                let status: String = row.get(2)?;
                let status = match status.as_str() {
                    "todo" => TaskStatus::Todo,
                    "in_progress" => TaskStatus::InProgress,
                    "done" => TaskStatus::Done,
                    _ => return Err(rusqlite::Error::InvalidQuery),
                };
                Ok(TaskChange {
                    task: CloudTask {
                        id: row.get(0)?,
                        title: row.get(1)?,
                        status,
                        deleted: row.get(3)?,
                        created_unix_ms: row.get(4)?,
                        updated_unix_ms: row.get(5)?,
                        server_version: row.get(6)?,
                    },
                    change_id: row.get(7)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        // Retry the exact attempted payload until its acknowledgement is applied,
        // even if a newer local edit arrives or the previous response is lost.
        let mut attempted = Vec::with_capacity(changes.len());
        for change in changes {
            let saved: Option<String> = self
                .connection
                .query_row(
                    "SELECT payload FROM task_sync_attempts WHERE task_id=?1",
                    [&change.task.id],
                    |row| row.get(0),
                )
                .optional()
                .map_err(|e| e.to_string())?;
            if let Some(saved) = saved {
                attempted.push(
                    serde_json::from_str(&saved)
                        .map_err(|e| format!("Invalid pending task upload: {e}"))?,
                );
            } else {
                let payload = serde_json::to_string(&change).map_err(|e| e.to_string())?;
                self.connection
                    .execute(
                        "INSERT INTO task_sync_attempts VALUES (?1,?2,?3)",
                        params![change.task.id, change.change_id, payload],
                    )
                    .map_err(|e| e.to_string())?;
                attempted.push(change);
            }
        }
        Ok(SyncBatch {
            changes: attempted,
            cursor,
        })
    }

    pub fn apply_task_sync(
        &mut self,
        account: &str,
        reply: &SyncReply,
        engine: &Engine,
        now: u64,
    ) -> Result<Engine, String> {
        self.check_sync_account(account)?;
        for task in reply
            .changes
            .iter()
            .chain(reply.acknowledged.iter().map(|ack| &ack.task))
        {
            if uuid::Uuid::parse_str(&task.id).is_err()
                || task.title.trim().is_empty()
                || task.created_unix_ms < 0
                || task.updated_unix_ms < 0
                || task.server_version <= 0
            {
                return Err(
                    "The server returned invalid task data. Local tasks were preserved.".into(),
                );
            }
        }
        let old_cursor = self.sync_batch(account)?.cursor;
        if reply.cursor < old_cursor {
            return Err("The server returned an outdated sync cursor.".into());
        }
        let tx = self.connection.transaction().map_err(|e| e.to_string())?;
        for ack in &reply.acknowledged {
            let current: Option<String> = tx
                .query_row(
                    "SELECT sync_change_id FROM tasks WHERE id=?1 AND sync_dirty=1",
                    [&ack.task.id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(|e| e.to_string())?;
            if current.as_deref() == Some(&ack.change_id) {
                write_remote(&tx, &ack.task)?;
            } else if current.is_some() && ack.applied {
                // A newer local edit arrived during the request. Acknowledge only
                // the sent edit, preserving the newer fields for the next request.
                tx.execute(
                    "UPDATE tasks SET sync_version=max(sync_version,?2) WHERE id=?1",
                    params![ack.task.id, ack.task.server_version],
                )
                .map_err(|e| e.to_string())?;
            }
        }
        for ack in &reply.acknowledged {
            tx.execute(
                "DELETE FROM task_sync_attempts WHERE task_id=?1 AND change_id=?2",
                params![ack.task.id, ack.change_id],
            )
            .map_err(|e| e.to_string())?;
        }
        for task in &reply.changes {
            let local: Option<(bool, i64)> = tx
                .query_row(
                    "SELECT sync_dirty,sync_version FROM tasks WHERE id=?1",
                    [&task.id],
                    |r| Ok((r.get(0)?, r.get(1)?)),
                )
                .optional()
                .map_err(|e| e.to_string())?;
            if local.is_none_or(|(dirty, version)| !dirty && task.server_version > version) {
                write_remote(&tx, task)?;
            }
        }
        let mut candidate = engine.clone();
        if let Some(selected) = candidate.view(now).selected_task {
            let title: Option<String> = tx
                .query_row(
                    "SELECT title FROM tasks WHERE id=?1 AND deleted=0 AND status!='done'",
                    [&selected.id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(|e| e.to_string())?;
            candidate.apply(
                Command::SelectTask {
                    task: title.map(|title| TaskReference {
                        id: selected.id,
                        title,
                    }),
                },
                now,
                0,
            )?;
        }
        let checkpoint =
            serde_json::to_string(&candidate.checkpoint(now)).map_err(|e| e.to_string())?;
        tx.execute("INSERT INTO app_state VALUES (1,?1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", [checkpoint]).map_err(|e| e.to_string())?;
        tx.execute("INSERT INTO preferences VALUES ('task_sync_cursor',?1) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload", [reply.cursor.to_string()]).map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())?;
        Ok(candidate)
    }
}

fn write_remote(tx: &rusqlite::Transaction<'_>, task: &CloudTask) -> Result<(), String> {
    tx.execute("INSERT INTO tasks (id,title,status,deleted,created_unix_ms,updated_unix_ms,sync_version)
        VALUES (?1,?2,?3,?4,?5,?6,?7) ON CONFLICT(id) DO UPDATE SET title=excluded.title,status=excluded.status,
        deleted=excluded.deleted,created_unix_ms=excluded.created_unix_ms,updated_unix_ms=excluded.updated_unix_ms,sync_version=excluded.sync_version",
        params![task.id, task.title, task.status.as_db_value(), task.deleted, task.created_unix_ms, task.updated_unix_ms, task.server_version]).map_err(|e| e.to_string())?;
    // Insertion/update triggers track ordinary local writes; this transaction
    // explicitly marks imported server data clean after those triggers run.
    tx.execute("UPDATE tasks SET sync_dirty=0 WHERE id=?1", [&task.id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    fn store() -> Store {
        Store::open(Path::new(":memory:")).unwrap()
    }
    fn acknowledge(change: &TaskChange, version: i64) -> SyncReply {
        let mut task = change.task.clone();
        task.server_version = version;
        SyncReply {
            acknowledged: vec![AcknowledgedTask {
                change_id: change.change_id.clone(),
                task: task.clone(),
                applied: true,
            }],
            changes: vec![task],
            cursor: version,
            has_more: false,
            conflicts: 0,
        }
    }

    #[test]
    fn new_tasks_edits_and_deletions_are_durable_and_imports_do_not_echo() {
        let mut store = store();
        let engine = Engine::default();
        let task = store.create_task("Local task", 100).unwrap();
        let first = store.sync_batch("account-a").unwrap().changes.remove(0);
        store
            .apply_task_sync("account-a", &acknowledge(&first, 1), &engine, 0)
            .unwrap();
        assert!(store.sync_batch("account-a").unwrap().changes.is_empty());
        store.rename_task(&task.id, "Renamed offline", 200).unwrap();
        let edit = store.sync_batch("account-a").unwrap().changes.remove(0);
        assert_ne!(first.change_id, edit.change_id);
        assert_eq!(edit.task.server_version, 1);
        store
            .apply_task_sync("account-a", &acknowledge(&edit, 2), &engine, 0)
            .unwrap();
        store.delete_task(&task.id, &engine, 300, 0).unwrap();
        let deletion = store.sync_batch("account-a").unwrap().changes.remove(0);
        assert!(deletion.task.deleted);
        store
            .apply_task_sync("account-a", &acknowledge(&deletion, 3), &engine, 0)
            .unwrap();
        assert!(store.tasks().unwrap().is_empty());
        assert!(store.sync_batch("account-a").unwrap().changes.is_empty());
    }

    #[test]
    fn edits_made_during_network_requests_are_not_lost() {
        let mut store = store();
        let task = store.create_task("First", 100).unwrap();
        let sent = store.sync_batch("account-a").unwrap().changes.remove(0);
        store
            .rename_task(&task.id, "Edited during upload", 200)
            .unwrap();
        store
            .apply_task_sync("account-a", &acknowledge(&sent, 7), &Engine::default(), 0)
            .unwrap();
        let pending = store.sync_batch("account-a").unwrap().changes.remove(0);
        assert_eq!(pending.task.title, "Edited during upload");
        assert_eq!(pending.task.server_version, 7);
        assert_ne!(pending.change_id, sent.change_id);
    }

    #[test]
    fn remote_deletion_clears_selection_but_preserves_active_session_task() {
        let mut store = store();
        let task = store.create_task("Active", 100).unwrap();
        let sent = store.sync_batch("account-a").unwrap().changes.remove(0);
        let mut engine = Engine::default();
        engine
            .apply(
                Command::SelectTask {
                    task: Some(TaskReference {
                        id: task.id.clone(),
                        title: task.title,
                    }),
                },
                0,
                0,
            )
            .unwrap();
        engine.apply(Command::Toggle, 0, 100).unwrap();
        let mut reply = acknowledge(&sent, 1);
        reply.acknowledged[0].task.deleted = true;
        reply.changes[0].deleted = true;
        let merged = store
            .apply_task_sync("account-a", &reply, &engine, 100)
            .unwrap();
        assert!(merged.view(100).selected_task.is_none());
        assert_eq!(merged.view(100).active_task.unwrap().id, task.id);
    }

    #[test]
    fn account_binding_prevents_uploading_local_tasks_to_another_account() {
        let store = store();
        store.create_task("Private task", 1).unwrap();
        store.sync_batch("project-a:user-a").unwrap();
        assert!(store.sync_batch("project-a:user-b").is_err());
        assert!(store.sync_batch("project-b:user-a").is_err());
        assert_eq!(store.tasks().unwrap()[0].title, "Private task");
    }

    #[test]
    fn invalid_server_data_rolls_back_all_tasks_and_the_cursor() {
        let mut store = store();
        store.create_task("Saved locally", 100).unwrap();
        let pending = store.sync_batch("account-a").unwrap().changes.remove(0);
        let mut reply = acknowledge(&pending, 3);
        reply.changes[0].id = "invalid-id".into();
        assert!(
            store
                .apply_task_sync("account-a", &reply, &Engine::default(), 0)
                .is_err()
        );
        let batch = store.sync_batch("account-a").unwrap();
        assert_eq!(batch.cursor, 0);
        assert_eq!(batch.changes[0].change_id, pending.change_id);
    }

    #[test]
    fn a_lost_response_retries_the_original_payload_before_sending_newer_edits() {
        let mut store = store();
        let task = store.create_task("Sent to server", 100).unwrap();
        let original = store.sync_batch("account-a").unwrap().changes.remove(0);
        store
            .rename_task(&task.id, "Edited after sending", 200)
            .unwrap();
        let retry = store.sync_batch("account-a").unwrap().changes.remove(0);
        assert_eq!(retry.change_id, original.change_id);
        assert_eq!(retry.task.title, "Sent to server");
        store
            .apply_task_sync("account-a", &acknowledge(&retry, 8), &Engine::default(), 0)
            .unwrap();
        let newer = store.sync_batch("account-a").unwrap().changes.remove(0);
        assert_eq!(newer.task.title, "Edited after sending");
        assert_eq!(newer.task.server_version, 8);
        assert_ne!(newer.change_id, original.change_id);
    }

    #[test]
    fn pending_edits_survive_reopening_the_database() {
        let path =
            std::env::temp_dir().join(format!("pomodoro-sync-{}.sqlite3", uuid::Uuid::new_v4()));
        let store = Store::open(&path).unwrap();
        store.create_task("Offline", 100).unwrap();
        let change = store.sync_batch("account-a").unwrap().changes.remove(0);
        drop(store);
        let reopened = Store::open(&path).unwrap();
        assert_eq!(
            reopened.sync_batch("account-a").unwrap().changes[0].change_id,
            change.change_id
        );
        drop(reopened);
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn upgrading_version_four_preserves_existing_tasks_and_queues_them() {
        let path =
            std::env::temp_dir().join(format!("pomodoro-v4-sync-{}.sqlite3", uuid::Uuid::new_v4()));
        let store = Store::open(&path).unwrap();
        let original = store.create_task("Existing task", 100).unwrap();
        store
            .connection
            .execute_batch(
                "DROP TRIGGER tasks_sync_insert; DROP TRIGGER tasks_sync_update; DROP TABLE task_sync_attempts;
            ALTER TABLE tasks DROP COLUMN sync_version; ALTER TABLE tasks DROP COLUMN sync_dirty;
            ALTER TABLE tasks DROP COLUMN sync_change_id; PRAGMA user_version=4;",
            )
            .unwrap();
        drop(store);
        let upgraded = Store::open(&path).unwrap();
        assert_eq!(upgraded.tasks().unwrap(), vec![original.clone()]);
        let pending = upgraded.sync_batch("account-a").unwrap();
        assert_eq!(pending.changes[0].task.id, original.id);
        assert_eq!(pending.changes[0].task.server_version, 0);
        assert!(!pending.changes[0].change_id.is_empty());
        drop(upgraded);
        std::fs::remove_file(path).unwrap();
    }
}
