<script setup lang="ts">
import { useAppStore } from "@/stores/AppStore";

const appStore = useAppStore();
</script>

<template>
  <v-layout class="app-layout">
    <v-navigation-drawer
      v-model="appStore.rail"
      :rail="!appStore.rail"
      permanent
    >
      <v-list>
        <v-list-item
          prepend-icon="mdi-home"
          title="Home"
          to="/"
        />
      </v-list>
    </v-navigation-drawer>

    <v-app-bar flat>
      <v-app-bar-nav-icon @click="appStore.toggleRail" />
      <v-app-bar-title>{{PROJECT_NAME}}</v-app-bar-title>
    </v-app-bar>

    <v-main>
      <slot />
    </v-main>
  </v-layout>
</template>
