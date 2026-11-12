---
name: cdo-review-implement-refinement
description: Code Review Implement Refinement - Implement refinements based on code review findings using bmad-agent-dev — CDO-owned copy invoked by the delivery org's pipeline
---

# Code Review Implement Refinement

## Overview

This workflow implements code refinements after `bmad-code-review` completes the code-alignment workflow. It leverages bmad-agent-dev (Amelia) to execute the implementation with strict adherence to acceptance criteria and testing standards.

**Input**: Code review findings provided in chat session from bmad-code-review (already classified, prioritized, and documented)
**Output**: Implemented refinements with tests and verification

## Prerequisites

1. **Code review completed** - bmad-code-review has finished and provided findings in chat session
2. **Findings available** - All findings are documented with severity, location, and description from code review session
3. **Project context loaded** - Ensure project context and style guides are accessible
4. **bmad-agent-dev available** - Verify the dev agent skill is accessible

## Step-by-Step Implementation Process

### Phase 1: Review Code Review Findings

#### Step 1: Retrieve Findings

Findings may be provided in either format:

**Option A: Document-based findings**
- Document will be attached by user in the next input session
- Review the attached document for findings, severity, locations, and recommendations

**Option B: Chat session findings**
- Findings provided directly in the chat session by the review agent
- Review the chat history for findings, severity, locations, and recommendations

#### Step 2: Review Findings Summary

Review the summary of findings from the code review:
- Total findings count
- Breakdown by severity (Critical, High, Medium, Low)
- Breakdown by category (Security, Performance, Code Quality, etc.)
- Affected files
- Estimated effort
- Style guide references

The findings should already be:
- **Classified by severity** (Critical, High, Medium, Low)
- **Categorized by type** (Security, Performance, Code Quality, etc.)
- **Mapped to style guides** - References to specific style guide sections
- **Prioritized** - In execution order based on dependencies and risk

### Phase 2: Prepare Implementation Tasks

#### Step 1: Create Implementation Task for Each Finding

For each finding from the code review, create an implementation task:

```markdown
## Implementation Task: [FINDING-ID] - [Title]

### From Code Review
- **Severity**: [Critical/High/Medium/Low]
- **Category**: [Security/Performance/Code Quality/etc.]
- **Style Guide**: `code-style-guide-[guide].md` - Section X.Y

### Location
- **File**: `path/to/file.ts`
- **Line**: `123`
- **Function**: `functionName`

### Issue Description (from code review)
[Detailed description from code review findings]

### Acceptance Criteria
- [ ] Issue is resolved according to style guide
- [ ] No new linting errors
- [ ] All existing tests pass
- [ ] New tests written for the fix
- [ ] No regressions in related functionality

### Test Requirements (from code review)
- **Unit Tests**: [Test requirements from code review]
- **Integration Tests**: [Integration test requirements from code review]
- **Regression Tests**: [Regression testing needs from code review]

### Affected Files
- `path/to/file.ts` - Primary file to modify
- `path/to/test.spec.ts` - Test file to update/create
- `interfaces/related.ts` - Interface file if needed

### Dependencies
- [Any dependencies identified in code review]

### Notes
- [Any additional context from code review]
```

### Phase 3: Invoke bmad-agent-dev for Implementation

#### Step 1: Activate bmad-agent-dev

```
Invoke skill: bmad-agent-dev
```

This activates Amelia (the dev agent) who will:
- Load project context
- Review style guides
- Prepare for implementation

#### Step 2: Provide Implementation Task to Amelia

Provide the implementation task with complete context from the code review findings:

```markdown
## Implementation Task from Code Review

### Task Information
- **Task ID**: [FINDING-ID]
- **Title**: [Title from code review]
- **Priority**: [Critical/High/Medium/Low] (from code review)
- **Category**: [Category from code review]

### Issue Description (from code review)
[Detailed description from code review findings]

### Location (from code review)
- **File**: `path/to/file.ts`
- **Line**: `123`
- **Function**: `functionName`

### Current Code (from code review)
```typescript
// Current implementation from code review
```

### Expected State
- **Description**: What the code should look like after fix
- **Style Guide Reference**: `code-style-guide-[guide].md` - Section X.Y (from code review)

### Acceptance Criteria
- [ ] Issue is resolved according to style guide
- [ ] No new linting errors
- [ ] All existing tests pass
- [ ] New tests written for the fix
- [ ] No regressions in related functionality

### Test Requirements (from code review)
- **Unit Tests**: [Requirements from code review]
- **Integration Tests**: [Requirements from code review]
- **Regression Tests**: [Requirements from code review]

### Affected Files (from code review)
- `path/to/file.ts` - Primary file to modify
- `path/to/test.spec.ts` - Test file to update/create
- `interfaces/related.ts` - Interface file if needed

### Dependencies (from code review)
- [Dependencies identified in code review]

### Notes (from code review)
- [Additional context from code review]
```

#### Step 3: Amelia Executes Implementation

Amelia will:
1. **Read the task completely** - Understand all requirements from code review
2. **Implement in order** - Follow acceptance criteria precisely
3. **Write tests first** - TDD approach
4. **Make minimal changes** - Fix only what's needed
5. **Run tests continuously** - Never proceed with failing tests
6. **Document changes** - Update the task record

