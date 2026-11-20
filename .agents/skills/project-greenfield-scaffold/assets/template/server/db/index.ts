import { neon } from "@neondatabase/serverless";
import { drizzle, type NeonHttpDatabase } from "drizzle-orm/neon-http";
import * as schema from "./schema";

/**
 * db is a lazy Proxy — the drizzle client builds on first property
 * access, not at import. This module sits in the transitive import
 * graph of every API route (auth adapter, guards, domain routers), so
 * throwing here on a missing DATABASE_URL would 500 the whole process —
 * including SSR pages and routes that never query. The error throws at
 * the first query instead: DB routes fail, everything else keeps
 * serving. Same contract as getRedis()/getResend().
 */
let client: NeonHttpDatabase<typeof schema> | null = null;

function getDb(): NeonHttpDatabase<typeof schema> {
  if (client) return client;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL environment variable is required for database connection",
    );
  }
  client = drizzle({
    schema,
    client: neon(url, {
      fetchOptions: {
        timeout: 30000, // 30 second timeout for database queries
      },
    }),
  });
  return client;
}

const db = new Proxy({} as NeonHttpDatabase<typeof schema>, {
  get(_target, prop) {
    const real = getDb();
    const value = real[prop as keyof typeof real];
    return typeof value === "function" ? value.bind(real) : value;
  },
});

export default db;
