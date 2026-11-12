---
trigger: always_on
---

# Clean Code Principles

## Overview

This document provides comprehensive guidelines for writing clean, maintainable, and robust code. It covers core principles like SOLID, DRY, KISS, and YAGNI, with practical examples for Vue 3, TypeScript, and modern JavaScript development.

## Core Values

Clean code should be:

| Characteristic   | Description                        | Why It Matters                |
| ---------------- | ---------------------------------- | ----------------------------- |
| **Clear**        | Easy to understand at first glance | Reduces cognitive load        |
| **Intuitive**    | Follows expected patterns          | Improves developer experience |
| **Reliable**     | Consistent behavior                | Builds trust in codebase      |
| **Maintainable** | Easy to modify and extend          | Reduces technical debt        |
| **Testable**     | Designed for testing               | Improves code quality         |

## SOLID Principles Applied to Vue/TypeScript

### Single Responsibility Principle (SRP)

Each component, composable, store, and function should have one reason to change.

```typescript
// ✅ Good - Single responsibility
const useUserAuthentication = () => {
  // Only handles authentication logic
  const login = async (credentials: Credentials) => { /* ... */ }
  const logout = async () => { /* ... */ }
  const isAuthenticated = computed(() => /* ... */)

  return { login, logout, isAuthenticated }
}

// ❌ Bad - Multiple responsibilities
const useUser = () => {
  // Authentication + UI state + data fetching = too many concerns
  const login = async (credentials: Credentials) => { /* ... */ }
  const setTheme = (theme: string) => { /* ... */ }
  const fetchUserProfile = async () => { /* ... */ }
  const showNotification = (message: string) => { /* ... */ }

  return { login, setTheme, fetchUserProfile, showNotification }
}
```

### Don't Repeat Yourself (DRY)

Extract repeated code into reusable functions, composables, or utilities.

```typescript
// ✅ Good - Store-based API calls
const userStore = useUserStore();
await userStore.fetchUsers();

// ✅ Better - Extracted reusable logic in store
const useApiCall = () => {
  const loading = ref(false);
  const error = ref<Error | null>(null);

  const execute = async <T>(apiCall: () => Promise<T>): Promise<T | null> => {
    loading.value = true;
    error.value = null;

    try {
      const result = await apiCall();
      return result;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error("Unknown error");
      return null;
    } finally {
      loading.value = false;
    }
  };

  return { loading, error, execute };
};
```

### Keep It Simple, Stupid (KISS)

Prefer simple solutions over complex ones. Avoid over-engineering.

```typescript
// ✅ Good - Store-based API calls
const userStore = useUserStore();
const users = await userStore.fetchUsers();
```

### You Ain't Gonna Need It (YAGNI)

Don't implement features until they're actually needed.

```typescript
// ✅ Good - Implement only what's needed now
// interfaces/user.ts
export interface User {
  id: string;
  name: string;
  email: string;
}
```

### Delete Code > Create Code

Prefer deleting code over creating code. Simpler solutions often emerge from removing unnecessary complexity.

> "One of my most productive days was when I threw away 1,000 lines of code." — Ken Thompson

```typescript
// ❌ Bad - Adding more code to solve a problem
function processUser(user: User) {
  if (user.isActive) {
    if (user.hasPermission) {
      if (user.isVerified) {
        // ... 50 more lines
      }
    }
  }
}

// ✅ Good - Delete unnecessary checks by simplifying logic
function processUser(user: User) {
  if (!user.canProcess) return;
  // ... simplified logic
}
```

## Additional Clean Code Guidelines

### Prefer Explicit Over Implicit

Make your code's intent clear through explicit naming and structure.

```typescript
// ❌ Implicit - Unclear what this does
const data = await getData();
const result = data.filter(x => x > 5).map(x => x * 2);

// ✅ Explicit - Clear intent
const userScores = await fetchUserScores();
const doubledHighScores = userScores
  .filter(score => score.value > passingThreshold)
  .map(score => score.value * 2);
```

