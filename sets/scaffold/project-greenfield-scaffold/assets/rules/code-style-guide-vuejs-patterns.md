---
trigger: always_on
---

# Vue.js Specific Patterns

## Overview

This document provides Vue 3-specific patterns and best practices for the application. It covers component structure, composables, template patterns, and Vue 3 reactivity to ensure consistent, performant, and maintainable Vue components.

## Component Structure

Follow this consistent structure for all Vue components:

```vue
<script setup lang="ts">
// 1. Imports (external libraries, types, utilities)
import { ref, computed, onMounted } from "vue";
import { useAppStore } from "@/stores/AppStore";
import type { UserPreferences } from "@/interfaces/user";
import type { ComponentProps } from "@/interfaces/component";

// 2. Store setup
const appStore = useAppStore();

// 3. Props definition (if needed)
const props = withDefaults(defineProps<ComponentProps>(), {
  variant: "default",
});

// 4. Local state
const loading = ref(false);
const error = ref<Error | null>(null);

// 5. Computed properties
const user = computed(() => appStore.getUserById(props.userId));
const isCompact = computed(() => props.variant === "compact");

// 6. Methods
function handleUserAction() {
  // Component logic
}

// 7. Lifecycle hooks
onMounted(() => {
  // Initialization
});
</script>

<template>
  <!-- Use semantic HTML and Vuetify utilities -->
  <v-container class="user-card" :class="{ 'user-card--compact': isCompact }">
    <v-row>
      <v-col>
        <h2 class="user-card__name">{{ user?.name }}</h2>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.user-card {
  padding: 1rem;

  &--compact {
    padding: 0.5rem;
  }

  &__name {
    font-size: 1.25rem;
    font-weight: 600;
  }
}
</style>
```

## Composable Patterns

Composables should follow these patterns:

```typescript
// composables/useUserData.ts
export interface UseUserDataOptions {
  autoFetch?: boolean;
  cacheTime?: number;
}

export const useUserData = (
  userId: MaybeRef<string>,
  options: UseUserDataOptions = {},
) => {
  const { autoFetch = true, cacheTime = 5 * 60 * 1000 } = options;

  // State
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref<Error | null>(null);
  const lastFetched = ref<number | null>(null);

  // Computed
  const isExpired = computed(() => {
    if (!lastFetched.value) return true;
    return Date.now() - lastFetched.value > cacheTime;
  });

  const isValid = computed(() => user.value !== null && !isExpired.value);

  // Methods
  const fetchUser = async () => {
    if (!unref(userId)) return;

    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const userIdValue = unref(userId);
      user.value = await $api.get(`/users/${userIdValue}`);
      lastFetched.value = Date.now();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error("Failed to fetch user");
    } finally {
      loading.value = false;
    }
  };

  // Auto-fetch
  if (autoFetch) {
    watchEffect(() => {
      const userIdValue = unref(userId);
      if (userIdValue && (!user.value || isExpired.value)) {
        fetchUser();
      }
    });
  }

  return {
    user: readonly(user),
    loading: readonly(loading),
    error: readonly(error),
    isValid,
    refresh: fetchUser,
  };
};
```

## Nuxt 3 Auto-Imports

Nuxt 3 provides automatic imports for commonly used utilities:

```vue
<script setup lang="ts">
// ✅ NO manual imports needed for these:
// - Vue: ref, computed, onMounted, watch, etc.
// - Pinia: defineStore
// - Nuxt: useRoute, useRouter, navigateTo, etc.
// - Stores: use[Feature]Store (auto-imported from stores/)

// ❌ Manual imports only needed for:
// - External libraries
// - Type imports (import type)
// - Custom utilities not in auto-import paths
import { authClient } from "@/lib/auth-client";
import type { VForm } from "vuetify/components";

// ✅ These are auto-imported:
const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
const loading = ref(false);
</script>
```

### Auto-Import Best Practices

Leverage Nuxt's auto-imports effectively:

```vue
<script setup lang="ts">
// ✅ These are auto-imported - no manual imports needed:
const route = useRoute()
const router = useRouter()
const { $api } = useNuxtApp()

// ✅ Stores are auto-imported from stores/ directory
const appStore = useAppStore()
const userStore = useUserStore()

// ✅ Vue composables are auto-imported
const loading = ref(false)
const computedValue = computed(() => /* ... */)

// ❌ Only import external libraries and types
import { authClient } from '@/lib/auth-client'
import type { User } from '@/interfaces/user'
</script>
```

## Client-Only Content Rendering

When Nuxt SSR runs on serverless functions, anything rendered or fetched during SSR exists in platform-held server memory. Sensitive or decrypted user content that must never touch the server should be fetched client-side only:

```vue
<script setup lang="ts">
// ✅ Fetch sensitive content client-side — stores hydrate in onMounted,
// SSR renders empty containers, the client fills them after.
onMounted(async () => {
  await contentStore.fetchContent();
});

// ❌ Never fetch sensitive state during SSR:
const { data } = await useAsyncData("content", () => $fetch("/api/content"));
const { data } = await useFetch("/api/content");
</script>
```

