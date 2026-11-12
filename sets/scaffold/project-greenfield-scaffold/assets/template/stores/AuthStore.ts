import { ref, computed } from "vue";
import { defineStore } from "pinia";
import type { ErrorContext, SuccessContext } from "better-auth/vue";
import { authClient } from "@/lib/auth-client";
import { useNotificationStore } from "@/stores/NotificationStore";
import { normalizeEmail } from "@/utils/email";
import type { SessionUser } from "@/interfaces/common";
import type { RegistrationData } from "@/interfaces/auth";

/**
 * Auth store — all auth API calls live here (never in components).
 * UI reads state via storeToRefs; actions set loading/error and surface
 * failures through NotificationStore.
 */
export const useAuthStore = defineStore("auth", () => {
  const user = ref<SessionUser | null>(null);
  const isAuthenticated = ref(false);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const pendingVerificationEmail = ref<string | null>(null);

  const currentUser = computed(() => user.value);
  const isLoggedIn = computed(() => isAuthenticated.value);
  const hasError = computed(() => !!error.value);
  const isLoading = computed(() => loading.value);

  function setUser(userData: SessionUser) {
    user.value = userData;
    isAuthenticated.value = true;
  }

  function clearUser() {
    user.value = null;
    isAuthenticated.value = false;
  }

  async function register(userData: RegistrationData) {
    loading.value = true;
    error.value = null;

    try {
      const normalizedEmail = normalizeEmail(userData.email);

      await authClient.signUp.email(
        {
          email: normalizedEmail,
          password: userData.password,
          name: userData.name,
        },
        {
          onSuccess: () => {
            pendingVerificationEmail.value = normalizedEmail;
            void navigateTo("/verify-email");
          },
          onError: (ctx: ErrorContext) => {
            error.value = ctx.error.message || "Registration failed";
          },
        },
      );
    }
    catch (e) {
      error.value = e instanceof Error ? e.message : "Registration failed";
      useNotificationStore().error(error.value);
    }
    finally {
      loading.value = false;
    }
  }

  async function signIn(email: string, password: string) {
    loading.value = true;
    error.value = null;

    try {
      await authClient.signIn.email(
        { email: normalizeEmail(email), password },
        {
          onSuccess: (ctx: SuccessContext) => {
            setUser(ctx.data.user as SessionUser);
            void navigateTo("/");
          },
          onError: (ctx: ErrorContext) => {
            error.value = ctx.error.message || "Sign in failed";
          },
        },
      );
    }
    catch (e) {
      error.value = e instanceof Error ? e.message : "Sign in failed";
      useNotificationStore().error(error.value);
    }
    finally {
      loading.value = false;
    }
  }

  async function signOut() {
    await authClient.signOut();
    clearUser();
    void navigateTo("/sign-in");
  }

  return {
    user,
    isAuthenticated,
    loading,
    error,
    pendingVerificationEmail,
    currentUser,
    isLoggedIn,
    hasError,
    isLoading,
    setUser,
    clearUser,
    register,
    signIn,
    signOut,
  };
});
