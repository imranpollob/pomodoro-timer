-- Run after 202610210001_task_sync.sql. Existing task-only clients keep working.
create table public.synced_history (
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('session','completion')),
  id uuid not null,
  payload jsonb,
  deleted boolean not null default false,
  server_version bigint not null unique,
  primary key(user_id,kind,id),
  check (deleted or (payload is not null and jsonb_typeof(payload) = 'object'))
);
create index synced_history_user_version on public.synced_history(user_id,server_version);
create sequence public.history_sync_version_seq;
alter table public.synced_history enable row level security;
create policy "Read own history" on public.synced_history for select to authenticated
  using ((select auth.uid()) = user_id);
revoke all on public.synced_history from public,anon,authenticated;
grant select on public.synced_history to authenticated;
revoke all on sequence public.history_sync_version_seq from public,anon,authenticated;

create function public.sync_history(p_changes jsonb, p_after_version bigint default 0)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  owner_id uuid := auth.uid();
  item jsonb;
  body jsonb;
  entry_id uuid;
  entry_kind text;
  is_deleted boolean;
  existing public.synced_history%rowtype;
  acknowledgements jsonb := '[]'::jsonb;
  pulled jsonb;
  next_cursor bigint;
  more boolean;
begin
  if owner_id is null then raise exception 'Sign in before syncing'; end if;
  if p_after_version is null or p_after_version < 0 or p_changes is null
    or jsonb_typeof(p_changes) <> 'array' or jsonb_array_length(p_changes) > 100 then
    raise exception 'Invalid history sync request';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('pomodoro:' || owner_id::text,0));
  for item in select value from jsonb_array_elements(p_changes) loop
    entry_id := (item->>'id')::uuid;
    entry_kind := item->>'kind';
    is_deleted := (item->>'deleted')::boolean;
    body := item->'payload';
    if entry_id is null or entry_kind is null or entry_kind not in ('session','completion') or is_deleted is null then
      raise exception 'Invalid history entry';
    end if;
    if not is_deleted then
      if jsonb_typeof(body) is distinct from 'object' or (body->>'id') is distinct from entry_id::text then
        raise exception 'Invalid history payload';
      end if;
      if entry_kind = 'session' then
        if body->>'phase' is null or body->>'phase' not in ('focus','short_break','long_break','stopwatch')
          or body->>'outcome' is null or body->>'outcome' not in ('completed','interrupted','finished','skipped')
          or body->>'started_unix_ms' is null or (body->>'started_unix_ms')::bigint < 0
          or body->>'active_ms' is null or (body->>'active_ms')::bigint < 0 then
          raise exception 'Invalid session';
        end if;
        if body->'task' is not null and body->'task' <> 'null'::jsonb then
          if jsonb_typeof(body->'task') <> 'object' or body->'task'->>'id' is null
            or body->'task'->>'title' is null then raise exception 'Invalid session task'; end if;
          perform (body->'task'->>'id')::uuid;
        end if;
      else
        if body->>'task_id' is null or body->>'completed_unix_ms' is null
          or (body->>'completed_unix_ms')::bigint < 0 then raise exception 'Invalid completion'; end if;
        perform (body->>'task_id')::uuid;
      end if;
    end if;
    -- UUID records are immutable. Retrying inserts does not double count history;
    -- retained tombstones prevent offline devices from restoring reset records.
    select * into existing from public.synced_history
      where user_id=owner_id and kind=entry_kind and id=entry_id for update;
    if not found then
      insert into public.synced_history values(owner_id,entry_kind,entry_id,
        case when is_deleted then null else body end,is_deleted,nextval('public.history_sync_version_seq'::regclass)) returning * into existing;
    elsif is_deleted and not existing.deleted then
      update public.synced_history set payload=null,deleted=true,
        server_version=nextval('public.history_sync_version_seq'::regclass)
        where user_id=owner_id and kind=entry_kind and id=entry_id returning * into existing;
    end if;
    acknowledgements := acknowledgements || jsonb_build_array(to_jsonb(existing)-'user_id');
  end loop;
  select coalesce(jsonb_agg(to_jsonb(t)-'user_id' order by t.server_version),'[]'::jsonb),
    coalesce(max(t.server_version),p_after_version) into pulled,next_cursor
    from (select * from public.synced_history where user_id=owner_id and server_version>p_after_version order by server_version limit 500) t;
  select exists(select 1 from public.synced_history where user_id=owner_id and server_version>next_cursor) into more;
  return jsonb_build_object('acknowledged',acknowledgements,'changes',pulled,'cursor',next_cursor,'has_more',more);
end;
$$;
revoke all on function public.sync_history(jsonb,bigint) from public,anon;
grant execute on function public.sync_history(jsonb,bigint) to authenticated;

create function public.sync_app_data(p_changes jsonb, p_after_version bigint,
  p_history_changes jsonb, p_history_after_version bigint)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare result jsonb;
begin
  result := public.sync_tasks(p_changes,p_after_version);
  return result || jsonb_build_object('history',public.sync_history(p_history_changes,p_history_after_version));
end;
$$;
revoke all on function public.sync_app_data(jsonb,bigint,jsonb,bigint) from public,anon;
grant execute on function public.sync_app_data(jsonb,bigint,jsonb,bigint) to authenticated;
