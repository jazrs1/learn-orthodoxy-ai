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

  return new Pool({
    connectionString,
    ssl: connectionString.includes("localhost") ? false : { rejectUnauthorized: false },
  });
}

function getPool() {
  if (globalThis.__orthodoxPgPool) {
    return globalThis.__orthodoxPgPool;
  }

  const pool = createPool();
  if (process.env.NODE_ENV !== "production") {
    globalThis.__orthodoxPgPool = pool;
  }
  return pool;
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
