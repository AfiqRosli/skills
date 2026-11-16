# Code Formatting & Organization

## Overview

This document provides comprehensive guidelines for code formatting, file organization, and structural patterns. It covers vertical formatting, import organization, function structure, and comment standards to ensure consistent, readable, and maintainable code across the entire project.

## Vertical Formatting

Code should read top-to-bottom. Related functions should be close vertically.

### Function Organization

```typescript
// ✅ Good - Related functions grouped (high-level to low-level)
function calculateOrderTotal(items: CartItem[], taxRate: number): number {
  const subtotal = calculateTotal(items);
  return applyTax(subtotal, taxRate);
}

function calculateTotal(items: CartItem[]): number {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

function applyTax(total: number, taxRate: number): number {
  return total * (1 + taxRate);
}

// ✅ Good - Public interface first, private implementation after
export class UserService {
  // Public methods
  async createUser(userData: CreateUserRequest): Promise<User> {
    const validatedUser = this.validateUserData(userData);
    return await this.saveUser(validatedUser);
  }

  async getUserById(id: string): Promise<User | null> {
    return await this.userRepository.findById(id);
  }

  // Private methods
  private validateUserData(userData: CreateUserRequest): CreateUserRequest {
    // Validation logic
    return userData;
  }

  private async saveUser(user: CreateUserRequest): Promise<User> {
    // Database save logic
    return await this.userRepository.save(user);
  }
}
```

### Conceptual Cohesion

Keep related concepts together:

```typescript
// ✅ Good - Related concepts grouped
class OrderProcessor {
  // Order calculation methods
  private calculateSubtotal(items: OrderItem[]): number { /* ... */ }
  private calculateTax(subtotal: number): number { /* ... */ }
  private calculateShipping(items: OrderItem[]): number { /* ... */ }
  
  // Order validation methods
  private validateItems(items: OrderItem[]): boolean { /* ... */ }
  private validateCustomer(customer: Customer): boolean { /* ... */ }
  private validateAddress(address: Address): boolean { /* ... */ }
  
  // Order processing methods
  private async processPayment(payment: Payment): Promise<PaymentResult> { /* ... */ }
  private async sendConfirmation(order: Order): Promise<void> { /* ... */ }
  private async updateInventory(items: OrderItem[]): Promise<void> { /* ... */ }
}
```

## File Organization Order

### Standard File Structure

1. Imports (external first, then internal)
2. Type definitions
3. Constants
4. State variables
5. Computed properties
6. Methods (grouped by functionality)
7. Lifecycle hooks
8. Exports

### Vue Component Structure

```vue
<script setup lang="ts">
// 1. Imports (external libraries, types, utilities)
import { ref, computed, onMounted, watch } from "vue";
import { useAppStore } from "@/stores/AppStore";
import { authClient } from "@/lib/auth-client";
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
const formData = ref<UserFormData>({
  name: "",
  email: "",
});

// 5. Computed properties
const user = computed(() => appStore.getUserById(props.userId));
const isCompact = computed(() => props.variant === "compact");
const isValid = computed(() => {
  return formData.value.name.trim() !== "" && 
         formData.value.email.includes("@");
});

// 6. Methods (grouped by functionality)
// Form handlers
function handleSubmit() { /* ... */ }
function handleReset() { /* ... */ }

// API calls
async function saveUser() { /* ... */ }
async function loadUserData() { /* ... */ }

// Utility methods
function validateForm(): boolean { /* ... */ }
function resetForm(): void { /* ... */ }

// 7. Lifecycle hooks
onMounted(() => {
  loadUserData();
});

watch(() => props.userId, (newUserId) => {
  if (newUserId) {
    loadUserData();
  }
});

// 8. Exports (if needed)
export { type UserFormData };
</script>

<template>
  <!-- Template content -->
</template>

<style scoped>
/* Component styles */
</style>
```

### Composable Structure

```typescript
// composables/useUserData.ts
// 1. Imports
import { ref, computed, watch, readonly } from "vue";
import type { User } from "@/interfaces/user";
import type { UseUserDataOptions, UseUserDataReturn } from "@/interfaces/composable";

// 2. Type definitions (if not in interfaces/)
export interface UseUserDataOptions {
  autoFetch?: boolean;
  cacheTime?: number;
}

export interface UseUserDataReturn {
  user: Readonly<Ref<User | null>>;
  loading: Readonly<Ref<boolean>>;
  error: Readonly<Ref<Error | null>>;
  refresh: () => Promise<void>;
}

// 3. Main composable function
export const useUserData = (
  userId: MaybeRef<string>,
  options: UseUserDataOptions = {},
): UseUserDataReturn => {
  // 4. State
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref<Error | null>(null);
  const lastFetched = ref<number | null>(null);

  // 5. Computed
  const isExpired = computed(() => {
    if (!lastFetched.value) return true;
    return Date.now() - lastFetched.value > (options.cacheTime || 300000);
  });

  const isValid = computed(() => user.value !== null && !isExpired.value);

  // 6. Methods
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

  // 7. Auto-fetch logic
  if (options.autoFetch) {
    watchEffect(() => {
      const userIdValue = unref(userId);
      if (userIdValue && (!user.value || isExpired.value)) {
        fetchUser();
      }
    });
  }

  // 8. Return
  return {
    user: readonly(user),
    loading: readonly(loading),
    error: readonly(error),
    isValid,
    refresh: fetchUser,
  };
};
```

