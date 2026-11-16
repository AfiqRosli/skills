# API Development with Elysia

## Overview

This document provides comprehensive patterns and best practices for API development using Elysia in the application. It covers route organization, schema validation, error handling, middleware, database integration, and testing patterns to create robust, type-safe, and maintainable APIs.

## Route Organization

### Basic Route Structure

```typescript
// server/api/users/routes.ts
export const userRoutes = new Elysia({ prefix: "/users" })
  .get("/", async () => {
    const users = await db.query.users.findMany();
    return users;
  })
  .get("/:id", async ({ params }) => {
    const user = await db.query.users.findById(params.id);
    if (!user) {
      throw new NotFoundError("User not found");
    }
    return user;
  })
  .post("/", async ({ body }) => {
    const newUser = await db.insert(users).values(body).returning();
    return newUser;
  })
  .patch("/:id", async ({ params, body }) => {
    const updatedUser = await db
      .update(users)
      .set(body)
      .where(eq(users.id, params.id))
      .returning();

    if (!updatedUser.length) {
      throw new NotFoundError("User not found");
    }

    return updatedUser[0];
  })
  .delete("/:id", async ({ params }) => {
    const deletedUser = await db
      .delete(users)
      .where(eq(users.id, params.id))
      .returning();

    if (!deletedUser.length) {
      throw new NotFoundError("User not found");
    }

    return { success: true };
  });
```

### Nested Routes

```typescript
// server/api/users/routes.ts
export const userRoutes = new Elysia({ prefix: "/users" })
  .get("/", async () => {
    return await db.query.users.findMany();
  })
  .get("/:id", async ({ params }) => {
    return await db.query.users.findById(params.id);
  })
  .get("/:id/profile", async ({ params }) => {
    const user = await db.query.users.findById(params.id);
    if (!user) {
      throw new NotFoundError("User not found");
    }
    return {
      id: user.id,
      name: user.name,
      email: user.email,
      profile: {
        bio: user.bio,
        avatar: user.avatar,
      },
    };
  })
  .post("/:id/orders", async ({ params, body }) => {
    // Create order for specific user
    const order = await db.insert(orders).values({
      ...body,
      userId: params.id,
    }).returning();
    return order;
  });
```

## Schema Validation

### Request Schema Definition

```typescript
// server/api/users/schemas.ts
import { t } from "elysia";

export const createUserSchema = t.Object({
  name: t.String({ minLength: 1, maxLength: 100 }),
  email: t.String({ format: "email" }),
  role: t.Enum(["admin", "user", "guest"]),
  preferences: t.Optional(
    t.Object({
      theme: t.Enum(["light", "dark", "auto"]),
      notifications: t.Boolean(),
    }),
  ),
});

export const updateUserSchema = t.Partial(createUserSchema);

export const userParamsSchema = t.Object({
  id: t.String({ format: "uuid" }),
});

export const loginSchema = t.Object({
  email: t.String({ format: "email" }),
  password: t.String({ minLength: 8 }),
});

export const passwordResetSchema = t.Object({
  token: t.String(),
  newPassword: t.String({ minLength: 8 }),
  confirmPassword: t.String(),
});
```

### Schema Validation in Routes

```typescript
// server/api/users/routes.ts
import { createUserSchema, updateUserSchema, userParamsSchema } from "./schemas";

export const userRoutes = new Elysia({ prefix: "/users" })
  .post("/", ({ body }) => {
    // Schema validation
    const validatedUser = createUserSchema.parse(body);
    
    // Process validated data
    const newUser = await db.insert(users).values(validatedUser).returning();
    return newUser;
  })
  .patch("/:id", ({ params, body }) => {
    // Validate params
    const { id } = userParamsSchema.parse(params);
    
    // Validate body
    const validatedUpdates = updateUserSchema.parse(body);
    
    const updatedUser = await db
      .update(users)
      .set(validatedUpdates)
      .where(eq(users.id, id))
      .returning();

    if (!updatedUser.length) {
      throw new NotFoundError("User not found");
    }

    return updatedUser[0];
  });
```

### Custom Validators

```typescript
// server/api/users/validators.ts
import { t } from "elysia";

export const passwordValidator = t.String({
  minLength: 8,
  pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/,
});

export const strongPasswordSchema = t.Object({
  password: passwordValidator,
  confirmPassword: t.String(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});
```

## Error Handling

### Custom Error Classes

```typescript
// server/api/errors.ts
export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number = 500,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NotFoundError extends ApiError {
  constructor(message: string = "Resource not found") {
    super(message, 404, "NOT_FOUND");
  }
}

export class ValidationError extends ApiError {
  constructor(
    message: string,
    public field?: string,
  ) {
    super(message, 400, "VALIDATION_ERROR");
  }
}

export class AuthenticationError extends ApiError {
  constructor(
    message: string = "Authentication failed",
    public code: "INVALID_CREDENTIALS" | "TOKEN_EXPIRED" | "INSUFFICIENT_PERMISSIONS" = "INVALID_CREDENTIALS",
  ) {
    super(message, 401, code);
  }
}

export class AuthorizationError extends ApiError {
  constructor(message: string = "Insufficient permissions") {
    super(message, 403, "INSUFFICIENT_PERMISSIONS");
  }
}
```

