---
trigger: always_on
---

# TypeScript Patterns

## Overview

This document provides comprehensive TypeScript patterns and best practices for the application. It covers interface vs type usage, strict typing, advanced patterns, error handling, and backend type definitions to ensure type safety and developer productivity.

## Interface vs Type

### When to Use Interfaces

Use interfaces for object shapes that can be extended or implemented:

```typescript
// ✅ Use interfaces for object shapes (defined in interfaces/ directory)
// interfaces/user.ts
export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: Date;
}

export interface Product {
  id: string;
  name: string;
  price: number;
  category: ProductCategory;
}

// ✅ Interfaces can be extended
export interface AdminUser extends User {
  role: 'admin';
  permissions: string[];
}

// ✅ Interfaces can be implemented
export class UserService implements IUserService {
  async getUser(id: string): Promise<User> {
    // Implementation
  }
}
```

### When to Use Types

Use types for unions, computed types, or complex type expressions:

```typescript
// ✅ Use types for unions, computed types, or complex types
type UserRole = 'admin' | 'user' | 'guest';
type LoadingState = 'idle' | 'loading' | 'success' | 'error';
type UserWithRole = User & { role: UserRole };

// ✅ Types for function signatures
type EventHandler<T> = (event: T) => void;
type AsyncFunction<T, R> = (arg: T) => Promise<R>;

// ✅ Types for mapped types
type OptionalUser = {
  [K in keyof User]?: User[K];
};

type UserLabels = {
  [K in keyof User]: string;
};
```

### Generic Interfaces

Use generic interfaces for reusable type definitions:

```typescript
// ✅ Generic interfaces (defined in interfaces/ directory)
// interfaces/api.ts
export interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
  };
}

export interface FormField<T = any> {
  name: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'select';
  value: T;
  validation?: ValidationRule<T>[];
}
```

## Strict Typing

### When to Use `unknown` vs Specific Types

**Rule**: Use `unknown` only for third-party library integrations where type definitions are unavailable or intentionally generic. For all internal codebase code, use specific interfaces or types.

```typescript
// ✅ Good - Use unknown for third-party library event handlers
// Vuetify component events use unknown for flexibility
function handleIconClick(event: { id: unknown; value: boolean; path: unknown[] }) {
  focusItem(String(event.id));
}

// ✅ Good - Use unknown for type guards on external data
function isUser(obj: unknown): obj is User {
  return obj !== null && 
         typeof obj === 'object' &&
         'id' in obj &&
         'name' in obj &&
         'email' in obj;
}

// ✅ Good - Use unknown for error handling from external sources
try {
  const data = await externalApiCall();
} catch (error: unknown) {
  if (error instanceof Error) {
    console.error(error.message);
  }
}

// ❌ Bad - Using unknown for internal data structures
function processUserData(data: unknown) {
  // Should use specific interface instead
  const user = data as User;
}

// ✅ Good - Use specific interface for internal data
function processUserData(data: User) {
  console.log(data.name);
}
```

**Guidelines**:
- **Third-party libraries**: Use `unknown` when library types are generic or unavailable (e.g., Vuetify event handlers, external API responses)
- **Type guards**: Use `unknown` as parameter type for type guard functions
- **Error handling**: Use `unknown` for catch blocks from external sources
- **Internal code**: Always use specific interfaces or types defined in `interfaces/` directory
- **API responses**: Use Elysia's type inference or define interfaces in `interfaces/api.ts`

### Explicit Return Types

Always specify return types for functions:

```typescript
// ✅ Be explicit with types
const fetchUsers = async (): Promise<User[]> => {
  const { $api } = useNuxtApp();
  return await $api.get<User[]>('/users');
};

const calculateTotal = (items: CartItem[]): number => {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
};

// ❌ Avoid implicit any
const processData = (data) => {
  // data is implicitly any
  return data.map(item => item.value);
};
```

### Function Parameter Types

Type all function parameters:

```typescript
// ✅ Type function parameters
const processUser = (user: User): ProcessedUser => {
  return {
    fullName: `${user.name}`,
    emailDomain: user.email.split('@')[1],
  };
};

const updateUser = async (id: string, updates: Partial<User>): Promise<User> => {
  const { $api } = useNuxtApp();
  return await $api.patch<User>(`/users/${id}`, updates);
};
```