### Phase 4: Verification & Documentation

#### Step 1: Verification

After Amelia completes implementation:
```bash
# Run linting
bun run lint

# Run formatting
bun run lintfix

# Run full test suite
bun run test

# Run type checking
bun run type-check
```

#### Step 2: Update Implementation Record

Track what was implemented:
```markdown
## Implementation Record: [FINDING-ID]

### Implemented By
- Agent: bmad-agent-dev (Amelia)
- Date: [YYYY-MM-DD]
- Duration: [X hours]

### Changes Made
- **Files Modified**:
  - `path/to/file.ts` - [Description of changes]
  - `path/to/test.spec.ts` - [Tests added/updated]

### Tests Added
- `test/path/to/file.spec.ts` - [Test description]
- [Additional tests]

### Verification Results
- [x] All tests pass
- [x] No linting errors
- [x] No type errors
- [x] Manual verification complete

### Decisions Made
- [Any decisions or trade-offs documented]

### Remaining Work
- [Any follow-up tasks identified]
```

#### Step 3: Report Implementation Status

Report the implementation status back to the user:
- Which findings were implemented
- Any issues encountered
- Verification results
- Next steps if needed

## Quality Gates

### Before Task Completion:
- [ ] All acceptance criteria met
- [ ] All tests pass (100%)
- [ ] No linting errors
- [ ] No type errors
- [ ] Code follows relevant style guide
- [ ] Tests written for the fix
- [ ] No regressions introduced

### Before Moving to Next Task:
- [ ] Current task fully verified
- [ ] Documentation updated
- [ ] Related tests passing
- [ ] No blocking issues

## Batch Implementation Strategy

### For Multiple Findings in Same File

When multiple findings affect the same file:
1. **Group them together** - Address all findings in one implementation
2. **Create single task** - With multiple acceptance criteria
3. **Coordinate tests** - Write comprehensive test suite
4. **Verify together** - Single verification pass

### For Related Findings Across Files

When findings are related across files:
1. **Identify relationships** - Map dependencies
2. **Sequence appropriately** - Implement in dependency order
3. **Test integration** - Verify cross-file functionality
4. **Document architecture** - Update architecture docs if needed

## Tools & Commands

### Verification Commands
```bash
# Lint specific files
bun run lint path/to/file.ts

# Format files
bun run lintfix path/to/file.ts

# Run specific tests
bun run test --grep="specificTest"

# Run full test suite
bun run test

# Type checking
bun run type-check
```

### Analysis Commands
```bash
# Find related files
grep -r "functionName" ./ --include="*.ts" --include="*.vue"

# Check test coverage
bun run test --coverage

# Find usages of modified code
grep -r "modifiedFunction" ./components/ ./stores/ ./composables/
```

## Batch Implementation Strategy

### For Multiple Findings in Same File

When multiple findings from code review affect the same file:
1. **Group them together** - Address all findings in one implementation task
2. **Create single task** - With multiple acceptance criteria (one per finding)
3. **Coordinate tests** - Write comprehensive test suite covering all findings
4. **Verify together** - Single verification pass

### For Related Findings Across Files

When findings from code review are related across files:
1. **Identify relationships** - Use dependency mapping from code review
2. **Sequence appropriately** - Implement in dependency order as specified in code review
3. **Test integration** - Verify cross-file functionality
4. **Document architecture** - Update architecture docs if needed

## Resources

### Style Guide Reference (16 Documents)

**Core Development Guides:**
1. **`code-style-guide.md`** - Main overview with links to all guides
2. **`code-style-guide-vuejs-patterns.md`** - Vue 3 component structure and patterns
3. **`code-style-guide-store-patterns-pinia.md`** - Pinia store architecture and patterns
4. **`code-style-guide-api-development-elysia.md`** - Backend API development with Elysia
5. **`code-style-guide-typescript-patterns.md`** - TypeScript patterns and type safety
6. **`code-style-guide-styling-css.md`** - SCSS, BEM, and Vuetify styling

**Code Quality & Standards Guides:**
7. **`code-style-guide-clean-code-principles.md`** - SOLID principles, DRY, KISS, YAGNI
8. **`code-style-guide-code-smells-anti-patterns.md`** - Common pitfalls and anti-patterns
9. **`code-style-guide-naming-conventions.md`** - Consistent naming across codebase
10. **`code-style-guide-code-formatting-organization.md`** - File structure and formatting
11. **`code-style-guide-project-structure-architecture.md`** - Directory organization and architecture
12. **`code-style-guide-code-quality-formatting.md`** - ESLint with @stylistic rules, quality tools

**Advanced Patterns & Performance Guides:**
13. **`code-style-guide-performance-best-practices.md`** - Performance optimization techniques
14. **`code-style-guide-error-handling.md`** - Error handling patterns and strategies
15. **`code-style-guide-reactivity-patterns.md`** - Vue 3 reactivity best practices
16. **`code-style-guide-testing-standards.md`** - Component, composable, and API testing

### Agent Skills
- **bmad-agent-dev** (Amelia) - Senior software engineer for implementation
- **bmad-code-review** - Comprehensive code review across quality facets

### Workflow Integration
- This workflow can be triggered after `bmad-code-review` completes
- Findings from code review feed directly into this workflow
- Implementation records feed back into code review for closure
