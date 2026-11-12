import { Elysia, t } from "elysia";
import { NotFoundError } from "./errors";

/**
 * Canonical domain router. One file per domain, prefix WITHOUT /api —
 * nuxt-elysia prepends /api automatically (see nuxt.config.ts
 * nuxtElysia.path). Register new routers in server/api.ts.
 *
 * Request validation lives on the route (t.Object schemas). Errors use
 * the ApiError family from ./errors so clients can branch on `code`.
 */
export const createItemSchema = t.Object({
  name: t.String({ minLength: 1, maxLength: 100 }),
  description: t.Optional(t.String({ maxLength: 500 })),
});

export const updateItemSchema = t.Partial(createItemSchema);

export const itemParamsSchema = t.Object({
  id: t.String({ format: "uuid" }),
});

export default new Elysia({ prefix: "/example" })
  .get("/", async () => {
    // Replace with: await db.select().from(items)
    return { items: [] };
  })
  .get("/:id", async ({ params: _params }) => {
    // Replace with a real lookup; throw NotFoundError on a miss.
    const item = null;
    if (!item) {
      throw new NotFoundError("Item not found");
    }
    return item;
  })
  .post("/", async ({ body }) => {
    // `body` is already validated against createItemSchema below.
    return { item: body, created: true };
  }, {
    body: createItemSchema,
  })
  .patch("/:id", async ({ params, body }) => {
    return { id: params.id, updates: body };
  }, {
    params: itemParamsSchema,
    body: updateItemSchema,
  })
  .delete("/:id", async ({ params }) => {
    return { id: params.id, deleted: true };
  }, {
    params: itemParamsSchema,
  });
