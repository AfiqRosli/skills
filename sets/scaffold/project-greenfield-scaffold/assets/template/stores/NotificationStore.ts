import { ref } from "vue";
import { defineStore } from "pinia";
import { logger } from "@/utils/logger";

interface Notification {
  id: number;
  message: string;
  type: "error" | "success" | "info" | "warning";
  timeout: number;
}

let nextId = 0;

/**
 * Single error/snackbar queue — the app root mounts one snackbar
 * (components/Common/NotificationSnackbar.vue) so every layout reaches
 * it. Stores and composables report failures here rather than managing
 * their own UI.
 */
export const useNotificationStore = defineStore("notification", () => {
  const notifications = ref<Notification[]>([]);
  const current = ref<Notification | null>(null);

  const notify = (
    message: string,
    type: Notification["type"] = "info",
    timeout = 5000,
  ) => {
    const notification: Notification = { id: nextId++, message, type, timeout };
    notifications.value.push(notification);
    if (!current.value) showNext();
  };

  const error = (message: string, timeout = 7000) => {
    logger.error("Notification", { message });
    notify(message, "error", timeout);
  };

  const showNext = () => {
    current.value = notifications.value.shift() ?? null;
  };

  const dismiss = () => {
    showNext();
  };

  return {
    current,
    notify,
    error,
    dismiss,
  };
});