### Global Error Handler

```typescript
// server/api/middleware/error-handler.ts
import { Elysia } from "elysia";
import { ApiError } from "../errors";

export const errorHandler = new Elysia().onError(({ error, set }) => {
  if (error instanceof ApiError) {
    set.status = error.statusCode;
    return {
      success: false,
      error: {
        message: error.message,
        code: error.code,
        field: error instanceof ValidationError ? error.field : undefined,
        timestamp: new Date().toISOString(),
      },
    };
  }

  // Default error response
  set.status = 500;
  return {
    success: false,
    error: {
      message: "Internal server error",
      code: "INTERNAL_ERROR",
      timestamp: new Date().toISOString(),
    },
  };
});

// Usage in main API file
// server/api.ts
export default () =>
  new Elysia()
    .use(errorHandler)
    .use(userRoutes)
    .use(authRoutes);
```

### Error Response Format

```typescript
// Consistent error response structure
interface ErrorResponse {
  success: false;
  error: {
    message: string;
    code?: string;
    field?: string;
    timestamp: string;
    details?: any;
  };
}

// Success response structure
interface SuccessResponse<T> {
  success: true;
  data: T;
  message?: string;
  timestamp: string;
}
```

## Nuxt-Elysia Routing Pattern

### Automatic API Prefix

**Important**: Do NOT prepend `/api` to Elysia route definitions. The nuxt-elysia module automatically handles this.

#### Configuration

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  modules: [
    "nuxt-elysia",
    // ... other modules
  ],
  nuxtElysia: {
    module: "~/server/api.ts",
    path: "/api", // This automatically prepends /api to ALL Elysia routes
  },
});
```

#### Route Definition Pattern

```typescript
// server/user.routes.ts - CORRECT
export const userRouter = new Elysia({ prefix: "/user" }).get(
  "/profile",
  () => ({ data: "profile" }),
);
// Becomes accessible at: /api/user/profile

// server/user.routes.ts - INCORRECT
export const userRouter = new Elysia({ prefix: "/api/user" }).get(
  "/profile",
  () => ({ data: "profile" }),
);
// Becomes accessible at: /api/api/user/profile (WRONG!)
```

### Frontend API Calls

```typescript
// Frontend calls always include /api prefix
const profile = await $fetch("/api/user/profile"); // CORRECT
const users = await $fetch("/api/users"); // CORRECT
```

## Store-Based API Calls

### Centralized API Pattern

**All API calls must be made through Pinia stores, not directly in components or composables.** This ensures:

- Centralized state management
- Consistent error handling
- Proper loading states
- Cache management
- Reusable business logic

### Store API Pattern

```typescript
// ❌ Bad - Direct API call in component
<script setup lang="ts">
const users = ref([]);
const loading = ref(false);

const fetchUsers = async () => {
  loading.value = true;
  try {
    const { $api } = useNuxtApp();
    users.value = await $api.get('/users');
  } finally {
    loading.value = false;
  }
};
</script>

// ✅ Good - API call through store
<script setup lang="ts">
const userStore = useUserStore();
const { users, loading } = storeToRefs(userStore);

onMounted(() => {
  userStore.fetchUsers();
});
</script>
```

### Store Implementation

```typescript
// stores/UserStore.ts
export const useUserStore = defineStore('user', () => {
  // State
  const users = ref<User[]>([]);
  const loading = ref(false);
  const error = ref<Error | null>(null);

  // Actions
  const fetchUsers = async () => {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const data = await $api.get<User[]>('/users');
      users.value = data;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error('Failed to fetch users');
      throw error.value;
    } finally {
      loading.value = false;
    }
  };

  const createUser = async (userData: CreateUserRequest) => {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const newUser = await $api.post<User>('/users', userData);
      users.value.push(newUser);
      return newUser;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error('Failed to create user');
      throw error.value;
    } finally {
      loading.value = false;
    }
  };

  return {
    users,
    loading,
    error,
    fetchUsers,
    createUser,
  };
});
```

## Middleware and Hooks

### Authentication Middleware

```typescript
// server/api/middleware/auth.ts
import { Elysia } from "elysia";
import { jwt } from "jsonwebtoken";

export const authMiddleware = new Elysia()
  .derive(({ request, cookie, set }) => {
    const token = request.headers.get("authorization")?.replace("Bearer ", "");
    
    if (!token) {
      set.status = 401;
      return {
        user: null,
        isAuthenticated: false,
      };
    }

    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET!);
      return {
        user: decoded,
        isAuthenticated: true,
      };
    } catch (error) {
      set.status = 401);
      return {
        user: null,
        isAuthenticated: false,
        error: "Invalid token",
      };
    }
  });

// Usage
export const protectedRoutes = new Elysia()
  .use(authMiddleware)
  .get("/profile", ({ user }) => {
    if (!user.isAuthenticated) {
      throw new AuthenticationError("Authentication required");
    }
    return user.user;
  });
