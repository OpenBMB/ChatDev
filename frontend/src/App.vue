<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'

const route = useRoute()

// Hide the sidebar on LaunchView, BatchRunView and WorkflowWorkbench
const showSidebar = computed(() => route.path !== '/launch' && route.path !== '/batch-run')
const isHomeRoute = computed(() => route.path === '/')
</script>

<template>
  <div class="app-container" :class="{ 'home-route': isHomeRoute }">
    <Sidebar v-if="showSidebar" />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-container.home-route {
  height: 100dvh;
  min-height: 100dvh;
  overflow: hidden;
}

.main-content {
  flex: 1;
  min-height: 0;
  background-color: white;
}

.home-route .main-content {
  overflow: hidden;
  background-color: #1a1a1a;
}

body {
  margin: 0;
  font-family: system-ui, sans-serif;
}
</style>
