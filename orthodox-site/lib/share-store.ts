// Shared answers (UI-030): frozen snapshots of one question, answer and sources, at /s/<id>.
//
// A snapshot is built on the server from the stored message, never from text the browser sends,
// so a link on learnorthodoxy.net only ever shows an answer the site gave. It keeps no user
// identifier and no link to the conversation; the same content shared again reuses its snapshot.
// The database is passed in, so tests can run these against an in-process Postgres.

import { createHash, createHmac, randomBytes } from "node:crypto";
import type { SourceRef } from "./chat-types";

// Each query declares its row type; the constraint matches pg's QueryResultRow.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Row = Record<string, any>;

export type Executor = {
  query<T extends Row = Row>(text: string, params?: unknown[]): Promise<{ rows: T[] }>;
};

export type ShareLanguage = "en" | "ar";

export type SnapshotContent = {
  question: string;
  answer: string;
  sources: SourceRef[];
  language: ShareLanguage;
  corpusVersion: string | null;
  promptVersion: string | null;
  model: string | null;
  answeredAt: string | null;
  /** The day it was answered on the sharer's calendar, "YYYY-MM-DD" (UI-034). */
  answeredOn: string | null;
};

export type Snapshot = SnapshotContent & { id: string; createdAt: string };

const ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
const ID_LENGTH = 16; // 62^16 ≈ 2^95: not guessable, not enumerable
export const SHARE_ID_PATTERN = /^[0-9A-Za-z]{16}$/;

/** Creating links: at most this many requests per client in the window (UI-030). */
export const SHARE_RATE_LIMIT = 20;
export const SHARE_RATE_WINDOW_MINUTES = 10;

export function newShareId(): string {
  // Rejection sampling keeps every character equally likely.
  let id = "";
  while (id.length < ID_LENGTH) {
    for (const byte of randomBytes(ID_LENGTH * 2)) {
      if (byte < 248 && id.length < ID_LENGTH) id += ID_ALPHABET[byte % 62];
    }
  }
  return id;
}

/** Identifies the content, not who shared it: the same answer shared twice gets the same link. */
export function contentHash(content: Pick<SnapshotContent, "question" | "answer" | "sources" | "language">): string {
  return createHash("sha256")
    .update(JSON.stringify([content.question, content.answer, content.sources, content.language]))
    .digest("hex");
}

/** A keyed hash of the client's IP, for the rate limit only; the IP itself is never stored. */
export function ipHash(ip: string, secret: string): string {
  return createHmac("sha256", secret || "learn-orthodoxy-share").update(ip || "unknown").digest("hex");
}

/** A time zone name the runtime knows ("America/Los_Angeles"), or null. */
export function validTimeZone(value: unknown): string | null {
  if (typeof value !== "string" || !value || value.length > 64 || !/^[A-Za-z0-9_+\-/]+$/.test(value)) return null;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value });
    return value;
  } catch {
    return null;
  }
}

/** The calendar day ("YYYY-MM-DD") an instant falls on in a time zone; UTC when it has none. */
export function localDate(instant: string, timeZone: string | null): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timeZone || "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(instant));
  const part = (type: string) => parts.find((p) => p.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function languageOf(text: string): ShareLanguage {
  return /[؀-ۿ]/.test(text) ? "ar" : "en";
}

type MessageRow = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  sources: SourceRef[] | string;
  meta: Record<string, unknown> | string | null;
  sort_order: number;
  created_at: string | Date;
  title: string;
};

const parse = <T,>(value: T | string | null | undefined, fallback: T): T =>
  typeof value === "string" ? (JSON.parse(value) as T) : (value ?? fallback);

const iso = (value: string | Date | null | undefined) =>
  value == null ? null : value instanceof Date ? value.toISOString() : new Date(value).toISOString();

/**
 * The answer with this message ID, if it belongs to one of this visitor's conversations, with the
 * question asked just before it. Null for anything else (another visitor's message, a message not
 * saved, a question rather than an answer).
 */
