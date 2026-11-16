import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema";

// Fail fast — a missing DATABASE_URL surfaces at boot, not mid-request.
if (!process.env.DATABASE_URL) {
  throw new Error(
    "DATABASE_URL environment variable is required for database connection",
  );
}

const sql = neon(process.env.DATABASE_URL, {
  fetchOptions: {
    timeout: 30000, // 30 second timeout for database queries
  },
});

const db = drizzle({
  schema,
  client: sql,
});

export default db;
