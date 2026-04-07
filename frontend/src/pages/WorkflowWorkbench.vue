<template>
  <div class="workflow-workbench">
    <section class="workbench-toolbar">
      <div class="toolbar-copy">
        <div class="toolbar-eyebrow">{{ t('workbench.eyebrow') }}</div>
        <h1 class="toolbar-title">{{ t('workbench.title') }}</h1>
      </div>
      <button class="library-toggle" @click="handleToggleSidebar">
        <span>{{ isSidebarOpen ? t('workbench.hideLibrary') : t('workbench.showLibrary') }}</span>
      </button>
    </section>

    <div class="studio-grid">
      <aside v-if="isSidebarOpen" class="studio-library">
        <div class="panel-heading">
          <div>
            <div class="panel-eyebrow">{{ t('workbench.libraryEyebrow') }}</div>
            <div class="panel-title">{{ t('workbench.libraryTitle') }}</div>
          </div>
        </div>
        <WorkflowList
          ref="workflowListRef"
          :use-routing="false"
          :selected="selectedWorkflow"
          @select="handleSelect"
        />
      </aside>

      <section class="studio-stage" :class="{ 'studio-stage--wide': !isSidebarOpen }">
        <WorkflowView
          v-if="selectedWorkflow"
          :workflow-name="selectedWorkflow"
          :embedded="true"
          :key="selectedWorkflow"
          @refresh-workflows="handleRefreshWorkflows"
        />

        <div v-else class="placeholder">
          <div class="placeholder-panel">
            <div class="placeholder-icon">⌘</div>
            <div class="placeholder-title">{{ t('workbench.selectWorkflow') }}</div>
            <div class="placeholder-subtitle">{{ t('workbench.selectWorkflowDesc') }}</div>
            <button class="placeholder-action" @click="isSidebarOpen = true">
              {{ t('workbench.showLibrary') }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowList from './WorkflowList.vue'
import WorkflowView from './WorkflowView.vue'
import { t } from '../utils/i18n.js'
import { buildWorkflowPath, getLastWorkflowName, setLastWorkflowName } from '../utils/workflowSession.js'

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
    if (selectedWorkflow.value) {
      setLastWorkflowName(selectedWorkflow.value)
    }
  },
  { immediate: true }
)

function handleToggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
}

onMounted(() => {
  window.addEventListener('toggle-workflow-sidebar', handleToggleSidebar)
})

onBeforeUnmount(() => {
  window.removeEventListener('toggle-workflow-sidebar', handleToggleSidebar)
})

const handleSelect = async (name) => {
  const normalized = normalizeName(name)
  selectedWorkflow.value = normalized
  setLastWorkflowName(normalized)

  if (normalized) {
    await router.push({ path: `/workflows/${normalized}` })
  } else {
    await router.push({ path: '/workflows' })
  }

  window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
}

const handleRefreshWorkflows = async () => {
  if (workflowListRef.value?.loadWorkflows) {
    await workflowListRef.value.loadWorkflows()
  }
}

onMounted(async () => {
  const routeWorkflow = normalizeName(route.params.name)
  if (routeWorkflow) {
    setLastWorkflowName(routeWorkflow)
    return
  }

  const rememberedWorkflow = getLastWorkflowName()
  if (!rememberedWorkflow) {
    return
  }

  selectedWorkflow.value = rememberedWorkflow
  await router.replace({ path: buildWorkflowPath(rememberedWorkflow) })
})
</script>

<style scoped>
.workflow-workbench {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - 36px);
  min-height: calc(100vh - 36px);
  overflow: hidden;
}

.workbench-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 2px 0;
}

.toolbar-eyebrow,
.panel-eyebrow {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #738689;
}

.toolbar-title {
  margin: 6px 0 0;
  font-family: var(--mv-heading-font);
  font-size: 32px;
  line-height: 1.05;
  color: var(--mv-ink);
  letter-spacing: -0.04em;
}

.library-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  border: 1px solid rgba(21, 58, 64, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.84);
  color: #17353c;
  font-weight: 700;
  cursor: pointer;
}

.studio-grid {
  display: grid;
  grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);
  gap: 14px;
  min-height: 0;
  flex: 1;
}

.studio-library,
.studio-stage {
  min-height: 0;
  border-radius: var(--mv-radius-lg);
  background: rgba(255, 250, 242, 0.82);
  border: 1px solid var(--mv-line);
  box-shadow: var(--mv-shadow-soft);
}

.studio-library {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
  height: 100%;
}

.studio-stage {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
  height: 100%;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-title {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--mv-ink);
}

.toolbar-eyebrow,
.panel-eyebrow {
  color: var(--mv-ink-muted);
}

.library-toggle,
.placeholder-action {
  border: 1px solid var(--mv-line);
  background: var(--mv-primary);
  color: #fffaf2;
  box-shadow: 0 12px 26px rgba(30, 100, 107, 0.18);
}

.library-toggle:hover,
.placeholder-action:hover {
  background: var(--mv-primary-strong);
}

.studio-stage--wide {
  grid-column: 1 / -1;
}

.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.placeholder-panel {
  max-width: 520px;
  width: 100%;
  text-align: center;
  padding: 44px 32px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top, rgba(63, 180, 173, 0.12), transparent 45%),
    #fffaf2;
  border: 1px solid rgba(26, 63, 66, 0.08);
}

.placeholder-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  background: linear-gradient(135deg, #1c6a73, #efc570);
  color: white;
  font-size: 32px;
  font-weight: 700;
}

.placeholder-title {
  font-size: 28px;
  font-weight: 700;
  color: #19343b;
}

.placeholder-subtitle {
  margin-top: 12px;
  font-size: 15px;
  line-height: 1.8;
  color: #60757a;
}

.placeholder-action {
  margin-top: 22px;
  padding: 13px 20px;
  border: none;
  border-radius: 999px;
  background: #194f57;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 1080px) {
  .workbench-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .studio-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .workflow-workbench {
    height: auto;
    min-height: auto;
    overflow: visible;
  }

  .studio-library,
  .studio-stage {
    padding: 18px;
    border-radius: 24px;
  }

  .panel-title {
    font-size: 18px;
  }
}
</style>
