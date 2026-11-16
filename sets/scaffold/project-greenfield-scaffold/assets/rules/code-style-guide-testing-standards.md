# Testing Standards

## Overview

This document provides comprehensive testing guidelines and patterns for the application. It covers component testing, composable testing, API testing, test utilities, configuration, and integration testing to ensure reliable, maintainable, and well-tested code.

## Component Testing

### Test Structure

```typescript
// tests/components/UserCard.spec.ts
import { mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import UserCard from "@/components/UserCard.vue";
import { createTestUser } from "@/tests/fixtures/users";

describe("UserCard", () => {
  it("renders user information correctly", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
    });

    expect(wrapper.find(".user-card__name").text()).toBe(user.name);
    expect(wrapper.find(".user-card__email").text()).toBe(user.email);
  });

  it("emits edit event when edit button is clicked", async () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
    });

    await wrapper.find('[data-testid="edit-button"]').trigger("click");

    expect(wrapper.emitted("edit")).toBeTruthy();
    expect(wrapper.emitted("edit")?.[0]).toEqual([user.id]);
  });

  it("shows loading state when loading prop is true", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user, loading: true },
    });

    expect(wrapper.find(".user-card__loading").exists()).toBe(true);
    expect(wrapper.find(".user-card__content").exists()).toBe(false);
  });
});
```

### Test Best Practices

```typescript
// ✅ Good - Descriptive test names
describe("UserCard", () => {
  it("renders user name and email correctly", () => {
    // Test implementation
  });

  it("emits edit event with user ID when edit button clicked", () => {
    // Test implementation
  });
});

// ✅ Good - AAA pattern (Arrange, Act, Assert)
it("calculates total price correctly", () => {
  // Arrange
  const items = [
    { name: "Item 1", price: 10, quantity: 2 },
    { name: "Item 2", price: 5, quantity: 3 },
  ];
  
  // Act
  const total = calculateTotal(items);
  
  // Assert
  expect(total).toBe(35);
});

// ✅ Good - Test data builders
const createTestUser = (overrides: Partial<User> = {}): User => ({
  id: "test-user-1",
  name: "Test User",
  email: "test@example.com",
  createdAt: new Date("2023-01-01"),
  ...overrides,
});

// Usage
it("renders with custom user data", () => {
  const customUser = createTestUser({
    name: "Custom Name",
    email: "custom@example.com",
  });
  
  const wrapper = mount(UserCard, {
    props: { user: customUser },
  });
  
  expect(wrapper.find(".user-card__name").text()).toBe("Custom Name");
});
```

### Component Testing Patterns

```typescript
// ✅ Good - Testing props
describe("UserCard Props", () => {
  it("renders with required props", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
    });

    expect(wrapper.exists()).toBe(true);
  });

  it("renders with optional variant prop", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user, variant: "compact" },
    });

    expect(wrapper.find(".user-card--compact").exists()).toBe(true);
  });

  it("renders with loading prop", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user, loading: true },
    });

    expect(wrapper.find(".user-card__loading").exists()).toBe(true);
  });
});

// ✅ Good - Testing events
describe("UserCard Events", () => {
  it("emits edit event when edit button clicked", async () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
    });

    await wrapper.find('[data-testid="edit-button"]').trigger("click");

    const emitted = wrapper.emitted("edit");
    expect(emitted).toBeTruthy();
    expect(emitted?.[0]).toEqual([user.id]);
  });

  it("emits delete event when delete button clicked", async () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
    });

    await wrapper.find('[data-testid="delete-button"]').trigger("click");

    const emitted = wrapper.emitted("delete");
    expect(emitted).toBeTruthy();
    expect(emitted?.[0]).toEqual([user.id]);
  });
});

// ✅ Good - Testing slots
describe("UserCard Slots", () => {
  it("renders default slot content", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
      slots: {
        default: "Custom slot content",
      },
    });

    expect(wrapper.text()).toContain("Custom slot content");
  });

  it("renders header slot with props", () => {
    const user = createTestUser();
    const wrapper = mount(UserCard, {
      props: { user },
      slots: {
        header: '<h1 class="custom-header">{{ user.name }}</h1>',
      },
    });

    expect(wrapper.find(".custom-header").exists()).toBe(true);
    expect(wrapper.find(".custom-header").text()).toBe(user.name);
  });
});
```

