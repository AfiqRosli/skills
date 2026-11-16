# Error Handling

## Overview

This document provides comprehensive error handling patterns and best practices for the application. It covers try/catch patterns, error boundaries, loading state management, custom error classes, global error handling, async error handling, and retry logic to ensure robust and user-friendly error management.

## Error Handling Patterns

### Try/Catch Pattern

Use try/catch for async operations with meaningful error messages:

```typescript
// ✅ Good - Try/catch pattern
async function fetchData() {
  try {
    const data = await $fetch('/api/data');
    return data;
  } catch (error) {
    console.error('Failed to fetch data:', error);
    throw new Error('Data fetch failed. Please try again.');
  }
}

// ✅ Good - Specific error handling
async function loginUser(credentials: LoginCredentials) {
  try {
    const response = await $fetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    return response;
  } catch (error) {
    if (error instanceof Response && error.status === 401) {
      throw new AuthenticationError('Invalid credentials', 'INVALID_CREDENTIALS');
    } else if (error instanceof Response && error.status === 429) {
      throw new Error('Too many login attempts. Please try again later.');
    } else {
      console.error('Login failed:', error);
      throw new Error('Login failed. Please try again.');
    }
  }
}
```

### Error Boundary Pattern

Create error boundaries for Vue components:

```vue
<template>
  <div v-if="error" class="error-boundary">
    <h2>Something went wrong</h2>
    <p>{{ error.message }}</p>
    <button @click="retry">Retry</button>
  </div>
  <div v-else>
    <slot />
  </div>
</template>

<script setup lang="ts">
interface Props {
  onError?: (error: Error) => void;
}

const props = withDefaults(defineProps<Props>(), {});

const error = ref<Error | null>(null);

const handleError = (err: Error) => {
  error.value = err;
  props.onError?.(err);
  console.error('Error boundary caught:', err);
};

const retry = () => {
  error.value = null;
};

// Error boundary for async operations
const withErrorHandling = async <T>(operation: () => Promise<T>): Promise<T | null> => {
  try {
    return await operation();
  } catch (err) {
    handleError(err instanceof Error ? err : new Error('Unknown error'));
    return null;
  }
};

// Expose error handling to children
provide('errorBoundary', {
  handleError,
  withErrorHandling,
});
</script>

<style scoped>
.error-boundary {
  padding: 2rem;
  border: 2px solid var(--v-theme-error);
  border-radius: 8px;
  background: var(--v-theme-error-lighten);
  text-align: center;
}

.error-boundary h2 {
  color: var(--v-theme-error);
  margin-bottom: 1rem;
}

.error-boundary p {
  margin-bottom: 1.5rem;
  color: var(--v-theme-text-secondary);
}

.error-boundary button {
  background: var(--v-theme-primary);
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
}
</style>
```

## Loading State Management

### Consistent Loading Pattern

```typescript
// ✅ Good - Consistent loading pattern
const loading = ref(false);
const error = ref<Error | null>(null);

async function loadData() {
  loading.value = true;
  error.value = null;

  try {
    const data = await fetchData();
    // handle success
  } catch (e) {
    error.value = e instanceof Error ? e : new Error("Unknown error");
  } finally {
    loading.value = false;
  }
}

// ✅ Good - Composable for loading states
export const useAsyncOperation = <T>() => {
  const loading = ref(false);
  const error = ref<Error | null>(null);
  const data = ref<T | null>(null);

  const execute = async (operation: () => Promise<T>): Promise<T | null> => {
    loading.value = true;
    error.value = null;

    try {
      const result = await operation();
      data.value = result;
      return result;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error("Unknown error");
      data.value = null;
      return null;
    } finally {
      loading.value = false;
    }
  };

  return {
    loading: readonly(loading),
    error: readonly(error),
    data: readonly(data),
    execute,
  };
};
```

### Store Error Handling

```typescript
// stores/UserStore.ts
export const useUserStore = defineStore("user", () => {
  const users = ref<User[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchUsers() {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const data = await $api.get<User[]>("/users");
      users.value = data;
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Failed to fetch users";
      error.value = errorMessage;
      throw new Error(errorMessage);
    } finally {
      loading.value = false;
    }
  }

  async function createUser(userData: CreateUserRequest) {
    loading.value = true;
    error.value = null;

    try {
      const { $api } = useNuxtApp();
      const newUser = await $api.post<User>("/users", userData);
      users.value.push(newUser);
      return newUser;
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Failed to create user";
      error.value = errorMessage;
      throw new Error(errorMessage);
    } finally {
      loading.value = false;
    }
  }

  function clearError() {
    error.value = null;
  }

  return {
    users,
    loading,
    error,
    fetchUsers,
    createUser,
    clearError,
  };
});
```

