---
trigger: always_on
---

# Project Code Style Guide

## Overview

This is the main overview of the project code style guidelines. Each section below links to detailed rule files that contain specific guidelines and examples.

## Table of Contents

1. [Clean Code Principles](./code-style-guide-clean-code-principles.md) - Core values and SOLID principles for writing maintainable code
2. [Code Smells & Anti-Patterns](./code-style-guide-code-smells-anti-patterns.md) - Common pitfalls and how to avoid them
3. [Naming Conventions](./code-style-guide-naming-conventions.md) - Guidelines for consistent naming across the codebase
4. [Code Formatting & Organization](./code-style-guide-code-formatting-organization.md) - File structure and formatting standards
5. [Project Structure & Architecture](./code-style-guide-project-structure-architecture.md) - Directory organization and import patterns
6. [Vue.js Specific Patterns](./code-style-guide-vuejs-patterns.md) - Vue 3 component structure and best practices
7. [TypeScript Patterns](./code-style-guide-typescript-patterns.md) - Type definitions and TypeScript usage guidelines
8. [Store Patterns (Pinia)](./code-style-guide-store-patterns-pinia.md) - State management patterns with Pinia
9. [API Development with Elysia](./code-style-guide-api-development-elysia.md) - Backend API development patterns
10. [Styling & CSS](./code-style-guide-styling-css.md) - SCSS, BEM, and Vuetify styling guidelines
11. [Testing Standards](./code-style-guide-testing-standards.md) - Component, composable, and API testing patterns
12. [Code Quality & Formatting](./code-style-guide-code-quality-formatting.md) - ESLint with @stylistic rules and quality tools
13. [Performance & Best Practices](./code-style-guide-performance-best-practices.md) - Performance optimization techniques
14. [Error Handling](./code-style-guide-error-handling.md) - Error handling patterns and strategies
15. [Reactivity Patterns](./code-style-guide-reactivity-patterns.md) - Vue 3 reactivity best practices

---

## Quick Reference

### Essential Commands

```bash
# Run all linters
bun run lint

# Fix formatting issues (ESLint stylistic only — no Prettier)
bunx eslint --fix .

# Start development server
bun run dev

# Build for production
bun run build
```

### Core Principles

- **Clean Code**: Write code that is clear, intuitive, reliable, maintainable, and testable
- **SOLID Principles**: Apply Single Responsibility, DRY, KISS, and YAGNI principles
- **Type Safety**: Leverage TypeScript for robust type checking
- **Component Architecture**: Use Vue 3 Composition API with consistent patterns
- **State Management**: Centralize API calls and state in Pinia stores
- **Testing**: Write comprehensive tests for components, composables, and APIs

### File Organization

```
.windsurf/rules/
├── code-style-guide.md                    # This overview file
├── code-style-guide-clean-code-principles.md
├── code-style-guide-code-smells-anti-patterns.md
├── code-style-guide-naming-conventions.md
├── code-style-guide-code-formatting-organization.md
├── code-style-guide-project-structure-architecture.md
├── code-style-guide-vuejs-patterns.md
├── code-style-guide-typescript-patterns.md
├── code-style-guide-store-patterns-pinia.md
├── code-style-guide-api-development-elysia.md
├── code-style-guide-styling-css.md
├── code-style-guide-testing-standards.md
├── code-style-guide-code-quality-formatting.md
├── code-style-guide-performance-best-practices.md
├── code-style-guide-error-handling.md
└── code-style-guide-reactivity-patterns.md
```

## Technology Stack

- **Framework**: Nuxt 3 with Vue 3 Composition API
- **Language**: TypeScript with strict typing
- **Styling**: Vuetify + SCSS with BEM methodology
- **State Management**: Pinia stores
- **Backend API**: Elysia with Drizzle ORM
- **Testing**: Vitest for unit/integration tests
- **Code Quality**: ESLint with @stylistic/eslint-plugin (no Prettier)

## Getting Started

1. Read the relevant rule files for your current task
2. Follow established patterns and conventions
3. Use the provided templates and examples
4. Run linting and formatting tools before committing
5. Write tests for new features and components

## Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Nuxt 3 Documentation](https://nuxt.com/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vuetify Documentation](https://vuetifyjs.com/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Elysia Documentation](https://elysiajs.com/)

---

*This guide is a living document. Contributions and suggestions for improvement are welcome.*
