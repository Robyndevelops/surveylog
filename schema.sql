-- ============================================================
-- SurveyLog — Multi-tenant schema (v2)
-- Matches the actual field names used by the deployed app,
-- extended with pair_id for multi-tenancy + real Supabase Auth.
-- Run this in the NEW SurveyLog Supabase project
-- (dqilfhjjmrkbijojvckf) — NOT the original Thwaites project.
-- ============================================================

create type user_role as enum ('student', 'supervisor');

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null,
  full_name text not null,
  created_at timestamptz not null default now()
);

create table pairs (
  id uuid primary key default gen_random_uuid(),
  supervisor_id uuid not null references profiles(id) on delete cascade,
  student_id uuid references profiles(id) on delete set null,
  invite_code text unique not null,
  status text not null default 'pending' check (status in ('pending','active','archived')),
  created_at timestamptz not null default now()
);

-- Per-pair settings — everything that was hardcoded for Thwaites/Robyn
-- becomes editable here, filled in during the supervisor's onboarding wizard.
create table pair_settings (
  pair_id uuid primary key references pairs(id) on delete cascade,
  organization_name text,
  principal_name text,             -- supervisor's display name/credentials for reports & PDF
  brand_color text not null default '#1a3a6b',
  hour_target integer not null default 3000,
  location_field_label text not null default 'Location',  -- generic version of "Parish"
  job_types jsonb not null default '{}',   -- { "Job Type Name": ["checklist item", ...], ... }
  report_sections jsonb not null default '[]',
  updated_at timestamptz not null default now()
);

-- Logbook entries — mirrors the original logbook_entries table,
-- with pair_id added for tenant isolation.
create table logbook_entries (
  id uuid primary key default gen_random_uuid(),
  pair_id uuid not null references pairs(id) on delete cascade,
  entry_number integer,
  job_type text,
  date date not null,
  parish text,                     -- label shown to user comes from pair_settings.location_field_label
  title_ref text,
  deposited_plan text,
  strata_plan text,
  property_desc text,
  parcel_size text,
  selected_nature jsonb not null default '[]',
  student_notes text,
  hour_rows jsonb not null default '[]',
  total_hours numeric(8,2) not null default 0,
  student_name text,
  attachments jsonb not null default '[]',   -- array of storage paths
  principal_comments text,          -- supervisor-only field (per-entry review)
  degree text check (degree in ('Meets Expectations','Exceeds Expectations','Superior')),
  deleted_at timestamptz,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 6-month progress reports — one row per period per pair
create table progress_reports (
  id uuid primary key default gen_random_uuid(),
  pair_id uuid not null references pairs(id) on delete cascade,
  period_label text not null,
  candidate_comments text,             -- student-editable only
  candidate_signature_date date,       -- student-editable only
  principal_observations text,         -- supervisor-editable only
  principal_signature_date date,       -- supervisor-editable only
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- Row Level Security
-- ============================================================

alter table profiles enable row level security;
alter table pairs enable row level security;
alter table pair_settings enable row level security;
alter table logbook_entries enable row level security;
alter table progress_reports enable row level security;

create policy "read own profile" on profiles
  for select using (id = auth.uid());
create policy "insert own profile" on profiles
  for insert with check (id = auth.uid());
create policy "update own profile" on profiles
  for update using (id = auth.uid());

create policy "pair visible to members" on pairs
  for select using (supervisor_id = auth.uid() or student_id = auth.uid());
create policy "supervisor creates pair" on pairs
  for insert with check (supervisor_id = auth.uid());
create policy "supervisor updates pair" on pairs
  for update using (supervisor_id = auth.uid());
-- Students need to be able to redeem an invite code (which requires
-- updating student_id/status on a pair they don't own yet). Restrict
-- this narrowly: only allow claiming a currently-unclaimed pending pair.
create policy "student redeems invite" on pairs
  for update using (status = 'pending' and student_id is null)
  with check (student_id = auth.uid());

create policy "settings visible to pair" on pair_settings
  for select using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );
create policy "settings editable by pair" on pair_settings
  for all using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );

create policy "entries visible to pair" on logbook_entries
  for select using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );
