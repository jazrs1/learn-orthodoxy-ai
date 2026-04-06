create table if not exists chat_conversations (
  id text primary key,
  session_id text not null,
  title text not null default 'New Chat',
  archived_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists chat_conversations_session_idx
  on chat_conversations (session_id, updated_at desc);

create index if not exists chat_conversations_active_idx
  on chat_conversations (session_id, updated_at desc)
  where archived_at is null;

create table if not exists chat_messages (
  id text primary key,
  conversation_id text not null references chat_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  entities jsonb not null default '[]'::jsonb,
  options jsonb not null default '[]'::jsonb,
  sources jsonb not null default '[]'::jsonb,
  sort_order integer not null,
  created_at timestamptz not null default now()
);

create unique index if not exists chat_messages_conversation_sort_idx
  on chat_messages (conversation_id, sort_order);

create table if not exists chat_migrations (
  name text primary key,
  created_at timestamptz not null default now()
);