```

### Request Logging

```typescript
// server/api/middleware/logger.ts
import { Elysia } from "elysia";

export const loggerMiddleware = new Elysia()
  .onBeforeHandle(({ request, set }) => {
    console.log(`${request.method} ${request.url}`, {
      headers: Object.fromEntries(request.headers.entries()),
      timestamp: new Date().toISOString(),
    });
  })
  .onAfterHandle(({ request, set }) => {
    console.log(`${request.method} ${request.url} completed`, {
      timestamp: new Date().toISOString(),
    });
  });

// Usage
export const userRoutes = new Elysia({ prefix: "/users" })
  .use(loggerMiddleware)
  .get("/", async () => {
    return await db.query.users.findMany();
  });
```

### CORS Configuration

```typescript
// server/api/middleware/cors.ts
import { Elysia } from "elysia";

export const corsMiddleware = new Elysia()
  .onBeforeHandle(({ set }) => {
    set.headers["Access-Control-Allow-Origin"] = process.env.ALLOWED_ORIGINS || "*";
    set.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS";
    set.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization";
    
    if (request.method === "OPTIONS") {
      set.status = 200;
      return new Response(null, {
        headers: set.headers,
      });
    }
  });

// Usage
export const api = new Elysia()
  .use(corsMiddleware)
  .use(userRoutes);
```

## Database Integration

### Drizzle ORM Integration

```typescript
// server/db/index.ts
import { drizzle } from "drizzle-orm/postgres-js";
import { pool } from "./connection";
import * as schema from "./schema";

export const db = drizzle(pool, { schema });

// server/api/users/routes.ts
import { db } from "@/server/db";
import { users } from "@/server/db/schema";
import { eq } from "drizzle-orm";

export const userRoutes = new Elysia({ prefix: "/users" })
  .get("/", async () => {
    return await db.select().from(users);
  })
  .get("/:id", async ({ params }) => {
    const result = await db
      .select()
      .from(users)
      .where(eq(users.id, params.id))
      .limit(1);
    return result[0] || null;
  })
  .post("/", async ({ body }) => {
    const newUser = await db
      .insert(users)
      .values(body)
      .returning();
    return newUser[0];
  });
```

### Transaction Support

```typescript
// server/api/orders/routes.ts
export const orderRoutes = new Elysia({ prefix: "/orders" })
  .post("/", async ({ body }) => {
    return await db.transaction(async (tx) => {
      // Create order
      const order = await tx
        .insert(orders)
        .values(body)
        .returning();
      
      // Update inventory
      for (const item of body.items) {
        await tx
          .update(inventory)
          .set({ 
            quantity: sql`${inventory.quantity} - ${item.quantity}` 
          })
          .where(eq(inventory.productId, item.productId));
      }
      
      // Create audit log
      await tx.insert(auditLogs).values({
        action: "order_created",
        orderId: order[0].id,
        timestamp: new Date(),
      });
      
      return order[0];
    });
  });
```

## API Documentation

### OpenAPI Integration

```typescript
// server/api/swagger.ts
import { Elysia } from "elysia";
import { swagger } from "@elysiajs/swagger";

export const swaggerPlugin = new Elysia()
  .use(swagger({
    documentation: {
      info: {
        title: "Project API",
        version: "1.0.0",
        description: "API documentation for the application",
      },
      servers: [
        {
          url: process.env.API_BASE_URL || "http://localhost:3000/api",
          description: "Development server",
        },
      ],
    },
  }));

// Usage
export const api = new Elysia()
  .use(swaggerPlugin)
  .use(userRoutes)
  .get("/docs", ({ swagger }) => swagger({ documentationOnly: false }));
```

### Route Documentation

```typescript
// server/api/users/routes.ts
/**
 * @api {get} /api/users Get all users
 * @description Retrieve a paginated list of all users
 * @response {200} User[] Successful response
 * @response {500} ErrorResponse Server error
 */
export const userRoutes = new Elysia({ prefix: "/users" })
  .get("/", async ({ query }) => {
    const page = parseInt(query.page || "1");
    const limit = parseInt(query.limit || "10");
    
    const users = await db
      .select()
      .from(usersTable)
      .limit(limit)
      .offset((page - 1) * limit);
    
    return {
      data: users,
      pagination: {
        page,
        limit,
        total: await db.select().from(usersTable).then(count => count.length),
      },
    };
  });

/**
 * @api {post} /api/users Create user
 * @description Create a new user account
 * @requestbody {CreateUserRequest} User creation data
 * @response {201} User Successfully created
 * @response {400} ErrorResponse Validation error
 * @response {500} ErrorResponse Server error
 */
  .post("/", async ({ body }) => {
    // Implementation
  });
```

## Resources

- [Elysia Documentation](https://elysiajs.com/)
- [Drizzle ORM Documentation](https://orm.drizzle.team/)
- [Nuxt Elysia Module](https://github.com/nuxt-modules/elysia)
- [OpenAPI Specification](https://swagger.io/specification/)
- [REST API Design Guidelines](https://restfulapi.net/)
