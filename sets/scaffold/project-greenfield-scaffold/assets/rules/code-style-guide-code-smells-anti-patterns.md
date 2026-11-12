---
trigger: always_on
---

# Code Smells & Anti-Patterns

## Overview

This document identifies common code smells and anti-patterns that should be avoided in Vue 3, TypeScript, and modern JavaScript development. It provides practical examples of problematic code and their clean alternatives, helping developers write more maintainable and robust applications.

## Rigidity

When every change requires modifications in multiple places.

### Symptoms

- Tight coupling between components
- Hardcoded values scattered throughout
- Changes cascade through codebase

### Solutions

- Use dependency injection
- Extract configuration to centralized locations
- Implement proper abstractions

```typescript
// ❌ Rigid - Hardcoded API URL
const fetchUsers = async () => {
  const response = await $fetch("https://api.example.com/v1/users");
  return response;
};

// ✅ Flexible - Configurable API URL through store
const userStore = useUserStore();
const users = await userStore.fetchUsers();
```

## Complexity

When code is difficult to understand due to unnecessary complexity.

### Solutions

- Use early returns
- Extract complex logic into well-named functions
- Prefer explicit code over clever code
- Avoid Hadouken IFs (deeply nested conditionals)

### Avoid Hadouken IFs

Avoid deeply nested IF statements ("Hadouken IFs") through early returns and guard clauses.

```typescript
// ❌ Bad - Hadouken IFs (deeply nested)
function processOrder(order: Order) {
  if (order) {
    if (order.items) {
      if (order.items.length > 0) {
        if (order.status === "pending") {
          // actual logic here
        }
      }
    }
  }
}

// ✅ Good - Early returns and guard clauses
function processOrder(order: Order) {
  if (!order) return;
  if (!order.items || order.items.length === 0) return;
  if (order.status !== "pending") return;

  // actual logic here
}
```

```typescript
// ❌ Complex - Nested ternary operator
const getStatusColor = (status: string) => {
  return status === "active"
    ? "green"
    : status === "pending"
      ? "yellow"
      : status === "suspended"
        ? "orange"
        : "red";
};

// ✅ Clear - Switch statement or object mapping
const getStatusColor = (status: string): string => {
  const statusColors: Record<string, string> = {
    active: "green",
    pending: "yellow",
    suspended: "orange",
    inactive: "red",
  };

  return statusColors[status] || "gray";
};
```

## Fragility

When small changes break unrelated functionality.

### Solutions

- Make dependencies explicit
- Use immutable data patterns
- Isolate side effects

```typescript
// ✅ Robust - Explicit dependencies
const calculateTotal = (items: CartItem[], taxRate: number) => {
  return (
    items.reduce((sum, item) => sum + item.price * item.quantity, 0) *
    (1 + taxRate)
  );
};
```

## Specific Anti-Patterns to Avoid

### Avoid Negative Conditionals

Prefer positive conditionals over negative ones.

```typescript
// ❌ Bad - Negative conditional
if (!user.isActive) return;

// ✅ Good - Positive conditional
if (user.isActive) {
  // proceed
}
```

### Encapsulate Conditionals

Extract complex boolean logic into named functions.

```typescript
// ❌ Bad - Complex inline
if (user.age > 18 && !user.hasChildren && (user.isPremium || user.hasCoupon)) {
  showOffer();
}

// ✅ Good - Encapsulated
if (isEligibleForOffer(user)) {
  showOffer();
}
```

### Avoid Flag Arguments

Avoid boolean arguments. Use enums or separate functions.

```typescript
// ❌ Bad - Flag argument
function createUser(data: UserData, isAdmin: boolean) {}

// ✅ Good - Clear enum
function createUser(data: UserData, role: "admin" | "user") {}
```

### Avoid Comments

Prefer self-documenting code over comments.

```typescript
// ❌ Bad - Comment explains what
// Check if user is eligible
if (user.age > 65) applyDiscount();

// ✅ Good - Self-documenting
if (isEligibleForDiscount(user)) applyDiscount();
```

