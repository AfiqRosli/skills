<script setup>
import { useAppStore } from "@/stores/AppStore";
import NotificationSnackbar from "@/components/Common/NotificationSnackbar.vue";

const appStore = useAppStore();
</script>

<template>
  <v-app theme="light">
    <NuxtLayout :name="appStore.layout">
      <NuxtPage />
    </NuxtLayout>
    <!-- The single error snackbar lives at the root so every layout
         (blank, minimal, app) reaches the queue — the layout name is
         dynamic, so a per-layout mount could silently drop errors. -->
    <ClientOnly>
      <NotificationSnackbar />
    </ClientOnly>
  </v-app>
</template>

<style lang="scss">
@use "@/assets/styles/settings";
</style>
