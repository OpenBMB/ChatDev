<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import SettingsModal from './components/SettingsModal.vue'

const route = useRoute()

const showSidebar = computed(() => route.path !== '/launch' && route.path !== '/batch-run')
const showSettingsModal = ref(false)
</script>

<template>
  <div class="app-container">
    <aside v-if="showSidebar" class="sidebar-shell">
      <Sidebar @open-settings="showSettingsModal = true" />
    </aside>
    <main class="main-content" :class="{ 'main-content--with-shell': showSidebar }">
      <router-view />
    </main>
    <SettingsModal
      :is-visible="showSettingsModal"
      @update:is-visible="showSettingsModal = $event"
    />
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(30, 100, 107, 0.1), transparent 22%),
    radial-gradient(circle at 85% 12%, rgba(197, 139, 42, 0.13), transparent 26%),
    linear-gradient(180deg, var(--mv-canvas) 0%, var(--mv-canvas-strong) 100%);
}

.sidebar-shell {
  width: 300px;
  flex-shrink: 0;
  padding: 18px 0 18px 18px;
  box-sizing: border-box;
}

.main-content {
  flex: 1;
  min-width: 0;
  padding: 18px;
  box-sizing: border-box;
}

.main-content--with-shell {
  padding-left: 12px;
}

:global(body) {
  margin: 0;
  font-family: "Inter", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: var(--mv-ink);
  background: var(--mv-canvas);
}

:global(#app) {
  min-height: 100vh;
}

@media (max-width: 1080px) {
  .app-container {
    flex-direction: column;
  }

  .sidebar-shell {
    width: 100%;
    padding: 16px 16px 0;
  }

  .main-content,
  .main-content--with-shell {
    padding: 16px;
  }
}
</style>
