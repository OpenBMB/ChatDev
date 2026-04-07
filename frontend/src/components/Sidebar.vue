<template>
  <div class="shell-nav">
    <div class="brand-card">
      <div class="brand-mark">MD</div>
      <div class="brand-copy">
        <div class="brand-eyebrow">{{ t('sidebar.productLabel') }}</div>
        <div class="brand-title">{{ t('sidebar.productTitle') }}</div>
        <p class="brand-subtitle">{{ t('sidebar.productSubtitle') }}</p>
      </div>
    </div>

    <div class="nav-section">
      <div class="section-label">{{ t('sidebar.sectionBuild') }}</div>
      <router-link
        :to="workflowStudioPath"
        :class="['nav-card', { active: route.path.startsWith('/workflows') }]"
      >
        <div class="nav-card-copy">
          <div class="nav-card-title">{{ t('sidebar.workflowStudio') }}</div>
          <div class="nav-card-subtitle">{{ t('sidebar.workflowStudioDesc') }}</div>
        </div>
        <span class="nav-card-arrow">↗</span>
      </router-link>
    </div>

    <div class="nav-section">
      <div class="section-label">{{ t('sidebar.sectionRun') }}</div>
      <router-link :to="launchCenterPath" :class="['nav-card', { active: route.path === '/launch' }]">
        <div class="nav-card-copy">
          <div class="nav-card-title">{{ t('sidebar.launchCenter') }}</div>
          <div class="nav-card-subtitle">{{ t('sidebar.launchCenterDesc') }}</div>
        </div>
        <span class="nav-card-arrow">↗</span>
      </router-link>
      <router-link to="/batch-run" :class="['nav-card', { active: route.path === '/batch-run' }]">
        <div class="nav-card-copy">
          <div class="nav-card-title">{{ t('sidebar.batchLab') }}</div>
          <div class="nav-card-subtitle">{{ t('sidebar.batchLabDesc') }}</div>
        </div>
        <span class="nav-card-arrow">↗</span>
      </router-link>
    </div>

    <button class="settings-button" @click="emit('open-settings')">
      <span>{{ t('settings.title') }}</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"></circle>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { t } from '../utils/i18n.js'
import { buildWorkflowPath, getLastWorkflowName, normalizeStoredWorkflowName } from '../utils/workflowSession.js'

const route = useRoute()
const emit = defineEmits(['open-settings'])
const activeWorkflowName = computed(() => {
  if (route.path.startsWith('/workflows')) {
    return normalizeStoredWorkflowName(route.params?.name)
  }
  return normalizeStoredWorkflowName(route.query?.workflow) || getLastWorkflowName()
})
const workflowStudioPath = computed(() => buildWorkflowPath(activeWorkflowName.value))
const launchCenterPath = computed(() => {
  const workflowName = activeWorkflowName.value
  if (!workflowName) {
    return '/launch'
  }
  return {
    path: '/launch',
    query: {
      workflow: `${workflowName}.yaml`
    }
  }
})
</script>

<style scoped>
.shell-nav {
  position: sticky;
  top: 18px;
  height: calc(100vh - 36px);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  box-sizing: border-box;
  border-radius: 22px;
  background: rgba(255, 252, 247, 0.92);
  border: 1px solid rgba(22, 51, 57, 0.08);
  box-shadow: 0 16px 40px rgba(18, 43, 48, 0.08);
  color: #17353c;
}

.brand-card {
  display: flex;
  gap: 14px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(247, 240, 214, 0.75), rgba(231, 245, 240, 0.92));
  border: 1px solid rgba(22, 51, 57, 0.08);
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #12373d;
  background: linear-gradient(135deg, #f3d58d, #8ce0c5);
}

.brand-copy {
  min-width: 0;
}

.brand-eyebrow,
.section-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #7a8d90;
}

.brand-title {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 700;
  color: #17353c;
}

.brand-subtitle {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #637679;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  text-decoration: none;
  color: inherit;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(22, 51, 57, 0.08);
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.nav-card:hover {
  border-color: rgba(31, 103, 109, 0.2);
  background: rgba(239, 246, 242, 0.96);
}

.nav-card.active {
  background: linear-gradient(135deg, rgba(239, 197, 112, 0.18), rgba(124, 212, 188, 0.18));
  border-color: rgba(31, 103, 109, 0.18);
}

.nav-card-copy {
  min-width: 0;
}

.nav-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #17353c;
}

.nav-card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #677a7d;
}

.nav-card-arrow {
  font-size: 18px;
  color: #a76f17;
}

.settings-button {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(22, 51, 57, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  color: #17353c;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.settings-button:hover {
  border-color: rgba(31, 103, 109, 0.2);
  background: rgba(239, 246, 242, 0.96);
}

.shell-nav {
  background: color-mix(in srgb, var(--mv-panel) 92%, white 8%);
  border-color: var(--mv-line);
  box-shadow: var(--mv-shadow-tight);
}

.brand-card {
  background:
    linear-gradient(180deg, rgba(255, 250, 242, 0.9), rgba(248, 241, 230, 0.94)),
    radial-gradient(circle at top right, rgba(197, 139, 42, 0.18), transparent 42%);
  border-color: var(--mv-line);
}

.brand-mark {
  border-radius: 14px;
  color: #fffaf2;
  background: #1e646b;
  box-shadow: inset 0 -10px 18px rgba(0, 0, 0, 0.12);
}

.brand-title,
.nav-card-title,
.settings-button {
  color: var(--mv-ink);
}

.brand-subtitle,
.nav-card-subtitle {
  color: var(--mv-ink-soft);
}

.brand-eyebrow,
.section-label {
  color: var(--mv-ink-muted);
}

.nav-card,
.settings-button {
  border-color: var(--mv-line);
  background: rgba(255, 250, 242, 0.72);
  box-shadow: none;
}

.nav-card:hover,
.settings-button:hover {
  transform: translateX(2px);
  border-color: rgba(30, 100, 107, 0.24);
  background: var(--mv-panel-green);
}

.nav-card.active {
  background: #183f45;
  border-color: #183f45;
  color: #fffaf2;
}

.nav-card.active .nav-card-title,
.nav-card.active .nav-card-subtitle,
.nav-card.active .nav-card-arrow {
  color: #fffaf2;
}

.nav-card-arrow {
  color: var(--mv-accent);
}

@media (max-width: 1080px) {
  .shell-nav {
    position: static;
    height: auto;
  }
}
</style>
