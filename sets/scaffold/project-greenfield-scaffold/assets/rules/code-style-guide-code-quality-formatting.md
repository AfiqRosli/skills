---
trigger: always_on
---

# Code Quality & Formatting

## Overview

This document provides comprehensive code quality and formatting guidelines for the application. It covers ESLint configuration with @stylistic rules, Vue-specific rules, TypeScript patterns, security practices, documentation standards, and automation tools to ensure consistent, high-quality code across the entire project.

## ESLint Configuration (No Prettier)

The project uses ESLint with `@stylistic/eslint-plugin` for all code formatting. Prettier is no longer used.

### Base Configuration

Based on `eslint.config.ts`:

```typescript
import js from "@eslint/js";
import stylistic from "@stylistic/eslint-plugin";
import withNuxt from "./.nuxt/eslint.config.mjs";

export default withNuxt(
  {
    ...js.configs.recommended,
    plugins: {
      "@stylistic": stylistic,
    },
    rules: {
      ...js.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@stylistic/indent": ["error", 2],
      "vue/component-name-in-template-casing": ["error", "PascalCase"],
      "vue/custom-event-name-casing": ["error", "camelCase"],
      "vue/define-macros-order": ["error", {
        order: ["defineProps", "defineEmits"],
      }],
      "vue/no-unused-vars": "error",
      "vue/padding-line-between-blocks": ["error", "always"],
      "vue/html-self-closing": ["error", {
        html: { void: "never", normal: "always", component: "always" },
        svg: "always",
        math: "always",
      }],
      "vue/max-attributes-per-line": ["error", { singleline: 3, multiline: 1 }],
      "vue/html-indent": ["error", 2],
      "vue/no-v-html": "error",
      "vue/require-default-prop": "error",
      "vue/require-prop-types": "error",
    },
  },
).append(
  {
    rules: {
      "no-unused-vars": ["error", { args: "all", argsIgnorePattern: "^_", caughtErrors: "none" }],
      "prefer-const": "error",
    },
  },
);
```

### Key @stylistic Rules

The `@stylistic/eslint-plugin` enforces formatting rules that replace Prettier:

- **`@stylistic/indent`** — 2-space indentation
- **`@stylistic/arrow-parens`** — No parentheses around single-argument arrow functions
- **`@stylistic/brace-style`** — Stroustrup brace style (closing brace on its own line before `else`/`catch`)
- **`@stylistic/operator-linebreak`** — Operators at the beginning of continuation lines

### Running ESLint

```bash
# Check for errors
bunx eslint .

# Auto-fix stylistic errors
bunx eslint --fix .

# Project lint script
bun run lint
```

**Important**: Do NOT run `prettier --write` on project files. It conflicts with `@stylistic` rules. Use `bunx eslint --fix` instead.

## Vue-Specific Rules

### Component Rules

```javascript
// ✅ Good - Vue component structure
export default {
  name: "UserProfile",
  props: {
    user: {
      type: Object,
      required: true,
      validator: (user) => user && typeof user.id === 'string',
    },
  },
  emits: {
    update: "user-updated",
    delete: "user-deleted",
  },
  setup(props, { emit }) {
    // Component logic
  },
};

// ❌ Bad - Missing component name or improper structure
export default {
  props: {
    user: Object,
  },
  setup(props) {
    // Component logic without proper typing
  },
};
```

### Template Rules

```vue
<!-- ✅ Good - Proper template structure -->
<template>
  <div class="user-profile">
    <h1 class="user-profile__title">{{ user.name }}</h1>
    <p class="user-profile__email">{{ user.email }}</p>
  </div>
</template>

<!-- ❌ Bad - Missing semantic structure -->
<template>
  <div>
    <h1>{{ user.name }}</h1>
    <p>{{ user.email }}</p>
  </div>
</template>
```

## TypeScript-Specific Rules

### Type Safety Rules

```typescript
// ✅ Good - Strict typing
interface User {
  id: string;
  name: string;
  email: string;
}

const processUser = (user: User): ProcessedUser => {
  return {
    fullName: `${user.name}`,
    emailDomain: user.email.split('@')[1],
  };
};

// ❌ Bad - Using any or loose typing
const processUser = (user: any): any => {
  return {
    fullName: user.name,
    email: user.email,
  };
};
```

### Interface and Type Rules

```typescript
// ✅ Good - Proper interface definition
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

type UserStatus = 'active' | 'inactive' | 'suspended';

// ❌ Bad - Poor type definitions
interface ApiResponse {
  data: any;
  status: number;
  message: string;
}

type UserStatus = 'active' | 'inactive' | 'suspended' | 'pending' | 'banned';
```

## Code Quality Rules

### Import/Export Rules

```typescript
// ✅ Good - Proper imports
import { ref, computed } from "vue";
import { defineStore } from "pinia";
import type { User } from "@/interfaces/user";

export { useUserStore } from "./UserStore";
export type { UserPreferences } from "./types";

// ❌ Bad - Poor import organization
import { ref, computed } from "vue";
import { defineStore } from "pinia";
import { User } from "@/interfaces/user";
import { useUserStore } from "./UserStore";
import { UserPreferences } from "./types";
```

### Function Rules