### Store Structure

```typescript
// stores/UserStore.ts
// 1. Imports
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { User, CreateUserRequest } from "@/interfaces/user";
import type { UIState } from "@/interfaces/ui";

// 2. Store definition
export const useUserStore = defineStore("user", () => {
  // 3. State
  const users = ref<User[]>([]);
  const currentUser = ref<User | null>(null);
  const uiState = ref<UIState>({ loading: false, error: null });

  // 4. Getters (computed)
  const userCount = computed(() => users.value.length);
  const isEmpty = computed(() => users.value.length === 0);
  const isAuthenticated = computed(() => currentUser.value !== null);

  // 5. Actions (grouped by functionality)
  // User management actions
  async function fetchUsers() {
    uiState.value.loading = true;
    uiState.value.error = null;

    try {
      const { $api } = useNuxtApp();
      const data = await $api.get<User[]>("/users");
      users.value = data;
    } catch (e) {
      uiState.value.error = e instanceof Error ? e.message : "Failed to fetch users";
      throw uiState.value.error;
    } finally {
      uiState.value.loading = false;
    }
  }

  async function createUser(userData: CreateUserRequest) {
    uiState.value.loading = true;
    uiState.value.error = null;

    try {
      const { $api } = useNuxtApp();
      const newUser = await $api.post<User>("/users", userData);
      users.value.push(newUser);
      return newUser;
    } catch (e) {
      uiState.value.error = e instanceof Error ? e.message : "Failed to create user";
      throw uiState.value.error;
    } finally {
      uiState.value.loading = false;
    }
  }

  // Current user actions
  async function login(credentials: LoginCredentials) {
    uiState.value.loading = true;
    uiState.value.error = null;

    try {
      const { $api } = useNuxtApp();
      const user = await $api.post<User>("/auth/login", credentials);
      currentUser.value = user;
      return user;
    } catch (e) {
      uiState.value.error = e instanceof Error ? e.message : "Login failed";
      throw uiState.value.error;
    } finally {
      uiState.value.loading = false;
    }
  }

  function logout() {
    currentUser.value = null;
    // Clear any stored tokens
    localStorage.removeItem("authToken");
  }

  // 6. Return
  return {
    // State
    users,
    currentUser,
    uiState,
    
    // Getters
    userCount,
    isEmpty,
    isAuthenticated,
    
    // Actions
    fetchUsers,
    createUser,
    login,
    logout,
  };
});

// 7. Hot Module Replacement
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useUserStore, import.meta.hot));
}
```

## Import Organization

### Import Order

1. External libraries (Vue, Pinia, etc.)
2. Internal modules (stores, composables, utilities)
3. Type-only imports

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

### Type-Only Imports

Use `import type` for TypeScript-only imports:

```typescript
// ✅ Good - Type-only imports
import type { User } from "@/interfaces/user";
import type { ApiResponse } from "@/interfaces/api";
import type { VForm } from "vuetify/components";

// ❌ Bad - Regular imports for types only
import { User } from "@/interfaces/user";
import { ApiResponse } from "@/interfaces/api";
import { VForm } from "vuetify/components";
```

### Named vs Default Exports

Prefer named exports for better tree-shaking:

```typescript
// ✅ Good - Named exports
// utils/formatters.ts
export const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
};

export const formatDate = (date: Date): string => {
  return date.toLocaleDateString();
};

export const formatPhoneNumber = (phone: string): string => {
  // Format phone number logic
  return phone;
};

// ✅ Good - Import named exports
import { formatCurrency, formatDate, formatPhoneNumber } from '@/utils/formatters';

// ❌ Bad - Default export
// utils/formatters.ts
export default {
  formatCurrency: (amount: number): string => { /* ... */ },
  formatDate: (date: Date): string => { /* ... */ },
  formatPhoneNumber: (phone: string): string => { /* ... */ },
};

// ❌ Bad - Import default export
import formatters from '@/utils/formatters';
const formatted = formatters.formatCurrency(100);
```

## Code Formatting Standards

### Line Length

Keep lines under 100 characters for readability:

```typescript
// ❌ Too long
const processUserOrder = async (userId: string, orderId: string, items: OrderItem[], shippingAddress: Address): Promise<Order> => {
  // Implementation
};

// ✅ Good - Break long lines
const processUserOrder = async (
  userId: string,
  orderId: string,
  items: OrderItem[],
  shippingAddress: Address,
): Promise<Order> => {
  // Implementation
};

// ✅ Good - Break complex expressions
const userDisplayName = user.title 
  ? `${user.title}. ${user.firstName} ${user.lastName}`
  : `${user.firstName} ${user.lastName}`;
```

