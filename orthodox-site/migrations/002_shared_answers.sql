-- Shared answers (UI-030): a frozen copy of one question, its answer and sources, reachable at
-- /s/<id>. No user identifiers: nothing links a snapshot to a visitor or a conversation. The same
-- content shared again reuses its snapshot (content_hash).
create table if not exists shared_answers (
  id text primary key,                -- 16 random base-62 characters (~95 bits)
  content_hash text not null unique,  -- sha-256 of question, answer, sources and language
  question text not null,
  answer text not null,
  sources jsonb not null default '[]'::jsonb,
  language text not null check (language in ('en', 'ar')),
  corpus_version text null,
  prompt_version text null,
  model text null,
  answered_at timestamptz null,       -- when the answer was given
  answered_on date null,              -- that day on the sharer's calendar (their time zone when sharing); shown on the page
  created_at timestamptz not null default now()
);

-- Share requests per client, for the rate limit only: a keyed hash of the IP, kept about an hour.
create table if not exists share_requests (
  ip_hash text not null,
  created_at timestamptz not null default now()
);

create index if not exists share_requests_ip_time_idx
  on share_requests (ip_hash, created_at desc);

-- What produced each answer (corpus and prompt version, model), as the backend reports it.
alter table chat_messages add column if not exists meta jsonb not null default '{}'::jsonb;