```typescript
// ✅ Good - Well-structured functions
const calculateTotal = (
  items: CartItem[],
  taxRate: number = 0.08,
): number => {
  const subtotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  return subtotal * (1 + taxRate);
};

const isAdult = (age: number): boolean => {
  return age >= 18;
};

// ❌ Bad - Poorly structured functions
const calculateTotal = (items, taxRate) => {
  let total = 0;
  for (let i = 0; i < items.length; i++) {
    total += items[i].price * items[i].quantity;
  }
  return total * (1 + taxRate);
};

const isAdult = (age) => {
  if (age >= 18) {
    return true;
  } else {
    return false;
  }
};
```

## Performance Rules

### Optimization Rules

```typescript
// ✅ Good - Efficient code patterns
const expensiveFilter = computed(() => {
  return users.value.filter(user => 
    user.name.toLowerCase().includes(searchQuery.value.toLowerCase()) &&
    user.status === 'active'
  );
});

const memoizedCalculation = useMemo(() => {
  return expensiveCalculation(data);
}, [data]);

// ❌ Bad - Inefficient code patterns
const expensiveFilter = () => {
  return users.value.filter(user => {
    const matchesName = user.name.toLowerCase().includes(searchQuery.value.toLowerCase());
    const isActive = user.status === 'active';
    return matchesName && isActive;
  });
};

const recalculateOnEveryRender = () => {
  return expensiveCalculation(data);
};
```

## Security Rules

### Security Best Practices

```typescript
// ✅ Good - Secure coding practices
const validateInput = (input: string): boolean => {
  // Input validation
  const sanitized = input.trim().replace(/[<>]/g, '');
  return sanitized.length > 0 && sanitized.length <= 100;
};

const apiCall = async (url: string, data: any): Promise<any> => {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify(data),
    });
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw new Error('Request failed');
  }
};

// ❌ Bad - Insecure coding practices
const processUserInput = (input: string): void => {
  // No input validation
  eval(input); // Dangerous
};

const insecureApiCall = async (url: string, data: any): Promise<any> => {
  // No proper error handling or validation
  return fetch(url, {
    method: 'POST',
    body: JSON.stringify(data),
  });
};
```

## Documentation Standards

### Code Documentation

```typescript
// ✅ Good - Well-documented code
/**
 * Calculates the total price including tax
 * @param items - Array of cart items
 * @param taxRate - Tax rate as decimal (0.08 = 8%)
 * @returns Formatted currency string
 * @example
 * ```typescript
 * const total = calculateOrderTotal(items, 0.08);
 * console.log(total); // "$108.00"
 * ```
 */
const calculateOrderTotal = (
  items: CartItem[],
  taxRate: number,
): string => {
  const subtotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const total = subtotal * (1 + taxRate);
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(total);
};

// ❌ Bad - Poorly documented code
const calculateTotal = (items, taxRate) => {
  // Calculate total
  const subtotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const total = subtotal * (1 + taxRate);
  return total.toString();
};
```

### Comment Standards

```typescript
// ✅ Good - Meaningful comments
// Check if user is eligible for premium features
const isPremiumEligible = (user: User): boolean => {
  return user.accountType === 'premium' || 
         user.yearsActive >= 5 || 
         user.purchaseTotal > 1000;
};

// TODO: Implement geolocation-based eligibility (ticket #123)
// FIXME: This is a temporary workaround for the legacy API
// NOTE: This function will be deprecated in v2.0

// ❌ Bad - Unhelpful comments
const checkUser = (user: User): boolean => {
  // Check user
  if (user.active) {
    return true;
  }
  return false;
};
```

## Automation Tools

### Pre-commit Hooks

```json
// package.json
{
  "husky": {
    "hooks": {
      "pre-commit": "lint-staged",
      "pre-push": "npm run test"
    }
  },
  "lint-staged": {
    "*.{js,ts,vue}": [
      "eslint --fix"
    ]
  }
}
```

### CI/CD Integration

```yaml
# .github/workflows/quality-check.yml
name: Code Quality Check

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          
      - name: Install dependencies
        run: npm ci
        
      - name: Run ESLint
        run: npm run lint
        
      - name: Run tests
        run: npm run test
        
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage/lcov.info
```

## Quality Metrics

### Code Coverage

```json
// package.json
{
  "vitest": {
    "coverage": {
      "provider": "c8",
      "reporter": ["text", "json", "html"],
      "exclude": [
        "node_modules/",
        "tests/",
        "**/*.config.*",
        "**/*.d.ts"
      ],
      "thresholds": {
        "global": {
          "branches": 80,
          "functions": 80,
          "lines": 80,
          "statements": 80
        }
      }
    }
  }
}
```

### Quality Gates

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        perFile: {
          // Allow lower coverage for test files
          'src/**/*': {
            statements: 80,
            branches: 80,
            functions: 80,
            lines: 80,
          },
          'tests/**/*': {
            statements: 0,
            branches: 0,
            functions: 0,
            lines: 0,
          },
        },
      },
    },
  },
});
```

## Resources

- [ESLint Rules](https://eslint.org/docs/rules/)
- [@stylistic/eslint-plugin](https://eslint.style/)
- [TypeScript ESLint Rules](https://typescript-eslint.io/rules/)
- [Vue ESLint Rules](https://eslint.vuejs.org/rules/)
- [Code Quality Best Practices](https://github.com/ryanmcdermott/clean-code-javascript)
- [Testing Best Practices](https://kentcdodds.com/blog/best-practices-for-unit-testing/)
