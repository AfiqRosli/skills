# Styling & CSS

## Overview

This document provides comprehensive styling guidelines and CSS patterns for the application. It covers SCSS conventions, BEM methodology, Vuetify theme variables, component styling patterns, responsive design, animations, and accessibility to ensure consistent, maintainable, and performant styles across the application.

## SCSS Conventions

- **Priority**: Vuetify utility classes first, then BEM for custom styles
- **Scoped Styles**: Use `scoped` for one-time use components
- **Global Styles**: Use `assets/styles/global.scss` for reusable classes
- **Vuetify Overrides**: Use `assets/styles/settings.scss` for theme variables

### BEM Naming Convention

```scss
// ✅ BEM structure
.card {
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
```

### BEM Best Practices

```scss
// ✅ Good - Clear hierarchy
.user-profile {
  &__avatar {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    
    &--large {
      width: 120px;
      height: 120px;
    }
  }

  &__info {
    &__name {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
    }

    &__email {
      color: var(--v-theme-secondary);
      font-size: 0.875rem;
    }
  }

  &__actions {
    margin-top: 1rem;
    
    &__button {
      margin-right: 0.5rem;
      
      &:last-child {
        margin-right: 0;
      }
    }
  }
}

// ❌ Bad - Inconsistent naming
.userProfile {
  .avatarLarge { // Should be &--large
    width: 120px;
  }
  
  .userName { // Should be &__name
    font-size: 1.25rem;
  }
  
  .userEmail { // Should be &__email
    color: #666;
  }
}
```

## Global Utility Classes

### Common Utilities

```scss
// assets/styles/global.scss
.cta-glow {
  position: relative !important;
  display: inline-block !important;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    background: linear-gradient(45deg, var(--v-theme-primary), var(--v-theme-accent));
    border-radius: 4px;
    opacity: 0.8;
    z-index: -1;
    transition: opacity 0.3s ease;
  }
  
  &:hover::before {
    opacity: 1;
  }
}

.shiny-radial-border {
  position: relative !important;
  isolation: isolate !important;
  
  &::before {
    content: '';
    position: absolute;
    inset: -2px;
    background: conic-gradient(
      from var(--v-theme-primary),
      through var(--v-theme-accent),
      to var(--v-theme-primary)
    );
    border-radius: 4px;
    z-index: -1;
    animation: rotate 3s linear infinite;
  }
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-truncate-2 {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.flex-column {
  display: flex;
  flex-direction: column;
}
```

### Layout Utilities

```scss
// assets/styles/global.scss
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
  
  &--narrow {
    max-width: 800px;
  }
  
  &--wide {
    max-width: 1400px;
  }
}

.grid {
  display: grid;
  gap: 1rem;
  
  &--2 {
    grid-template-columns: repeat(2, 1fr);
  }
  
  &--3 {
    grid-template-columns: repeat(3, 1fr);
  }
  
  &--4 {
    grid-template-columns: repeat(4, 1fr);
  }
}

.section {
  padding: 3rem 0;
  
  &--compact {
    padding: 1.5rem 0;
  }
  
  &--spacious {
    padding: 5rem 0;
  }
}
```

## Vuetify Theme Variables

### Theme Configuration

```scss
// assets/styles/settings.scss
@use "vuetify/settings" with (
  $utilities: false,
  $color-pack: true,
  $theme: (
    "light": (
      "primary": #1976d2,
      "secondary": #424242,
      "accent": #82b1ff,
      "error": #f44336,
      "warning": #ff9800,
      "info": #2196f3,
      "success": #4caf50,
    ),
    "dark": (
      "primary": #2196f3,
      "secondary": #424242,
      "accent": #ff4081,
      "error": #f44336,
      "warning": #ff9800,
      "info": #2196f3,
      "success": #4caf50,
    ),
  )
);
```

### Custom Theme Variables

