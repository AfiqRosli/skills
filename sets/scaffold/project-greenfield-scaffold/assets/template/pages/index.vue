<script setup lang="ts">
useSeoMeta({
  title: "{{PROJECT_NAME}}",
  description: "{{PROJECT_NAME}} — describe the product in one sentence.",
});
</script>

<template>
  <v-container class="home-page">
    <v-row justify="center">
      <v-col
        cols="12"
        md="8"
      >
        <v-card class="home-page__card pa-8">
          <h1 class="home-page__title text-h3 mb-4">
            {{PROJECT_NAME}}
          </h1>
          <p class="home-page__subtitle text-body-1">
            Your greenfield project is scaffolded. Start building.
          </p>
          <!-- @flag auth -->
          <v-btn
            color="primary"
            to="/sign-in"
            class="mt-6"
          >
            Sign in
          </v-btn>
          <!-- @endflag auth -->
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style lang="scss" scoped>
.home-page {
  &__card {
    text-align: center;
  }
}
</style>
