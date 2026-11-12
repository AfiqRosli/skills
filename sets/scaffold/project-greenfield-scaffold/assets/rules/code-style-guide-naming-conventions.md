---
trigger: always_on
---

# Naming Conventions

## Overview

This document establishes consistent naming conventions across the entire codebase. It covers variables, functions, classes, files, CSS classes, database entities, and more. Following these conventions ensures code readability, maintainability, and developer productivity.

## Principles

- **Descriptive**: Names should reveal intent
- **Pronounceable**: Names should be readable
- **Searchable**: Names should be easy to find
- **Consistent**: Follow conventions

## Variable Naming

### Good Practices

```typescript
// ✅ Good
const currentDate = new Date();
const userName = user.name;
const isAuthenticated = user.isActive;
const hasPermission = user.canEdit;
const shouldShowModal = isVisible && !isDismissed;

// ❌ Bad
const d = new Date();
const temp = user.name;
const flag = true;
const data = fetchData();
const val = calculateValue();
```

### Use Meaningful Names

```typescript
// ❌ Vague names
const data = await fetchUsers();
const result = processItems(data);
const output = formatDisplay(result);

// ✅ Descriptive names
const users = await fetchUsers();
const processedItems = processItems(users);
const displayData = formatDisplay(processedItems);
```

## Boolean Naming

Use prefixes that clearly indicate boolean nature:

### Preferred Prefixes

- `is` - for state or conditions
- `has` - for possession or presence
- `should` - for recommendations or actions
- `can` - for capabilities or permissions
- `are` - for plural boolean checks

```typescript
// ✅ Good (is/has/should/can/are)
const isActive = true;
const hasPermission = false;
const shouldRefresh = true;
const canEdit = user.role === 'admin';
const areItemsLoaded = items.length > 0;

// ❌ Bad
const flag = true;
const active = true; // Missing prefix
const permission = false; // Missing prefix
const refresh = true; // Ambiguous - could be action or state
```

## Function Naming

### Verb-Noun Pattern

Functions should start with a verb describing what they do:

```typescript
// ✅ Good
function calculateTotal(items: CartItem[]): number
function getUserById(id: string): User | null
function validateEmail(email: string): boolean
function renderUserProfile(user: User): void
function sendWelcomeEmail(email: string): Promise<void>

// ❌ Bad
function total(items: CartItem[]): number
function user(id: string): User | null
function email(email: string): boolean
function profile(user: User): void
function welcome(email: string): Promise<void>
```

### Async Functions

Prefix async functions with clear action indicators:

```typescript
// ✅ Good
async function fetchUsers(): Promise<User[]>
async function saveUser(user: User): Promise<User>
async function deleteAccount(id: string): Promise<void>
async function loadUserProfile(): Promise<UserProfile>

// ❌ Bad
async function users(): Promise<User[]>
async function user(user: User): Promise<User>
async function remove(id: string): Promise<void>
async function profile(): Promise<UserProfile>
```

## Class and Interface Naming

### PascalCase for Types

```typescript
// ✅ Good
class UserService {}
class OrderProcessor {}
class EmailValidator {}
interface UserProfile {}
type LoadingState = 'idle' | 'loading' | 'success' | 'error';

// ❌ Bad
class userService {}
class orderprocessor {}
class emailvalidator {}
interface userprofile {}
type loadingstate = 'idle' | 'loading' | 'success' | 'error';
```

### Descriptive Class Names

```typescript
// ✅ Good - Clear purpose
class PaymentProcessor {}
class AuthenticationManager {}
class DataRepository {}
class EmailNotificationService {}

// ❌ Bad - Vague purpose
class Manager {}
class Processor {}
class Repository {}
class Service {}
```

## File Naming

### Component Files

- **Components**: PascalCase (`UserProfile.vue`, `DataTable.vue`)
- **Directory Structure**: Reflect component hierarchy

```
components/
├── Auth/
│   ├── LoginForm.vue
│   └── RegisterForm.vue
├── User/
│   ├── UserProfile.vue
│   └── UserList.vue
└── Common/
    ├── Header.vue
    └── Footer.vue
```

### Composable Files

- **Composables**: camelCase with `use` prefix (`useUserData.ts`, `useAuth.ts`)

```
composables/
├── useUserData.ts
├── useAuth.ts
├── useApiCall.ts
└── useValidation.ts
```

### Utility Files