## Composable Testing

### Test Structure

```typescript
// tests/composables/useUserData.spec.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUserData } from "@/composables/useUserData";

describe("useUserData", () => {
  beforeEach(() => {
    // Mock Nuxt composables
    vi.mock("#app", () => ({
      useNuxtApp: () => ({
        $api: {
          get: vi.fn(),
        },
      }),
    }));
  });

  it("fetches user data on mount", async () => {
    const mockUser = { id: "1", name: "John Doe" };
    const { $api } = useNuxtApp();
    $api.get.mockResolvedValue(mockUser);

    const { user, loading, error } = useUserData("1");

    expect(loading.value).toBe(true);

    await nextTick();

    expect(loading.value).toBe(false);
    expect(user.value).toEqual(mockUser);
    expect(error.value).toBeNull();
  });

  it("handles API errors gracefully", async () => {
    const { $api } = useNuxtApp();
    $api.get.mockRejectedValue(new Error("API Error"));

    const { user, loading, error } = useUserData("1");

    await nextTick();

    expect(loading.value).toBe(false);
    expect(user.value).toBeNull();
    expect(error.value).toBeInstanceOf(Error);
    expect(error.value?.message).toBe("API Error");
  });
});
```

### Composable Testing Patterns

```typescript
// ✅ Good - Testing reactive state
it("updates reactive state correctly", async () => {
  const { count, increment } = useCounter();

  expect(count.value).toBe(0);

  increment();

  expect(count.value).toBe(1);
});

// ✅ Good - Testing computed properties
it("computes derived values correctly", () => {
  const { doubled, quadrupled } = useCounter(5);

  expect(doubled.value).toBe(10);
  expect(quadrupled.value).toBe(20);
});

// ✅ Good - Testing async operations
it("fetches data and updates state", async () => {
  const mockData = { id: "1", name: "Test" };
  const { $api } = useNuxtApp();
  $api.get.mockResolvedValue(mockData);

  const { data, loading, error, refresh } = useDataFetcher("1");

  expect(loading.value).toBe(true);

  await nextTick();

  expect(loading.value).toBe(false);
  expect(data.value).toEqual(mockData);
  expect(error.value).toBeNull();
});

// ✅ Good - Testing error handling
it("handles fetch errors", async () => {
  const mockError = new Error("Network error");
  const { $api } = useNuxtApp();
  $api.get.mockRejectedValue(mockError);

  const { data, loading, error, refresh } = useDataFetcher("1");

  await nextTick();

  expect(loading.value).toBe(false);
  expect(data.value).toBeNull();
  expect(error.value).toBe(mockError);
});
```

## API Testing

### Test Structure

```typescript
// tests/api/users.spec.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Elysia } from "elysia";
import { userRoutes } from "@/server/api/users/routes";
import { db } from "@/server/db";

describe("User API", () => {
  let app: Elysia;

  beforeEach(() => {
    app = new Elysia().use(userRoutes);
  });

  afterEach(() => {
    // Clean up database
    vi.clearAllMocks();
  });

  it("should fetch all users", async () => {
    const response = await app
      .handle(new Request("http://localhost/api/users"))
      .then((res) => res.json());

    expect(response).toHaveProperty("data");
    expect(Array.isArray(response.data)).toBe(true);
  });

  it("should create a new user", async () => {
    const userData = {
      name: "John Doe",
      email: "john@example.com",
      role: "user",
    };

    const response = await app
      .handle(
        new Request("http://localhost/api/users", {
          method: "POST",
          body: JSON.stringify(userData),
          headers: { "Content-Type": "application/json" },
        }),
      )
      .then((res) => res.json());

    expect(response).toHaveProperty("id");
    expect(response.name).toBe(userData.name);
    expect(response.email).toBe(userData.email);
  });
});
```

