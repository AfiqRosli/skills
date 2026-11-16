import { ref } from "vue";
import { defineStore } from "pinia";
import type { LayoutType } from "@/interfaces/app";
import { GUEST_ROUTES, APP_ROUTES } from "@/interfaces/app";

// useRoute is auto-imported by Nuxt — no explicit import, which also
// keeps the store unit-testable under vitest where "#app" doesn't
// resolve.
export const useAppStore = defineStore("app", () => {
  const layout = ref<LayoutType>("minimal");

  // Persistent navigation rail state
  const rail = ref<boolean>(false);

  const toggleRail = () => {
    rail.value = !rail.value;
  };

  // Route matching is case-insensitive and trailing-slash-tolerant —
  // normalize before comparing or a bare === miss falls through and
  // leaks the wrong layout chrome onto a page.
  const determineLayoutForPath = (path: string): LayoutType => {
    const normalized = path.replace(/\/+$/, "").toLowerCase() || "/";

    if (GUEST_ROUTES.includes(normalized as (typeof GUEST_ROUTES)[number])) {
      return "blank";
    }

    if (APP_ROUTES.includes(normalized as (typeof APP_ROUTES)[number])) {
      return "app";
    }

    return "minimal";
  };

  const route = useRoute();
  layout.value = determineLayoutForPath(route.path);

  watch(
    () => route.path,
    (path) => {
      layout.value = determineLayoutForPath(path);
    },
  );

  return {
    layout,
    rail,
    toggleRail,
    determineLayoutForPath,
  };
});
