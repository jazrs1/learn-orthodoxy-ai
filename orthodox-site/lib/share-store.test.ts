// Share snapshots against a real Postgres (PGlite, in process) with the site's migrations (UI-032).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, before, beforeEach, describe, it } from "node:test";
import { PGlite } from "@electric-sql/pglite";
import {
  SHARE_ID_PATTERN,
  SHARE_RATE_LIMIT,
  allowShareRequest,
  getSnapshot,
  ipHash,
  loadShareableAnswer,
  localDate,
  newShareId,
  saveSnapshot,
  validTimeZone,
  type Executor,
} from "./share-store.ts";

let pg: PGlite;
let db: Executor;

const migration = (name: string) => readFileSync(new URL(`../migrations/${name}`, import.meta.url), "utf8");

const SOURCES = [
  { n: 1, pdf: "catechism1.pdf", page: 31, pages: "31", title: "What is prayer?" },
  { n: 2, pdf: "saints2.pdf", page: 406, pages: "406", entry: "St. Anthony the Great" },
];

async function seedConversation(sessionId: string, conversationId: string, turns: [string, string][], archived = false) {
  await pg.query("insert into chat_conversations (id, session_id, title, archived_at) values ($1, $2, $3, $4)", [
    conversationId,
    sessionId,
    turns[0][0],
    archived ? new Date() : null,
  ]);
  let order = 0;
  for (const [question, answer] of turns) {
    await pg.query(
      "insert into chat_messages (id, conversation_id, role, content, sort_order) values ($1, $2, 'user', $3, $4)",
      [`${conversationId}-q${order}`, conversationId, question, order]
    );
    await pg.query(
      `insert into chat_messages (id, conversation_id, role, content, sources, meta, sort_order)
       values ($1, $2, 'assistant', $3, $4::jsonb, $5::jsonb, $6)`,
      [
        `${conversationId}-a${order + 1}`,
        conversationId,
        answer,
        JSON.stringify(SOURCES),
        JSON.stringify({ corpus_version: "v2-test", prompt_version: "p7", model: "gpt-test" }),
        order + 1,
      ]
    );
    order += 2;
  }
}

const count = async (table: string) => Number((await pg.query<{ n: number }>(`select count(*)::int as n from ${table}`)).rows[0].n);

before(async () => {
  pg = await PGlite.create();
  await pg.exec(migration("001_create_chat_tables.sql"));
  await pg.exec(migration("002_shared_answers.sql"));
  db = { query: (text, params) => pg.query(text, params) } as Executor;
});

after(async () => {
  await pg.close();
});

beforeEach(async () => {
  await pg.exec("delete from shared_answers; delete from share_requests; delete from chat_conversations;");
});

