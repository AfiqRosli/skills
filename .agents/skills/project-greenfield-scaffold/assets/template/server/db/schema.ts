import {
  pgTable,
  uuid,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

// @flag auth
// better-auth tables live in auth-schema.ts (better-auth CLI output
// shape) — re-exported here so drizzle-kit sees a single schema entry
// point and app code has one import site.
export * from "../../auth-schema";
// @endflag auth

/**
 * App tables. Add enums first (pgEnum), then tables, then relations.
 * Migrations: `bun run db:generate` → drizzle/ → `bun run db:migrate`.
 */
export const items = pgTable("items", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  description: text("description"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => /* @__PURE__ */ new Date())
    .notNull(),
});
