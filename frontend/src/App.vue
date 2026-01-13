<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'

const route = useRoute()

// Hide the sidebar on LaunchView, BatchRunView and WorkflowWorkbench
const showSidebar = computed(() => route.path !== '/launch' && route.path !== '/batch-run')
</script>

<template>
  <div class="app-container">
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

.main-content {
  flex: 1;
  background-color: white;
}

body {
  margin: 0;
  font-family: system-ui, sans-serif;
}
</style>