## Custom Error Classes

### Specific Error Types

Create specific error types for better error handling:

```typescript
// utils/errors.ts
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number = 500,
    public code?: string,
    public details?: any,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class AuthenticationError extends Error {
  constructor(
    message: string = "Authentication failed",
    public code: "INVALID_CREDENTIALS" | "TOKEN_EXPIRED" | "INSUFFICIENT_PERMISSIONS" = "INVALID_CREDENTIALS",
    public status: number = 401,
  ) {
    super(message);
    this.name = "AuthenticationError";
  }
}

export class ValidationError extends Error {
  constructor(
    message: string,
    public field?: string,
    public value?: any,
  ) {
    super(message);
    this.name = "ValidationError";
  }
}

export class NetworkError extends Error {
  constructor(
    message: string = "Network error occurred",
    public status?: number,
    public isTimeout: boolean = false,
  ) {
    super(message);
    this.name = "NetworkError";
  }
}

export class BusinessLogicError extends Error {
  constructor(
    message: string,
    public code: string,
    public context?: any,
  ) {
    super(message);
    this.name = "BusinessLogicError";
  }
}
```

### Error Usage Examples

```typescript
// API error handling
async function fetchUser(id: string): Promise<User> {
  try {
    const response = await $fetch(`/api/users/${id}`);
    
    if (!response.ok) {
      throw new ApiError(
        `Failed to fetch user: ${response.statusText}`,
        response.status,
        'USER_FETCH_FAILED'
      );
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    throw new NetworkError("Failed to connect to server");
  }
}

// Validation error handling
function validateUserEmail(email: string): void {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  
  if (!emailRegex.test(email)) {
    throw new ValidationError(
      "Invalid email format",
      "email",
      email
    );
  }
}

// Business logic error handling
function deleteUser(userId: string, currentUser: User): void {
  if (userId === currentUser.id) {
    throw new BusinessLogicError(
      "Users cannot delete their own accounts",
      "SELF_DELETION_FORBIDDEN",
      { userId, currentUserRole: currentUser.role }
    );
  }
  
  // Proceed with deletion
}
```

## Global Error Handling

### Global Error Handler

```typescript
// plugins/error-handler.client.ts
export default defineNuxtPlugin(() => {
  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    
    // Report to error tracking service
    reportError(event.reason);
    
    // Prevent default browser behavior
    event.preventDefault();
  });

  // Handle uncaught errors
  window.addEventListener('error', (event) => {
    console.error('Uncaught error:', event.error);
    
    // Report to error tracking service
    reportError(event.error);
  });
});

// Server-side error handler
// server/api/middleware/error-handler.ts
import { Elysia } from "elysia";
import { ApiError } from "@/utils/errors";

export const errorHandler = new Elysia().onError(({ error, set }) => {
  console.error('API Error:', error);
  
  if (error instanceof ApiError) {
    set.status = error.status;
    return {
      success: false,
      error: {
        message: error.message,
        code: error.code,
        details: error.details,
        timestamp: new Date().toISOString(),
      },
    };
  }

  if (error instanceof ValidationError) {
    set.status = 400;
    return {
      success: false,
      error: {
        message: error.message,
        field: error.field,
        value: error.value,
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
```

### Error Reporting

```typescript
// utils/error-reporting.ts
interface ErrorReport {
  error: Error;
  context?: {
    userAgent?: string;
    url?: string;
    userId?: string;
    action?: string;
  };
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

const reportError = async (error: Error, context?: any) => {
  const report: ErrorReport = {
    error,
    context: {
      userAgent: navigator.userAgent,
      url: window.location.href,
      userId: getCurrentUserId(),
      action: context?.action,
      ...context,
    },
    timestamp: new Date().toISOString(),
    severity: determineSeverity(error),
  };

  try {
    // Send to error tracking service
    await $fetch('/api/errors', {
      method: 'POST',
      body: JSON.stringify(report),
    });
  } catch (reportingError) {
    console.error('Failed to report error:', reportingError);
  }
};

const determineSeverity = (error: Error): 'low' | 'medium' | 'high' | 'critical' => {
  if (error instanceof AuthenticationError) return 'high';
  if (error instanceof NetworkError) return 'medium';
  if (error instanceof BusinessLogicError) return 'low';
  return 'medium';
};
```

## Component Error Handling

### Error States in Components