### Avoid Magic Numbers and Strings

Replace magic values with named constants.

```typescript
// ❌ Magic numbers and strings
if (user.age > 65 && status === "active") {
  sendEmail("welcome@example.com", "Welcome!");
}

// ✅ Named constants
const RETIREMENT_AGE = 65;
const ACTIVE_STATUS = "active";
const WELCOME_EMAIL = "welcome@example.com";

if (user.age > RETIREMENT_AGE && status === ACTIVE_STATUS) {
  sendEmail(WELCOME_EMAIL, "Welcome!");
}
```

### Avoid Long Parameter Lists

Too many parameters indicate the function is doing too much.

```typescript
// ❌ Too many parameters
function createUser(name, email, age, address, phone, role, department, startDate, salary) {
  // ... implementation
}

// ✅ Use object parameter
function createUser(userData: {
  name: string;
  email: string;
  age: number;
  address: Address;
  phone: string;
  role: UserRole;
  department: string;
  startDate: Date;
  salary: number;
}) {
  // ... implementation
}

// ✅ Even better - Use interface
interface CreateUserRequest {
  name: string;
  email: string;
  age: number;
  address: Address;
  phone: string;
  role: UserRole;
  department: string;
  startDate: Date;
  salary: number;
}

function createUser(request: CreateUserRequest) {
  // ... implementation
}
```

### Avoid Primitive Obsession

Don't use primitives when you need more complex types.

```typescript
// ❌ Primitive obsession
function processOrder(orderId: string, customerName: string, items: string, total: number) {
  // items is a string that needs to be parsed
  const parsedItems = JSON.parse(items);
  // ... processing logic
}

// ✅ Rich domain objects
interface OrderItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
}

interface Order {
  id: string;
  customerName: string;
  items: OrderItem[];
  total: number;
}

function processOrder(order: Order) {
  // items is already typed and structured
  // ... processing logic
}
```

### Avoid Shotgun Surgery

When making changes, avoid scattering modifications across many files.

```typescript
// ❌ Shotgun surgery - Changes scattered across files
// user.service.ts
function createUser(userData) {
  // ... existing logic
  // NEW: Add email validation
  if (!isValidEmail(userData.email)) {
    throw new Error("Invalid email");
  }
}

// user.controller.ts
function handleCreateUser(req, res) {
  // ... existing logic
  // NEW: Add email error handling
  if (req.body.email && !isValidEmail(req.body.email)) {
    return res.status(400).json({ error: "Invalid email" });
  }
}

// user.model.ts
const userSchema = {
  // ... existing fields
  // NEW: Add email validation rule
  email: { type: 'string', required: true, validate: isValidEmail }
};

// ✅ Single responsibility - Changes focused in one place
// user.validation.ts
export const validateUserEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

// user.service.ts
import { validateUserEmail } from './user.validation';

function createUser(userData) {
  if (!validateUserEmail(userData.email)) {
    throw new ValidationError("Invalid email", "email");
  }
  // ... existing logic
}

// user.controller.ts
import { validateUserEmail } from './user.validation';

function handleCreateUser(req, res) {
  if (!validateUserEmail(req.body.email)) {
    return res.status(400).json({ error: "Invalid email" });
  }
  // ... existing logic
}
```

### Avoid Feature Envy

When a class uses more methods of another class than its own.

