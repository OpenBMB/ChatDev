<template>
    <div class="sidebar">

        <nav class="sidebar-nav">
            <router-link to="/">Home</router-link>
            <router-link to="/tutorial">Tutorial</router-link>
            <router-link
                to="/workflows"
                :class="{ active: isWorkflowsActive }"
            >Workflows</router-link>
            <router-link to="/launch" target="_blank" rel="noopener">Launch</router-link>
            <router-link to="/batch-run" target="_blank" rel="noopener">Labaratory</router-link>
        </nav>
        <div class="sidebar-actions">
            <button class="settings-nav-btn" @click="showSettingsModal = true" title="Settings">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
            </button>
        </div>
    </div>
    <SettingsModal
      :is-visible="showSettingsModal"
      @update:is-visible="showSettingsModal = $event"
    />
</template>

<script setup>
import { RouterLink, useRoute } from 'vue-router'
import { computed, ref } from 'vue'
import SettingsModal from './SettingsModal.vue'

const showSettingsModal = ref(false)

const route = useRoute()
const isWorkflowsActive = computed(() => route.path.startsWith('/workflows'))


</script>

<style scoped>
.sidebar {
    width: 100%;
    background-color: #1a1a1a; /* Dark theme background */
    padding: 0 24px 0 0;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    height: 55px;
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid #4d4d4d;
    position: relative; /* For absolute positioning of actions */
    justify-content: center;
}

.sidebar-actions {
    position: absolute;
    right: 24px;
    top: 50%;
    transform: translateY(-50%);
}

.sidebar-nav {
    display: flex;
    flex-direction: row;
    gap: 24px;
    align-items: center;
    /* Remove auto margins to let flexbox center it if parent has justify-content: center */
    /* But since we just added justify-content: center to sidebar, we don't strictly need auto margins, 
       but they don't hurt if we want to be safe. */
    margin-left: auto;
    margin-right: auto;
}

.sidebar-nav a {
    text-decoration: none;
    color: #8e8e8e;
    font-weight: 500;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
    transition: color 0.2s ease;
}

.sidebar-nav a:hover {
    color: #f2f2f2;
}

.sidebar-nav a.router-link-active,
.sidebar-nav a.active {
    background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
    );
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    -webkit-text-fill-color: transparent;
}

.settings-nav-btn {
  background: transparent;
  border: none;
  color: #8e8e8e;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
}

.settings-nav-btn:hover {
  color: #f2f2f2;
}
</style>