describe("share snapshots (UI-030)", () => {
  it("takes the answer and the question before it from the visitor's own conversation", async () => {
    await seedConversation("session-a", "c1", [
      ["What is prayer?", "Prayer is **speaking** with God [1]."],
      ["Why fast?", "Fasting trains the will [2]."],
    ]);
    const content = await loadShareableAnswer(db, "session-a", "c1-a3");
    assert.ok(content);
    assert.equal(content.question, "Why fast?");
    assert.equal(content.answer, "Fasting trains the will [2].");
    assert.deepEqual(content.sources, SOURCES);
    assert.equal(content.language, "en");
    assert.equal(content.corpusVersion, "v2-test");
    assert.equal(content.promptVersion, "p7");
    assert.equal(content.model, "gpt-test");
    assert.match(content.answeredAt ?? "", /^\d{4}-\d\d-\d\dT/);
  });

  it("refuses another visitor's answer, a question, an unknown ID and an archived conversation", async () => {
    await seedConversation("session-a", "c1", [["What is prayer?", "Prayer is speaking with God [1]."]]);
    await seedConversation("session-a", "c2", [["Who was St. Anthony?", "The father of monks [2]."]], true);
    assert.equal(await loadShareableAnswer(db, "session-b", "c1-a1"), null);
    assert.equal(await loadShareableAnswer(db, "session-a", "c1-q0"), null);
    assert.equal(await loadShareableAnswer(db, "session-a", "nope"), null);
    assert.equal(await loadShareableAnswer(db, "session-a", "c2-a1"), null);
  });

  it("marks an Arabic answer as Arabic", async () => {
    await seedConversation("session-a", "c1", [["ما هي الصلاة؟", "الصلاة هي صلة الإنسان بالله [1]."]]);
    assert.equal((await loadShareableAnswer(db, "session-a", "c1-a1"))?.language, "ar");
  });

  it("creates a snapshot with a random ID and no user identifiers", async () => {
    await seedConversation("session-a", "c1", [["What is prayer?", "Prayer is speaking with God [1]."]]);
    const content = await loadShareableAnswer(db, "session-a", "c1-a1");
    assert.ok(content);
    const { id, reused } = await saveSnapshot(db, content);
    assert.equal(reused, false);
    assert.match(id, SHARE_ID_PATTERN);

    const snapshot = await getSnapshot(db, id);
    assert.ok(snapshot);
    assert.equal(snapshot.question, "What is prayer?");
    assert.equal(snapshot.answer, "Prayer is speaking with God [1].");
    assert.deepEqual(snapshot.sources, SOURCES);
    assert.equal(snapshot.language, "en");
    assert.equal(snapshot.corpusVersion, "v2-test");
    assert.equal(snapshot.answeredAt, content.answeredAt);
    assert.equal(snapshot.answeredOn, content.answeredOn);

    const columns = (
      await pg.query<{ column_name: string }>(
        "select column_name from information_schema.columns where table_name = 'shared_answers'"
      )
    ).rows.map((row) => row.column_name);
    for (const column of columns) assert.doesNotMatch(column, /session|user|conversation|message|ip/);
    const stored = JSON.stringify((await pg.query("select * from shared_answers")).rows);
    assert.doesNotMatch(stored, /session-a|c1-a1|"c1"/);
  });

  it("reuses the snapshot when the same answer is shared again, from any session", async () => {
    await seedConversation("session-a", "c1", [["What is prayer?", "Prayer is speaking with God [1]."]]);
    await seedConversation("session-b", "c2", [["What is prayer?", "Prayer is speaking with God [1]."]]);
    const first = await saveSnapshot(db, (await loadShareableAnswer(db, "session-a", "c1-a1"))!);
    const again = await saveSnapshot(db, (await loadShareableAnswer(db, "session-a", "c1-a1"))!);
    const other = await saveSnapshot(db, (await loadShareableAnswer(db, "session-b", "c2-a1"))!);
    assert.deepEqual(again, { id: first.id, reused: true });
    assert.deepEqual(other, { id: first.id, reused: true });
    assert.equal(await count("shared_answers"), 1);
  });

  it("makes a new snapshot when the content differs", async () => {
    await seedConversation("session-a", "c1", [
      ["What is prayer?", "Prayer is speaking with God [1]."],
      ["What is prayer?", "Prayer is the breath of the soul [1]."],
    ]);
    const first = await saveSnapshot(db, (await loadShareableAnswer(db, "session-a", "c1-a1"))!);
    const second = await saveSnapshot(db, (await loadShareableAnswer(db, "session-a", "c1-a3"))!);
    assert.notEqual(first.id, second.id);
    assert.equal(second.reused, false);
  });

  it("finds nothing for an unknown or malformed ID", async () => {
    assert.equal(await getSnapshot(db, newShareId()), null);
    assert.equal(await getSnapshot(db, "short"), null);
    assert.equal(await getSnapshot(db, "' or 1=1 --AAAAA"), null);
  });

  it("makes IDs of 16 base-62 characters that don't repeat", () => {
    const ids = new Set(Array.from({ length: 2000 }, () => newShareId()));
    assert.equal(ids.size, 2000);
    for (const id of ids) assert.match(id, SHARE_ID_PATTERN);
  });
});

