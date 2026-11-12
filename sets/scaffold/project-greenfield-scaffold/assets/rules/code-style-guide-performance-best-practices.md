---
trigger: always_on
---

# Performance & Best Practices

## Overview

This document provides comprehensive performance optimization guidelines and best practices for the application. It covers Vue performance patterns, API optimization, memory leak prevention, bundle optimization, database performance, and monitoring to ensure fast, efficient, and scalable applications.

## Vue Performance

### Computed Properties

Use computed for expensive calculations:

```typescript
// ✅ Use computed for expensive calculations
const expensiveFilter = computed(() => {
  return users.value.filter(user =>
    user.name.toLowerCase().includes(searchQuery.value.toLowerCase()) &&
    user.status === 'active'
  )
})

// ✅ Use computed for derived values
const fullName = computed(() => `${user.value.firstName} ${user.value.lastName}`);
const initials = computed(() => user.value.name.split(' ').map(n => n[0]).join('').toUpperCase());
```

### Reactive Optimization

Use shallowRef for large objects that don't need deep reactivity:

```typescript
// ✅ Use shallowRef for large objects
const largeDataset = shallowRef<LargeDataItem[]>([])
const userPreferences = shallowRef<UserPreferences>({})

// ✅ Use readonly for computed values that shouldn't be mutated
const readOnlyUser = readonly(user);
const readOnlyConfig = readonly(config);
```

### Template Optimization

```vue
<template>
  <!-- ✅ Use v-memo for template optimization -->
  <div 
    v-for="user in users" 
    :key="user.id" 
    v-memo="[user.id, user.status, user.lastUpdated]"
    class="user-item"
  >
    <UserCard :user="user" />
  </div>

  <!-- ✅ Use v-once for one-time events -->
  <div v-once:mounted="initializeChart"></div>

  <!-- ✅ Use v-show instead of v-if for frequent toggles -->
  <div v-show="isVisible" class="modal">
    <!-- Modal content -->
  </div>
</template>
```

### Debouncing and Throttling

```typescript
// ✅ Debounce search inputs
const debouncedSearch = useDebounceFn(searchUsers, 300)
watch(searchQuery, debouncedSearch)

// ✅ Throttle scroll events
const throttledScroll = useThrottleFn(handleScroll, 100)
window.addEventListener('scroll', throttledScroll)

// ✅ Debounce API calls
const debouncedApiCall = useDebounceFn(async (query: string) => {
  const { $api } = useNuxtApp();
  return await $api.get(`/search?q=${query}`);
}, 500)
```

## API Performance

### Caching Strategies

Implement caching for API calls:

```typescript
// ✅ Implement caching for API calls
const cachedApiCall = async <T>(
  key: string,
  apiCall: () => Promise<T>,
  ttl: number = 5 * 60 * 1000, // 5 minutes
): Promise<T> => {
  const cached = sessionStorage.getItem(key);
  
  if (cached) {
    const { data, timestamp } = JSON.parse(cached);
    if (Date.now() - timestamp < ttl) {
      return data;
    }
  }

  const result = await apiCall();
  sessionStorage.setItem(key, JSON.stringify({
    data: result,
    timestamp: Date.now(),
  }));
  
  return result;
};

// Usage
const users = await cachedApiCall('users', () => $api.get('/users'));
```

### Pagination

Implement pagination for large datasets:

