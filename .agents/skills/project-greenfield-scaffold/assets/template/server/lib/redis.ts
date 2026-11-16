import { Redis } from "ioredis";
import { logger } from "@/utils/logger";

/**
 * Shared Redis client (rate limiting, caching, ephemeral state).
 * REDIS_URL resolves lazily — modules can be imported in specs and dev
 * tooling without a live Redis. maxRetriesPerRequest stays low: a down
 * Redis should degrade fast (callers treat failures as pass-through),
 * not hang the request.
 */
let client: Redis | null = null;

export function getRedis(): Redis | null {
  if (!process.env.REDIS_URL) return null;
  if (!client) {
    client = new Redis(process.env.REDIS_URL, {
      maxRetriesPerRequest: 1,
      lazyConnect: true,
    });
    client.on("error", (err) => {
      logger.warn("Redis error", { message: err.message });
    });
  }
  return client;
}