- Stores holding sensitive content fetch only from `onMounted`/event handlers — never `useAsyncData`/`useFetch`, never inside `import.meta.server` branches.
- Never interpolate sensitive store state into SSR-reachable paths (head tags, error messages, `Sentry.setExtra`).
- Full contract: `docs/security/content-encryption-boundary.md` ("Client-only rendering isolation"); enforced by `tests/security/client-only-rendering.spec.ts`.

## Props and Emits

### Props Definition

```typescript
// ✅ Good - With defaults and types
interface ComponentProps {
  userId: string;
  variant?: 'default' | 'compact' | 'expanded';
  showActions?: boolean;
}

const props = withDefaults(defineProps<ComponentProps>(), {
  variant: 'default',
  showActions: true,
});

// ✅ Good - Runtime prop validation
const props = defineProps<{
  id: string;
  title: string;
  active?: boolean;
  metadata?: Record<string, any>;
}>();

// ❌ Bad - No type safety
const props = defineProps(['id', 'title', 'active']);
```

### Emits Definition

```typescript
// ✅ Good - Typed emits
const emit = defineEmits<{
  update: [value: string];
  delete: [id: string];
  'user-action': [action: 'edit' | 'delete', userId: string];
}>();

// Usage
emit('update', newValue);
emit('delete', userId);
emit('user-action', 'edit', userId);

// ✅ Good - Event handler syntax
const emit = defineEmits(['update', 'delete', 'user-action']);

// Usage
emit('update', newValue);
emit('delete', userId);
emit('user-action', { action: 'edit', userId });
```

## Template Patterns

### Conditional Rendering

```vue
<template>
  <!-- ✅ Good - Use v-if for conditional blocks -->
  <div v-if="user" class="user-profile">
    <h2>{{ user.name }}</h2>
    <p>{{ user.email }}</p>
  </div>
  
  <div v-else-if="loading" class="loading">
    <p>Loading user data...</p>
  </div>
  
  <div v-else class="error">
    <p>Failed to load user</p>
  </div>

  <!-- ✅ Good - Use v-show for toggle visibility -->
  <div v-show="isVisible" class="modal">
    <!-- Modal content -->
  </div>

  <!-- ❌ Bad - Complex inline logic -->
  <div v-if="user && user.isActive && user.hasPermission">
    <!-- Content -->
  </div>

  <!-- ✅ Good - Extract to computed -->
  <div v-if="shouldShowContent">
    <!-- Content -->
  </div>
</template>

<script setup lang="ts">
const shouldShowContent = computed(() => 
  user.value && 
  user.value.isActive && 
  user.value.hasPermission
);
</script>
```

### List Rendering

```vue
<template>
  <!-- ✅ Good - Use :key with stable identifier -->
  <div v-for="user in users" :key="user.id" class="user-list">
    <UserCard :user="user" @edit="handleEdit" @delete="handleDelete" />
  </div>

  <!-- ✅ Good - Use v-memo for optimization -->
  <div 
    v-for="user in users" 
    :key="user.id" 
    v-memo="[user.id, user.status, user.lastUpdated]"
    class="user-list"
  >
    <UserCard :user="user" />
  </div>

  <!-- ✅ Good - Handle empty state -->
  <div v-if="users.length === 0" class="empty-state">
    <p>No users found</p>
  </div>

  <!-- ❌ Bad - Using index as key (anti-pattern) -->
  <div v-for="(user, index) in users" :key="index">
    <!-- Content -->
  </div>
</template>
```

### Event Handling

```vue
<template>
  <!-- ✅ Good - Clear event handlers -->
  <v-btn @click="handleSubmit">Submit</v-btn>
  <v-btn @click="handleEdit(user.id)">Edit</v-btn>
  <v-text-field 
    v-model="formData.email"
    @update:model-value="handleEmailUpdate"
    @blur="validateEmail"
  />

  <!-- ✅ Good - Event modifiers -->
  <form @submit.prevent="handleSubmit">
    <input @keyup.enter="handleSubmit" />
    <div @click.stop="handleClick">
      <!-- Content -->
    </div>
  </form>

  <!-- ❌ Bad - Inline methods -->
  <v-btn @click="() => submitForm()">Submit</v-btn>
  <v-btn @click="user => deleteUser(user.id)">Delete</v-btn>
</template>
```

## Slots Usage

### Component with Slots