create policy "student creates entries" on logbook_entries
  for insert with check (
    exists (select 1 from pairs p where p.id = pair_id and p.student_id = auth.uid())
  );
-- Both can update rows (student edits their own fields, supervisor
-- edits principal_comments/degree) — the trigger below enforces which
-- columns each side may actually change.
create policy "pair updates entries" on logbook_entries
  for update using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );

create policy "reports visible to pair" on progress_reports
  for select using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );
create policy "pair creates reports" on progress_reports
  for insert with check (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );
create policy "pair updates reports" on progress_reports
  for update using (
    exists (select 1 from pairs p where p.id = pair_id
            and (p.supervisor_id = auth.uid() or p.student_id = auth.uid()))
  );

-- ============================================================
-- Column-level enforcement
-- RLS is row-level only, so without this, either party could
-- technically overwrite the other's field via the API.
-- ============================================================

-- logbook_entries: student owns everything except principal_comments/degree
create or replace function enforce_entry_column_ownership()
returns trigger as $$
declare
  is_student boolean;
  is_supervisor boolean;
begin
  select (p.student_id = auth.uid()), (p.supervisor_id = auth.uid())
    into is_student, is_supervisor
    from pairs p where p.id = new.pair_id;

  if is_supervisor and not is_student then
    if new.job_type is distinct from old.job_type
       or new.date is distinct from old.date
       or new.parish is distinct from old.parish
       or new.title_ref is distinct from old.title_ref
       or new.deposited_plan is distinct from old.deposited_plan
       or new.strata_plan is distinct from old.strata_plan
       or new.property_desc is distinct from old.property_desc
       or new.parcel_size is distinct from old.parcel_size
       or new.selected_nature is distinct from old.selected_nature
       or new.student_notes is distinct from old.student_notes
       or new.hour_rows is distinct from old.hour_rows
       or new.total_hours is distinct from old.total_hours
       or new.attachments is distinct from old.attachments
       or new.deleted_at is distinct from old.deleted_at then
      raise exception 'Supervisors can only edit their comments and degree rating on an entry';
    end if;
  end if;

  if is_student and not is_supervisor then
    if new.principal_comments is distinct from old.principal_comments
       or new.degree is distinct from old.degree then
      raise exception 'Students cannot edit supervisor comments or the degree rating';
    end if;
  end if;

  return new;
end;
$$ language plpgsql security definer;

create trigger trg_enforce_entry_column_ownership
  before update on logbook_entries
  for each row
  execute function enforce_entry_column_ownership();

-- progress_reports: student owns candidate_* fields, supervisor owns principal_* fields
create or replace function enforce_report_column_ownership()
returns trigger as $$
declare
  is_student boolean;
  is_supervisor boolean;
begin
  select (p.student_id = auth.uid()), (p.supervisor_id = auth.uid())
    into is_student, is_supervisor
    from pairs p where p.id = new.pair_id;

  if is_student and not is_supervisor then
    if new.principal_observations is distinct from old.principal_observations
       or new.principal_signature_date is distinct from old.principal_signature_date then
      raise exception 'Students cannot edit supervisor observations or sign for the supervisor';
    end if;
  end if;

  if is_supervisor and not is_student then
    if new.candidate_comments is distinct from old.candidate_comments
       or new.candidate_signature_date is distinct from old.candidate_signature_date then
      raise exception 'Supervisors cannot edit candidate comments or sign for the student';
    end if;
  end if;

  return new;
end;
$$ language plpgsql security definer;

create trigger trg_enforce_report_column_ownership
  before update on progress_reports
  for each row
  execute function enforce_report_column_ownership();
