---
name: cdo-documentation
description: Comprehensive workflow for agents to write, update, and maintain documentation in the project docs system — CDO-owned copy invoked by the delivery org's pipeline
---

# Documentation Workflow

## Overview

This workflow guides agents through the process of creating, updating, and maintaining documentation in the project's VitePress-based multi-dimensional documentation system. It ensures consistency, proper metadata formatting, adherence to established patterns, and proper integration with VitePress configuration.

## VitePress Context

The project uses VitePress as its documentation framework, which provides:

- **File-based routing**: Directory structure directly maps to URL paths
- **Sidebar configuration**: Navigation managed through `.vitepress/config.ts`
- **Markdown-based content**: All documentation written in CommonMark with Vue components
- **Multi-department structure**: Organized by functional areas with dedicated sidebars

## When to Use This Workflow

Use this workflow when you need to:

- Create new documentation files
- Update existing documentation
- Reorganize documentation structure
- Ensure documentation follows established patterns
- Add cross-references between documents

## Prerequisites

Before starting, ensure you:

- Understand the project documentation architecture
- Have access to the docs directory structure
- Know the target department and temporal pattern
- Have reviewed existing documentation for consistency

## Workflow Steps

### Step 1: Analyze Documentation Requirements

**Objective**: Determine the type, scope, department, and placement of documentation needed.

**Actions**:

1. **Identify Department Category**:
   - **Engineering**: Technical documentation, APIs, architecture, coding standards, testing
   - **Security**: Security policies, audit reports, incident response, compliance
   - **Product**: Product requirements, features, user guides, specifications
   - **Operations**: Infrastructure, deployment procedures, incident reports, monitoring
   - **Getting Started**: Onboarding, setup guides, quick start documentation

2. **Determine Documentation Type**:
   - API documentation → `engineering/api/`
   - Architecture documentation → `engineering/architecture/`
   - Feature documentation → `product/features/`
   - Operational procedures → `operations/procedures/`
   - Security documentation → `security/`
   - Testing documentation → `engineering/testing/`
   - Tools documentation → `engineering/tools/`

3. **Map to VitePress Structure**:
   - Review existing sidebar configuration in `docs/.vitepress/config.ts`
   - Identify appropriate department section and subsection
   - Determine if new sidebar group or item is needed
   - Check for existing related documents for cross-referencing

4. **Determine Temporal Pattern**:
   - `audit-trail`: Immutable, linear progression (security audits, compliance)
   - `evolving`: Versioned, living documents (API specs, features)
   - `fundamentals`: Stable core principles (coding guidelines, architecture)

5. **Assess Scope and Complexity**:
   - Single document or multi-part series
   - Cross-departmental dependencies
   - Technical depth required
   - Target audience expertise level

6. **VitePress Placement Analysis**:
   - File path mapping: `/docs/department/subsection/document.md`
   - URL generation: `/department/subsection/document`
   - Sidebar placement: Which group and position
   - Navigation impact: How it affects discoverability

**Verification**:

- [ ] Department category clearly identified
- [ ] Documentation type clearly identified
- [ ] Temporal pattern determined
- [ ] Scope and complexity assessed
- [ ] Target audience defined
- [ ] VitePress placement analyzed
- [ ] Sidebar configuration requirements understood

### Step 2: Plan Document Structure and VitePress Integration

**Objective**: Create a clear outline, structure, and VitePress integration plan for the documentation.

**Actions**:

1. **Create Document Outline**:
   - Main sections and subsections
   - Key concepts and terminology
   - Code examples and diagrams (Vue components supported)
   - Cross-reference opportunities
   - VitePress-specific features (tabs, code groups, etc.)

2. **Plan Metadata Requirements**:
   - Department assignment
   - Temporal pattern
   - Content type
   - Version information
   - Owner assignment
   - Cross-reference targets
   - VitePress frontmatter fields

3. **Design Navigation Flow**:
   - How users will discover this document
   - Related documents to reference
   - Logical reading order
   - Search optimization keywords
   - Sidebar placement strategy