```typescript
// ✅ Implement pagination for large datasets
const fetchPaginatedUsers = async (page: number, limit: number) => {
  const { $api } = useNuxtApp();
  return await $api.get("/users", {
    query: { page, limit },
  });
};

// Store implementation
export const useUserStore = defineStore("user", () => {
  const users = ref<User[]>([]);
  const currentPage = ref(1);
  const pageSize = ref(20);
  const totalUsers = ref(0);
  const loading = ref(false);

  const totalPages = computed(() => 
    Math.ceil(totalUsers.value / pageSize.value)
  );

  const hasNextPage = computed(() => 
    currentPage.value < totalPages.value
  );

  const fetchUsers = async (page: number = currentPage.value) => {
    loading.value = true;
    
    try {
      const { $api } = useNuxtApp();
      const response = await $api.get<{ users: User[], total: number }>("/users", {
        query: { page, limit: pageSize.value },
      });
      
      users.value = response.users;
      totalUsers.value = response.total;
      currentPage.value = page;
    } catch (error) {
      console.error("Failed to fetch users:", error);
    } finally {
      loading.value = false;
    }
  };

  return {
    users,
    currentPage,
    pageSize,
    totalPages,
    hasNextPage,
    loading,
    fetchUsers,
  };
});
```

### Request Deduplication

```typescript
// ✅ Use request deduplication
const pendingRequests = new Map<string, Promise<any>>();

const deduplicatedRequest = async <T>(
  key: string,
  apiCall: () => Promise<T>,
): Promise<T> => {
  if (pendingRequests.has(key)) {
    return pendingRequests.get(key);
  }

  const request = apiCall();
  pendingRequests.set(key, request);

  try {
    const result = await request;
    return result;
  } finally {
    pendingRequests.delete(key);
  }
};

// Usage
const user = await deduplicatedRequest(`user-${userId}`, () => 
  $api.get(`/users/${userId}`)
);
```

## Memory Leak Prevention

### Clean Up Event Listeners

```typescript
// ✅ Clean up watchers
const stopWatcher = watch(source, callback);

onUnmounted(() => {
  stopWatcher();
});

// ✅ Clean up event listeners
onMounted(() => {
  window.addEventListener("resize", handleResize);
  document.addEventListener("click", handleClick);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  document.removeEventListener("click", handleClick);
});

// ✅ Clean up timers
const timer = ref<NodeJS.Timeout | null>(null);

const startTimer = () => {
  timer.value = setTimeout(() => {
    console.log("Timer executed");
  }, 1000);
};

onUnmounted(() => {
  if (timer.value) {
    clearTimeout(timer.value);
  }
});
```

### Component Unmounting

```typescript
// ✅ Proper cleanup in composables
export const useWebSocket = (url: string) => {
  const socket = ref<WebSocket | null>(null);
  const isConnected = ref(false);

  const connect = () => {
    socket.value = new WebSocket(url);
    
    socket.value.onopen = () => {
      isConnected.value = true;
    };
    
    socket.value.onclose = () => {
      isConnected.value = false;
    };
  };

  const disconnect = () => {
    if (socket.value) {
      socket.value.close();
      socket.value = null;
      isConnected.value = false;
    }
  };

  onUnmounted(() => {
    disconnect();
  });

  return {
    socket: readonly(socket),
    isConnected: readonly(isConnected),
    connect,
    disconnect,
  };
};
```

## Bundle Optimization

### Code Splitting

```typescript
// ✅ Dynamic imports for code splitting
const AdminPanel = defineAsyncComponent(() => 
  import("@/components/AdminPanel.vue")
);

const LazyChart = defineAsyncComponent(() => 
  import("@/components/Chart.vue")
);

// Usage in template
<template>
  <div>
    <AdminPanel v-if="isAdmin" />
    <LazyChart :data="chartData" />
  </div>
</template>
```

### Tree Shaking

```typescript
// ✅ Use named exports for better tree-shaking
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

// ❌ Avoid default exports for utilities
export default {
  formatCurrency,
  formatDate,
  formatPhoneNumber,
};
```

### Asset Optimization

