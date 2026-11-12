---
name: cdo-alignment-uncommitted-changes
description: Cross-check code style guideline alignment against git uncommitted changes — CDO-owned copy invoked by the delivery org's pipeline
---

# Uncommitted Changes Alignment Workflow

## Overview

This workflow provides a focused approach to validate git uncommitted changes against project style guidelines. Instead of providing reference documentation, it actively checks current modifications for compliance and identifies specific violations that need to be addressed before committing.

## Prerequisites

1. **Git status check** - Identify uncommitted changes in working directory
2. **Change categorization** - Group changes by file type and functionality
3. **Style guide mapping** - Map changed files to relevant style guidelines
4. **Violation detection** - Identify specific guideline violations in changed code

## Pipeline Invocation (cdo-code-e2e)

When invoked under `cdo-code-e2e` step 6 — usually inside a subagent — the envelope supplies the changed-file list and a `checks_status` field (`not-run` when the step-8 health check hasn't run yet). Apply these bounds:

- **Skip Phase 1 automated checks** — when `checks_status` carries a completed result, use it; when `not-run`, skip them anyway — step 8's health check is the authoritative run, and duplicating it here just burns time. This skill's value is the manual style-guide review (Phases 2–4).
- **Report only** — do not remediate. Violations go to the orchestrator's merged step-7 fix loop.
- **Return a compact verdict** — `{counts_by_severity, findings: [{id, severity, file, line, title, remediation}]}`; write the full report to `<devlog_dir>/audit-alignment.md`, not to chat.
- Standalone invocation (no envelope): run all phases as written below.

## Change Detection & Analysis

### Step 1: Identify Uncommitted Changes

```bash
# Get list of modified files
git status --porcelain

# Show detailed changes for modified files
git diff --name-only

# Show staged changes (if any)
git diff --cached --name-only

# Show all changes (staged + unstaged)
git diff HEAD --name-only
```

### Step 2: Categorize Changes by Type

**Component Changes:**
- `.vue` files in `components/`
- Template, script, and style modifications
- Props, emits, and slot changes

**Store Changes:**
- `.ts` files in `stores/`
- State management, actions, and getters
- API integration patterns

**API Changes:**
- `.ts` files in `server/`
- Route definitions and handlers
- Schema and validation changes

**Composable Changes:**
- `.ts` files in `composables/`
- Reactive logic and utility functions
- Return type patterns

**Interface Changes:**
- `.ts` files in `interfaces/`
- Type definitions and contracts
- Generic types and utilities

**Utility Changes:**
- `.ts` files in `utils/`
- Helper functions and formatters
- Constants and configurations

### Step 3: Map Changes to Style Guides

**File Type → Style Guide Mapping:**

| File Type | Primary Style Guides | Secondary Guides |
|------------|-------------------|------------------|
| `.vue` components | `code-style-guide-vuejs-patterns.md` | `code-style-guide-styling-css.md`, `code-style-guide-typescript-patterns.md` |
| Store `.ts` | `code-style-guide-store-patterns-pinia.md` | `code-style-guide-typescript-patterns.md`, `code-style-guide-api-development-elysia.md` |
| API `.ts` | `code-style-guide-api-development-elysia.md` | `code-style-guide-typescript-patterns.md`, `code-style-guide-error-handling.md` |
| Composable `.ts` | `code-style-guide-reactivity-patterns.md` | `code-style-guide-typescript-patterns.md`, `code-style-guide-clean-code-principles.md` |
| Interface `.ts` | `code-style-guide-typescript-patterns.md` | `code-style-guide-naming-conventions.md` |
| Utility `.ts` | `code-style-guide-clean-code-principles.md` | `code-style-guide-naming-conventions.md`, `code-style-guide-code-formatting-organization.md` |

## Violation Detection Process

### Phase 1: Automated Checks

#### Step 1: Run ESLint on Changed Files
```bash
# Get list of changed files
CHANGED_FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E '\.(ts|vue|js)$' | tr '\n' ' ')

# Run ESLint on changed files only
if [ -n "$CHANGED_FILES" ]; then
  bun run lint $CHANGED_FILES
fi

# Auto-fix where possible
bun run lintfix $CHANGED_FILES
```

#### Step 2: TypeScript Compilation Check
```bash
# Check TypeScript compilation for changed files
bun run type-check

# Focus on errors in changed files
bun run type-check 2>&1 | grep -E "(error|warning)" | head -20
```

#### Step 3: ESLint Stylistic Validation
```bash
# Check ESLint stylistic rules on changed files
if [ -n "$CHANGED_FILES" ]; then
  bunx eslint $CHANGED_FILES
fi
```

### Phase 2: Manual Style Guide Validation

#### Step 1: Component Violation Detection
For each changed `.vue` file:

**Vue Structure Checks:**
- [ ] Script setup syntax correct (`<script setup lang="ts">`)
- [ ] Props properly typed with `defineProps<T>()`
- [ ] Emits properly typed with `defineEmits<T>()`
- [ ] Composition API used consistently
- [ ] Reactive state uses `ref()` and `computed()`
- [ ] Template uses semantic HTML and Vuetify components

**Template Pattern Checks:**
- [ ] Conditional rendering uses `v-if`/`v-else` appropriately
- [ ] List rendering uses `:key` with stable identifiers
- [ ] Event handlers properly named and bound
- [ ] Slots used correctly for component composition

**Style Checks:**
- [ ] Scoped styles used where appropriate
- [ ] BEM naming conventions followed
- [ ] Vuetify utility classes prioritized
- [ ] CSS variables used for theming

#### Step 2: Store Violation Detection
For each changed store file:

**Store Architecture Checks:**
- [ ] Uses `defineStore()` with proper ID
- [ ] State uses `ref()` for reactivity
- [ ] Getters use `computed()` for derived values
- [ ] Actions are properly typed functions
- [ ] API calls centralized in store actions
- [ ] Error handling consistent across actions

**Pattern Compliance:**
- [ ] State is readonly when returned
- [ ] Loading states properly managed
- [ ] Error states properly handled
- [ ] Async/await used correctly
- [ ] Store follows single responsibility principle

#### Step 3: API Violation Detection
For each changed API file:

**Route Structure Checks:**
- [ ] Routes follow RESTful conventions
- [ ] Proper HTTP methods used
- [ ] Route parameters properly typed
- [ ] Request/response schemas defined
- [ ] Error responses consistent

**Elysia Pattern Checks:**
- [ ] Uses `t.Object()` for validation
- [ ] Proper error handling with custom error classes
- [ ] Middleware properly applied
- [ ] Database operations use Drizzle patterns
- [ ] Response format consistent

#### Step 4: Composable Violation Detection
For each changed composable:

**Reactivity Checks:**
- [ ] Returns reactive refs with `readonly()`
- [ ] Computed properties used for derived values
- [ ] Watch/watchEffect used appropriately
- [ ] Proper cleanup in `onUnmounted()`

**Pattern Compliance:**
- [ ] Generic types used properly
- [ ] Parameters properly typed
- [ ] Return type explicitly defined
- [ ] Side effects properly managed

#### Step 5: TypeScript Violation Detection
For each changed TypeScript file:

**Type Safety Checks:**
- [ ] All functions have explicit return types
- [ ] Parameters properly typed
- [ ] Interfaces defined in `interfaces/` directory
- [ ] Type-only imports used where appropriate
- [ ] No `any` types used without justification

**Advanced Pattern Checks:**
- [ ] Generic types properly constrained
- [ ] Utility types used effectively
- [ ] Type guards implemented where needed
- [ ] Discriminated unions used for variant types

### Phase 3: Cross-File Integration Checks

#### Step 1: Import/Export Consistency
- [ ] Import paths use `@/` alias consistently
- [ ] Import order follows conventions (external → internal → types)
- [ ] Named exports preferred over default exports
- [ ] Circular imports avoided

#### Step 2: Interface Implementation
- [ ] Components implement interfaces correctly
- [ ] API responses match interface definitions
- [ ] Store state aligns with interface contracts
- [ ] Props and emits properly typed

### Phase 4: Deep Manual Review — Pattern & Logic Blindspots

> **Purpose:** Automated checks (ESLint, TypeScript, tests) catch syntax and type errors but miss subtle logic, reactivity, and pattern issues. This phase requires re-reading the actual changed code line-by-line and asking targeted questions about each block.

#### Step 1: Logic Flow & Guard Clause Analysis

For each changed function or code block, verify:

- [ ] **Guard clauses**: Are all edge cases handled with early returns? (empty input, null/undefined, zero-length, missing references)
- [ ] **Loop safety**: Do all `while`/`for` loops have termination guarantees? Are circular reference protections in place for chain-walking logic (e.g., parent traversals, tree walks)?
- [ ] **Existing pattern consistency**: Does chain-walking logic follow the established codebase pattern? (e.g., if `FocusStore.syncNewDescendant` uses a `visited` Set, new chain-walking code must too)
- [ ] **State mutation order**: Are state mutations sequenced correctly? (e.g., compute new state → filter old state → set new state, not interleaved)
- [ ] **Side-effect isolation**: Do pure utility functions have zero side effects? Are they truly pure (no external state reads/writes beyond parameters)?

#### Step 2: Reactivity & Watcher Blindspots

For each new `watch`, `watchEffect`, or reactive ref in changed code:

- [ ] **Watch timing**: Does the watcher fire at the right time? Consider component mount timing — if the component is gated behind `v-if` or skeleton loading, the watcher may miss the initial data replacement
- [ ] **Shallow vs deep**: Is `watch` shallow (default) or deep (`{ deep: true }`)? Does the chosen mode match the intent? Shallow watches miss in-place mutations; deep watches have performance cost
- [ ] **Initial trigger**: Will the watcher fire on initial data load? If not, is there an `onMounted` call or `{ immediate: true }` to compensate?
- [ ] **Re-trigger safety**: If the watcher fires again (e.g., on tab refocus), does it correctly reconcile state? (e.g., removing stale entries, preserving manual user state)
- [ ] **Reactive ref vs Set/Map**: Is the reactive container type appropriate? `ref<Set>` requires `.value` reassignment for reactivity — mutations to the Set itself don't trigger Vue reactivity
- [ ] **storeToRefs usage**: Are store refs destructured with `storeToRefs`? Direct store property access loses reactivity

#### Step 3: State Tracking & Manual-vs-Auto Distinction

For code that manages user-controlled state alongside auto-managed state:

- [ ] **Tracking separation**: Is there a mechanism to distinguish user-initiated changes from auto-initiated changes? (e.g., `autoExpandedNodeIds` Set vs `openNodes` array)
- [ ] **Stale removal**: When auto-managed state is recomputed, are old auto-managed entries removed without removing user-managed entries?
- [ ] **Preservation guarantee**: After recomputation, are user-managed entries guaranteed to survive? Verify with a concrete trace: "User opens X → auto-expand fires → is X still in the result?"
- [ ] **Manual collapse respect**: If a user manually collapses an auto-expanded node, does the next auto-expand cycle respect that collapse? Or does it immediately re-expand?
- [ ] **Empty result handling**: When auto-managed computation returns empty, does the code correctly remove only old auto-managed entries without adding new ones?

#### Step 4: Naming Accuracy After Scope Changes

- [ ] **Variable name matches content**: After scope changes (e.g., adding the item itself to an "ancestors" collection), does the variable name still accurately describe its contents?
- [ ] **Function name matches behaviour**: After behavioural changes (e.g., filtering by `top_3` instead of "not everything_else"), does the function name or its documentation still match?
- [ ] **No misleading names**: Are there variables whose names imply a narrower or broader scope than their actual contents?

#### Step 5: Test Coverage Blindspots

- [ ] **Mixed scenario tests**: Are there tests for mixed inputs? (e.g., `top_3` and `top_20_percent` in the same area — only `top_3` should trigger)
- [ ] **Circular reference test**: Is there a test for circular parent/child references that could cause infinite loops?
- [ ] **Interaction logic tests**: Are pure utility functions tested but the integration logic (e.g., `applyAutoExpand` set manipulation) is not? Is this acceptable given the complexity?
- [ ] **Boundary condition tests**: Are boundary conditions tested? (root-level items with no ancestors, empty area, undefined areaId, missing parent references)
- [ ] **State reconciliation tests**: If the code reconciles old and new state (e.g., removing stale entries), are there tests verifying the reconciliation preserves the correct subset?

#### Step 6: Cross-File Pattern Consistency

- [ ] **Utility co-location**: Are new utility functions placed in the correct existing file? (e.g., tree-related helpers in `thing-helpers.ts`, not inline in components)
- [ ] **Import pattern**: Does the new import follow the established pattern? (e.g., `@/utils/` alias, named exports)
- [ ] **Comment style**: Do comments explain "why" not "what"? Are they consistent with the codebase's comment style?
- [ ] **Function declaration style**: Are functions declared with `function` keyword (consistent with existing code) vs arrow functions?

## Specific Violation Categories

### High Priority Violations

**Type Safety Issues:**
- Missing type annotations
- Incorrect prop types
- Interface mismatches
- `any` type usage

**Code Quality Issues:**
- ESLint errors
- TypeScript compilation errors
- Formatting inconsistencies
- Naming convention violations

**Pattern Violations:**
- Incorrect Vue 3 usage
- Store pattern violations
- API anti-patterns
- Improper reactivity

### Medium Priority Violations

**Style Guide Deviations:**
- Inconsistent code organization
- Missing error handling
- Performance anti-patterns
- Test coverage gaps

**Architectural Issues:**
- Poor separation of concerns
- Inconsistent patterns
- Missing abstractions
- Code duplication

### Low Priority Violations

**Cosmetic Issues:**
- Minor formatting differences
- Comment inconsistencies
- Variable naming improvements
- Documentation gaps

## Automated Validation Commands

### Pre-Commit Validation Script
```bash
#!/bin/bash
# pre-commit-validation.sh

echo "🔍 Running uncommitted changes validation..."

# Get changed files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMRT | grep -E '\.(ts|vue|js)$' | tr '\n' ' ')

if [ -z "$CHANGED_FILES" ]; then
  echo "✅ No TypeScript/Vue files to validate"
  exit 0
fi

echo "📁 Changed files: $CHANGED_FILES"

# Run ESLint
echo "🔧 Running ESLint..."
bun run lint $CHANGED_FILES
LINT_EXIT_CODE=$?

# Run TypeScript check
echo "📝 Running TypeScript check..."
bun run type-check
TS_EXIT_CODE=$?

# Check ESLint stylistic rules
echo "🎨 Checking ESLint stylistic rules..."
bunx eslint $CHANGED_FILES
FORMAT_EXIT_CODE=$?

# Run tests for changed files
echo "🧪 Running tests..."
bun run test --reporter=verbose --run $CHANGED_FILES
TEST_EXIT_CODE=$?

# Summary
if [ $LINT_EXIT_CODE -eq 0 ] && [ $TS_EXIT_CODE -eq 0 ] && [ $FORMAT_EXIT_CODE -eq 0 ] && [ $TEST_EXIT_CODE -eq 0 ]; then
  echo "✅ All checks passed! Ready to commit."
  exit 0
else
  echo "❌ Validation failed. Please fix issues before committing."
  echo ""
  echo "📋 Summary:"
  [ $LINT_EXIT_CODE -ne 0 ] && echo "  - ESLint errors found"
  [ $TS_EXIT_CODE -ne 0 ] && echo "  - TypeScript errors found"
  [ $FORMAT_EXIT_CODE -ne 0 ] && echo "  - Formatting issues found"
  [ $TEST_EXIT_CODE -ne 0 ] && echo "  - Test failures found"
  exit 1
fi
```

### Interactive Validation Script
```bash
#!/bin/bash
# interactive-validation.sh

echo "🔍 Interactive Uncommitted Changes Validation"
echo "=========================================="

# Show changed files
echo "📁 Changed files:"
git diff --name-only --diff-filter=ACMRT
echo ""

# Choose validation type
echo "🎯 Choose validation scope:"
echo "1) All changes"
echo "2) Components only"
echo "3) Stores only"
echo "4) API only"
echo "5) Composables only"
echo "6) Interfaces only"
echo "7) Utilities only"
echo ""

read -p "Enter choice (1-7): " choice

case $choice in
  1) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E '\.(ts|vue|js)$') ;;
  2) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'components/.*\.(vue|ts)$') ;;
  3) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'stores/.*\.ts$') ;;
  4) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'server/.*\.ts$') ;;
  5) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'composables/.*\.ts$') ;;
  6) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'interfaces/.*\.ts$') ;;
  7) FILES=$(git diff --name-only --diff-filter=ACMRT | grep -E 'utils/.*\.ts$') ;;
  *) echo "Invalid choice"; exit 1 ;;
esac

if [ -z "$FILES" ]; then
  echo "✅ No files found for selected category"
  exit 0
fi

echo ""
echo "🔧 Validating: $FILES"
echo ""

# Run validation
bun run lint $FILES
bun run type-check
bunx eslint $FILES

echo ""
echo "📋 Validation complete. Review output above for any issues."
```

## Violation Resolution Guidelines

### Immediate Fixes (High Priority)
```bash
# Auto-fix ESLint issues
bun run lintfix [files]

# Auto-fix formatting
bun run format [files]

# Re-run validation
bun run lint [files]
bun run type-check
```

### Manual Fixes (Medium/Low Priority)
1. **Review specific style guide** for violation type
2. **Apply pattern** from relevant guide
3. **Verify integration** with related files
4. **Re-run validation** to confirm fix

### Documentation Updates
If violations reveal missing documentation:
1. **Update interface definitions** in `interfaces/`
2. **Add component examples** in comments
3. **Update store documentation**
4. **Add API endpoint documentation**

## Quality Gates Before Commit

### Must Pass (Blocking)
- [ ] No ESLint errors
- [ ] No TypeScript compilation errors
- [ ] No ESLint @stylistic formatting errors
- [ ] All related tests pass
- [ ] No type safety violations

### Should Pass (Warning)
- [ ] No code smell violations
- [ ] No naming convention violations
- [ ] No performance anti-patterns
- [ ] No error handling gaps
- [ ] Phase 4: No circular reference risks in chain-walking logic
- [ ] Phase 4: No reactivity timing blindspots (watcher misses initial data)
- [ ] Phase 4: No state tracking gaps (auto vs manual state distinction)
- [ ] Phase 4: No misleading variable names after scope changes
- [ ] Phase 4: No test coverage blindspots for mixed scenarios or edge cases

### Recommended (Non-blocking)
- [ ] Documentation updated for new interfaces
- [ ] Test coverage maintained or improved
- [ ] Code comments added for complex logic
- [ ] Architectural patterns followed

## Reporting & Summary

### Violation Summary Template
```markdown
# Uncommitted Changes Validation Report

## Changed Files Analysis
- **Total Files Changed**: [count]
- **Component Files**: [count]
- **Store Files**: [count]
- **API Files**: [count]
- **Composable Files**: [count]
- **Interface Files**: [count]
- **Utility Files**: [count]

## Violations Found

### High Priority (Must Fix)
- [ ] ESLint errors: [count]
- [ ] TypeScript errors: [count]
- [ ] Formatting issues: [count]
- [ ] Type safety violations: [count]

### Medium Priority (Should Fix)
- [ ] Code smell violations: [count]
- [ ] Pattern violations: [count]
- [ ] Performance issues: [count]

### Low Priority (Nice to Fix)
- [ ] Documentation gaps: [count]
- [ ] Naming improvements: [count]
- [ ] Code organization: [count]

## Resolution Status
- [ ] High priority issues resolved
- [ ] Medium priority issues resolved
- [ ] Low priority issues documented
- [ ] Ready for commit validation

## Style Guides Referenced
- Vue Component Patterns: `code-style-guide-vuejs-patterns.md`
- Store Patterns: `code-style-guide-store-patterns-pinia.md`
- API Development: `code-style-guide-api-development-elysia.md`
- TypeScript Patterns: `code-style-guide-typescript-patterns.md`
- Clean Code Principles: `code-style-guide-clean-code-principles.md`
- Code Smells & Anti-Patterns: `code-style-guide-code-smells-anti-patterns.md`
- Naming Conventions: `code-style-guide-naming-conventions.md`
- Code Formatting & Organization: `code-style-guide-code-formatting-organization.md`
```

## Integration with Git Workflow

### Pre-commit Hook Setup
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
echo "🔍 Running pre-commit validation..."
./scripts/pre-commit-validation.sh
```

### Git Alias for Quick Validation
```bash
# Add to .gitconfig
[alias]
    validate-changes = "!f() { git diff --name-only --diff-filter=ACMRT | grep -E '\\.(ts|vue|js)$' | xargs bun run lint; }; f"
    check-style = "!f() { ./scripts/interactive-validation.sh; }; f"
```

## Resources

### Style Guide Reference (16 Documents)
**Core Development Guides:**
1. `code-style-guide-vuejs-patterns.md` - Vue 3 component structure
2. `code-style-guide-store-patterns-pinia.md` - Pinia store architecture
3. `code-style-guide-api-development-elysia.md` - Backend API development
4. `code-style-guide-typescript-patterns.md` - TypeScript patterns
5. `code-style-guide-styling-css.md` - SCSS, BEM, Vuetify styling

**Code Quality & Standards:**
6. `code-style-guide-clean-code-principles.md` - SOLID principles
7. `code-style-guide-code-smells-anti-patterns.md` - Common pitfalls
8. `code-style-guide-naming-conventions.md` - Naming consistency
9. `code-style-guide-code-formatting-organization.md` - File structure
10. `code-style-guide-project-structure-architecture.md` - Directory organization
11. `code-style-guide-code-quality-formatting.md` - ESLint with @stylistic rules

**Advanced Patterns & Performance:**
12. `code-style-guide-performance-best-practices.md` - Performance optimization
13. `code-style-guide-error-handling.md` - Error handling patterns
14. `code-style-guide-reactivity-patterns.md` - Vue 3 reactivity
15. `code-style-guide-testing-standards.md` - Testing patterns

**Main Reference:**
16. `code-style-guide.md` - Overview with links to all guides

### Quick Reference Commands
```bash
# Validate all changes
bun run lint && bun run type-check && bunx eslint .

# Validate specific file types
git diff --name-only | grep '\.vue$' | xargs bun run lint
git diff --name-only | grep '\.ts$' | xargs bun run type-check

# Show changes by category
git diff --name-only | grep '^components/'
git diff --name-only | grep '^stores/'
git diff --name-only | grep '^server/'
```