- **Utilities**: camelCase (`formatters.ts`, `validators.ts`, `constants.ts`)

```
utils/
├── formatters.ts
├── validators.ts
├── constants.ts
└── helpers.ts
```

### Store Files

- **Stores**: PascalCase with `Store` suffix (`UserStore.ts`, `AppStore.ts`)

```
stores/
├── UserStore.ts
├── AppStore.ts
└── AuthStore.ts
```

### Interface Files

- **Interfaces**: PascalCase, singular (`user.ts`, `product.ts`)

```
interfaces/
├── user.ts
├── product.ts
├── order.ts
└── api.ts
```

## Constant Naming

### UPPER_SNAKE_CASE

```typescript
// ✅ Good
const API_BASE_URL = 'https://api.example.com/v1';
const MAX_RETRY_ATTEMPTS = 3;
const DEFAULT_PAGE_SIZE = 20;
const SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes

// ❌ Bad
const apiUrl = 'https://api.example.com/v1';
const maxRetries = 3;
const pageSize = 20;
const timeout = 30 * 60 * 1000;
```

### Group Related Constants

```typescript
// ✅ Good - Grouped by namespace
const API_ENDPOINTS = {
  USERS: '/users',
  ORDERS: '/orders',
  PRODUCTS: '/products',
} as const;

const HTTP_STATUS_CODES = {
  OK: 200,
  CREATED: 201,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
} as const;

// ❌ Bad - Scattered constants
const USERS_ENDPOINT = '/users';
const ORDERS_ENDPOINT = '/orders';
const PRODUCTS_ENDPOINT = '/products';
const OK_STATUS = 200;
const CREATED_STATUS = 201;
```

## Enum Naming

### PascalCase for Enums

```typescript
// ✅ Good
enum UserRole {
  ADMIN = 'admin',
  USER = 'user',
  GUEST = 'guest',
}

enum LoadingState {
  IDLE = 'idle',
  LOADING = 'loading',
  SUCCESS = 'success',
  ERROR = 'error',
}

enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PUT = 'PUT',
  DELETE = 'DELETE',
}

// ❌ Bad
enum userRole {
  admin = 'admin',
  user = 'user',
  guest = 'guest',
}

enum loadingState {
  idle = 'idle',
  loading = 'loading',
  success = 'success',
  error = 'error',
}
```

## Event Naming

### camelCase for Events

```typescript
// ✅ Good
const USER_LOGIN_SUCCESS = 'userLoginSuccess';
const FORM_SUBMIT_ERROR = 'formSubmitError';
const DATA_LOADED = 'dataLoaded';
const MODAL_CLOSED = 'modalClosed';

// ❌ Bad
const user_login_success = 'user_login_success';
const form_submit_error = 'form_submit_error';
const data_loaded = 'data_loaded';
const modal_closed = 'modal_closed';
```

### Event Handler Naming

```typescript
// ✅ Good - Clear purpose
const handleUserLogin = (credentials: LoginCredentials) => { /* ... */ };
const handleFormSubmit = (formData: FormData) => { /* ... */ };
const handleModalClose = () => { /* ... */ };
const handleDataLoad = async () => { /* ... */ };

// ❌ Bad - Unclear purpose
const login = (credentials: LoginCredentials) => { /* ... */ };
const submit = (formData: FormData) => { /* ... */ };
const close = () => { /* ... */ };
const load = async () => { /* ... */ };
```

## CSS Class Naming

### BEM Methodology

```scss
// ✅ Good - BEM structure
.user-card {
  &__header {
    &--highlighted {
      background: var(--v-theme-primary);
    }
  }

  &__content {
    &__title {
      font-size: 1.2rem;
    }
  }

  &__footer {
    &__button {
      &--primary {
        background: var(--v-theme-primary);
      }
    }
  }
}

// ❌ Bad - Inconsistent naming
.userCard {
  .header-highlighted {
    background: var(--v-theme-primary);
  }

  .contentTitle {
    font-size: 1.2rem;
  }

  .footerButtonPrimary {
    background: var(--v-theme-primary);
  }
}
```

## Database Naming

### Table and Column Naming

