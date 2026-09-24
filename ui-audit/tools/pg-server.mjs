// A local Postgres for the site (PGlite over the wire protocol) with the chat tables created, so a
// check can save conversations without touching a hosted database (UI-026). In-memory: gone on exit.
//   node pg-server.mjs ../../orthodox-site/migrations/*.sql     (applied in the order given)
//   then run the site with POSTGRES_URL=postgres://postgres:postgres@localhost:5433/postgres
// Needs @electric-sql/pglite and @electric-sql/pglite-socket next to this script.
import fs from "node:fs";
import { PGlite } from "@electric-sql/pglite";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";

const db = await PGlite.create();
for (const file of process.argv.slice(2)) await db.exec(fs.readFileSync(file, "utf8"));
const server = new PGLiteSocketServer({ db, port: 5433, host: "127.0.0.1", maxConnections: 20 });
await server.start();
console.log("pglite listening on 5433");