4. **VitePress Configuration Planning**:
   - Determine file path: `/docs/department/subsection/document.md`
   - Plan sidebar configuration updates in `.vitepress/config.ts`
   - Identify if new sidebar group needed
   - Plan navigation menu updates if applicable
   - Consider VitePress features to enhance content

**Verification**:

- [ ] Document outline created
- [ ] Metadata requirements planned
- [ ] Navigation flow designed
- [ ] Cross-references identified
- [ ] VitePress file path determined
- [ ] Sidebar configuration planned
- [ ] VitePress features considered

### Step 3: Create Document with Proper VitePress Metadata

**Objective**: Write the document with correct YAML frontmatter, VitePress structure, and markdown formatting.

**Actions**:

1. **Apply VitePress Metadata Template**:

   ```yaml
   ---
   # Project Documentation Metadata
   department: [engineering|product|operations|security|getting-started]
   temporal_pattern: [audit-trail|evolving|fundamentals]
   content_type: [api-documentation|feature-documentation|operational-procedure|security-policy|architecture-guide|user-guide|etc.]
   version: v1.0
   last_reviewed: YYYY-MM-DD
   next_review: YYYY-MM-DD
   owner: @team-name
   status: [current-stable|legacy|deprecated|draft]

   # VitePress Frontmatter
   title: "Document Title"
   description: "Brief description for SEO and preview"
   outline: [2, 3] # Table of contents depth
   lastUpdated: true
   editLink: true

   # Cross-references
   cross_references:
     [department]:
       - /path/to/related/doc
   related_versions:
     previous: /path/to/previous/version
     next_preview: /path/to/next/version
   ---
   ```

2. **Write Document Content with VitePress Features**:
   - Follow established content patterns
   - Use VitePress markdown extensions (code groups, tabs, etc.)
   - Include Vue components where appropriate
   - Add practical examples and syntax-highlighted code
   - Use proper heading hierarchy for TOC generation
   - Include VitePress-specific features like `:::tip`, `:::warning`

3. **Implement Cross-References**:
   - Add links to related documents using relative paths
   - Ensure bidirectional references where appropriate
   - Use VitePress link format: `[text](/department/subsection/document)`
   - Test all links for validity
   - Consider adding related documents section

4. **Create File in Correct Location**:
   - Place file at: `/docs/department/subsection/document.md`
   - Ensure directory structure matches sidebar configuration
   - Use kebab-case for file names
   - Create index.md files for subsections if needed

**Verification**:

- [ ] VitePress frontmatter properly formatted
- [ ] File placed in correct directory structure
- [ ] Content follows VitePress patterns
- [ ] Cross-references implemented with correct paths
- [ ] Links tested and valid
- [ ] VitePress features properly used

### Step 4: Ensure Quality and Consistency

**Objective**: Review document for quality, accuracy, and consistency.

**Actions**:

1. **Content Quality Review**:
   - Technical accuracy verification
   - Clarity and readability assessment
   - Completeness of information
   - Proper grammar and spelling

2. **Format Consistency Check**:
   - Heading hierarchy consistency
   - Code block formatting
   - Table and list formatting
   - Link and reference formatting

3. **Cross-Reference Validation**:
   - All links point to valid documents
   - Bidirectional references maintained
   - Metadata cross-references accurate
   - Navigation paths logical

4. **Dead Link Detection and Resolution**:
   - Run VitePress development server to identify dead links
   - Use targeted grep searches for common dead link patterns
   - Convert all relative paths to absolute paths starting with `/`
   - Ensure directory links point to `index.md` files
   - Update cross-references to match existing file structure
   - Remove references to deleted/non-existent files

**Verification**:

- [ ] Content quality verified
- [ ] Format consistency checked
- [ ] Cross-references validated
- [ ] Dead links resolved
- [ ] Navigation tested

### Step 5: Update VitePress Configuration and Navigation

