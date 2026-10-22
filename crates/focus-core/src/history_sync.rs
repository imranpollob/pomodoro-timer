//! Saved history is immutable; deletion always wins over a stale offline upload.
use crate::{Record, TaskCompletionEvent, store::Store};
use rusqlite::{OptionalExtension, params};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloudHistory {
    pub kind: String,
    pub id: String,
    pub payload: Option<Value>,
    pub deleted: bool,
    pub server_version: i64,
}
#[derive(Debug, Clone, Default, Deserialize)]
pub struct HistoryReply {
    pub acknowledged: Vec<CloudHistory>,
    pub changes: Vec<CloudHistory>,
    pub cursor: i64,
    pub has_more: bool,
}
impl Store {
    pub(crate) fn history_batch(&self) -> Result<(Vec<CloudHistory>, i64), String> {
        let cursor = self
            .preference("history_sync_cursor")?
            .map(|s| serde_json::from_str(&s))
            .transpose()
            .map_err(|e| e.to_string())?
            .unwrap_or(0);
        let mut query = self.connection.prepare("SELECT kind,id,payload,deleted,server_version FROM history_sync WHERE sync_dirty=1 ORDER BY rowid LIMIT 100").map_err(|e| e.to_string())?;
        let rows = query
            .query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, Option<String>>(2)?,
                    r.get::<_, bool>(3)?,
                    r.get::<_, i64>(4)?,
                ))
            })
            .map_err(|e| e.to_string())?;
        let mut entries = Vec::new();
        for row in rows {
            let (kind, id, payload, deleted, server_version) = row.map_err(|e| e.to_string())?;
            entries.push(CloudHistory {
                kind,
                id,
                payload: payload
                    .map(|s| serde_json::from_str(&s))
                    .transpose()
                    .map_err(|e| e.to_string())?,
                deleted,
                server_version,
            });
        }
        Ok((entries, cursor))
    }
    pub(crate) fn validate_history_reply(&self, reply: &HistoryReply) -> Result<(), String> {
        if reply.cursor < self.history_batch()?.1 {
            return Err("The server returned an outdated history cursor.".into());
        }
        for entry in reply.changes.iter().chain(&reply.acknowledged) {
            validate(entry)?;
        }
        Ok(())
    }
}
fn validate(entry: &CloudHistory) -> Result<(), String> {
    let invalid =
        || "The server returned invalid focus history. Local history was preserved.".to_string();
    if uuid::Uuid::parse_str(&entry.id).is_err()
        || entry.server_version <= 0
        || !matches!(entry.kind.as_str(), "session" | "completion")
    {
        return Err(invalid());
    }
    if entry.deleted {
        return Ok(());
    }
    let payload = entry.payload.clone().ok_or_else(invalid)?;
    if entry.kind == "session" {
        let r: Record = serde_json::from_value(payload).map_err(|_| invalid())?;
        if r.id != entry.id
            || r.started_unix_ms > i64::MAX as u64
            || r.active_ms > i64::MAX as u64
            || !matches!(
                r.outcome.as_str(),
                "completed" | "interrupted" | "finished" | "skipped"
            )
            || r.task
                .as_ref()
                .is_some_and(|t| uuid::Uuid::parse_str(&t.id).is_err())
        {
            return Err(invalid());
        }
    } else {
        let r: TaskCompletionEvent = serde_json::from_value(payload).map_err(|_| invalid())?;
        if r.id != entry.id
            || uuid::Uuid::parse_str(&r.task_id).is_err()
            || r.completed_unix_ms > i64::MAX as u64
        {
            return Err(invalid());
        }
    }
    Ok(())
}
pub(crate) fn apply_history(
    tx: &rusqlite::Transaction<'_>,
    reply: &HistoryReply,
) -> Result<(), String> {
    for entry in reply.acknowledged.iter().chain(&reply.changes) {
        let local: Option<(bool, i64)> = tx
            .query_row(
                "SELECT deleted,server_version FROM history_sync WHERE kind=?1 AND id=?2",
                params![entry.kind, entry.id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .optional()
            .map_err(|e| e.to_string())?;
        // A reset during an upload must remain queued. Never resurrect tombstones.
        if local.is_some_and(|(deleted, version)| {
            version > entry.server_version || (deleted && !entry.deleted)
        }) {
            continue;
        }
        if entry.deleted {
            let sql = if entry.kind == "session" {
                "DELETE FROM sessions WHERE id=?1"
            } else {
                "DELETE FROM task_completion_events WHERE id=?1"
            };
            tx.execute(sql, [&entry.id]).map_err(|e| e.to_string())?;
        } else if entry.kind == "session" {
            let r: Record = serde_json::from_value(entry.payload.clone().unwrap())
                .map_err(|e| e.to_string())?;
            tx.execute("INSERT INTO sessions(id,phase,started_unix_ms,active_ms,outcome,task_id,task_title) VALUES (?1,?2,?3,?4,?5,?6,?7) ON CONFLICT(id) DO UPDATE SET phase=excluded.phase,started_unix_ms=excluded.started_unix_ms,active_ms=excluded.active_ms,outcome=excluded.outcome,task_id=excluded.task_id,task_title=excluded.task_title",params![r.id,serde_json::to_string(&r.phase).map_err(|e| e.to_string())?,r.started_unix_ms as i64,r.active_ms as i64,r.outcome,r.task.as_ref().map(|t| &t.id),r.task.as_ref().map(|t| &t.title)]).map_err(|e| e.to_string())?;
        } else {
            let r: TaskCompletionEvent = serde_json::from_value(entry.payload.clone().unwrap())
                .map_err(|e| e.to_string())?;
            tx.execute("INSERT INTO task_completion_events(id,task_id,completed_unix_ms) VALUES (?1,?2,?3) ON CONFLICT(id) DO UPDATE SET task_id=excluded.task_id,completed_unix_ms=excluded.completed_unix_ms",params![r.id,r.task_id,r.completed_unix_ms as i64]).map_err(|e| e.to_string())?;
        }
        tx.execute("INSERT INTO history_sync(kind,id,payload,deleted,sync_dirty,server_version) VALUES (?1,?2,?3,?4,0,?5) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,deleted=excluded.deleted,sync_dirty=0,server_version=excluded.server_version", params![entry.kind,entry.id,entry.payload.as_ref().map(Value::to_string),entry.deleted,entry.server_version]).map_err(|e| e.to_string())?;
    }
    tx.execute("INSERT INTO preferences VALUES ('history_sync_cursor',?1) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",[reply.cursor.to_string()]).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Engine, Phase, TaskStatus, sync::SyncReply};
    use std::path::Path;
    fn reply(entries: Vec<CloudHistory>, acknowledged: bool, cursor: i64) -> SyncReply {
        SyncReply {
            acknowledged: vec![],
            changes: vec![],
            cursor: 0,
            has_more: false,
            conflicts: 0,
            history: HistoryReply {
                acknowledged: if acknowledged {
                    entries.clone()
                } else {
                    vec![]
                },
                changes: entries,
                cursor,
                has_more: false,
            },
        }
    }
    fn saved_session(store: &mut Store) -> Record {
        let r = Record {
            id: uuid::Uuid::new_v4().to_string(),
            phase: Phase::Focus,
            started_unix_ms: 100,
            active_ms: 60000,
            outcome: "completed".into(),
            task: None,
        };
        store.save(&Engine::default(), 0, Some(&r)).unwrap();
        r
    }
    #[test]
    fn two_devices_merge_sessions_and_completions_without_double_counting() {
        let mut a = Store::open(Path::new(":memory:")).unwrap();
        let mut b = Store::open(Path::new(":memory:")).unwrap();
        let record = saved_session(&mut a);
        let task = a.create_task("Task", 100).unwrap();
        a.set_task_status(&task.id, TaskStatus::Done, &Engine::default(), 200, 0)
            .unwrap();
        let mut entries = a.sync_batch("account").unwrap().history_changes;
        assert_eq!(entries.len(), 2);
        for (i, entry) in entries.iter_mut().enumerate() {
            entry.server_version = i as i64 + 1;
        }
        let upload = reply(entries.clone(), true, 2);
        a.apply_task_sync("account", &upload, &Engine::default(), 0)
            .unwrap();
        a.apply_task_sync("account", &upload, &Engine::default(), 0)
            .unwrap();
        b.apply_task_sync("account", &reply(entries, false, 2), &Engine::default(), 0)
            .unwrap();
        assert_eq!(b.records().unwrap()[0].id, record.id);
        assert_eq!(b.daily_totals(0, 1000).unwrap().pomodoro_ms, 60000);
        assert_eq!(
            b.task_completion_events().unwrap(),
            a.task_completion_events().unwrap()
        );
        assert!(a.sync_batch("account").unwrap().history_changes.is_empty());
        assert!(b.sync_batch("account").unwrap().history_changes.is_empty());
        b.clear_reports().unwrap();
        let mut deleted = b.sync_batch("account").unwrap().history_changes;
        assert_eq!(deleted.len(), 2);
        for (i, entry) in deleted.iter_mut().enumerate() {
            assert!(entry.deleted);
            entry.server_version = i as i64 + 3;
        }
        a.apply_task_sync("account", &reply(deleted, false, 4), &Engine::default(), 0)
            .unwrap();
        assert!(a.records().unwrap().is_empty());
        assert!(a.task_completion_events().unwrap().is_empty());
    }
    #[test]
    fn reset_during_upload_survives_the_acknowledgement_and_restart() {
        let path = std::env::temp_dir().join(format!("history-{}.db", uuid::Uuid::new_v4()));
        let mut store = Store::open(&path).unwrap();
        saved_session(&mut store);
        let mut sent = store.sync_batch("account").unwrap().history_changes;
        sent[0].server_version = 1;
        store.clear_reports().unwrap();
        store
            .apply_task_sync("account", &reply(sent, true, 1), &Engine::default(), 0)
            .unwrap();
        assert!(store.records().unwrap().is_empty());
        drop(store);
        let reopened = Store::open(&path).unwrap();
        let queued = reopened.sync_batch("account").unwrap().history_changes;
        assert_eq!(queued.len(), 1);
        assert!(queued[0].deleted);
        drop(reopened);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn upgrade_backfills_all_history_and_invalid_reply_rolls_back() {
        let path =
            std::env::temp_dir().join(format!("history-upgrade-{}.db", uuid::Uuid::new_v4()));
        let mut store = Store::open(&path).unwrap();
        for _ in 0..25 {
            saved_session(&mut store);
        }
        store.connection.execute_batch("DROP TRIGGER sessions_history_insert; DROP TRIGGER sessions_history_delete; DROP TRIGGER completions_history_insert; DROP TRIGGER completions_history_delete; DROP TABLE history_sync; PRAGMA user_version=6;").unwrap();
        drop(store);
        let mut store = Store::open(&path).unwrap();
        let mut entries = store.sync_batch("account").unwrap().history_changes;
        assert_eq!(
            entries.len(),
            25,
            "backfill must not use the last-20 sessions preview"
        );
        entries[0].server_version = 1;
        entries[0].payload.as_mut().unwrap()["active_ms"] = serde_json::json!(-1);
        assert!(
            store
                .apply_task_sync("account", &reply(entries, true, 1), &Engine::default(), 0)
                .is_err()
        );
        assert_eq!(store.records_between(0, 1000).unwrap().len(), 25);
        assert_eq!(store.sync_batch("account").unwrap().history_cursor, 0);
        drop(store);
        std::fs::remove_file(path).unwrap();
    }
}