### Const Assertions

Use const assertions for literal types:

```typescript
// ✅ Use const assertions for literal types
const themes = ['light', 'dark', 'auto'] as const;
type Theme = (typeof themes)[number]; // 'light' | 'dark' | 'auto'

const httpMethods = ['GET', 'POST', 'PUT', 'DELETE'] as const;
type HttpMethod = (typeof httpMethods)[number];

// Usage
const currentTheme: Theme = 'dark';
const requestMethod: HttpMethod = 'POST';
```

## Advanced Type Patterns

### Discriminated Unions

Use discriminated unions for type-safe conditional logic:

```typescript
// ✅ Discriminated union for result types
type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };

const safeApiCall = async <T>(
  apiCall: () => Promise<T>,
): Promise<Result<T>> => {
  try {
    const data = await apiCall();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error : new Error('Unknown error'),
    };
  }
};

// Usage with type narrowing
const result = await safeApiCall(() => fetchUser('123'));

if (result.success) {
  // TypeScript knows result.data is User
  console.log(result.data.name);
} else {
  // TypeScript knows result.error is Error
  console.error(result.error.message);
}
```

### Utility Types

Create reusable utility types:

```typescript
// ✅ Common utility types
type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
type RequiredBy<T, K extends keyof T> = T & Required<Pick<T, K>>;

// ✅ Deep partial type
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

// ✅ Async function type
type AsyncFunction<T extends any[], R> = (...args: T) => Promise<R>;

// Usage
interface UpdateUserRequest {
  id: string;
  data: Optional<User, 'name' | 'email'>;
}
```

### Conditional Types

Use conditional types for dynamic type logic:

```typescript
// ✅ Conditional types
type NonNullable<T> = T extends null | undefined ? never : T;
type ArrayElement<T> = T extends (infer U)[] ? U : never;
type FirstParameter<T> = T extends (arg: infer U, ...args: any[]) => any ? U : never;

// Usage
type RequiredString = NonNullable<string>; // string
type UserArrayType = ArrayElement<User[]>; // User
type FirstArg = FirstParameter<(id: string, name: string) => void>; // string
```

## Error Handling Types

### Custom Error Classes

Create specific error types with type safety:

```typescript
// ✅ Create specific error types
class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ValidationError extends Error {
  constructor(
    message: string,
    public field: string,
    public value: unknown,
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

class AuthenticationError extends Error {
  constructor(
    message: string = 'Authentication failed',
    public code: 'INVALID_CREDENTIALS' | 'TOKEN_EXPIRED' | 'INSUFFICIENT_PERMISSIONS',
  ) {
    super(message);
    this.name = 'AuthenticationError';
  }
}
```

### Type Guards

Use type guards for runtime type checking:

```typescript
// ✅ Type guard functions
function isUser(obj: unknown): obj is User {
  return obj !== null && 
         typeof obj === 'object' &&
         'id' in obj &&
         'name' in obj &&
         'email' in obj;
}

function isApiError(error: unknown): error is ApiError {
  return error instanceof Error && error.name === 'ApiError';
}

// Usage
function processData(data: unknown) {
  if (isUser(data)) {
    // TypeScript knows data is User
    console.log(data.name);
  }
  
  if (isApiError(data)) {
    // TypeScript knows data is ApiError
    console.log(`API Error: ${data.status}`);
  }
}
```

## Interface Location

### Centralized Interface Management

**CRITICAL**: All interface definitions must be in the `interfaces/` directory. Do not define interfaces inline in components, composables, stores, or other files.

```typescript
// ❌ Bad - Interface defined inline in component
<script setup lang="ts">
interface User {
  id: string;
  name: string;
}
</script>

// ❌ Bad - Interface defined in composable
// composables/useUserData.ts
interface User {
  id: string;
  name: string;
}

// ✅ Good - Interface defined in interfaces/ directory
// interfaces/user.ts
export interface User {
  id: string;
  name: string;
  email: string;
}

// ✅ Good - Import from interfaces/ directory
<script setup lang="ts">
import type { User } from '@/interfaces/user';
</script>
```

