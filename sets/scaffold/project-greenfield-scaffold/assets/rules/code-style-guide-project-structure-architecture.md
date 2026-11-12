---
trigger: always_on
---

# Project Structure & Architecture

## Overview

This document defines the architectural patterns and project structure for the application. It covers directory organization, import patterns, module boundaries, and dependency management to create a scalable, maintainable, and well-organized codebase.

## File Organization

### Component Files

Use PascalCase for component file names (e.g., `UserProfile.vue`, `DataTable.vue`)

### Directory Structure

Organize by feature, not by type:

```
components/
├── Auth/
│   ├── LoginForm.vue
│   ├── RegisterForm.vue
│   └── PasswordReset.vue
├── User/
│   ├── UserProfile.vue
│   ├── UserList.vue
│   └── UserCard.vue
├── Areas/
│   ├── Popup.vue
│   ├── List.vue
│   └── CreateForm.vue
└── Common/
    ├── Header.vue
    ├── Footer.vue
    ├── LoadingSpinner.vue
    └── ErrorBoundary.vue
```

### Feature-Based Organization

Group related files together:

```
features/
├── authentication/
│   ├── components/
│   │   ├── LoginForm.vue
│   │   └── RegisterForm.vue
│   ├── composables/
│   │   └── useAuth.ts
│   ├── stores/
│   │   └── AuthStore.ts
│   └── types/
│       └── auth.ts
├── users/
│   ├── components/
│   │   ├── UserList.vue
│   │   └── UserCard.vue
│   ├── composables/
│   │   └── useUsers.ts
│   ├── stores/
│   │   └── UserStore.ts
│   └── types/
│       └── user.ts
└── areas/
    ├── components/
    │   ├── AreaList.vue
    │   └── AreaCard.vue
    ├── composables/
    │   └── useAreas.ts
    ├── stores/
    │   └── AreaStore.ts
    └── types/
        └── area.ts
```

## Import Patterns

### Import Order

1. External libraries → Internal modules → Vue-specific imports
2. Use relative imports with `@/` alias for internal modules
3. Use `import type` for TypeScript-only imports

```typescript
// ✅ Correct import order
import { ref, computed, onMounted } from "vue";
import { defineStore } from "pinia";
import { authClient } from "@/lib/auth-client";
import { useAppStore } from "@/stores/AppStore";
import { formatCurrency } from "@/utils/formatters";
import type { UserPreferences } from "@/interfaces/user";
import type { LoadingState } from "@/types/user";
import type { ComponentProps } from "@/interfaces/component";
```

### Import Best Practices

```typescript
// ✅ Good - Grouped and ordered imports
// Vue imports
import { ref, computed, onMounted, watch } from "vue";

// Third-party libraries
import { z } from "zod";
import { format } from "date-fns";

// Internal stores
import { useAppStore } from "@/stores/AppStore";
import { useUserStore } from "@/stores/UserStore";

// Internal composables
import { useApiCall } from "@/composables/useApiCall";
import { useValidation } from "@/composables/useValidation";

// Internal utilities
import { formatCurrency, formatDate } from "@/utils/formatters";
import { validateEmail } from "@/utils/validators";

// Type-only imports
import type { User } from "@/interfaces/user";
import type { ApiResponse } from "@/interfaces/api";
import type { VForm } from "vuetify/components";

// ❌ Bad - Unorganized imports
import { ref } from "vue";
import { useAppStore } from "@/stores/AppStore";
import { computed } from "vue";
import { formatCurrency } from "@/utils/formatters";
import type { User } from "@/interfaces/user";
import { onMounted } from "vue";
import { validateEmail } from "@/utils/validators";
```

## Directory Structure

### Root Level Organization

