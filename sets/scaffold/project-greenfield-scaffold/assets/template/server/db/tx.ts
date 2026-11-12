/**
 * Transaction-capable db client.
 *
 * The default `server/db` client is drizzle-orm/neon-http: stateless, one
 * HTTP round-trip per query, and deliberately no `db.transaction()`
 * support. Any write that must be all-or-nothing can't be made safe by
 * operation ordering alone — so this module provides a `pg`-backed
 * NodePgDatabase for the paths that need real transactions.
 *
 * Lifecycle is per-invocation: connect → transaction → end. No pool —
 * callers are single user-action endpoints, not hot paths, and a Pool
 * buys lifecycle management for zero gain on serverless functions.
 *
 * Everything else keeps using the neon-http `db` — do NOT route normal
 * traffic through here.
 */

import { Client } from "pg";
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import * as schema from "./schema";

/** The transaction handle passed to `withDbTx` callbacks — drizzle-typed. */
export type DbTx = Parameters<
  Parameters<NodePgDatabase<typeof schema>["transaction"]>[0]
>[0];

/**
 * Run `fn` inside a real Postgres transaction on a dedicated connection.
 * Any throw rolls the whole thing back; the client is always ended.
 * DATABASE_URL resolves lazily per call so specs can import this module
 * without a database.
 */
export async function withDbTx<T>(
  fn: (_tx: DbTx) => Promise<T>,
): Promise<T> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL environment variable is required for database connection",
    );
  }
  const client = new Client({ connectionString });
  try {
    await client.connect();
    const txDb = drizzle(client, { schema });
    return await txDb.transaction(fn);
  }
  finally {
    // end() runs even when connect() failed; its own failure must not
    // mask the real error that brought us here.
    await client.end().catch(() => {});
  }
}