```typescript
// ❌ Feature envy - Order class knows too much about Customer
class Order {
  constructor(
    private customer: Customer,
    private items: OrderItem[]
  ) {}

  calculateTotal(): number {
    let total = this.items.reduce((sum, item) => sum + item.price, 0);
    
    // Using too many Customer methods
    if (this.customer.isPremium()) {
      total *= 0.9; // Premium discount
    }
    
    if (this.customer.getLoyaltyPoints() > 1000) {
      total *= 0.95; // Loyalty discount
    }
    
    return total;
  }
}

// ✅ Move behavior to appropriate class
class Customer {
  constructor(
    private loyaltyPoints: number,
    private isPremiumMember: boolean
  ) {}

  isPremium(): boolean {
    return this.isPremiumMember;
  }

  getLoyaltyPoints(): number {
    return this.loyaltyPoints;
  }

  calculateDiscountPercentage(): number {
    let discount = 0;
    
    if (this.isPremium()) {
      discount += 10; // 10% premium discount
    }
    
    if (this.getLoyaltyPoints() > 1000) {
      discount += 5; // 5% loyalty discount
    }
    
    return Math.min(discount, 20); // Max 20% discount
  }
}

class Order {
  constructor(
    private customer: Customer,
    private items: OrderItem[]
  ) {}

  calculateTotal(): number {
    let total = this.items.reduce((sum, item) => sum + item.price, 0);
    
    const discountPercentage = this.customer.calculateDiscountPercentage();
    total *= (1 - discountPercentage / 100);
    
    return total;
  }
}
```

### Avoid Data Clumps

When groups of data variables appear together in many places.

```typescript
// ❌ Data clumps - Same group of variables used together everywhere
function processUser(user) {
  const firstName = user.firstName;
  const lastName = user.lastName;
  const email = user.email;
  const phone = user.phone;
  
  // Used together in multiple places
  console.log(`${firstName} ${lastName} (${email})`);
  sendNotification(email, `${firstName} ${lastName}`);
  updateContact(firstName, lastName, email, phone);
}

function displayUser(user) {
  const firstName = user.firstName;
  const lastName = user.lastName;
  const email = user.email;
  const phone = user.phone;
  
  return `${firstName} ${lastName} - ${email} - ${phone}`;
}

// ✅ Extract into a class or interface
interface PersonalInfo {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  
  getFullName(): string;
  getDisplayString(): string;
}

class UserPersonalInfo implements PersonalInfo {
  constructor(
    public firstName: string,
    public lastName: string,
    public email: string,
    public phone: string
  ) {}

  getFullName(): string {
    return `${this.firstName} ${this.lastName}`;
  }

  getDisplayString(): string {
    return `${this.getFullName()} - ${this.email} - ${this.phone}`;
  }
}

function processUser(user: { personalInfo: PersonalInfo }) {
  const info = user.personalInfo;
  
  console.log(`${info.getFullName()} (${info.email})`);
  sendNotification(info.email, info.getFullName());
  updateContact(info.firstName, info.lastName, info.email, info.phone);
}

function displayUser(user: { personalInfo: PersonalInfo }) {
  return user.personalInfo.getDisplayString();
}
```

## Detecting Code Smells

### Signs to Watch For

1. **Long Methods**: Methods longer than 20-30 lines
2. **Large Classes**: Classes with too many responsibilities
3. **Long Parameter Lists**: More than 3-4 parameters
4. **Duplicated Code**: Similar code in multiple places
5. **Large Switch/If Statements**: More than 5-6 conditions
6. **Comments Explaining "What"**: Comments needed to understand code
7. **Inconsistent Naming**: Mixed naming conventions
8. **Dead Code**: Unused variables, functions, or imports

### Refactoring Strategies

1. **Extract Method**: Break down large methods
2. **Extract Class**: Group related data and behavior
3. **Replace Conditional with Polymorphism**: Use polymorphism instead of conditionals
4. **Introduce Parameter Object**: Replace long parameter lists
5. **Replace Magic Number with Symbolic Constant**: Name magic values
6. **Extract Interface**: Separate abstraction from implementation

## Resources

- [Refactoring: Improving the Design of Existing Code](https://www.amazon.com/Refactoring-Improving-Existing-Addison-Wesley/dp/0201485672)
- [Code Smells](https://refactoring.guru/refactoring/smells)
- [Clean Code: A Handbook of Agile Software Craftsmanship](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350884)