```scss
// assets/styles/settings.scss
@use "vuetify/settings" with (
  $utilities: false,
  $color-pack: true,
  $theme: (
    "light": (
      "primary": #1976d2,
      "secondary": #424242,
      "accent": #82b1ff,
      "surface": #ffffff,
      "background": #fafafa,
      "error": #f44336,
      "warning": #ff9800,
      "info": #2196f3,
      "success": #4caf50,
      "text": {
        "primary": rgba(0, 0, 0, 0.87),
        "secondary": rgba(0, 0, 0, 0.6),
        "disabled": rgba(0, 0, 0, 0.38),
      },
    "border": {
        "color": rgba(0, 0, 0, 0.12),
        "opacity": 1,
      },
    "divider": rgba(0, 0, 0, 0.12),
    ),
    "dark": (
      "primary": #2196f3,
      "secondary": #424242,
      "accent": #ff4081,
      "surface": #121212,
      "background": #000000,
      "error": #f44336,
      "warning": #ff9800,
      "info": #2196f3,
      "success": #4caf50,
      "text": {
        "primary": rgba(255, 255, 255, 0.87),
        "secondary": rgba(255, 255, 255, 0.6),
        "disabled": rgba(255, 255, 255, 0.38),
      },
      "border": {
        "color": rgba(255, 255, 255, 0.12),
        "opacity": 1,
      },
      "divider": rgba(255, 255, 255, 0.12),
    ),
  )
);

// Custom variables for consistent spacing
$spacing-xs: 0.25rem;
$spacing-sm: 0.5rem;
$spacing-md: 1rem;
$spacing-lg: 1.5rem;
$spacing-xl: 2rem;
$spacing-xxl: 3rem;

// Custom variables for consistent typography
$font-size-xs: 0.75rem;
$font-size-sm: 0.875rem;
$font-size-md: 1rem;
$font-size-lg: 1.125rem;
$font-size-xl: 1.25rem;
$font-size-xxl: 1.5rem;

// Custom variables for consistent borders
$border-radius-sm: 0.25rem;
$border-radius-md: 0.5rem;
$border-radius-lg: 0.75rem;
$border-radius-xl: 1rem;
```

## Component Styling Patterns

### Vue Component Styles

```vue
<template>
  <!-- Use Vuetify utilities first -->
  <v-container class="user-card d-flex flex-column">
    <!-- Custom BEM classes when needed -->
    <div class="user-card__header">
      <h1 class="user-card__title">{{ title }}</h1>
    </div>
    
    <v-card class="user-card__content">
      <v-card-text class="user-card__text">
        {{ content }}
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped lang="scss">
.user-card {
  padding: $spacing-lg;
  border-radius: $border-radius-lg;
  background: var(--v-theme-surface);
  border: 1px solid var(--v-theme-divider);
  
  &__header {
    margin-bottom: $spacing-md;
    
    &--compact {
      margin-bottom: $spacing-sm;
    }
  }

  &__title {
    font-size: $font-size-xl;
    font-weight: 600;
    color: var(--v-theme-text-primary);
    line-height: 1.2;
  }

  &__content {
    flex: 1;
    
    &__text {
      color: var(--v-theme-text-secondary);
      line-height: 1.5;
    }
  }
}
</style>
```

### Responsive Design

```scss
// assets/styles/global.scss
@mixin respond-to($breakpoint) {
  @if $breakpoint == sm {
    @media (min-width: 600px) { @content; }
  }
  @if $breakpoint == md {
    @media (min-width: 960px) { @content; }
  }
  @if $breakpoint == lg {
    @media (min-width: 1264px) { @content; }
  }
  @if $breakpoint == xl {
    @media (min-width: 1920px) { @content; }
  }
}

// Usage
.user-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: $spacing-md;
  
  @include respond-to(md) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @include respond-to(lg) {
    grid-template-columns: repeat(3, 1fr);
  }
  
  @include respond-to(xl) {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

## Animation and Transitions

### CSS Transitions

```scss
// assets/styles/global.scss
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from {
  transform: translateY(20px);
  opacity: 0;
}

.slide-up-leave-to {
  transform: translateY(-20px);
  opacity: 0;
}