export async function loadShareableAnswer(
  db: Executor,
  sessionId: string,
  messageId: string,
  timeZone: string | null = null
): Promise<SnapshotContent | null> {
  const { rows } = await db.query<MessageRow>(
    `
      select m.id, m.conversation_id, m.role, m.content, m.sources, m.meta, m.sort_order, m.created_at, c.title
      from chat_messages m
      join chat_conversations c on c.id = m.conversation_id
      where m.id = $1 and c.session_id = $2 and c.archived_at is null
      limit 1
    `,
    [messageId, sessionId]
  );
  const message = rows[0];
  if (!message || message.role !== "assistant" || !message.content.trim()) return null;

  const asked = await db.query<{ content: string }>(
    `
      select content from chat_messages
      where conversation_id = $1 and role = 'user' and sort_order < $2
      order by sort_order desc
      limit 1
    `,
    [message.conversation_id, message.sort_order]
  );
  const question = (asked.rows[0]?.content || message.title || "").trim();
  const meta = parse<Record<string, unknown>>(message.meta, {});
  const text = (key: string) => (typeof meta[key] === "string" ? (meta[key] as string) : null);
  const answeredAt = iso(message.created_at);
  return {
    question,
    answer: message.content,
    sources: parse<SourceRef[]>(message.sources, []),
    language: languageOf(`${question} ${message.content}`),
    corpusVersion: text("corpus_version"),
    promptVersion: text("prompt_version"),
    model: text("model"),
    answeredAt,
    // The date the page shows is fixed now, as the sharer's calendar has it, not by each reader.
    answeredOn: answeredAt ? localDate(answeredAt, timeZone) : null,
  };
}

/** Records this request and says whether the client is still within the limit. */
export async function allowShareRequest(db: Executor, clientHash: string): Promise<boolean> {
  // Old rows are cleared as we go; nothing is kept longer than about an hour.
  await db.query("delete from share_requests where created_at < now() - interval '1 hour'");
  const { rows } = await db.query<{ count: string | number }>(
    `select count(*) as count from share_requests
     where ip_hash = $1 and created_at > now() - ($2 || ' minutes')::interval`,
    [clientHash, String(SHARE_RATE_WINDOW_MINUTES)]
  );
  if (Number(rows[0]?.count ?? 0) >= SHARE_RATE_LIMIT) return false;
  await db.query("insert into share_requests (ip_hash) values ($1)", [clientHash]);
  return true;
}

/** Stores the snapshot, or finds the one already made for the same content. */
export async function saveSnapshot(db: Executor, content: SnapshotContent): Promise<{ id: string; reused: boolean }> {
  const hash = contentHash(content);
  const inserted = await db.query<{ id: string }>(
    `
      insert into shared_answers
        (id, content_hash, question, answer, sources, language, corpus_version, prompt_version, model, answered_at, answered_on)
      values ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11::date)
      on conflict (content_hash) do nothing
      returning id
    `,
    [
      newShareId(),
      hash,
      content.question,
      content.answer,
      JSON.stringify(content.sources),
      content.language,
      content.corpusVersion,
      content.promptVersion,
      content.model,
      content.answeredAt,
      content.answeredOn,
    ]
  );
  if (inserted.rows[0]) return { id: inserted.rows[0].id, reused: false };
  const existing = await db.query<{ id: string }>("select id from shared_answers where content_hash = $1", [hash]);
  return { id: existing.rows[0].id, reused: true };
}

type SnapshotRow = {
  id: string;
  question: string;
  answer: string;
  sources: SourceRef[] | string;
  language: ShareLanguage;
  corpus_version: string | null;
  prompt_version: string | null;
  model: string | null;
  answered_at: string | Date | null;
  answered_on: string | null;
  created_at: string | Date;
};

export async function getSnapshot(db: Executor, id: string): Promise<Snapshot | null> {
  if (!SHARE_ID_PATTERN.test(id)) return null;
  const { rows } = await db.query<SnapshotRow>(
    `select id, question, answer, sources, language, corpus_version, prompt_version, model, answered_at,
            answered_on::text as answered_on, created_at
     from shared_answers where id = $1`,
    [id]
  );
  const row = rows[0];
  if (!row) return null;
  return {
    id: row.id,
    question: row.question,
    answer: row.answer,
    sources: parse<SourceRef[]>(row.sources, []),
    language: row.language,
    corpusVersion: row.corpus_version,
    promptVersion: row.prompt_version,
    model: row.model,
    answeredAt: iso(row.answered_at),
    answeredOn: row.answered_on,
    createdAt: iso(row.created_at) as string,
  };
}