### Indentation and Spacing

Use consistent indentation (2 spaces):

```typescript
// ✅ Good - Consistent indentation
function calculateTotal(items: CartItem[]): number {
  let total = 0;
  
  for (const item of items) {
    total += item.price * item.quantity;
  }
  
  return total;
}

// ❌ Bad - Inconsistent indentation
function calculateTotal(items: CartItem[]): number {
let total = 0;

  for (const item of items) {
total += item.price * item.quantity;
  }

return total;
}
```

### Function Length

Keep functions under 30-50 lines:

```typescript
// ❌ Too long - Should be broken down
function processComplexOrder(order: Order): Promise<OrderResult> {
  // Validation logic (20 lines)
  if (!order.items || order.items.length === 0) {
    throw new Error("Order must have items");
  }
  for (const item of order.items) {
    if (!item.productId || item.price <= 0) {
      throw new Error("Invalid item");
    }
  }
  
  // Calculation logic (15 lines)
  let subtotal = 0;
  for (const item of order.items) {
    subtotal += item.price * item.quantity;
  }
  const tax = subtotal * 0.08;
  const shipping = calculateShipping(order.items);
  const total = subtotal + tax + shipping;
  
  // Database logic (10 lines)
  const savedOrder = await database.save({
    ...order,
    subtotal,
    tax,
    shipping,
    total,
  });
  
  // Notification logic (5 lines)
  await emailService.sendConfirmation(order.customerEmail, savedOrder.id);
  
  return savedOrder;
}

// ✅ Good - Broken into smaller functions
function validateOrderItems(items: OrderItem[]): void {
  if (!items || items.length === 0) {
    throw new Error("Order must have items");
  }
  
  for (const item of items) {
    if (!item.productId || item.price <= 0) {
      throw new Error("Invalid item");
    }
  }
}

function calculateOrderTotals(items: OrderItem[]): OrderTotals {
  const subtotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const tax = subtotal * 0.08;
  const shipping = calculateShipping(items);
  const total = subtotal + tax + shipping;
  
  return { subtotal, tax, shipping, total };
}

async function saveOrderToDatabase(order: Order, totals: OrderTotals): Promise<Order> {
  return await database.save({
    ...order,
    ...totals,
  });
}

async function sendOrderConfirmation(customerEmail: string, orderId: string): Promise<void> {
  await emailService.sendConfirmation(customerEmail, orderId);
}

// Main function - Clear and concise
async function processComplexOrder(order: Order): Promise<OrderResult> {
  validateOrderItems(order.items);
  const totals = calculateOrderTotals(order.items);
  const savedOrder = await saveOrderToDatabase(order, totals);
  await sendOrderConfirmation(order.customerEmail, savedOrder.id);
  
  return savedOrder;
}
```

## Comment Formatting

### When to Use Comments

- Explain **why**, not **what**
- Document complex business logic
- Explain workarounds or temporary solutions
- Document API usage examples

```typescript
// ❌ Bad - Comments explain what code does
// Increment the counter
counter++;

// Check if user is admin
if (user.role === 'admin') {
  // Show admin panel
  showAdminPanel();
}

// ✅ Good - Comments explain why
// Counter is incremented here because this represents the number of active sessions
counter++;

// Admin check is required because admin users have access to sensitive operations
if (user.role === 'admin') {
  // Admin panel provides system management tools
  showAdminPanel();
}

// TODO: Remove this temporary workaround once API v2 is available
// This legacy API doesn't support bulk operations, so we need to make individual calls
for (const item of items) {
  await legacyApi.createItem(item);
}
```

### Comment Style

```typescript
// ✅ Good - Consistent comment style
/**
 * Calculate the total price including tax and shipping
 * @param items - Array of order items
 * @param taxRate - Tax rate as decimal (0.08 = 8%)
 * @returns Formatted currency string
 */
function calculateOrderTotal(items: OrderItem[], taxRate: number): string {
  // Implementation
}

// ✅ Good - Inline comments for complex logic
const discount = user.isPremium 
  ? 0.15                    // Premium users get 15% discount
  : user.loyaltyPoints > 1000 
    ? 0.10                  // High loyalty gets 10% discount
    : 0.05;                  // Standard 5% discount

// ❌ Bad - Inconsistent comment style
/* Calculate total */
function calculateOrderTotal(items, taxRate) {
  // do stuff
}
```

## Resources

- [Clean Code Chapter 5: Formatting](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350884)
- [JavaScript Style Guide](https://github.com/airbnb/javascript)
- [TypeScript Handbook: Code Organization](https://www.typescriptlang.org/docs/handbook/modules.html)
- [Vue.js Style Guide](https://vuejs.org/style-guide/)