```
project-root/
├── .windsurf/                 # BMAD configuration
│   ├── rules/                 # Code style guides
│   ├── skills/                # BMAD skills
│   └── workflows/             # BMAD workflows
├── assets/                    # Static assets
│   ├── styles/                # Global styles
│   │   ├── global.scss
│   │   └── settings.scss
│   └── images/                # Images and icons
├── components/                # Vue components
├── composables/               # Vue composables
├── constants/                 # Application constants
├── interfaces/                # TypeScript interfaces
├── layouts/                   # Nuxt layouts
├── middleware/                # Nuxt middleware
├── pages/                     # Nuxt pages
├── plugins/                   # Nuxt plugins
├── server/                    # Backend code
│   ├── api/                  # API routes
│   ├── auth/                 # Authentication
│   └── db/                   # Database configuration
├── stores/                    # Pinia stores
├── tests/                     # Test files
├── types/                     # TypeScript types
├── utils/                     # Utility functions
└── public/                    # Public static files
```

### Server-Side Organization

```
server/
├── api/                       # API route definitions
│   ├── users/
│   │   ├── routes.ts
│   │   └── schemas.ts
│   ├── auth/
│   │   ├── routes.ts
│   │   └── schemas.ts
│   └── areas/
│       ├── routes.ts
│       └── schemas.ts
├── auth/                      # Authentication logic
│   ├── index.ts
│   └── routes.ts
├── db/                        # Database configuration
│   ├── index.ts
│   ├── model.ts
│   └── schema.ts
└── middleware/                # Server middleware
    ├── auth.ts
    └── error-handler.ts
```

### Client-Side Organization

```
src/
├── components/                 # Reusable components
├── composables/               # Reusable logic
├── interfaces/                 # TypeScript interfaces
│   ├── api.ts                # API response types
│   ├── user.ts               # User-related types
│   ├── component.ts          # Component prop types
│   └── ui.ts                 # UI state types
├── stores/                     # Pinia stores
├── utils/                      # Utility functions
│   ├── formatters.ts         # Data formatting
│   ├── validators.ts         # Validation functions
│   └── constants.ts          # Application constants
├── types/                      # Additional types
└── constants/                  # Application constants
```

## Architecture Patterns

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Pages     │  │ Components  │  │   Layouts   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Business Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Composables │  │   Stores    │  │  Services    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │    API     │  │ Interfaces  │  │    Utils    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
Component Structure:
┌─────────────────────────────────────────┐
│           Template                 │
│  ┌─────────────────────────────┐    │
│  │        HTML/Template        │    │
│  │     Vuetify Components    │    │
│  │     Custom Components      │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│           Script                  │
│  ┌─────────────────────────────┐    │
│  │     Composition API        │    │
│  │   - Reactive State       │    │
│  │   - Computed Properties   │    │
│  │   - Methods             │    │
│  │   - Lifecycle Hooks      │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│           Style                   │
│  ┌─────────────────────────────┐    │
│  │        Scoped CSS          │    │
│  │     BEM Classes          │    │
│  │   Vuetify Overrides      │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Module Boundaries

### Clear Separation of Concerns

```typescript
// ✅ Good - Each module has clear responsibility
// interfaces/user.ts - Data contracts
export interface User {
  id: string;
  name: string;
  email: string;
}

// stores/UserStore.ts - State management
export const useUserStore = defineStore("user", () => {
  const users = ref<User[]>([]);
  const fetchUsers = async () => {
    // API calls and state management
  };
  return { users, fetchUsers };
});

// composables/useUserData.ts - Business logic
export const useUserData = (userId: string) => {
  const userStore = useUserStore();
  const user = computed(() => userStore.getUserById(userId));
  return { user };
};

// components/UserCard.vue - Presentation
<template>
  <div>{{ user.name }}</div>
</template>
```

### Dependency Flow

```
┌─────────────────────────────────────────────────────┐
│                 Pages                           │
│                    │                            │
│                    ▼                            │
│              Components                        │
│                    │                            │
│                    ▼                            │
│             Composables                        │
│                    │                            │
│                    ▼                            │
│               Stores                           │
│                    │                            │
│                    ▼                            │
│                 API Layer                        │
└─────────────────────────────────────────────────────┘
```

## File Naming Conventions

### Component Files

```
components/
├── Auth/                          # Feature directory
│   ├── LoginForm.vue               # PascalCase, descriptive
│   ├── RegisterForm.vue
│   └── PasswordReset.vue
├── User/
│   ├── UserProfile.vue             # Entity + action/purpose
│   ├── UserList.vue
│   └── UserCard.vue
└── Common/
    ├── Header.vue                  # Generic components
    ├── Footer.vue
    └── LoadingSpinner.vue
```