```typescript
// ✅ Good - Consistent naming
export const users = pgTable("users", {
  id: text("id").primaryKey(),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  email: text("email").notNull().unique(),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const userProfiles = pgTable("user_profiles", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull().references(() => users.id),
  bio: text("bio"),
  avatar: text("avatar_url"),
});

// ❌ Bad - Inconsistent naming
export const Users = pgTable("Users", {
  ID: text("ID").primaryKey(),
  fname: text("fname").notNull(),
  lname: text("lname").notNull(),
  email_address: text("email_address").notNull().unique(),
  created_date: timestamp("created_date").defaultNow(),
  updated_date: timestamp("updated_date").defaultNow(),
});
```

## API Endpoint Naming

### RESTful Conventions

```typescript
// ✅ Good - RESTful patterns
GET    /api/users           // List all users
GET    /api/users/:id       // Get specific user
POST   /api/users           // Create new user
PUT    /api/users/:id       // Update user (replace)
PATCH  /api/users/:id       // Update user (partial)
DELETE /api/users/:id       // Delete user

// ✅ Good - Nested resources
GET    /api/users/:id/orders     // Get user's orders
POST   /api/users/:id/orders     // Create order for user

// ❌ Bad - Non-RESTful patterns
GET    /api/getAllUsers
POST   /api/createUser
PUT    /api/updateUser/:id
DELETE /api/removeUser/:id
GET    /api/userOrders/:userId
```

## Test Naming

### Test File Naming

```typescript
// ✅ Good - Clear what's being tested
UserCard.spec.ts
useUserData.spec.ts
UserService.test.ts
EmailValidator.test.ts

// ❌ Bad - Unclear purpose
user.spec.ts
data.spec.ts
service.test.ts
util.test.ts
```

### Test Description Naming

```typescript
// ✅ Good - Descriptive test names
describe("UserCard", () => {
  it("renders user information correctly", () => {
    // Test implementation
  });

  it("emits edit event when edit button is clicked", async () => {
    // Test implementation
  });

  it("shows loading state when loading prop is true", () => {
    // Test implementation
  });
});

// ❌ Bad - Vague test names
describe("UserCard", () => {
  it("works", () => {
    // Test implementation
  });

  it("click", async () => {
    // Test implementation
  });

  it("loading", () => {
    // Test implementation
  });
});
```

## Git Naming

### Branch Naming

```bash
# ✅ Good - Descriptive branch names
feature/user-authentication
bugfix/login-validation-error
hotfix/security-vulnerability
refactor/user-service-optimization

# ❌ Bad - Unclear branch names
feat-auth
fix-login
hotfix-security
refactor-users
```

### Commit Message Naming

```bash
# ✅ Good - Conventional commits
feat: add user authentication system
fix: resolve login validation error
docs: update API documentation
refactor: optimize user service performance
test: add unit tests for user service

# ❌ Bad - Unclear commit messages
Added auth
Fixed login
Updated docs
Made users faster
Added tests
```

## Quick Reference

| Context | Convention | Examples |
|----------|-------------|-----------|
| Variables | camelCase, descriptive | `userName`, `isActive`, `hasPermission` |
| Booleans | is/has/should/can/are prefixes | `isLoading`, `hasError`, `shouldRefresh` |
| Functions | camelCase, verb-noun | `calculateTotal()`, `getUserById()`, `validateEmail()` |
| Classes | PascalCase, singular | `UserService`, `OrderProcessor`, `EmailValidator` |
| Interfaces | PascalCase, singular | `User`, `Product`, `Order` |
| Constants | UPPER_SNAKE_CASE | `API_BASE_URL`, `MAX_RETRY_ATTEMPTS` |
| Enums | PascalCase | `UserRole`, `LoadingState`, `HttpMethod` |
| Files | PascalCase for components, camelCase for utilities | `UserProfile.vue`, `useUserData.ts`, `formatters.ts` |
| CSS Classes | BEM methodology | `.user-card__header--highlighted` |
| Database | snake_case, plural tables | `users`, `user_profiles`, `order_items` |
| API Endpoints | RESTful, plural resources | `/api/users`, `/api/users/:id/orders` |
| Tests | *.spec.ts or *.test.ts | `UserCard.spec.ts`, `UserService.test.ts` |

## Resources

- [Clean Code Chapter 2: Meaningful Names](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350884)
- [Refactoring.com Naming](https://refactoring.guru/refactoring/naming)
- [JavaScript Naming Conventions](https://github.com/airbnb/javascript#naming-conventions)
- [TypeScript Handbook: Interfaces](https://www.typescriptlang.org/docs/handbook/2/interfaces.html)
