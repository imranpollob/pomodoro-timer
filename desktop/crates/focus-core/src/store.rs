use crate::{Engine, Record};
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
        if version > 2 {
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
        Ok(Self { connection })
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
                "INSERT INTO sessions VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(id) DO NOTHING",
                params![
                    r.id,
                    serde_json::to_string(&r.phase).map_err(|e| e.to_string())?,
                    started,
                    active,
                    r.outcome
                ],
            )
            .map_err(|e| e.to_string())?;
        }
        tx.execute("INSERT INTO app_state VALUES (1, ?1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", [payload]).map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())
    }
    pub fn records(&self) -> Result<Vec<Record>, String> {
        let mut query = self.connection.prepare("SELECT id, phase, started_unix_ms, active_ms, outcome FROM sessions ORDER BY started_unix_ms DESC, rowid DESC LIMIT 20").map_err(|e| e.to_string())?;
        let rows = query
            .query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, i64>(2)?,
                    r.get::<_, i64>(3)?,
                    r.get::<_, String>(4)?,
                ))
            })
            .map_err(|e| e.to_string())?;
        rows.map(|row| {
            let (id, phase, started_unix_ms, active_ms, outcome) =
                row.map_err(|e| e.to_string())?;
            Ok(Record {
                id,
                phase: serde_json::from_str(&phase).map_err(|e| e.to_string())?,
                started_unix_ms: u64::try_from(started_unix_ms).map_err(|e| e.to_string())?,
                active_ms: u64::try_from(active_ms).map_err(|e| e.to_string())?,
                outcome,
            })
        })
        .collect()
    }
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
