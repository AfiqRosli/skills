<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/AuthStore";
import { storeToRefs } from "pinia";

definePageMeta({ layout: "blank" });

const authStore = useAuthStore();
const { loading, error } = storeToRefs(authStore);

const name = ref("");
const email = ref("");
const password = ref("");

const submit = () =>
  authStore.register({
    name: name.value,
    email: email.value,
    password: password.value,
  });
</script>

<template>
  <v-container class="register fill-height">
    <v-row
      justify="center"
      align="center"
    >
      <v-col
        cols="12"
        sm="8"
        md="4"
      >
        <v-card class="register__card pa-6">
          <h1 class="register__title text-h5 mb-4">
            Create account
          </h1>
          <v-form @submit.prevent="submit">
            <v-text-field
              v-model="name"
              label="Name"
              required
            />
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
              hint="Minimum 8 characters"
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
              Register
            </v-btn>
          </v-form>
          <p class="register__sign-in text-body-2 mt-4">
            Have an account? <NuxtLink to="/sign-in">Sign in</NuxtLink>
          </p>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
