BEGIN IMMEDIATE;
CREATE TABLE history_sync (
    kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT, deleted INTEGER NOT NULL DEFAULT 0,
    sync_dirty INTEGER NOT NULL DEFAULT 1, server_version INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(kind,id)
);
INSERT INTO history_sync(kind,id,payload)
SELECT 'session',id,json_object('id',id,'phase',json(phase),'started_unix_ms',started_unix_ms,
    'active_ms',active_ms,'outcome',outcome,'task',CASE WHEN task_id IS NULL THEN NULL ELSE json_object('id',task_id,'title',task_title) END) FROM sessions;
INSERT INTO history_sync(kind,id,payload)
SELECT 'completion',id,json_object('id',id,'task_id',task_id,'completed_unix_ms',completed_unix_ms) FROM task_completion_events;
CREATE TRIGGER sessions_history_insert AFTER INSERT ON sessions BEGIN
    INSERT INTO history_sync(kind,id,payload) VALUES ('session',NEW.id,json_object('id',NEW.id,'phase',json(NEW.phase),
        'started_unix_ms',NEW.started_unix_ms,'active_ms',NEW.active_ms,'outcome',NEW.outcome,
        'task',CASE WHEN NEW.task_id IS NULL THEN NULL ELSE json_object('id',NEW.task_id,'title',NEW.task_title) END))
    ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,deleted=0,sync_dirty=1;
END;
CREATE TRIGGER sessions_history_delete AFTER DELETE ON sessions BEGIN
    INSERT INTO history_sync(kind,id,deleted) VALUES ('session',OLD.id,1)
    ON CONFLICT(kind,id) DO UPDATE SET payload=NULL,deleted=1,sync_dirty=1;
END;
CREATE TRIGGER completions_history_insert AFTER INSERT ON task_completion_events BEGIN
    INSERT INTO history_sync(kind,id,payload) VALUES ('completion',NEW.id,json_object('id',NEW.id,'task_id',NEW.task_id,'completed_unix_ms',NEW.completed_unix_ms))
    ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,deleted=0,sync_dirty=1;
END;
CREATE TRIGGER completions_history_delete AFTER DELETE ON task_completion_events BEGIN
    INSERT INTO history_sync(kind,id,deleted) VALUES ('completion',OLD.id,1)
    ON CONFLICT(kind,id) DO UPDATE SET payload=NULL,deleted=1,sync_dirty=1;
END;
PRAGMA user_version=7;
COMMIT;