describe("the sharer's date (UI-034)", () => {
  it("dates the answer by the sharer's time zone and keeps that date", async () => {
    await seedConversation("session-a", "c1", [["What is prayer?", "Prayer is speaking with God [1]."]]);
    await pg.query("update chat_messages set created_at = '2026-09-24T03:04:00Z' where id = 'c1-a1'");
    const inLosAngeles = await loadShareableAnswer(db, "session-a", "c1-a1", "America/Los_Angeles");
    assert.equal(inLosAngeles?.answeredOn, "2026-09-23");
    assert.equal((await loadShareableAnswer(db, "session-a", "c1-a1", "Africa/Cairo"))?.answeredOn, "2026-09-24");
    assert.equal((await loadShareableAnswer(db, "session-a", "c1-a1"))?.answeredOn, "2026-09-24");

    const { id } = await saveSnapshot(db, inLosAngeles!);
    assert.equal((await getSnapshot(db, id))?.answeredOn, "2026-09-23");
    // Shared again from Cairo: the same snapshot, still with the first sharer's date.
    const again = await saveSnapshot(db, (await loadShareableAnswer(db, "session-a", "c1-a1", "Africa/Cairo"))!);
    assert.deepEqual(again, { id, reused: true });
    assert.equal((await getSnapshot(db, id))?.answeredOn, "2026-09-23");
  });

  it("stores the date only, not the time zone", async () => {
    const columns = (
      await pg.query<{ column_name: string; data_type: string }>(
        "select column_name, data_type from information_schema.columns where table_name = 'shared_answers'"
      )
    ).rows;
    assert.ok(columns.some((c) => c.column_name === "answered_on" && c.data_type === "date"));
    assert.ok(!columns.some((c) => /zone|tz/.test(c.column_name)));
  });

  it("accepts real time zone names only", () => {
    assert.equal(validTimeZone("America/Los_Angeles"), "America/Los_Angeles");
    assert.equal(validTimeZone("Africa/Cairo"), "Africa/Cairo");
    assert.equal(validTimeZone("UTC"), "UTC");
    for (const bad of ["Mars/Olympus", "", "a,b", "x".repeat(65), 42, null]) assert.equal(validTimeZone(bad), null);
    assert.equal(localDate("2026-12-31T23:30:00Z", "Asia/Tokyo"), "2027-01-01");
    assert.equal(localDate("2026-12-31T23:30:00Z", null), "2026-12-31");
  });
});

describe("share rate limit (UI-030)", () => {
  it(`allows ${SHARE_RATE_LIMIT} links per client in the window, then refuses`, async () => {
    const client = ipHash("203.0.113.7", "secret");
    for (let i = 0; i < SHARE_RATE_LIMIT; i += 1) assert.equal(await allowShareRequest(db, client), true);
    assert.equal(await allowShareRequest(db, client), false);
    assert.equal(await allowShareRequest(db, ipHash("203.0.113.8", "secret")), true);
  });

  it("forgets requests outside the window, and deletes them after an hour", async () => {
    const client = ipHash("203.0.113.7", "secret");
    await pg.query(
      "insert into share_requests (ip_hash, created_at) select $1, now() - interval '11 minutes' from generate_series(1, $2::int)",
      [client, SHARE_RATE_LIMIT]
    );
    await pg.query("insert into share_requests (ip_hash, created_at) values ($1, now() - interval '2 hours')", [client]);
    assert.equal(await allowShareRequest(db, client), true);
    assert.equal(await count("share_requests"), SHARE_RATE_LIMIT + 1);
  });

  it("stores a keyed hash, never the IP", async () => {
    await allowShareRequest(db, ipHash("203.0.113.7", "secret"));
    const stored = JSON.stringify((await pg.query("select * from share_requests")).rows);
    assert.doesNotMatch(stored, /203\.0\.113\.7/);
    assert.notEqual(ipHash("203.0.113.7", "secret"), ipHash("203.0.113.7", "other"));
  });
});