**Objective**: Ensure the document is discoverable and properly integrated with VitePress navigation including both sidebar and main navigation.

**Actions**:

1. **Update VitePress Sidebar Configuration**:
   - Edit `docs/.vitepress/config.ts`
   - Add document to appropriate department sidebar under `themeConfig.sidebar`
   - Position correctly within existing hierarchy
   - Create new sidebar group if needed
   - Use proper link format: `/department/subsection/document`
   - Maintain consistent indentation and TypeScript syntax

2. **Update Main Navigation Menu** (if applicable):
   - Edit `themeConfig.nav` array in `docs/.vitepress/config.ts`
   - Add new navigation items for major sections or reorganize existing ones
   - Update department landing pages to reflect new structure
   - Ensure proper categorization and logical grouping
   - Test navigation in development mode

3. **Synchronize Navigation Changes**:
   - Ensure sidebar and main navigation are consistent
   - Update department index pages to match navigation structure
   - Verify all links in navigation point to existing documents
   - Check for duplicate or orphaned navigation items

4. **Create Cross-Department Links**:
   - Update related documents with new references
   - Add to department index pages
   - Ensure bidirectional linking
   - Test cross-department navigation

5. **VitePress Development Testing**:
   - Run `bun run docs:dev` to test changes
   - Verify sidebar displays correctly
   - Test main navigation menu functionality
   - Test navigation and links
   - Check mobile responsiveness
   - Validate search functionality

**Verification**:

- [ ] VitePress sidebar configuration updated
- [ ] Main navigation menu updated if needed
- [ ] Navigation changes synchronized
- [ ] Cross-department links added
- [ ] Development mode testing completed
- [ ] Sidebar navigation tested
- [ ] Main navigation menu tested
- [ ] Navigation and links tested
- [ ] Mobile responsiveness verified

### Step 6: Final Review and VitePress Publication

**Objective**: Complete final checks and publish the documentation using VitePress build process.

**Actions**:

1. **Final Quality Assurance**:
   - Complete document review
   - Test all VitePress features and components
   - Verify metadata accuracy
   - Check mobile responsiveness
   - Validate accessibility compliance

2. **VitePress Build and Publication**:
   - Run `bun run docs:build` to generate static site
   - Test build output locally
   - Commit changes to version control
   - Deploy to production (Netlify, Vercel, etc.)
   - Update changelog if applicable

3. **Post-Publication Validation**:
   - Test in production environment
   - Verify VitePress search functionality
   - Check sidebar navigation in production
   - Validate all links and cross-references
   - Monitor for any build or runtime issues
   - Test performance and SEO

**Verification**:

- [ ] Final QA completed
- [ ] VitePress build successful
- [ ] Documentation deployed to production
- [ ] Production validation done
- [ ] All VitePress features working
- [ ] Performance and SEO verified
- [ ] Issues monitoring established

## Agent-Specific Guidelines

### For Technical Writers

- Focus on clarity and accuracy
- Use established terminology consistently
- Include practical examples
- Ensure proper technical depth

### For Engineers

- Include code examples and implementation details
- Provide technical specifications
- Document edge cases and error handling
- Include performance considerations

### For Product Managers

- Focus on user value and business context
- Include use cases and scenarios
- Document feature interactions
- Provide strategic context

### For Security Specialists

- Include security considerations
- Document compliance requirements
- Provide risk assessments
- Include audit trail information

## Quality Standards

### Content Requirements

- **Accuracy**: All technical information must be correct
- **Clarity**: Content must be easily understandable by target audience
- **Completeness**: Cover all essential aspects of the topic
- **Currency**: Information must be up-to-date and relevant

### Format Requirements

- **Metadata**: All documents must have proper YAML frontmatter
- **Structure**: Follow established heading hierarchy
- **Code**: Use proper syntax highlighting and formatting
- **Links**: All links must be valid and functional

### Cross-Reference Requirements