### Utility Files

```
utils/
├── formatters.ts                   # camelCase, plural for related functions
├── validators.ts
├── constants.ts
├── helpers.ts
└── api/
    ├── client.ts
    └── types.ts
```

### Type Files

```
interfaces/
├── user.ts                        # Singular, lowercase
├── product.ts
├── order.ts
├── api.ts                         # API-related types
├── component.ts                   # Component prop types
└── ui.ts                         # UI state types

types/
├── global.d.ts                    # Global type declarations
├── env.d.ts                      # Environment types
└── api.d.ts                      # API response types
```

## Import Path Strategies

### Absolute Imports with @ Alias

```typescript
// ✅ Good - Use @ alias for clean imports
import { User } from "@/interfaces/user";
import { useUserStore } from "@/stores/UserStore";
import { LoginForm } from "@/components/Auth/LoginForm";
import { formatCurrency } from "@/utils/formatters";

// ❌ Bad - Long relative paths
import { User } from "../../../../interfaces/user";
import { useUserStore } from "../../../stores/UserStore";
import { LoginForm } from "../Auth/LoginForm";
import { formatCurrency } from "../../utils/formatters";
```

### Index Files for Barrel Exports

```typescript
// interfaces/index.ts - Barrel export
export * from "./user";
export * from "./product";
export * from "./order";
export * from "./api";
export * from "./component";
export * from "./ui";

// Usage
import { User, Product, Order, ApiResponse, ComponentProps, UIState } from "@/interfaces";
```

## Architecture Guidelines

### Single Responsibility Principle

Each file, module, and component should have one clear responsibility:

```typescript
// ✅ Good - Single responsibility per file
// stores/UserStore.ts - Only state management
export const useUserStore = defineStore("user", () => {
  const users = ref<User[]>([]);
  const loading = ref(false);
  
  const fetchUsers = async () => {
    // Only API calls and state updates
  };
  
  return { users, loading, fetchUsers };
});

// composables/useUserData.ts - Only business logic
export const useUserData = (userId: string) => {
  const userStore = useUserStore();
  
  const user = computed(() => userStore.getUserById(userId));
  const updateProfile = async (data: Partial<User>) => {
    // Only business logic, no direct API calls
    await userStore.updateUser(userId, data);
  };
  
  return { user, updateProfile };
});
```

### Dependency Inversion

Depend on abstractions, not concretions:

```typescript
// ✅ Good - Depend on interfaces
interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

class UserService {
  constructor(private userRepository: UserRepository) {}
  
  async getUser(id: string): Promise<User | null> {
    return this.userRepository.findById(id);
  }
}

// ❌ Bad - Depend on concrete implementations
class UserService {
  constructor(private postgresRepository: PostgresUserRepository) {}
  
  async getUser(id: string): Promise<User | null> {
    return this.postgresRepository.findById(id);
  }
}
```

### Configuration Management

Centralize configuration in dedicated files:

```typescript
// config/api.ts
export const API_CONFIG = {
  BASE_URL: process.env.API_BASE_URL || "https://api.example.com/v1",
  TIMEOUT: 30000,
  RETRY_ATTEMPTS: 3,
} as const;

// config/app.ts
export const APP_CONFIG = {
  NAME: "MyApp",
  VERSION: "1.0.0",
  ENVIRONMENT: process.env.NODE_ENV || "development",
} as const;

// Usage
import { API_CONFIG } from "@/config/api";
import { APP_CONFIG } from "@/config/app";
```

## Resources

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob-clean-architecture/)
- [Vue.js Style Guide](https://vuejs.org/style-guide/)
- [Nuxt.js Directory Structure](https://nuxt.com/docs/getting-started/directory-structure)
- [TypeScript Handbook: Modules](https://www.typescriptlang.org/docs/handbook/modules.html)
- [Pattern: Feature-First Structure](https://kentcdodds.com/blog/application-structure-feature-first/)
