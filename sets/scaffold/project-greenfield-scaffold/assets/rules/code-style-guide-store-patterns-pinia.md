# Store Patterns (Pinia)

## Overview

This document provides comprehensive Pinia store patterns for the application. It covers store architecture, state management, computed properties, actions, and testing patterns to ensure consistent, scalable, and maintainable state management across the application.

## Store Architecture

Apply these Pinia store patterns consistently:

### Basic Store Structure

```typescript
// stores/[feature].ts
// Note: Nuxt auto-imports defineStore, no manual import needed
export const use[Feature]Store = defineStore("[feature]", () => {
  // 🔵 State - Use ref()
  const state = ref(initialValue);

  // 🟢 Getters - Use computed()
  const computedValue = computed(() => /* ... */);

  // 🟡 Actions - Use functions
  function action() {
    // mutation logic
  }

  async function asyncAction() {
    // async logic
  }

  // ✅ Return everything to expose
  return {
    state,
    computedValue,
    action,
    asyncAction,
  };
});

// 🔥 Hot Module Replacement
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(use[Feature]Store, import.meta.hot));
}
```

### Component Integration

```vue
<script setup lang="ts">
// ✅ Get store instance
const store = use[Feature]Store();

// ✅ Destructure state/getters with storeToRefs
const { state, computedValue } = storeToRefs(store);

// ✅ Call actions directly
function handleAction() {
  store.action();
}

// ✅ Or destructure actions (not reactive, but safe)
const { action } = store;
</script>
```

## Store Naming Conventions

- Use `use*Store` pattern: `useUserStore`, `useCartStore`
- Store ID should match filename: `defineStore("user", ...)`
- File should be PascalCase: `UserStore.ts`

```typescript
// ✅ Good naming
// stores/UserStore.ts
export const useUserStore = defineStore("user", () => {
  // Store implementation
});

// stores/ShoppingCartStore.ts
export const useShoppingCartStore = defineStore("shoppingCart", () => {
  // Store implementation
});

// ❌ Bad naming
// stores/user.ts
export const useUser = defineStore("user", () => {
  // Store implementation
});

// stores/userStore.ts
export const userStore = defineStore("user", () => {
  // Store implementation
});
```

## State Management Patterns

### Primitive State

```typescript
// ✅ Good - Individual reactive values
export const useAppStore = defineStore("app", () => {
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const theme = ref<'light' | 'dark'>('light');

  return {
    isLoading,
    error,
    theme,
  };
});
```