- **Bidirectional**: Related documents should reference each other
- **Relevant**: Only include truly related documents
- **Current**: Link to current versions, not deprecated ones
- **Tested**: All links must be tested for validity

## Troubleshooting

### VitePress-Specific Issues

**Build Errors**:

- Check VitePress configuration syntax in `.vitepress/config.ts`
- Verify all sidebar links point to existing files
- Ensure proper YAML frontmatter formatting
- Check for invalid Vue component usage
- Run `bun run docs:build --verbose` for detailed error messages

**Development Server Issues**:

- Clear VitePress cache: `rm -rf .vitepress/cache`
- Check port conflicts with other services
- Verify Node.js version compatibility
- Ensure all dependencies are installed: `bun install`

**Sidebar Configuration Problems**:

- Validate TypeScript syntax in config.ts
- Check for duplicate link paths
- Ensure proper array structure for sidebar items
- Test navigation in development mode

**Navigation Menu Issues**:

- Verify `themeConfig.nav` array syntax in config.ts
- Check for duplicate navigation items
- Ensure navigation links match existing file paths
- Test navigation menu responsiveness on mobile devices
- Verify navigation items are properly categorized

**Markdown Rendering Issues**:

- Check for invalid markdown syntax
- Verify Vue component imports and usage
- Test custom VitePress extensions (tabs, code groups)
- Validate link formats: `/department/subsection/document`

### General Documentation Issues

**Metadata Errors**:

- Check YAML frontmatter syntax
- Verify required VitePress fields are present
- Ensure project metadata fields are valid
- Test metadata parsing with VitePress

**Link Issues**:

- Verify file paths match VitePress routing
- Check for case sensitivity in URLs
- Ensure files exist at target locations
- Test links in both development and production

**Navigation Problems**:

- Check VitePress sidebar configuration
- Verify department-specific sidebar structures
- Test navigation menu updates
- Validate cross-department linking

**Quality Issues**:

- Review content for technical accuracy
- Check VitePress formatting consistency
- Validate Vue component functionality
- Test code examples and syntax highlighting

### Resolution Steps

1. **Identify Issue Type**: Determine if it's VitePress configuration, content, or navigation
2. **Check VitePress Logs**: Review build output and console errors
3. **Fix Root Cause**: Address the underlying issue, not just symptoms
4. **Test in Development**: Use `bun run docs:dev` to verify fixes
5. **Test Production Build**: Run `bun run docs:build` to ensure production readiness
6. **Update Related Items**: Ensure consistency across affected documents and configurations

## Maintenance

### Regular Tasks

- **Review Schedule**: Quarterly review of all documentation
- **Link Validation**: Monthly check of all cross-references
- **Metadata Updates**: Keep version and review dates current
- **Quality Audits**: Annual comprehensive quality review

### Version Management

- **Semantic Versioning**: Use proper version numbering
- **Change Tracking**: Document all significant changes
- **Backward Compatibility**: Maintain links to previous versions
- **Deprecation Process**: Properly handle outdated content

## Tools and Resources

### VitePress Development Tools

- **VitePress CLI**: `bun run docs:dev` for development, `bun run docs:build` for production
- **VitePress Config**: `.vitepress/config.ts` for sidebar (`themeConfig.sidebar`) and navigation (`themeConfig.nav`) management
- **Markdown Editor**: For content creation with VitePress syntax support
- **Vue DevTools**: For debugging Vue components in documentation
- **Link Checker**: For validation of internal and external links
- **Metadata Validator**: For frontmatter checking

### VitePress Reference Materials

