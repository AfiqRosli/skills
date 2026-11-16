<template>
  <v-layout class="minimal-layout">
    <v-app-bar flat>
      <v-app-bar-title>{{PROJECT_NAME}}</v-app-bar-title>
    </v-app-bar>
    <v-main>
      <slot />
    </v-main>
  </v-layout>
</template>
