import "server-only";

import { Pool, PoolClient, QueryResult, QueryResultRow } from "pg";

declare global {
  var __orthodoxPgPool: Pool | undefined;
}

function getConnectionString() {
  return process.env.POSTGRES_URL || process.env.DATABASE_URL || "";
}

export function getDatabaseConfigError() {
  return "Chat storage is not configured. Set POSTGRES_URL or DATABASE_URL in orthodox-site/.env.local.";
}

function createPool() {
  const connectionString = getConnectionString();
  if (!connectionString) {
    throw new Error(getDatabaseConfigError());
  }

  const pool = new Pool({
    connectionString,
    ssl: connectionString.includes("localhost") ? false : { rejectUnauthorized: false },
  });
  // An idle connection the server drops (Neon suspending, a network blip) is removed from the
  // pool; without a listener its error would be unhandled and stop the process.
  pool.on("error", (error) => console.error("idle database connection lost", error.message));
  return pool;
}

// One pool per server process. It used to be kept only outside production, so a production server
// made a new pool, and a new connection, for every query (found in UI-032). The global also
// survives dev reloads.
function getPool() {
  globalThis.__orthodoxPgPool ??= createPool();
  return globalThis.__orthodoxPgPool;
}

export async function query<T extends QueryResultRow>(text: string, params: unknown[] = []) {
  return getPool().query<T>(text, params);
}

export async function withTransaction<T>(
  callback: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const result = await callback(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

export type DbQueryResult<T extends QueryResultRow> = QueryResult<T>;
