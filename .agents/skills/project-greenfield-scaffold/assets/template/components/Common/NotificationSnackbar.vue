<script setup lang="ts">
import { computed } from "vue";
import { useNotificationStore } from "@/stores/NotificationStore";

const notificationStore = useNotificationStore();

const snackbar = computed({
  get: () => !!notificationStore.current,
  set: (value) => {
    if (!value) notificationStore.dismiss();
  },
});
</script>

<template>
  <v-snackbar
    v-model="snackbar"
    :color="notificationStore.current?.type || 'info'"
    :timeout="notificationStore.current?.timeout || 5000"
    location="bottom right"
    @update:model-value="notificationStore.dismiss"
  >
    {{ notificationStore.current?.message }}
    <template #actions>
      <v-btn
        variant="text"
        icon="mdi-close"
        @click="notificationStore.dismiss"
      />
    </template>
  </v-snackbar>
</template>
