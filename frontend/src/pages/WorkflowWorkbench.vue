<template>
  <div class="workflow-workbench">
    <div class="workflow-sidebar" :class="{ open: isSidebarOpen }">
      <WorkflowList
        ref="workflowListRef"
        :use-routing="false"
        :selected="selectedWorkflow"
        @select="handleSelect"
      />
    </div>
    <!-- Sidebar toggle button, positioned next to the sidebar -->
    <button 
      class="sidebar-toggle-btn" 
      :class="{ 'sidebar-open': isSidebarOpen }"
      @click="handleToggleSidebar" 
      aria-label="Toggle sidebar"
    >
      <span v-if="isSidebarOpen">‹</span>
      <span v-else>›</span>
    </button>
    <div class="workflow-viewer" :class="{ 'sidebar-open': isSidebarOpen }">
      <WorkflowView
        v-if="selectedWorkflow"
        :workflow-name="selectedWorkflow"
        :key="selectedWorkflow"
        @refresh-workflows="handleRefreshWorkflows"
      />
      <div v-else class="placeholder">
        <div class="placeholder-title"> Select a workflow</div>
        <div class="placeholder-subtitle">Choose a workflow from the list to view or edit.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowList from './WorkflowList.vue'
import WorkflowView from './WorkflowView.vue'

const route = useRoute()
const router = useRouter()
const workflowListRef = ref(null)

const normalizeName = (name) => name?.replace?.('.yaml', '') ?? ''
const selectedWorkflow = ref(normalizeName(route.params.name))
const isSidebarOpen = ref(true)

watch(
  () => route.params.name,
  (name) => {
    selectedWorkflow.value = normalizeName(name)
  },
  { immediate: true }
)

function handleToggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
  window.dispatchEvent(new CustomEvent('workflow-sidebar-state', { detail: { open: isSidebarOpen.value } }))
}

onMounted(() => {
  window.addEventListener('toggle-workflow-sidebar', handleToggleSidebar)
})

onBeforeUnmount(() => {
  window.removeEventListener('toggle-workflow-sidebar', handleToggleSidebar)
})

const handleSelect = (name) => {
  const normalized = normalizeName(name)
  selectedWorkflow.value = normalized

  // Minimize sidebar when an entry is selected
  isSidebarOpen.value = false
  window.dispatchEvent(new CustomEvent('workflow-sidebar-state', { detail: { open: isSidebarOpen.value } }))

  if (normalized) {
    router.push({ path: `/workflows/${normalized}` })
  } else {
    router.push({ path: '/workflows' })
  }
}

const handleRefreshWorkflows = async () => {
  // Reload workflows in WorkflowList
  if (workflowListRef.value?.loadWorkflows) {
    await workflowListRef.value.loadWorkflows()
  }
}
</script>

<style scoped>
.workflow-workbench {
  position: relative;
  display: flex;
  height: calc(100vh - 55px);
  background-color: #1a1a1a;
  color: #f2f2f2;
  overflow: hidden;
}

.workflow-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 400px;
  transform: translateX(calc(-100% + 10px));
  transition: transform 0.35s cubic-bezier(.77,.2,.05,1.0);
  z-index: 3;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background-color: #161616;
  overflow-y: auto;
  overflow-x: hidden;
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.35);
}
.workflow-sidebar.open {
  transform: translateX(0);
}

/* Sidebar toggle button - positioned next to the sidebar */
.sidebar-toggle-btn {
  position: absolute;
  left: 10px; /* Keep 10px visible when collapsed */
  top: 50%;
  transform: translateY(-50%);
  width: 12px;
  height: 72px;
  padding: 12px;
  background: linear-gradient(180deg, #252525, #1e1e1e);
  border: 1px solid rgba(160, 196, 255, 0.3);
  border-left: none;
  border-radius: 0 12px 12px 0;
  color: #a0c4ff;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  transition: left 0.35s cubic-bezier(.77,.2,.05,1.0), 
              background 0.2s, 
              color 0.2s,
              border-color 0.2s;
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.4);
}

.sidebar-toggle-btn.sidebar-open {
  left: 400px; /* Follow the sidebar when expanded */
}

.sidebar-toggle-btn:hover {
  background: linear-gradient(180deg, #333, #2a2a2a);
  color: #c0d8ff;
  border-color: rgba(160, 196, 255, 0.6);
  box-shadow: 4px 0 16px rgba(160, 196, 255, 0.15);
}

.sidebar-toggle-btn span {
  font-weight: 700;
  line-height: 1;
  text-shadow: 0 0 8px rgba(160, 196, 255, 0.5);
}

.workflow-viewer {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: margin-left 0.35s cubic-bezier(.77,.2,.05,1.0);
  margin-left: 10px; /* Match the visible width when the sidebar is collapsed */
}

.placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: transparent;
  color: rgba(235, 235, 235, 0.7);
  text-align: center;
  padding: 24px;
}

.placeholder::before {
  content: '';
  position: absolute;
  top: -150px;
  left: 0;
  right: 0;
  height: 500px;
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  filter: blur(120px);
  opacity: 0.15;
  z-index: 0;
  pointer-events: none;
}

.placeholder-title {
  position: relative;
  z-index: 1;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.placeholder-subtitle {
  position: relative;
  z-index: 1;
  font-size: 14px;
  color: rgba(235, 235, 235, 0.6);
}
</style>
