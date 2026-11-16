# Reactivity Patterns

## Overview

This document provides comprehensive Vue 3 reactivity patterns and best practices for the application. It covers standard reactivity, advanced patterns, watch vs watchEffect usage, computed properties, reactive arrays/objects, and performance considerations to ensure efficient and maintainable reactive code.

## Standard Vue 3 Reactivity (Recommended)

Use `ref()` for most cases, `computed()` for derived values, and `watch()` for side effects:

```typescript
// ✅ Good - Standard reactivity
const count = ref(0);
const doubled = computed(() => count.value * 2);

watch(count, (newValue, oldValue) => {
  console.log(`Count changed from ${oldValue} to ${newValue}`);
});

// ✅ Good - Reactive object
const user = ref<User>({
  id: '1',
  name: 'John Doe',
  email: 'john@example.com',
});

const userDisplayName = computed(() => `${user.value.name} (${user.value.email})`);
```

## Advanced Reactivity

### Shallow Ref

Use `shallowRef()` for performance optimization with large objects:

```typescript
// ✅ Good - Shallow ref for large objects
const largeDataset = shallowRef<LargeDataItem[]>([]);
const userPreferences = shallowRef<UserPreferences>({});

// Updates to top-level properties are reactive
userPreferences.value.theme = 'dark'; // Triggers reactivity

// But nested property updates are not
userPreferences.value.notifications.email = true; // Does NOT trigger reactivity

// Force reactivity for nested updates
userPreferences.value = { ...userPreferences.value };
```

### Custom Ref

Use `customRef()` for custom reactivity logic:

```typescript
// ✅ Good - Custom ref with debouncing
const useDebouncedRef = <T>(value: T, delay: number = 300) => {
  let timeout: NodeJS.Timeout;
  let innerValue = value;

  return customRef((track, trigger) => {
    return {
      get() {
        track();
        return innerValue;
      },
      set(newValue) {
        innerValue = newValue;
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          trigger();
        }, delay);
      },
    };
  });
};

// Usage
const debouncedSearch = useDebouncedRef('', 500);
```

### Readonly Ref

Use `readonly()` to prevent mutations in **composables** and **component-local refs**:

```typescript
// ✅ Good - Readonly refs for computed values
const count = ref(0);
const doubled = readonly(computed(() => count.value * 2));

// Attempting to modify will cause warning in development
// doubled.value = 100; // Warning: Attempt to mutate readonly value
```

