import { ref, computed } from "vue";
import { defineStore } from "pinia";
import { authClient } from "@/lib/auth-client";
import { useNotificationStore } from "@/stores/NotificationStore";

/**
 * Billing store — Polar checkout/portal flows via the better-auth
 * client plugin. Checkout slug "monthly" maps to the product wired in
 * auth.ts (polar → checkout.products).
 */
export const useBillingStore = defineStore("billing", () => {
  const loading = ref(false);
  const checkoutPending = ref(false);

  const isLoading = computed(() => loading.value || checkoutPending.value);

  async function startCheckout(slug: string = "monthly") {
    checkoutPending.value = true;
    try {
      // polarClient's endpoint inference doesn't reduce under this
      // better-auth/@better-fetch matrix — call the endpoint directly
      // (see lib/auth-client.ts). Same route the generated
      // authClient.checkout() method would hit.
      await authClient.$fetch("/checkout", {
        method: "POST",
        body: { slug },
      });
    }
    catch (e) {
      useNotificationStore().error(
        e instanceof Error ? e.message : "Checkout failed",
      );
    }
    finally {
      checkoutPending.value = false;
    }
  }

  async function openPortal() {
    loading.value = true;
    try {
      await authClient.$fetch("/customer/portal");
    }
    catch (e) {
      useNotificationStore().error(
        e instanceof Error ? e.message : "Could not open billing portal",
      );
    }
    finally {
      loading.value = false;
    }
  }

  return {
    loading,
    isLoading,
    startCheckout,
    openPortal,
  };
});