### Interface Organization

Organize interfaces by domain or purpose:

```typescript
// interfaces/user.ts - User-related interfaces
export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: Date;
}

export interface CreateUserRequest {
  name: string;
  email: string;
  password: string;
}

export interface UpdateUserRequest {
  name?: string;
  email?: string;
}

// interfaces/api.ts - API-related interfaces
export interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
  };
}

// interfaces/component.ts - Component-related interfaces
export interface BaseComponentProps {
  id?: string;
  class?: string;
}

export interface FormComponentProps extends BaseComponentProps {
  modelValue: any;
  rules?: ValidationRule[];
}
```

## Generic Naming

### Type Parameter Naming

Use descriptive single letters or descriptive names:

```typescript
// ✅ Good - Descriptive single letters
interface ApiResponse<T> {
  data: T;
  status: number;
}

interface Repository<T, K = string> {
  findById(id: K): Promise<T | null>;
  save(entity: T): Promise<T>;
}

// ✅ Good - Descriptive names for complex generics
interface UserRepository<TUser, TId = string> {
  findById(id: TId): Promise<TUser | null>;
  save(user: TUser): Promise<TUser>;
}

// ❌ Bad - Vague single letters
interface ApiResponse<X> {
  data: X;
  status: number;
}

interface Repository<A, B = string> {
  findById(id: B): Promise<A | null>;
  save(entity: A): Promise<A>;
}
```

### Constraint Types

Use constraint types to restrict generic parameters:

```typescript
// ✅ Good - Use constraint types
interface Identifiable {
  id: string;
}

interface Repository<T extends Identifiable> {
  findById(id: string): Promise<T | null>;
  delete(entity: T): Promise<void>;
}

interface ValidatedForm<T extends Record<string, any>> {
  data: T;
  errors: Partial<Record<keyof T, string>>;
}

// ✅ Good - Keyof constraints
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

// Usage
const userName = getProperty(user, 'name'); // Type-safe property access
```

## Backend Type Definitions

### Database Schema Types

- **Schema**: Database schemas defined in `server/db/schema.ts` using Drizzle ORM
- **Models**: Database models accessed through `server/db/model.ts`
- **API Types**: Elysia automatically provides type safety for API endpoints

```typescript
// server/db/schema.ts (Backend only)
export const users = pgTable('users', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  // ... other fields
});

export const areas = pgTable('areas', {
  id: uuid('id').primaryKey().defaultRandom(),
  title: text('title'),
  description: text('description'),
  // ... other fields
});

// server/db/model.ts (Backend only)
export const model = {
  insert: spreads(
    {
      users: table.users,
      areas: table.areas,
      // ... other tables
    },
    'insert',
  ),
  select: spreads(
    {
      users: table.users,
      areas: table.areas,
      // ... other tables
    },
    'select',
  ),
} as const;
```

### Type Usage Guidelines

- **API Responses**: Use backend schema types directly through Elysia's type inference
- **Client State**: Use client-side interfaces for UI state, forms, and local data
- **Shared Data**: Let Elysia handle type safety between client and server
- **No Duplication**: Avoid redefining backend types on the client side

## Type-Only Imports

### Import Type Only

Use `import type` for TypeScript-only imports to avoid runtime overhead:

```typescript
// ✅ Good - Type-only imports
import type { User } from '@/interfaces/user';
import type { ApiResponse } from '@/interfaces/api';
import type { VForm } from 'vuetify/components';

// ❌ Bad - Regular imports for types only
import { User } from '@/interfaces/user';
import { ApiResponse } from '@/interfaces/api';
import { VForm } from 'vuetify/components';
```

### Mixed Imports

Separate type and runtime imports:

```typescript
// ✅ Good - Separate type and runtime imports
import type { User } from '@/interfaces/user';
import { userService } from '@/services/user';

// ❌ Bad - Mixed imports
import { User, userService } from '@/services/user';
```

## Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [TypeScript Deep Dive](https://basarat.gitbooks.io/typescript/content/)
- [Effective TypeScript](https://effectivetypescript.com/)
- [TypeScript Utility Types](https://www.typescriptlang.org/docs/handbook/utility-types.html)