> **⚠️ Do NOT use `readonly()` in Pinia store returns** — Nuxt SSR hydration writes serialized state to store refs on the client. `readonly()` blocks this write, causing "Set operation on key 'value' failed: target is readonly" warnings. See [Store Patterns — Nuxt SSR Hydration](./code-style-guide-store-patterns-pinia.md#nuxt-ssr-hydration-and-readonly) for details.

## Watch vs WatchEffect

### Watch for Specific Dependencies

Use `watch()` when you need to watch specific dependencies:

```typescript
// ✅ Good - Watch specific dependencies
watch(
  () => user.value.id,
  async (newId) => {
    if (newId) {
      await fetchUserData(newId);
    }
  },
);

// ✅ Good - Watch multiple dependencies
watch(
  [() => user.value.id, () => user.value.preferences],
  async ([newId, newPreferences], [oldId, oldPreferences]) => {
    if (newId !== oldId) {
      await fetchUserData(newId);
    }
    if (newPreferences !== oldPreferences) {
      await saveUserPreferences(newPreferences);
    }
  },
);
```

### WatchEffect for Automatic Dependency Tracking

Use `watchEffect()` when you want automatic dependency tracking:

```typescript
// ✅ Good - Automatic dependency tracking
watchEffect(() => {
  if (user.value && user.value.preferences.theme) {
    applyTheme(user.value.preferences.theme);
  }
  
  // Automatically tracks all reactive dependencies used in the function
  document.title = `User: ${user.value?.name || 'Unknown'}`;
});

// ✅ Good - Side effects that depend on multiple reactive values
watchEffect(() => {
  const total = cartItems.value.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const tax = total * 0.08;
  const grandTotal = total + tax;
  
  updateOrderSummary({ total, tax, grandTotal });
});
```

### Watch Options

```typescript
// ✅ Good - Immediate execution
watch(
  searchQuery,
  (newValue) => {
    performSearch(newValue);
  },
  { immediate: true } // Run immediately with current value
);

// ✅ Good - Deep watching
watch(
  userObject,
  (newValue) => {
    console.log('User object changed:', newValue);
  },
  { deep: true } // Watch nested properties (use sparingly for performance)
);

// ✅ Good - Flush behavior
watch(
  searchQuery,
  (newValue, oldValue, onCleanup) => {
    const timeout = setTimeout(() => {
      performSearch(newValue);
    }, 300);
    
    onCleanup(() => {
      clearTimeout(timeout);
    });
  },
  { flush: 'post' } // Run after DOM updates
);
```

## Computed Properties

### Simple Computed

```typescript
// ✅ Good - Simple derived values
const fullName = computed(() => `${user.value.firstName} ${user.value.lastName}`);
const isAdult = computed(() => user.value.age >= 18);
const formattedPrice = computed(() => 
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(product.value.price)
);
```

### Computed with Getters and Setters

```typescript
// ✅ Good - Computed with getter and setter
const searchQuery = ref('');

const filteredUsers = computed({
  get() {
    if (!searchQuery.value) return users.value;
    
    return users.value.filter(user =>
      user.name.toLowerCase().includes(searchQuery.value.toLowerCase())
    );
  },
  set(value: User[]) {
    // This allows setting the computed value
    users.value = value;
    searchQuery.value = '';
  },
});

// Usage
filteredUsers.value = []; // Triggers the setter
console.log(filteredUsers.value); // Triggers the getter
```

### Computed Caching

```typescript
// ✅ Good - Expensive computed with caching
const expensiveCalculation = computed(() => {
  // This will only recompute when dependencies change
  let result = 0;
  for (let i = 0; i < 10000; i++) {
    result += Math.sqrt(i);
  }
  return result;
});

// ✅ Good - Memoizing expensive operations
const memoizedExpensiveOperation = useMemo(() => {
  return expensiveOperation(largeDataSet.value);
}, [largeDataSet.value]);
```

## Reactive Arrays and Objects

### Reactive Array Operations

```typescript
// ✅ Good - Proper array mutations
const items = ref<Item[]>([]);

// Add items
items.value.push(newItem); // Triggers reactivity

// Remove items
const index = items.value.findIndex(item => item.id === targetId);
if (index > -1) {
  items.value.splice(index, 1); // Triggers reactivity
}

// Update items
items.value = items.value.map(item =>
  item.id === targetId ? { ...item, ...updates } : item
);

// ❌ Bad - Non-reactive array operations
const items = ref<Item[]>([]);
const newArray = [...items.value, newItem];
items.value = newArray; // Only triggers once
```

### Reactive Object Operations

```typescript
// ✅ Good - Proper object mutations
const user = ref<User>({
  name: 'John',
  preferences: {
    theme: 'light',
    notifications: true,
  },
});

// Update top-level properties
user.value.name = 'Jane'; // Triggers reactivity

// Update nested properties (with reactivity)
user.value.preferences = {
  ...user.value.preferences,
  theme: 'dark',
};

// ❌ Bad - Non-reactive nested updates
user.value.preferences.theme = 'dark'; // Does NOT trigger reactivity
```

### Using toRefs and toRaw

```typescript
// ✅ Good - Using toRefs for destructuring
const userStore = useUserStore();
const { users, loading, error } = storeToRefs(userStore);

// Now you can use them directly in templates without .value
// {{ users }} instead of {{ userStore.users }}

// ✅ Good - Using toRaw when needed
const rawUser = toRaw(user.value);
console.log(rawUser); // Non-reactive version

// Use sparingly - mainly for debugging or external libraries
```

## Advanced Patterns

### Reactive State Machines

```typescript
// ✅ Good - Simple state machine with reactivity
type State = 'idle' | 'loading' | 'success' | 'error';

const state = ref<State>('idle');
const error = ref<string | null>(null);

const isLoading = computed(() => state.value === 'loading');
const isSuccess = computed(() => state.value === 'success');
const isError = computed(() => state.value === 'error');

const transition = (newState: State, errorMessage?: string) => {
  state.value = newState;
  error.value = errorMessage || null;
};

const execute = async () => {
  transition('loading');
  
  try {
    const result = await asyncOperation();
    transition('success');
    return result;
  } catch (err) {
    transition('error', err instanceof Error ? err.message : 'Unknown error');
    throw err;
  }
};
```

### Reactive Collections

```typescript
// ✅ Good - Reactive collection with utilities
const useReactiveCollection = <T>(initialItems: T[] = []) => {
  const items = ref<T[]>([...initialItems]);
  
  const addItem = (item: T) => {
    items.value.push(item);
  };
  
  const removeItem = (predicate: (item: T) => boolean) => {
    const index = items.value.findIndex(predicate);
    if (index > -1) {
      items.value.splice(index, 1);
    }
  };
  
  const updateItem = (predicate: (item: T) => boolean, updates: Partial<T>) => {
    const index = items.value.findIndex(predicate);
    if (index > -1) {
      items.value[index] = { ...items.value[index], ...updates };
    }
  };
  
  const clearItems = () => {
    items.value = [];
  };
  
  return {
    items: readonly(items),
    addItem,
    removeItem,
    updateItem,
    clearItems,
  };
};

// Usage
const users = useReactiveCollection<User>();
users.addUser({ id: '1', name: 'John' });
users.removeItem(user => user.id === '1');
```

### Reactive Form Handling

```typescript
// ✅ Good - Reactive form with validation
const useForm = <T extends Record<string, any>>(initialValues: T) => {
  const formData = ref<T>({ ...initialValues });
  const errors = ref<Partial<Record<keyof T, string>>>({});
  const touched = ref<Partial<Record<keyof T, boolean>>>({});
  
  const isFieldValid = (field: keyof T) => {
    return !errors.value[field];
  };
  
  const isFieldTouched = (field: keyof T) => {
    return touched.value[field] === true;
  };
  
  const updateField = (field: keyof T, value: any) => {
    formData.value[field] = value;
    touched.value[field] = true;
    
    // Validate field
    const fieldError = validateField(field, value);
    if (fieldError) {
      errors.value[field] = fieldError;
    } else {
      delete errors.value[field];
    }
  };
  
  const isFormValid = computed(() => {
    return Object.keys(errors.value).length === 0;
  });
  
  const resetForm = () => {
    formData.value = { ...initialValues };
    errors.value = {};
    touched.value = {};
  };
  
  return {
    formData: readonly(formData),
    errors: readonly(errors),
    touched: readonly(touched),
    isFormValid,
    isFieldValid,
    isFieldTouched,
    updateField,
    resetForm,
  };
};
```

## Performance Considerations

### Avoid Over-Reactivity

```typescript
// ✅ Good - Minimal reactivity
const user = ref<User>(initialUser);
const displayName = computed(() => user.value.name);

// ❌ Bad - Unnecessary reactivity
const user = reactive(initialUser);
const displayName = computed(() => user.name);
```

### Debounce Reactive Updates

```typescript
// ✅ Good - Debounced reactive updates
const searchQuery = ref('');
const debouncedQuery = ref('');

const updateDebouncedQuery = useDebounceFn((value: string) => {
  debouncedQuery.value = value;
}, 300);

watch(searchQuery, updateDebouncedQuery);

// Use debouncedQuery for API calls
watch(debouncedQuery, (newValue) => {
  performSearch(newValue);
});
```

### Lazy Computed Properties

```typescript
// ✅ Good - Lazy computed for expensive operations
const expensiveData = computed(() => {
  // Only computed when accessed
  console.log('Expensive calculation performed');
  return heavyCalculation(largeDataSet.value);
});

// Access only when needed
if (showDetails.value) {
  const data = expensiveData.value;
  // Use data
}
```

## Resources

- [Vue 3 Reactivity Documentation](https://vuejs.org/guide/reactivity-fundamentals.html)
- [Vue 3 Reactivity API](https://vuejs.org/api/reactivity-core.html)
- [Vue 3 Computed Properties](https://vuejs.org/guide/essentials/computed.html)
- [Vue 3 Watchers](https://vuejs.org/guide/essentials/watchers.html)
- [Vue 3 Reactivity in Depth](https://vuejs.org/guide/reactivity-in-depth.html)