.scale-enter-active,
.scale-leave-active {
  transition: transform 0.2s ease;
}

.scale-enter-from,
.scale-leave-to {
  transform: scale(0.8);
  opacity: 0;
}
```

### Vue Transition Usage

```vue
<template>
  <transition name="fade" mode="out-in">
    <div v-if="show" class="modal">
      <!-- Modal content -->
    </div>
  </transition>
  
  <transition-group name="slide-up" tag="div" class="user-list">
    <div v-for="user in users" :key="user.id" class="user-item">
      {{ user.name }}
    </div>
  </transition-group>
</template>

<style scoped lang="scss">
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.user-list {
  display: grid;
  gap: $spacing-sm;
}

.user-item {
  padding: $spacing-md;
  background: var(--v-theme-surface);
  border-radius: $border-radius-md;
  border: 1px solid var(--v-theme-divider);
}
</style>
```

## Performance Optimization

### CSS Performance

```scss
// ✅ Good - Efficient selectors
.user-card {
  .user-card__title {
    // Direct child selector
  }
}

// ❌ Bad - Expensive selectors
.user-card div h1 span {
  // Too specific, slow to evaluate
}

// ✅ Good - Use CSS variables for repeated values
.button {
  background: var(--v-theme-primary);
  color: var(--v-theme-on-primary);
  padding: var(--spacing-md);
}

// ❌ Bad - Hardcoded values
.button {
  background: #1976d2;
  color: #ffffff;
  padding: 1rem;
}
```

### Bundle Optimization

```scss
// ✅ Good - Modular imports
@use './variables';
@use './mixins';
@use './components';

// ✅ Good - Group related styles
// _buttons.scss
.btn {
  // Base button styles
}

.btn--primary {
  // Primary button styles
}

.btn--secondary {
  // Secondary button styles
}

// ❌ Bad - Monolithic files
// _styles.scss - Everything in one file
```

## Accessibility

### ARIA-Friendly Styling

```scss
// ✅ Good - Focus states
.button {
  &:focus {
    outline: 2px solid var(--v-theme-primary);
    outline-offset: 2px;
  }
  
  &:focus:not(:focus-visible) {
    outline: none;
  }
}

// ✅ Good - High contrast
.text {
  color: var(--v-theme-text-primary);
  
  &--muted {
    color: var(--v-theme-text-secondary);
  }
  
  &--error {
    color: var(--v-theme-error);
  }
}

// ✅ Good - Accessible animations
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Screen Reader Support

```scss
// ✅ Good - Hidden elements for screen readers
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

// ✅ Good - Focus indicators
.focus-trap {
  outline: 2px solid var(--v-theme-primary);
  outline-offset: 2px;
}
```

## Dark Mode Support

### Theme-Aware Styles

```scss
// assets/styles/global.scss
:root {
  --bg-primary: var(--v-theme-surface);
  --text-primary: var(--v-theme-text-primary);
  --border-color: var(--v-theme-divider);
}

[data-theme="dark"] {
  --bg-primary: var(--v-theme-surface);
  --text-primary: var(--v-theme-text-primary);
  --border-color: var(--v-theme-divider);
}

// Usage
.card {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}
```

### Dynamic Theme Switching

```vue
<template>
  <div :data-theme="currentTheme">
    <slot />
  </div>
</template>

<script setup lang="ts">
const currentTheme = ref<'light' | 'dark'>('light');

const toggleTheme = () => {
  currentTheme.value = currentTheme.value === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', currentTheme.value);
  localStorage.setItem('theme', currentTheme.value);
};

onMounted(() => {
  const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
  if (savedTheme) {
    currentTheme.value = savedTheme;
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
});
</script>
```

## Resources

- [BEM Methodology](http://getbem.com/)
- [Sass Guidelines](https://sass-lang.com/guide)
- [Vuetify Theming](https://vuetifyjs.com/en/features/theming/)
- [CSS Performance](https://web.dev/fast/)
- [Web Accessibility Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
