use crate::{Engine, Record, Task};
use rusqlite::{Connection, OptionalExtension, params};
use std::path::Path;

pub struct Store {
    connection: Connection,
}

impl Store {
    #[cfg(test)]
    pub(crate) fn reject_records(&self) {
        self.connection.execute_batch("CREATE TRIGGER reject_record BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END;").unwrap();
    }
    pub fn open(path: &Path) -> Result<Self, String> {
        let connection = Connection::open(path).map_err(|e| e.to_string())?;
        connection
            .busy_timeout(std::time::Duration::from_secs(3))
            .map_err(|e| e.to_string())?;
        connection
            .execute_batch(
                "PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;",
            )
            .map_err(|e| e.to_string())?;
        let version: u32 = connection
            .query_row("PRAGMA user_version", [], |r| r.get(0))
            .map_err(|e| e.to_string())?;
        if version > 3 {
            return Err("Database was created by a newer app; it was left intact.".into());
        }
        if version == 0 {
            connection.execute_batch("BEGIN IMMEDIATE;
                CREATE TABLE sessions (id TEXT PRIMARY KEY, phase TEXT NOT NULL, started_unix_ms INTEGER NOT NULL, active_ms INTEGER NOT NULL CHECK(active_ms >= 0), outcome TEXT NOT NULL);
                CREATE TABLE app_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                PRAGMA user_version=1; COMMIT;").map_err(|e| e.to_string())?;
        }
        if version < 2 {
            connection
                .execute_batch(
                    "BEGIN IMMEDIATE;
                CREATE TABLE preferences (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
                PRAGMA user_version=2; COMMIT;",
                )
                .map_err(|e| e.to_string())?;
        }
        if version < 3 {
            connection
                .execute_batch(
                    "BEGIN IMMEDIATE;
                    CREATE TABLE tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                        deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0, 1)),
                        created_unix_ms INTEGER NOT NULL,
                        updated_unix_ms INTEGER NOT NULL
                    );
                    ALTER TABLE sessions ADD COLUMN task_id TEXT;
                    ALTER TABLE sessions ADD COLUMN task_title TEXT;
                    CREATE INDEX sessions_started_idx ON sessions(started_unix_ms DESC);
                    PRAGMA user_version=3;
                    COMMIT;",
                )
                .map_err(|e| e.to_string())?;
        }
        Ok(Self { connection })
    }
    pub fn create_task(&self, title: &str, now: u64) -> Result<Task, String> {
        let title = validate_title(title)?;
        let id = uuid::Uuid::new_v4().to_string();
        let now = i64::try_from(now).map_err(|e| e.to_string())?;
        self.connection
            .execute(
                "INSERT INTO tasks (id, title, created_unix_ms, updated_unix_ms) VALUES (?1, ?2, ?3, ?3)",
                rusqlite::params![id, title, now],
            )
            .map_err(|e| e.to_string())?;
        self.task(&id)?
            .ok_or_else(|| "Created task could not be read back".into())
    }
    pub fn rename_task(&self, id: &str, title: &str, now: u64) -> Result<Task, String> {
        let title = validate_title(title)?;
        let now = i64::try_from(now).map_err(|e| e.to_string())?;
        let changed = self
            .connection
            .execute(
                "UPDATE tasks SET title=?2, updated_unix_ms=?3 WHERE id=?1 AND deleted=0",
                rusqlite::params![id, title, now],
            )
            .map_err(|e| e.to_string())?;
        if changed == 0 {
            return Err("Task no longer exists.".into());
        }
        self.task(id)?
            .ok_or_else(|| "Updated task could not be read back".into())
    }
    pub fn set_task_completed(&self, id: &str, completed: bool, now: u64) -> Result<(), String> {
        let changed = self
            .connection
            .execute(
                "UPDATE tasks SET completed=?2, updated_unix_ms=?3 WHERE id=?1 AND deleted=0",
                rusqlite::params![
                    id,
                    completed,
                    i64::try_from(now).map_err(|e| e.to_string())?
                ],
            )
            .map_err(|e| e.to_string())?;
        if changed == 0 {
            return Err("Task no longer exists.".into());
        }
        Ok(())
    }
    pub fn delete_task(
        &mut self,
        id: &str,
        engine: &Engine,
        wall_now: u64,
        tick_now: u64,
    ) -> Result<(), String> {
        let wall_now = i64::try_from(wall_now).map_err(|e| e.to_string())?;
        let checkpoint =
            serde_json::to_string(&engine.checkpoint(tick_now)).map_err(|e| e.to_string())?;
        let tx = self.connection.transaction().map_err(|e| e.to_string())?;
        let changed = tx
            .execute(
                "UPDATE tasks SET deleted=1, updated_unix_ms=?2 WHERE id=?1 AND deleted=0",
                rusqlite::params![id, wall_now],
            )
            .map_err(|e| e.to_string())?;
        if changed == 0 {
            return Err("Task no longer exists.".into());
        }
        tx.execute("INSERT INTO app_state VALUES (1, ?1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", [checkpoint]).map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())
    }
    pub fn task(&self, id: &str) -> Result<Option<Task>, String> {
        self.connection.query_row(
            "SELECT id, title, completed, created_unix_ms, updated_unix_ms FROM tasks WHERE id=?1 AND deleted=0",
            [id], task_from_row,
        ).optional().map_err(|e| e.to_string())
    }
    pub fn selectable_task(&self, id: &str) -> Result<Option<Task>, String> {
        self.connection.query_row(
            "SELECT id, title, completed, created_unix_ms, updated_unix_ms FROM tasks WHERE id=?1 AND deleted=0 AND completed=0",
            [id], task_from_row,
        ).optional().map_err(|e| e.to_string())
    }
    pub fn tasks(&self) -> Result<Vec<Task>, String> {
        let mut query = self.connection.prepare(
            "SELECT id, title, completed, created_unix_ms, updated_unix_ms FROM tasks WHERE deleted=0 ORDER BY completed ASC, updated_unix_ms DESC, rowid DESC"
        ).map_err(|e| e.to_string())?;
        query
            .query_map([], task_from_row)
            .map_err(|e| e.to_string())?
            .map(|row| row.map_err(|e| e.to_string()))
            .collect()
    }
    pub fn preference(&self, key: &str) -> Result<Option<String>, String> {
        self.connection
            .query_row("SELECT payload FROM preferences WHERE key=?1", [key], |r| {
                r.get(0)
            })
            .optional()
            .map_err(|e| e.to_string())
    }
    pub fn save_preference(&self, key: &str, payload: &str) -> Result<(), String> {
        serde_json::from_str::<serde_json::Value>(payload).map_err(|e| e.to_string())?;
        self.connection.execute("INSERT INTO preferences VALUES (?1, ?2) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload", [key, payload])
            .map_err(|e| e.to_string())?;
        Ok(())
    }
    pub fn load(&self) -> Result<Engine, String> {
        let payload: Option<String> = self
            .connection
            .query_row("SELECT payload FROM app_state WHERE id=1", [], |r| r.get(0))
            .optional()
            .map_err(|e| e.to_string())?;
        let state: Engine = match payload {
            Some(p) => serde_json::from_str(&p).map_err(|e| format!("Invalid checkpoint: {e}"))?,
            None => Engine::default(),
        };
        state.validate()?;
        Ok(state)
    }
    pub fn save(
        &mut self,
        engine: &Engine,
        now: u64,
        record: Option<&Record>,
    ) -> Result<(), String> {
        let payload = serde_json::to_string(&engine.checkpoint(now)).map_err(|e| e.to_string())?;
        let tx = self.connection.transaction().map_err(|e| e.to_string())?;
        if let Some(r) = record {
            let started = i64::try_from(r.started_unix_ms).map_err(|e| e.to_string())?;
            let active = i64::try_from(r.active_ms).map_err(|e| e.to_string())?;
            tx.execute(
                "INSERT INTO sessions (id, phase, started_unix_ms, active_ms, outcome, task_id, task_title) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(id) DO NOTHING",
                params![
                    r.id,
                    serde_json::to_string(&r.phase).map_err(|e| e.to_string())?,
                    started,
                    active,
                    r.outcome,
                    r.task.as_ref().map(|task| task.id.as_str()),
                    r.task.as_ref().map(|task| task.title.as_str())
                ],
            )
            .map_err(|e| e.to_string())?;
        }
        tx.execute("INSERT INTO app_state VALUES (1, ?1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", [payload]).map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())
    }
    pub fn records(&self) -> Result<Vec<Record>, String> {
        self.records_query(None)
    }
    pub fn records_between(
        &self,
        start_unix_ms: u64,
        end_unix_ms: u64,
    ) -> Result<Vec<Record>, String> {
        let start = i64::try_from(start_unix_ms).map_err(|e| e.to_string())?;
        let end = i64::try_from(end_unix_ms).map_err(|e| e.to_string())?;
        if start >= end {
            return Err("Invalid report date range.".into());
        }
        self.records_query(Some((start, end)))
    }
    fn records_query(&self, range: Option<(i64, i64)>) -> Result<Vec<Record>, String> {
        let sql = if range.is_some() {
            "SELECT id, phase, started_unix_ms, active_ms, outcome, task_id, task_title FROM sessions WHERE started_unix_ms >= ?1 AND started_unix_ms < ?2 ORDER BY started_unix_ms DESC, rowid DESC"
        } else {
            "SELECT id, phase, started_unix_ms, active_ms, outcome, task_id, task_title FROM sessions ORDER BY started_unix_ms DESC, rowid DESC LIMIT 20"
        };
        let mut query = self.connection.prepare(sql).map_err(|e| e.to_string())?;
        let rows = query
            .query_map(
                rusqlite::params_from_iter(range.into_iter().flat_map(|(s, e)| [s, e])),
                |r| {
                    Ok((
                        r.get::<_, String>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, i64>(2)?,
                        r.get::<_, i64>(3)?,
                        r.get::<_, String>(4)?,
                        r.get::<_, Option<String>>(5)?,
                        r.get::<_, Option<String>>(6)?,
                    ))
                },
            )
            .map_err(|e| e.to_string())?;
        rows.map(|row| {
            let (id, phase, started_unix_ms, active_ms, outcome, task_id, task_title) =
                row.map_err(|e| e.to_string())?;
            Ok(Record {
                id,
                phase: serde_json::from_str(&phase).map_err(|e| e.to_string())?,
                started_unix_ms: u64::try_from(started_unix_ms).map_err(|e| e.to_string())?,
                active_ms: u64::try_from(active_ms).map_err(|e| e.to_string())?,
                outcome,
                task: task_id
                    .zip(task_title)
                    .map(|(id, title)| crate::TaskReference { id, title }),
            })
        })
        .collect()
    }
    pub fn clear_sessions(&self) -> Result<(), String> {
        self.connection
            .execute_batch("DELETE FROM sessions;")
            .map_err(|e| e.to_string())
    }

    pub fn daily_totals(
        &self,
        start_unix_ms: u64,
        end_unix_ms: u64,
    ) -> Result<DailyTotals, String> {
        let start = i64::try_from(start_unix_ms).map_err(|e| e.to_string())?;
        let end = i64::try_from(end_unix_ms).map_err(|e| e.to_string())?;
        if start >= end {
            return Err("Invalid report date range.".into());
        }
        self.connection
            .query_row(
                "SELECT COALESCE(SUM(CASE WHEN phase='\"focus\"' THEN active_ms ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN phase='\"stopwatch\"' THEN active_ms ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN phase='\"focus\"' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN phase='\"stopwatch\"' THEN 1 ELSE 0 END), 0)
             FROM sessions WHERE started_unix_ms >= ?1 AND started_unix_ms < ?2",
                rusqlite::params![start, end],
                |row| {
                    Ok(DailyTotals {
                        pomodoro_ms: u64::try_from(row.get::<_, i64>(0)?).unwrap_or(0),
                        stopwatch_ms: u64::try_from(row.get::<_, i64>(1)?).unwrap_or(0),
                        pomodoro_sessions: u64::try_from(row.get::<_, i64>(2)?).unwrap_or(0),
                        stopwatch_sessions: u64::try_from(row.get::<_, i64>(3)?).unwrap_or(0),
                    })
                },
            )
            .map_err(|e| e.to_string())
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct DailyTotals {
    pub pomodoro_ms: u64,
    pub stopwatch_ms: u64,
    pub pomodoro_sessions: u64,
    pub stopwatch_sessions: u64,
}

fn validate_title(title: &str) -> Result<String, String> {
    let title = title.trim();
    if title.is_empty() {
        return Err("Task title cannot be empty.".into());
    }
    if title.chars().count() > 120 {
        return Err("Task title must be 120 characters or fewer.".into());
    }
    Ok(title.to_owned())
}

fn task_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Task> {
    Ok(Task {
        id: row.get(0)?,
        title: row.get(1)?,
        completed: row.get(2)?,
        created_unix_ms: u64::try_from(row.get::<_, i64>(3)?).unwrap_or(0),
        updated_unix_ms: u64::try_from(row.get::<_, i64>(4)?).unwrap_or(0),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Command;
    #[test]
    fn version_one_upgrade_preserves_sessions_and_checkpoint() {
        let path =
            std::env::temp_dir().join(format!("pomodoro-upgrade-{}.sqlite3", uuid::Uuid::new_v4()));
        let connection = Connection::open(&path).unwrap();
        connection.execute_batch("CREATE TABLE sessions (id TEXT PRIMARY KEY, phase TEXT NOT NULL, started_unix_ms INTEGER NOT NULL, active_ms INTEGER NOT NULL, outcome TEXT NOT NULL);
            CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL); PRAGMA user_version=1;").unwrap();
        let mut engine = Engine::default();
        engine.apply(Command::Toggle, 0, 1000).unwrap();
        connection
            .execute(
                "INSERT INTO app_state VALUES (1, ?1)",
                [serde_json::to_string(&engine.checkpoint(5500)).unwrap()],
            )
            .unwrap();
        connection
            .execute(
                "INSERT INTO sessions VALUES (?1, ?2, 1000, 65000, 'interrupted')",
                [uuid::Uuid::new_v4().to_string(), "\"focus\"".into()],
            )
            .unwrap();
        drop(connection);
        let store = Store::open(&path).unwrap();
        assert_eq!(store.records().unwrap()[0].active_ms, 65000);
        assert_eq!(store.load().unwrap().view(u64::MAX).active_ms, 5500);
        store.save_preference("desktop", "{\"volume\":60}").unwrap();
        assert_eq!(
            store.preference("desktop").unwrap().as_deref(),
            Some("{\"volume\":60}")
        );
        drop(store);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn completion_and_checkpoint_commit_once() {
        let mut store = Store::open(Path::new(":memory:")).unwrap();
        let mut e = Engine::default();
        e.apply(Command::Toggle, 0, 0).unwrap();
        let record = e.apply(Command::Finish, 65_000, 0).unwrap().unwrap();
        store.save(&e, 65_000, Some(&record)).unwrap();
        store.save(&e, 65_000, Some(&record)).unwrap();
        assert_eq!(store.records().unwrap().len(), 1);
        assert!(!store.load().unwrap().has_active());
    }
    #[test]
    fn clear_sessions_removes_records_and_totals() {
        let store = Store::open(Path::new(":memory:")).unwrap();
        store
            .connection
            .execute(
                "INSERT INTO sessions (id, phase, started_unix_ms, active_ms, outcome) VALUES (?1, '\"focus\"', ?2, 60000, 'completed')",
                params![uuid::Uuid::new_v4().to_string(), 1000],
            )
            .unwrap();
        assert_eq!(store.records_between(0, 2000).unwrap().len(), 1);
        assert_eq!(store.daily_totals(0, 2000).unwrap().pomodoro_sessions, 1);
        store.clear_sessions().unwrap();
        assert!(store.records_between(0, 2000).unwrap().is_empty());
        let totals = store.daily_totals(0, 2000).unwrap();
        assert_eq!(totals.pomodoro_ms, 0);
        assert_eq!(totals.pomodoro_sessions, 0);
    }

    #[test]
    fn report_range_returns_every_matching_session_not_only_the_preview_limit() {
        let store = Store::open(Path::new(":memory:")).unwrap();
        for started in 1000..1030 {
            store.connection.execute(
                "INSERT INTO sessions (id, phase, started_unix_ms, active_ms, outcome) VALUES (?1, '\"focus\"', ?2, 60000, 'completed')",
                params![uuid::Uuid::new_v4().to_string(), started],
            ).unwrap();
        }
        assert_eq!(store.records().unwrap().len(), 20);
        let range = store.records_between(1005, 1028).unwrap();
        assert_eq!(range.len(), 23);
        assert_eq!(range.first().unwrap().started_unix_ms, 1027);
        assert_eq!(range.last().unwrap().started_unix_ms, 1005);
        assert!(store.records_between(20, 20).is_err());
    }
    #[test]
    fn failed_transaction_keeps_prior_session_and_checkpoint() {
        let mut store = Store::open(Path::new(":memory:")).unwrap();
        let mut e = Engine::default();
        e.apply(Command::Toggle, 0, 0).unwrap();
        store.save(&e, 10_000, None).unwrap();
        store.connection.execute_batch("CREATE TRIGGER reject_record BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END;").unwrap();
        let record = e.apply(Command::Finish, 65_000, 0).unwrap().unwrap();
        assert!(store.save(&e, 65_000, Some(&record)).is_err());
        assert!(store.records().unwrap().is_empty());
        assert_eq!(store.load().unwrap().view(9_000_000).active_ms, 10_000);
    }
    #[test]
    fn corrupt_checkpoint_cannot_be_treated_as_empty() {
        let store = Store::open(Path::new(":memory:")).unwrap();
        store
            .connection
            .execute("INSERT INTO app_state VALUES (1, '{bad')", [])
            .unwrap();
        assert!(store.load().is_err());
    }
}
