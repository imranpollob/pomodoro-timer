-- Task-only synchronization. Focus sessions, reports and device preferences remain local.
create table public.synced_tasks (
  user_id uuid not null references auth.users(id) on delete cascade,
  id uuid not null,
  title text not null check (length(btrim(title)) > 0),
  status text not null check (status in ('todo', 'in_progress', 'done')),
  deleted boolean not null default false,
  created_unix_ms bigint not null check (created_unix_ms >= 0),
  updated_unix_ms bigint not null check (updated_unix_ms >= 0),
  server_version bigint not null unique,
  last_change_id text not null,
  primary key (user_id, id)
);
create index synced_tasks_user_version on public.synced_tasks(user_id, server_version);
create sequence public.task_sync_version_seq;
alter table public.synced_tasks enable row level security;
create policy "Read own tasks" on public.synced_tasks for select to authenticated
  using ((select auth.uid()) = user_id);
revoke all on public.synced_tasks from public, anon, authenticated;
grant select on public.synced_tasks to authenticated;
revoke all on sequence public.task_sync_version_seq from public, anon, authenticated;

-- Only this RPC can write, so revisions and account ownership cannot be bypassed.
-- A per-user transaction lock orders commits before advancing a device's cursor.
create function public.sync_tasks(p_changes jsonb, p_after_version bigint default 0)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  owner_id uuid := auth.uid();
  item jsonb;
  existing public.synced_tasks%rowtype;
  task_id uuid;
  change_id text;
  base_version bigint;
  applied boolean;
  acknowledgements jsonb := '[]'::jsonb;
  pulled jsonb;
  next_cursor bigint;
  more boolean;
  conflict_count integer := 0;
begin
  if owner_id is null then raise exception 'Sign in before syncing'; end if;
  if p_after_version is null or p_after_version < 0 or p_changes is null
    or jsonb_typeof(p_changes) <> 'array' or jsonb_array_length(p_changes) > 100 then
    raise exception 'Invalid sync request';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('pomodoro:' || owner_id::text, 0));
  for item in select value from jsonb_array_elements(p_changes) loop
    task_id := (item->>'id')::uuid;
    change_id := item->>'change_id';
    base_version := (item->>'server_version')::bigint;
    if task_id is null or change_id is null or length(change_id) not between 16 and 128
      or base_version is null or base_version < 0 then raise exception 'Invalid task change'; end if;
    select * into existing from public.synced_tasks where user_id=owner_id and id=task_id for update;
    applied := true;
    if not found then
      if base_version <> 0 then raise exception 'Task is missing on the server'; end if;
      insert into public.synced_tasks values (
        owner_id, task_id, item->>'title', item->>'status', (item->>'deleted')::boolean,
        (item->>'created_unix_ms')::bigint, (item->>'updated_unix_ms')::bigint,
        nextval('public.task_sync_version_seq'::regclass), change_id
      ) returning * into existing;
    elsif existing.last_change_id = change_id then
      -- Retrying a request whose response was lost is safe and creates no new version.
      null;
    elsif existing.server_version = base_version then
      update public.synced_tasks set title=item->>'title', status=item->>'status',
        deleted=(item->>'deleted')::boolean, updated_unix_ms=(item->>'updated_unix_ms')::bigint,
        server_version=nextval('public.task_sync_version_seq'::regclass), last_change_id=change_id
        where user_id=owner_id and id=task_id returning * into existing;
    else
      -- Preserve the server copy on simultaneous edits; tell the app about the conflict.
      applied := false;
      conflict_count := conflict_count + 1;
    end if;
    acknowledgements := acknowledgements || jsonb_build_array(jsonb_build_object(
      'change_id', change_id, 'task', to_jsonb(existing) - 'user_id' - 'last_change_id', 'applied', applied));
  end loop;
  select coalesce(jsonb_agg(to_jsonb(t) - 'user_id' - 'last_change_id' order by t.server_version), '[]'::jsonb),
    coalesce(max(t.server_version), p_after_version) into pulled, next_cursor
    from (select * from public.synced_tasks where user_id=owner_id and server_version>p_after_version
          order by server_version limit 500) t;
  select exists(select 1 from public.synced_tasks where user_id=owner_id and server_version>next_cursor) into more;
  return jsonb_build_object('acknowledged', acknowledgements, 'changes', pulled,
    'cursor', next_cursor, 'has_more', more, 'conflicts', conflict_count);
end;
$$;
revoke all on function public.sync_tasks(jsonb,bigint) from public, anon;
grant execute on function public.sync_tasks(jsonb,bigint) to authenticated;