> **⚠️ Do NOT wrap state with `readonly()`** — See [Nuxt SSR Hydration](#nuxt-ssr-hydration-and-readonly) below.

### Object State

```typescript
// ✅ Good - Grouped related state
export const useUserStore = defineStore("user", () => {
  const currentUser = ref<User | null>(null);
  const preferences = ref<UserPreferences>({
    theme: 'auto',
    notifications: true,
  });

  return {
    currentUser,
    preferences,
  };
});
```

### Array State

```typescript
// ✅ Good - Array state with operations
export const useUserStore = defineStore("users", () => {
  const users = ref<User[]>([]);
  const loading = ref(false);

  // Actions for array manipulation
  function addUser(user: User) {
    users.value.push(user);
  }

  function removeUser(userId: string) {
    const index = users.value.findIndex(u => u.id === userId);
    if (index > -1) {
      users.value.splice(index, 1);
    }
  }

  function updateUser(userId: string, updates: Partial<User>) {
    const index = users.value.findIndex(u => u.id === userId);
    if (index > -1) {
      users.value[index] = { ...users.value[index], ...updates };
    }
  }

  return {
    users,
    loading,
    addUser,
    removeUser,
    updateUser,
  };
});
```

## Computed Properties

### Simple Computed

```typescript
// ✅ Good - Simple derived values
export const useUserStore = defineStore("user", () => {
  const firstName = ref('');
  const lastName = ref('');

  const fullName = computed(() => `${firstName.value} ${lastName.value}`.trim());
  const initials = computed(() => {
    const names = fullName.value.split(' ');
    return names.map(name => name[0]).join('').toUpperCase();
  });

  return {
    firstName,
    lastName,
    fullName,
    initials,
  };
});
```

### Complex Computed

```typescript
// ✅ Good - Complex derived values with caching
export const useCartStore = defineStore("cart", () => {
  const items = ref<CartItem[]>([]);
  const discountCode = ref<string>('');

  const subtotal = computed(() => 
    items.value.reduce((sum, item) => sum + (item.price * item.quantity), 0)
  );

  const discount = computed(() => {
    if (!discountCode.value) return 0;
    
    // Apply discount logic
    const total = subtotal.value;
    if (discountCode.value === 'SAVE10') return total * 0.1;
    if (discountCode.value === 'SAVE20') return total * 0.2;
    return 0;
  });

  const total = computed(() => subtotal.value - discount.value);

  const itemCount = computed(() => 
    items.value.reduce((count, item) => count + item.quantity, 0)
  );

  return {
    items,
    discountCode,
    subtotal,
    discount,
    total,
    itemCount,
  };
});
```

## Action Patterns

### Synchronous Actions

```typescript
// ✅ Good - Simple synchronous mutations
export const useCounterStore = defineStore("counter", () => {
  const count = ref(0);

  function increment() {
    count.value++;
  }

  function decrement() {
    count.value--;
  }

  function reset() {
    count.value = 0;
  }

  function setCount(value: number) {
    count.value = Math.max(0, value);
  }

  return {
    count,
    increment,
    decrement,
    reset,
    setCount,
  };
});
```

### Asynchronous Actions

```typescript
// ✅ Good - Async actions with proper error handling
export const useUserStore = defineStore("user", () => {
  const users = ref<User[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchUsers() {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const data = await $api.get<User[]>('/users');
      users.value = data;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch users';
      throw error.value;
    } finally {
      loading.value = false;
    }
  }

  async function createUser(userData: CreateUserRequest) {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const newUser = await $api.post<User>('/users', userData);
      users.value.push(newUser);
      return newUser;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create user';
      throw error.value;
    } finally {
      loading.value = false;
    }
  }

  return {
    users,
    loading,
    error,
    fetchUsers,
    createUser,
  };
});
```

### Actions with Parameters

```typescript
// ✅ Good - Actions with typed parameters
export const useTodoStore = defineStore("todos", () => {
  const todos = ref<Todo[]>([]);

  function addTodo(text: string) {
    const newTodo: Todo = {
      id: Date.now().toString(),
      text: text.trim(),
      completed: false,
      createdAt: new Date(),
    };
    todos.value.unshift(newTodo);
  }

  function updateTodo(id: string, updates: Partial<Todo>) {
    const index = todos.value.findIndex(todo => todo.id === id);
    if (index > -1) {
      todos.value[index] = { ...todos.value[index], ...updates };
    }
  }

  function deleteTodo(id: string) {
    const index = todos.value.findIndex(todo => todo.id === id);
    if (index > -1) {
      todos.value.splice(index, 1);
    }
  }

  return {
    todos,
    addTodo,
    updateTodo,
    deleteTodo,
  };
});
```

## Advanced Patterns

### Store Composition

```typescript
// ✅ Good - Combine multiple stores
export const useUserDashboard = () => {
  const userStore = useUserStore();
  const analyticsStore = useAnalyticsStore();
  const notificationStore = useNotificationStore();

  const user = computed(() => userStore.currentUser);
  const isLoading = computed(() => 
    userStore.loading || analyticsStore.loading
  );

  async function loadDashboard() {
    try {
      await Promise.all([
        userStore.fetchUserProfile(),
        analyticsStore.fetchUserStats(),
      ]);
      notificationStore.showSuccess('Dashboard loaded successfully');
    } catch (error) {
      notificationStore.showError('Failed to load dashboard');
    }
  }

  return {
    user,
    isLoading,
    loadDashboard,
  };
};
```

### Store Inheritance/Extension

```typescript
// ✅ Good - Base store with common functionality
// stores/base/BaseStore.ts
export const createBaseStore = <T>(name: string, initialState: T) => {
  return defineStore(name, () => {
    const state = ref<T>(initialState);
    const loading = ref(false);
    const error = ref<string | null>(null);

    function setLoading(value: boolean) {
      loading.value = value;
    }

    function setError(message: string | null) {
      error.value = message;
    }

    function clearError() {
      error.value = null;
    }

    return {
      state,
      loading,
      error,
      setLoading,
      setError,
      clearError,
    };
  });
};

// stores/UserStore.ts
export const useUserStore = createBaseStore('user', {
  currentUser: null as User | null,
  preferences: {
    theme: 'auto',
    notifications: true,
  },
});
```

### Pagination Store

```typescript
// ✅ Good - Pagination with state management
export const usePaginatedStore = <T>(name: string, fetchFunction: (page: number, limit: number) => Promise<T[]>) => {
  return defineStore(name, () => {
    const items = ref<T[]>([]);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalItems = ref(0);
    const loading = ref(false);

    const totalPages = computed(() => 
      Math.ceil(totalItems.value / pageSize.value)
    );

    const hasNextPage = computed(() => 
      currentPage.value < totalPages.value
    );

    const hasPrevPage = computed(() => 
      currentPage.value > 1
    );

    async function fetchPage(page: number = currentPage.value) {
      loading.value = true;
      try {
        const data = await fetchFunction(page, pageSize.value);
        items.value = data;
        currentPage.value = page;
      } catch (error) {
        console.error('Failed to fetch page:', error);
      } finally {
        loading.value = false;
      }
    }

    async function nextPage() {
      if (hasNextPage.value) {
        await fetchPage(currentPage.value + 1);
      }
    }

    async function prevPage() {
      if (hasPrevPage.value) {
        await fetchPage(currentPage.value - 1);
      }
    }

    return {
      items,
      currentPage,
      pageSize,
      totalItems,
      totalPages,
      hasNextPage,
      hasPrevPage,
      loading,
      fetchPage,
      nextPage,
      prevPage,
    };
  });
};
```

## Store Persistence

### Local Storage Integration

```typescript
// ✅ Good - Persistent store with localStorage
export const useSettingsStore = defineStore('settings', () => {
  // Initialize from localStorage
  const storedSettings = localStorage.getItem('app-settings');
  const initialState = storedSettings ? JSON.parse(storedSettings) : {
    theme: 'light',
    language: 'en',
    notifications: true,
  };

  const settings = ref(initialState);

  // Watch for changes and persist
  watch(settings, (newSettings) => {
    localStorage.setItem('app-settings', JSON.stringify(newSettings));
  }, { deep: true });

  function updateSetting<K extends keyof typeof initialState>(
    key: K, 
    value: typeof initialState[K]
  ) {
    settings.value[key] = value;
  }

  function resetSettings() {
    settings.value = initialState;
  }

  return {
    settings,
    updateSetting,
    resetSettings,
  };
});
```

## Nuxt SSR Hydration and `readonly()`

**Never wrap store state with `readonly()` in Pinia setup stores when using Nuxt SSR.**

### The Problem

When a Pinia setup store returns `readonly(ref)` and a component uses `storeToRefs()` to destructure that state, Nuxt's SSR hydration process attempts to write server-rendered values onto the readonly refs on the client. This triggers repeated Vue warnings:

```
[Vue warn] Set operation on key "value" failed: target is readonly. RefImpl { ... }
```

### Why It Happens

1. Server renders the app, serializing store state
2. Client hydrates, Pinia restores the serialized state by writing to refs
3. `readonly()` prevents the write, causing the warning
4. Every store ref triggers a separate warning (one per ref per store per component)

### The Solution

Return refs directly without `readonly()`:

```typescript
// ❌ Bad - Causes SSR hydration warnings
export const useUserStore = defineStore("user", () => {
  const user = ref<User | null>(null);
  const loading = ref(false);

  return {
    user: readonly(user),        // Triggers warning on hydration
    loading: readonly(loading),  // Triggers warning on hydration
  };
});

// ✅ Good - No readonly(), mutations via actions only
export const useUserStore = defineStore("user", () => {
  const user = ref<User | null>(null);
  const loading = ref(false);

  function setUser(newUser: User) {
    user.value = newUser;
  }

  function setLoading(value: boolean) {
    loading.value = value;
  }

  return {
    user,
    loading,
    setUser,
    setLoading,
  };
});
```

### Mutation Discipline Without `readonly()`

Instead of `readonly()`, enforce immutability through convention:

1. **Actions are the only mutation path** — Components call actions, never assign directly
2. **Use `storeToRefs()` for reactive access** — Destructured refs are read in templates
3. **Name actions clearly** — `setUser()`, `setLoading()`, `clearError()` make intent obvious
4. **Review store usage in PRs** — Ensure no direct `store.state = value` assignments

### When `readonly()` Is Acceptable

`readonly()` may be used in **composables** (not stores) where the composable owns the ref and only exposes it for reading. Composables don't go through Pinia's state serialization/hydration cycle:

```typescript
// ✅ Acceptable in composables (not Pinia stores)
export const useUserData = (userId: MaybeRef<string>) => {
  const user = ref<User | null>(null);

  return {
    user: readonly(user),  // OK — composable, not a Pinia store
    refresh: fetchUser,
  };
};
```

## Testing Stores

### Unit Testing Store

```typescript
// tests/stores/UserStore.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useUserStore } from '@/stores/UserStore';

describe('UserStore', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it('should initialize with default state', () => {
    const store = useUserStore();
    
    expect(store.users).toEqual([]);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('should add user correctly', async () => {
    const store = useUserStore();
    const mockUser = { id: '1', name: 'Test User' };
    
    await store.addUser(mockUser);
    
    expect(store.users).toContainEqual(mockUser);
    expect(store.users).toHaveLength(1);
  });

  it('should handle fetch errors', async () => {
    const store = useUserStore();
    const mockError = new Error('Network error');
    
    vi.mocked(useNuxtApp).$api.get.mockRejectedValue(mockError);
    
    await expect(store.fetchUsers()).rejects.toThrow('Network error');
    expect(store.error).toBe('Network error');
    expect(store.loading).toBe(false);
  });
});
```

## Resources

- [Pinia Documentation](https://pinia.vuejs.org/)
- [Pinia Best Practices](https://pinia.vuejs.org/core-concepts/)
- [Vue 3 State Management](https://vuejs.org/guide/scaling-up/state-management.html)
- [Testing Pinia Stores](https://pinia.vuejs.org/cookbook/testing.html)
