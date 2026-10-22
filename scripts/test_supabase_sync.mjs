import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import assert from 'node:assert/strict';
import test from 'node:test';

test('Supabase task sync: isolation, retries, conflicts, tombstones and pagination', async () => {
  const database = new PGlite();
  try {
    // A minimal test-only replacement for Supabase Auth. The production
    // migration uses Supabase's verified auth.uid(), never a client-supplied ID.
    await database.exec(`
      create schema auth;
      create role anon;
      create role authenticated;
      create table auth.users (id uuid primary key);
      create function auth.uid() returns uuid language sql stable as
        'select nullif(current_setting(''app.test_user'',true),'''')::uuid';
      grant usage on schema auth to authenticated;
      grant execute on function auth.uid() to authenticated;
    `);
    const users = [randomUUID(), randomUUID()];
    for (const id of users) await database.query('insert into auth.users values ($1)', [id]);
    const migration = await readFile(new URL('../supabase/migrations/202610210001_task_sync.sql', import.meta.url), 'utf8');
    await database.exec(migration);
    await database.exec('set role authenticated');
    const asUser = async id => { await database.query("select set_config('app.test_user',$1,false)", [id]); };
    const sync = async (changes = [], cursor = 0) => {
      const { rows } = await database.query('select public.sync_tasks($1::jsonb,$2::bigint) as result', [JSON.stringify(changes), cursor]);
      return rows[0].result;
    };
    const change = (title, extra = {}) => ({ id: randomUUID(), title, status: 'todo', deleted: false,
      created_unix_ms: 100, updated_unix_ms: 100, server_version: 0, change_id: randomUUID(), ...extra });

    await asUser(users[0]);
    const first = change('Account A task');
    const upload = await sync([first]);
    const version = upload.acknowledged[0].task.server_version;
    assert.equal(upload.acknowledged[0].applied, true);
    assert.equal(upload.changes.length, 1);
    assert.equal(upload.changes[0].title, first.title);
    const retry = await sync([first]);
    assert.equal(retry.acknowledged[0].task.server_version, version, 'lost acknowledgements must not create another version');
    assert.equal((await sync([], upload.cursor)).changes.length, 0);

    await asUser(users[1]);
    assert.equal((await sync()).changes.length, 0, 'another account cannot read A’s tasks');
    const second = change('Account B task', { id: first.id, user_id: users[0] });
    await sync([second]);
    assert.deepEqual((await database.query('select title from public.synced_tasks')).rows.map(row => row.title), ['Account B task']);
    await assert.rejects(database.query("update public.synced_tasks set title='bypass'"), /permission denied/i);
    await assert.rejects(database.query("select nextval('public.task_sync_version_seq')"), /permission denied/i);

    await asUser(users[0]);
    const edit = change('Edited on another device', { id: first.id, server_version: version });
    const edited = await sync([edit]);
    const stale = change('Stale offline edit', { id: first.id, server_version: version });
    const conflict = await sync([stale]);
    assert.equal(conflict.conflicts, 1);
    assert.equal(conflict.acknowledged[0].applied, false);
    assert.equal(conflict.acknowledged[0].task.title, edit.title);
    const deletion = change(edit.title, { id: first.id, server_version: edited.acknowledged[0].task.server_version, deleted: true });
    const removed = await sync([deletion]);
    const staleAfterDelete = await sync([stale]);
    assert.equal(staleAfterDelete.acknowledged[0].task.deleted, true, 'an offline edit must not resurrect a deleted task');
    assert.equal((await sync()).changes[0].deleted, true, 'new devices receive deletion markers');

    const baseline = removed.cursor;
    const many = Array.from({ length: 501 }, (_, i) => change(`Task ${i}`));
    for (let i = 0; i < many.length; i += 100) await sync(many.slice(i, i + 100), baseline);
    const page1 = await sync([], baseline);
    const page2 = await sync([], page1.cursor);
    assert.equal(page1.changes.length, 500);
    assert.equal(page1.has_more, true);
    assert.equal(page2.changes.length, 1);
    assert.equal(page2.has_more, false);
    await assert.rejects(sync(many.slice(0, 101)), /Invalid sync request/);

    await asUser('');
    assert.equal((await database.query('select * from public.synced_tasks')).rows.length, 0);
    await assert.rejects(sync(), /Sign in before syncing/);
    await database.exec('reset role; set role anon');
    await assert.rejects(sync(), /permission denied/i);
  } finally { await database.close(); }
});