### API Testing Patterns

```typescript
// ✅ Good - Testing success responses
it("returns 200 with user data", async () => {
  const response = await app
    .handle(new Request("http://localhost/api/users/1"))
    .then((res) => res.json());

  expect(response).toEqual({
    id: "1",
    name: "John Doe",
    email: "john@example.com",
  });
});

// ✅ Good - Testing error responses
it("returns 404 for non-existent user", async () => {
  const response = await app
    .handle(new Request("http://localhost/api/users/999"))
    .then((res) => {
      expect(res.status).toBe(404);
      return res.json();
    });

  expect(response).toEqual({
    success: false,
    error: {
      message: "User not found",
      code: "NOT_FOUND",
    },
  });
});

// ✅ Good - Testing validation errors
it("returns 400 for invalid user data", async () => {
  const invalidData = {
    name: "", // Invalid: empty name
    email: "invalid-email", // Invalid: bad format
  };

  const response = await app
    .handle(
      new Request("http://localhost/api/users", {
        method: "POST",
        body: JSON.stringify(invalidData),
        headers: { "Content-Type": "application/json" },
      }),
      )
      .then((res) => {
        expect(res.status).toBe(400);
        return res.json();
      });

  expect(response).toEqual({
    success: false,
    error: {
      message: "Validation failed",
      code: "VALIDATION_ERROR",
      field: "name",
    },
  });
});
```

## Test Utilities and Helpers

### Test Fixtures

```typescript
// tests/fixtures/users.ts
import type { User } from "@/interfaces/user";

export const createTestUser = (overrides: Partial<User> = {}): User => ({
  id: "test-user-1",
  name: "Test User",
  email: "test@example.com",
  createdAt: new Date("2023-01-01"),
  ...overrides,
});

export const createTestUsers = (count: number): User[] => 
  Array.from({ length: count }, (_, index) => 
    createTestUser({
      id: `test-user-${index + 1}`,
      name: `Test User ${index + 1}`,
      email: `test${index + 1}@example.com`,
    })
  );

// tests/fixtures/orders.ts
export const createTestOrder = (overrides: Partial<Order> = {}): Order => ({
  id: "test-order-1",
  userId: "test-user-1",
  items: [
    { id: "item-1", name: "Test Item", price: 10, quantity: 2 },
  ],
  total: 20,
  status: "pending",
  ...overrides,
});
```

### Test Helpers

```typescript
// tests/helpers/mount.ts
import { mount, VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

export const mountWithStore = (component: any, options: any = {}): VueWrapper => {
  const pinia = createPinia();
  setActivePinia(pinia);
  
  return mount(component, {
    global: {
      plugins: [pinia],
    },
    ...options,
  });
};

// tests/helpers/api.ts
import { Elysia } from "elysia";

export const createTestApp = (routes: any): Elysia => {
  return new Elysia().use(routes);
};

export const makeRequest = (
  method: string,
  path: string,
  body?: any
): Request => {
  return new Request(`http://localhost:3000${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
};
```

### Mock Implementations

```typescript
// tests/mocks/api.ts
import { vi } from "vitest";

export const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
};

export const mockApiResponses = {
  users: [
    { id: "1", name: "John Doe", email: "john@example.com" },
    { id: "2", name: "Jane Smith", email: "jane@example.com" },
  ],
  error: new Error("API Error"),
};

// tests/mocks/db.ts
import { vi } from "vitest";