### Keep Functions Small

Functions should do one thing and do it well.

```typescript
// ❌ Too large - Multiple responsibilities
function processOrder(order: Order) {
  // Validate order
  if (!order.items || order.items.length === 0) {
    throw new Error("Order has no items");
  }
  
  // Calculate total
  let total = 0;
  for (const item of order.items) {
    total += item.price * item.quantity;
  }
  
  // Apply tax
  total *= 1.08;
  
  // Save to database
  const savedOrder = await database.save(order);
  
  // Send confirmation email
  await emailService.sendConfirmation(order.customerEmail, savedOrder.id);
  
  return savedOrder;
}

// ✅ Small functions - Single responsibility
function validateOrder(order: Order): void {
  if (!order.items || order.items.length === 0) {
    throw new Error("Order has no items");
  }
}

function calculateOrderTotal(items: OrderItem[]): number {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

function applyTax(amount: number, rate: number = 0.08): number {
  return amount * (1 + rate);
}

async function saveOrder(order: Order): Promise<Order> {
  return await database.save(order);
}

async function sendOrderConfirmation(email: string, orderId: string): Promise<void> {
  await emailService.sendConfirmation(email, orderId);
}

// Main function orchestrates the small functions
async function processOrder(order: Order): Promise<Order> {
  validateOrder(order);
  
  const subtotal = calculateOrderTotal(order.items);
  const total = applyTax(subtotal);
  
  const orderWithTotal = { ...order, total };
  const savedOrder = await saveOrder(orderWithTotal);
  
  await sendOrderConfirmation(order.customerEmail, savedOrder.id);
  
  return savedOrder;
}
```

### Meaningful Names

Use names that describe the purpose and context of the code.

```typescript
// ❌ Poor names
const d = new Date();
const temp = user.name;
const flag = true;
const data = await getData();

// ✅ Good names
const currentDate = new Date();
const userName = user.name;
const isAuthenticated = true;
const userProfiles = await fetchUserProfiles();
```

### Avoid Magic Numbers and Strings

Replace magic values with named constants.

```typescript
// ❌ Magic numbers
if (user.age > 65) {
  applyDiscount();
}

if (status === "active") {
  enableFeatures();
}

// ✅ Named constants
const RETIREMENT_AGE = 65;
const ACTIVE_STATUS = "active";

if (user.age > RETIREMENT_AGE) {
  applyDiscount();
}

if (status === ACTIVE_STATUS) {
  enableFeatures();
}
```

### Consistent Error Handling

Handle errors consistently throughout your codebase.

```typescript
// ❌ Inconsistent error handling
async function fetchUser(id: string) {
  try {
    return await api.get(`/users/${id}`);
  } catch (error) {
    console.log(error); // Sometimes console.log
    return null; // Sometimes return null
  }
}

async function updateUser(id: string, data: any) {
  try {
    return await api.patch(`/users/${id}`, data);
  } catch (error) {
    throw new Error("Update failed"); // Sometimes throw
  }
}

// ✅ Consistent error handling
const handleApiError = (error: unknown, context: string): never => {
  const errorMessage = error instanceof Error ? error.message : "Unknown error";
  console.error(`API Error in ${context}:`, error);
  throw new Error(`${context} failed: ${errorMessage}`);
};

async function fetchUser(id: string): Promise<User> {
  try {
    return await api.get(`/users/${id}`);
  } catch (error) {
    handleApiError(error, "fetchUser");
  }
}

async function updateUser(id: string, data: any): Promise<User> {
  try {
    return await api.patch(`/users/${id}`, data);
  } catch (error) {
    handleApiError(error, "updateUser");
  }
}
```

## Resources

- [Clean Code by Robert C. Martin](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350884)
- [The Pragmatic Programmer](https://www.amazon.com/Pragmatic-Programmer-journey-mastery-Anniversary/dp/0135957052)
- [Refactoring by Martin Fowler](https://www.amazon.com/Refactoring-Improving-Existing-Addison-Wesley/dp/0201485672)