```vue
<template>
  <div class="user-form">
    <!-- Error display -->
    <v-alert
      v-if="error"
      type="error"
      :title="errorTitle"
      :text="errorMessage"
      closable
      @click:close="clearError"
    />
    
    <!-- Form content -->
    <v-form
      :loading="loading"
      @submit.prevent="handleSubmit"
    >
      <v-text-field
        v-model="formData.email"
        label="Email"
        :error-messages="emailError"
        :disabled="loading"
      />
      
      <v-text-field
        v-model="formData.password"
        label="Password"
        type="password"
        :error-messages="passwordError"
        :disabled="loading"
      />
      
      <v-btn
        type="submit"
        :loading="loading"
        :disabled="loading || !isFormValid"
        color="primary"
      >
        Login
      </v-btn>
    </v-form>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/AuthStore';

const authStore = useAuthStore();
const { loading, error } = storeToRefs(authStore);

const formData = ref({
  email: '',
  password: '',
});

const errorTitle = computed(() => {
  if (!error.value) return '';
  
  if (error.value instanceof AuthenticationError) {
    return 'Authentication Failed';
  }
  
  return 'Error';
});

const errorMessage = computed(() => {
  if (!error.value) return '';
  return error.value.message;
});

const emailError = computed(() => {
  if (!error.value || !(error.value instanceof ValidationError)) return '';
  if (error.value.field === 'email') return error.value.message;
  return '';
});

const passwordError = computed(() => {
  if (!error.value || !(error.value instanceof ValidationError)) return '';
  if (error.value.field === 'password') return error.value.message;
  return '';
});

const isFormValid = computed(() => {
  return formData.value.email.includes('@') && formData.value.password.length >= 8;
});

const handleSubmit = async () => {
  try {
    await authStore.login(formData.value);
    // Navigation handled by store
  } catch (error) {
    // Error already handled by store
    console.error('Login failed:', error);
  }
};

const clearError = () => {
  authStore.clearError();
};
</script>

<style scoped>
.user-form {
  max-width: 400px;
  margin: 0 auto;
  padding: 2rem;
}
</style>
```

## Async Error Handling

### Promise Error Handling

```typescript
// ✅ Good - Promise error handling with proper typing
const fetchUserData = async (userId: string): Promise<User> => {
  try {
    const response = await fetch(`/api/users/${userId}`);
    
    if (!response.ok) {
      throw new ApiError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status
      );
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new NetworkError('Network connection failed', undefined, true);
    }
    
    throw new Error(`Failed to fetch user data: ${error.message}`);
  }
};

// ✅ Good - Multiple async operations with error aggregation
const fetchMultipleUsers = async (userIds: string[]): Promise<User[]> => {
  const promises = userIds.map(id => 
    fetchUserData(id).catch(error => ({ id, error }))
  );
  
  const results = await Promise.allSettled(promises);
  
  const users: User[] = [];
  const errors: { id: string; error: Error }[] = [];
  
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      users.push(result.value);
    } else {
      errors.push({
        id: userIds[index],
        error: result.reason,
      });
    }
  });
  
  if (errors.length > 0) {
    console.error('Failed to fetch some users:', errors);
    // Optionally throw aggregated error
    throw new Error(`Failed to fetch ${errors.length} users`);
  }
  
  return users;
};
```

### Retry Logic

```typescript
// utils/retry.ts
interface RetryOptions {
  maxAttempts?: number;
  delay?: number;
  backoff?: 'linear' | 'exponential';
  shouldRetry?: (error: Error) => boolean;
}

export const withRetry = async <T>(
  operation: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> => {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoff = 'exponential',
    shouldRetry = (error) => true,
  } = options;

  let lastError: Error;
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('Unknown error');
      
      if (!shouldRetry(lastError) || attempt === maxAttempts) {
        throw lastError;
      }
      
      const waitTime = backoff === 'exponential' 
        ? delay * Math.pow(2, attempt - 1)
        : delay * attempt;
      
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw lastError!;
};

// Usage
const userData = await withRetry(
  () => fetchUserData(userId),
  {
    maxAttempts: 3,
    delay: 1000,
    shouldRetry: (error) => 
      error instanceof NetworkError || 
      (error instanceof ApiError && error.status >= 500),
  }
);
```

## Resources

- [Error Handling Best Practices](https://kentcdodds.com/blog/get-error-handling-right)
- [JavaScript Error Handling](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Control_flow_and_error_handling)
- [Vue Error Handling](https://vuejs.org/guide/components/edge-cases.html)
- [Promise Error Handling](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/catch)
- [TypeScript Error Handling](https://basarat.gitbooks.io/typescript/docs/quickstart/error-handling.html)