```vue
<!-- ParentComponent.vue -->
<template>
  <div class="card">
    <header class="card__header">
      <slot name="header" :title="title">
        <h2>{{ title }}</h2>
      </slot>
    </header>
    
    <main class="card__content">
      <slot :data="data" :loading="loading">
        <div v-if="loading">Loading...</div>
        <div v-else>{{ data }}</div>
      </slot>
    </main>
    
    <footer class="card__footer">
      <slot name="footer" :actions="availableActions">
        <v-btn @click="defaultAction">Default Action</v-btn>
      </slot>
    </footer>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title: string;
  data: any;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
});

const availableActions = computed(() => [
  { id: 'default', label: 'Default Action' },
  { id: 'cancel', label: 'Cancel' },
]);
</script>

<!-- Usage -->
<template>
  <ParentComponent title="User Profile" :data="userData" :loading="isLoading">
    <template #header="{ title }">
      <h1>{{ title }}</h1>
      <v-btn icon="mdi-close" @click="close" />
    </template>
    
    <template #default="{ data, loading }">
      <div v-if="!loading">
        <UserDisplay :user="data" />
      </div>
    </template>
    
    <template #footer="{ actions }">
      <v-btn 
        v-for="action in actions" 
        :key="action.id"
        @click="handleAction(action)"
      >
        {{ action.label }}
      </v-btn>
    </template>
  </ParentComponent>
</template>
```

## Component Registration & Naming

- **Component Path**: Reflect page folder structure
  - Page: `/pages/areas/index.vue`
  - Component: `/components/Areas/Popup.vue`
- **Registration**: Use auto-import features when available

### Component Naming

```vue
<!-- ✅ Good - PascalCase component names -->
<template>
  <UserProfile :user="currentUser" />
  <DataTable :items="tableData" />
  <LoadingSpinner v-if="loading" />
</template>

<!-- ❌ Bad - kebab-case in template -->
<template>
  <user-profile :user="currentUser" />
  <data-table :items="tableData" />
  <loading-spinner v-if="loading" />
</template>
```

## Provide/Inject Pattern

```typescript
// Parent component providing data
const theme = ref('light');

provide('theme', readonly(theme));

// Child component injecting data
const theme = inject<Ref<string>>('theme');

// With default value
const theme = inject('theme', ref('light'));
```

## Teleport Usage

```vue
<template>
  <div>
    <!-- Regular content -->
    <button @click="showModal = true">Open Modal</button>
    
    <!-- Teleported modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay">
        <div class="modal">
          <h2>Modal Content</h2>
          <button @click="showModal = false">Close</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
```

## Performance Patterns

### v-memo for Template Optimization

```vue
<template>
  <!-- ✅ Good - Memoize expensive components -->
  <div 
    v-for="user in users" 
    :key="user.id"
    v-memo="[user.id, user.status, user.lastUpdated]"
  >
    <UserCard :user="user" />
  </div>

  <!-- ✅ Good - Memoize conditional rendering -->
  <div v-memo="[shouldShow, data]">
    <ExpensiveComponent v-if="shouldShow" :data="data" />
  </div>
</template>
```

### Computed vs Methods

```vue
<template>
  <!-- ✅ Good - Use computed for derived data -->
  <div>
    <p>{{ fullName }}</p>
    <p>{{ formattedDate }}</p>
    <p>{{ isAdult ? 'Adult' : 'Minor' }}</p>
  </div>

  <!-- ❌ Bad - Use methods for derived data -->
  <div>
    <p>{{ getFullName() }}</p>
    <p>{{ getFormattedDate() }}</p>
    <p>{{ getAgeCategory() }}</p>
  </div>
</template>

<script setup lang="ts">
const user = ref({
  firstName: 'John',
  lastName: 'Doe',
  birthDate: new Date('1990-01-01'),
});

// ✅ Good - Computed properties
const fullName = computed(() => `${user.value.firstName} ${user.value.lastName}`);
const formattedDate = computed(() => user.value.birthDate.toLocaleDateString());
const isAdult = computed(() => {
  const age = new Date().getFullYear() - user.value.birthDate.getFullYear();
  return age >= 18;
});

// ❌ Bad - Methods for derived data
const getFullName = () => `${user.value.firstName} ${user.value.lastName}`;
const getFormattedDate = () => user.value.birthDate.toLocaleDateString();
const getAgeCategory = () => {
  const age = new Date().getFullYear() - user.value.birthDate.getFullYear();
  return age >= 18 ? 'Adult' : 'Minor';
};
</script>
```

## Error Handling in Components

```vue
<template>
  <!-- ✅ Good - Error boundaries -->
  <div v-if="error" class="error-boundary">
    <h2>Something went wrong</h2>
    <p>{{ error.message }}</p>
    <v-btn @click="retry">Retry</v-btn>
  </div>
  
  <div v-else-if="loading" class="loading-state">
    <v-progress-circular indeterminate />
    <p>Loading...</p>
  </div>
  
  <div v-else class="content">
    <!-- Normal content -->
    <slot />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  error?: Error | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  retry: [];
}>();

const retry = () => {
  emit('retry');
};
</script>
```

## Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Composition API Handbook](https://composition-api.vuejs.org/)
- [Nuxt 3 Documentation](https://nuxt.com/)
- [Vue.js Style Guide](https://vuejs.org/style-guide/)
- [Vue 3 Best Practices](https://learnvue.co/)