- **VitePress Documentation**: [vitepress.dev](https://vitepress.dev/)
- **Project Style Guide**: Documentation standards and conventions
- **VitePress Templates**: Document templates for different types
- **Component Library**: Vue components available for documentation
- **Sidebar Configuration**: Examples and patterns for `.vitepress/config.ts`
- **Department Guidelines**: Writing guidelines for each department

## Success Criteria

Documentation is considered successful when:

- [ ] All VitePress frontmatter is properly formatted and complete
- [ ] Project metadata follows established patterns
- [ ] Content is accurate, clear, and comprehensive
- [ ] VitePress features (tabs, code groups, Vue components) work correctly
- [ ] Cross-references are bidirectional and functional
- [ ] Document is discoverable through VitePress navigation and search
- [ ] Sidebar configuration properly displays the document
- [ ] Development server runs without errors
- [ ] Production build completes successfully
- [ ] Target audience can easily understand and use information
- [ ] Document integrates seamlessly with the VitePress documentation system
- [ ] Mobile responsiveness and accessibility are maintained

## Related Workflows

- [Code Review](../code-review.md) - For technical documentation review
- [Quality Assurance](../quality-assurance.md) - For documentation testing
- [Release Management](../release-management.md) - For documentation publication
- [VitePress Deployment](../vitepress-deployment.md) - For VitePress-specific deployment procedures

## Quick Reference Commands

```bash
# Start development server
bun run docs:dev

# Build for production
bun run docs:build

# Preview production build
bun run docs:preview

# Clear cache (if needed)
rm -rf .vitepress/cache
```

## Dead Link Prevention Guidelines

### **Path Best Practices**

1. **Always Use Absolute Paths**: Start all internal links with `/` for VitePress compatibility
   - ✅ `/engineering/architecture/overview.md`
   - ❌ `../architecture/overview.md`

2. **Directory Links Should Point to Index Files**: When linking to directories, always specify the index file
   - ✅ `/security/index.md`
   - ❌ `/security/`

3. **Include File Extensions**: Always include `.md` extension for markdown files
   - ✅ `/product/features/avatar-system.md`
   - ❌ `/product/features/avatar-system`

### **Common Dead Link Patterns to Avoid**

1. **Non-existent Directories**: Avoid references to deleted/empty directories
   - ❌ `/operations/procedures/` (deleted)
   - ❌ `/security/policies/access-control` (non-existent)

2. **API Endpoint References**: Use architecture overview instead of specific API files
   - ✅ `/engineering/architecture/overview.md`
   - ❌ `/engineering/api/authentication/v2/endpoints`

3. **Feature Specification References**: Use existing files instead of planned ones
   - ✅ `/product/requirements/prfaq.md`
   - ❌ `/product/requirements/feature-specifications`

### **Link Validation Workflow**

1. **Development Server Check**: Run `bun docs:dev` and watch terminal for dead link warnings
2. **Targeted Grep Searches**: Search for common patterns like `operations/`, `api/`, `policies/`
3. **Cross-Reference Verification**: Ensure metadata cross-references match actual content
4. **Navigation Testing**: Click through all navigation links in the built documentation

### **When Files Are Deleted or Moved**

1. **Update All References**: Search for the old file path across the entire docs directory
2. **Update VitePress Config**: Remove deleted files from sidebar configuration
3. **Update Cross-References**: Fix both content links and metadata references
4. **Test Navigation**: Verify all navigation still works after changes

## VitePress File Structure Reference

```
docs/
├── .vitepress/
│   ├── config.ts          # Main configuration
│   ├── cache/             # Development cache
│   └── dist/              # Production build output
├── engineering/           # Engineering documentation
│   ├── api/              # API docs
│   ├── architecture/      # Architecture docs
│   └── testing/          # Testing docs
├── security/             # Security documentation
│   ├── policies/          # Security policies
│   └── procedures/       # Security procedures
├── product/              # Product documentation
│   ├── features/          # Feature docs
│   └── user-guides/      # User guides
├── operations/           # Operations documentation
│   ├── procedures/        # Operational procedures
│   └── infrastructure/    # Infrastructure docs
└── getting-started/       # Onboarding docs
```

---

**Last Updated**: 2026-04-25  
**Maintainer**: @technical-writing-team  
**Review Frequency**: Quarterly

**This workflow should be followed for all documentation creation and updates to ensure consistency and quality across the project documentation system.**