```typescript
// ✅ Lazy load images
const useLazyImage = (src: string) => {
  const imageLoaded = ref(false);
  const error = ref<string | null>(null);

  const loadImage = () => {
    imageLoaded.value = false;
    error.value = null;
    
    const img = new Image();
    img.onload = () => {
      imageLoaded.value = true;
    };
    img.onerror = () => {
      error.value = "Failed to load image";
    };
    img.src = src;
  };

  return {
    imageLoaded: readonly(imageLoaded),
    error: readonly(error),
    loadImage,
  };
};

// ✅ Preload critical resources
const preloadCriticalResources = () => {
  const criticalImages = [
    "/images/hero-banner.jpg",
    "/images/logo.png",
  ];
  
  criticalImages.forEach(src => {
    const link = document.createElement("link");
    link.rel = "preload";
    link.as = "image";
    link.href = src;
    document.head.appendChild(link);
  });
};
```

## Database Performance

### Query Optimization

```typescript
// ✅ Use efficient database queries
const fetchUsersWithPosts = async (userId: string) => {
  // Inefficient: N+1 queries
  const user = await db.query.users.findById(userId);
  const posts = await db.query.posts.findMany({ 
    where: eq(posts.userId, userId) 
  });

  // Efficient: Single query with joins
  const userWithPosts = await db.query.users.findMany({
    where: eq(users.id, userId),
    with: {
      posts: true,
    _count: true,
    _sum: {
      posts: {
        views: true,
      likes: true,
      },
    },
    },
  });

  return userWithPosts;
};

// ✅ Use proper indexes
const users = pgTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
  // Add indexes for frequently queried fields
  name: text("name").notNull(),
  status: text("status").notNull(),
});

// Create indexes
await db.execute(sql`
  CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
  CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
  CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
`);
```

### Connection Pooling

```typescript
// ✅ Use connection pooling for database
import { Pool } from "pg";

const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || "5432"),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  max: 20, // Maximum number of connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

export const db = drizzle(pool, { schema });
```

## Monitoring and Profiling

### Performance Monitoring

```typescript
// ✅ Performance monitoring setup
const usePerformanceMonitor = () => {
  const metrics = ref({
    pageLoadTime: 0,
    apiCallCount: 0,
    errorCount: 0,
  memoryUsage: 0,
  });

  const measurePageLoad = () => {
    const navigationEntry = performance.getEntriesByType("navigation")[0];
    if (navigationEntry) {
      metrics.value.pageLoadTime = navigationEntry.loadEventEnd - navigationEntry.loadEventStart;
    }
  };

  const trackApiCall = (duration: number) => {
    metrics.value.apiCallCount++;
    
    // Track slow API calls
    if (duration > 1000) {
      console.warn(`Slow API call detected: ${duration}ms`);
    }
  };

  const trackError = () => {
    metrics.value.errorCount++;
  };

  return {
    metrics: readonly(metrics),
    measurePageLoad,
    trackApiCall,
    trackError,
  };
};
```

### Memory Usage Monitoring

```typescript
// ✅ Memory usage monitoring
const useMemoryMonitor = () => {
  const memoryInfo = ref({
    used: 0,
    total: 0,
    percentage: 0,
  });

  const updateMemoryInfo = () => {
    if ("memory" in performance) {
      const memory = (performance as any).memory;
      memoryInfo.value = {
        used: Math.round(memory.usedJSHeapSize / 1024 / 1024),
        total: Math.round(memory.totalJSHeapSize / 1024 / 1024),
        percentage: Math.round((memory.usedJSHeapSize / memory.totalJSHeapSize) * 100),
      };
    }
  };

  // Monitor memory usage every 5 seconds
  const interval = setInterval(updateMemoryInfo, 5000);

  onUnmounted(() => {
    clearInterval(interval);
  });

  return {
    memoryInfo: readonly(memoryInfo),
    updateMemoryInfo,
  };
};
```

## Resources

- [Vue Performance Guide](https://vuejs.org/guide/best-practices/performance.html)
- [Web Performance Best Practices](https://web.dev/performance/)
- [JavaScript Memory Management](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Memory_Management)
- [Database Performance Optimization](https://www.postgresql.org/docs/performance-tips/)
- [Bundle Size Optimization](https://web.dev/performance/optimizing-content-efficiency/)