export const mockDb = {
  users: {
    findMany: vi.fn(),
    findById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  orders: {
    findMany: vi.fn(),
    findById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
};
```

## Test Configuration

### Vitest Configuration

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "c8",
      reporter: ["text", "json", "html"],
      exclude: [
        "node_modules/",
        "tests/",
        "**/*.d.ts",
        "**/*.config.*",
        "**/coverage/**",
      ],
      include: [
        "src/**/*.{js,ts,vue}",
        "composables/**/*.{js,ts}",
        "stores/**/*.{js,ts}",
      ],
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./"),
    },
  },
});
```

### Test Setup

```typescript
// tests/setup.ts
import { vi } from "vitest";
import { config } from "@vue/test-utils";

// Mock global objects
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    onchange: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Configure Vue Test Utils
config.global.stubs = {
  // Stub components that might cause issues
  "v-transition": true,
  "v-transition-group": true,
};

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
});
```

## Integration Testing

### End-to-End Testing

```typescript
// tests/e2e/user-auth.spec.ts
import { test, expect } from "@playwright/test";

test("user can login and view profile", async ({ page }) => {
  // Navigate to login page
  await page.goto("/login");

  // Fill login form
  await page.fill('[data-testid="email-input"]', "test@example.com");
  await page.fill('[data-testid="password-input"]', "password123");

  // Submit form
  await page.click('[data-testid="login-button"]');

  // Should be redirected to profile
  await expect(page).toHaveURL("/profile");

  // Verify user info is displayed
  await expect(page.locator('[data-testid="user-name"]')).toHaveText("Test User");
});

test("user cannot login with invalid credentials", async ({ page }) => {
  await page.goto("/login");

  await page.fill('[data-testid="email-input"]', "test@example.com');
  await page.fill('[data-testid="password-input"]', "wrongpassword");

  await page.click('[data-testid="login-button"]');

  // Should show error message
  await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
  
  // Should remain on login page
  await expect(page).toHaveURL("/login");
});
```

### Visual Testing

```typescript
// tests/visual/user-profile.spec.ts
import { test, expect } from "@playwright/test";

test("user profile visual regression", async ({ page }) => {
  await page.goto("/profile/john-doe");

  // Wait for page to load
  await page.waitForLoadState("networkidle");

  // Take screenshot and compare
  await expect(page).toHaveScreenshot("user-profile.png", {
    fullPage: true,
    animations: "disabled",
  });
});
```

## Test Data Management

### Database Seeding

```typescript
// tests/setup/database.ts
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import { db } from "@/server/db";
import * as schema from "@/server/db/schema";

export const setupTestDatabase = async () => {
  // Use in-memory database for testing
  const testDb = drizzle("postgres://localhost:5432/test", { schema });
  
  // Run migrations
  await migrate(testDb, { migrationsFolder: "./drizzle" });
  
  // Seed test data
  await testDb.insert(schema.users).values([
    {
      id: "test-user-1",
      name: "Test User 1",
      email: "test1@example.com",
      createdAt: new Date(),
    },
    {
      id: "test-user-2",
      name: "Test User 2",
      email: "test2@example.com",
      createdAt: new Date(),
    },
  ]);

  return testDb;
};

export const cleanupTestDatabase = async (testDb: any) => {
  // Clean up test data
  await testDb.delete(schema.users);
  await testDb.delete(schema.orders);
};
```

### Test Isolation

```typescript
// tests/helpers/database.ts
let testDb: any = null;

export const getTestDatabase = async () => {
  if (!testDb) {
    testDb = await setupTestDatabase();
  }
  return testDb;
};

export const resetTestDatabase = async () => {
  if (testDb) {
    await cleanupTestDatabase(testDb);
    await setupTestDatabase();
  }
};

// Usage in tests
beforeEach(async () => {
  await resetTestDatabase();
});
```

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [Playwright Documentation](https://playwright.dev/)
- [Testing Best Practices](https://kentcdodds.com/blog/best-practices-for-unit-testing/)
- [Testing Vue Components](https://vuejs.org/guide/scaling-up/testing.html)
- [Test-Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment)
