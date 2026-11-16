<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/AuthStore";
import { storeToRefs } from "pinia";

definePageMeta({ layout: "blank" });

const authStore = useAuthStore();
const { loading, error } = storeToRefs(authStore);

const email = ref("");
const password = ref("");

const submit = () => authStore.signIn(email.value, password.value);
</script>

<template>
  <v-container class="sign-in fill-height">
    <v-row
      justify="center"
      align="center"
    >
      <v-col
        cols="12"
        sm="8"
        md="4"
      >
        <v-card class="sign-in__card pa-6">
          <h1 class="sign-in__title text-h5 mb-4">
            Sign in
          </h1>
          <v-form @submit.prevent="submit">
            <v-text-field
              v-model="email"
              label="Email"
              type="email"
              required
            />
            <v-text-field
              v-model="password"
              label="Password"
              type="password"
              required
            />
            <v-alert
              v-if="error"
              type="error"
              class="mb-4"
            >
              {{ error }}
            </v-alert>
            <v-btn
              type="submit"
              color="primary"
              block
              :loading="loading"
            >
              Sign in
            </v-btn>
          </v-form>
          <p class="sign-in__register text-body-2 mt-4">
            No account? <NuxtLink to="/register">Register</NuxtLink>
          </p>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
