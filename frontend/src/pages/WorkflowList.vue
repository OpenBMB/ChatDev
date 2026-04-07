<template>
  <div class="workflow-list">
    <div class="list-toolbar">
      <div class="toolbar-copy">
        <div class="toolbar-title">{{ t('workflows.libraryTitle') }}</div>
        <div class="toolbar-subtitle">{{ t('workflows.librarySubtitle', { count: filteredFiles.length }) }}</div>
      </div>
      <button class="create-btn" @click="openFormGenerator" :title="t('workflows.createWorkflow')">
        <span class="create-plus">+</span>
        <span>{{ t('workflows.createWorkflow') }}</span>
      </button>
    </div>

    <div class="search-shell">
      <span class="search-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="t('common.search')"
      />
    </div>

    <div v-if="loading" class="state-card">
      <div class="spinner"></div>
      <p>{{ t('workflows.loading') }}</p>
    </div>

    <div v-else-if="error" class="state-card">
      <div class="state-title">{{ error }}</div>
      <button @click="loadWorkflows()" class="retry-button">{{ t('common.retry') }}</button>
    </div>

    <div v-else class="groups-shell">
      <div v-for="group in groupedFiles" :key="group.organization" class="workflow-group">
        <div class="group-header-row">
          <button
            class="group-header"
            type="button"
            @click="toggleGroup(group.organization)"
            :title="isGroupCollapsed(group.organization) ? t('workflows.expandFolder') : t('workflows.collapseFolder')"
          >
            <div class="group-main">
              <span class="group-arrow">{{ isGroupCollapsed(group.organization) ? '▸' : '▾' }}</span>
              <span class="group-name">{{ group.label }}</span>
            </div>
            <span class="group-count">{{ t('workflows.folderCount', { count: group.files.length }) }}</span>
          </button>
          <button
            class="group-batch-action"
            type="button"
            @click="openMoveGroupModalForGroup(group, $event)"
          >
            {{ t('workflows.moveGroupBatch') }}
          </button>
        </div>

        <transition-group
          v-if="!isGroupCollapsed(group.organization)"
          name="file-fade"
          tag="div"
          class="group-files"
        >
          <div
            v-for="file in group.files"
            :key="file.name"
            :class="['file-item', { active: isSelected(file) }]"
            role="button"
            tabindex="0"
            @click="goToWorkflowView(file.name, $event)"
            @keydown.enter.prevent="goToWorkflowView(file.name, $event)"
            @keydown.space.prevent="goToWorkflowView(file.name, $event)"
          >
            <div class="file-item-top">
              <div class="file-name">{{ file.name }}</div>
              <span v-if="file.organization" class="file-folder-badge">{{ file.organization }}</span>
            </div>
            <div class="file-description">{{ file.description || t('common.noDescription') }}</div>
            <div class="file-meta">
              <span>{{ t('workflows.openWorkflow') }}</span>
              <button
                type="button"
                class="file-action"
                @click.stop="openMoveGroupModal(file, $event)"
              >
                {{ t('workflows.moveGroup') }}
              </button>
              <button
                type="button"
                class="file-action file-action-danger"
                @click.stop="deleteWorkflowFile(file, $event)"
              >
                {{ t('workflows.deleteWorkflow') }}
              </button>
            </div>
          </div>
        </transition-group>
      </div>

      <div v-if="groupedFiles.length === 0" class="state-card state-card--empty">
        <p>{{ t('workflows.empty') }}</p>
      </div>
    </div>

    <Teleport to="body">
      <FormGenerator
        v-if="showFormGenerator"
        :breadcrumbs="[{ node: 'DesignConfig', field: 'graph' }]"
        :recursive="false"
        @close="closeFormGenerator"
        @submit="handleFormGeneratorSubmit"
      />

      <div v-if="showMoveGroupModal" class="modal-overlay" @click.self="closeMoveGroupModal">
        <div class="group-modal">
          <div class="group-modal-header">
            <div>
              <div class="group-modal-eyebrow">{{ t('workflows.groupManagement') }}</div>
              <h3>{{ moveGroupModalTitle }}</h3>
              <p>{{ moveGroupSummary }}</p>
            </div>
            <button class="modal-close" type="button" @click="closeMoveGroupModal">×</button>
          </div>
          <div class="group-modal-body">
            <label for="move-group-name">{{ t('workflows.targetGroup') }}</label>
            <input
              id="move-group-name"
              v-model="moveGroupName"
              class="group-input"
              type="text"
              list="workflow-group-options"
              :placeholder="t('workflows.groupPlaceholder')"
              @keyup.enter="submitMoveGroup"
            />
            <datalist id="workflow-group-options">
              <option
                v-for="groupName in availableOrganizations"
                :key="groupName"
                :value="groupName"
              />
            </datalist>
            <div class="group-hint">{{ t('workflows.groupHint') }}</div>
            <div v-if="moveGroupError" class="group-error">{{ moveGroupError }}</div>
          </div>
          <div class="group-modal-actions">
            <button class="group-secondary-button" type="button" @click="clearMoveGroup">
              {{ t('workflows.moveToUngrouped') }}
            </button>
            <button class="group-secondary-button" type="button" @click="closeMoveGroupModal">
              {{ t('common.cancel') }}
            </button>
            <button
              class="group-primary-button"
              type="button"
              :disabled="moveGroupSaving"
              @click="submitMoveGroup"
            >
              {{ moveGroupSaving ? t('common.loading') : t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { deleteWorkflow, fetchWorkflowsWithDesc, updateWorkflowOrganization } from '../utils/apiFunctions.js'
import FormGenerator from '../components/FormGenerator.vue'
import { t } from '../utils/i18n.js'

const router = useRouter()
const props = defineProps({
  selected: {
    type: String,
    default: ''
  },
  useRouting: {
    type: Boolean,
    default: true
  }
})
const emit = defineEmits(['select'])
const yamlFiles = ref([])
const loading = ref(false)
const error = ref(null)

const showFormGenerator = ref(false)
const searchQuery = ref('')
const collapsedGroups = ref({})
const showMoveGroupModal = ref(false)
const moveGroupWorkflow = ref(null)
const moveGroupTargets = ref([])
const moveGroupSourceLabel = ref('')
const moveGroupName = ref('')
const moveGroupError = ref('')
const moveGroupSaving = ref(false)

const loadWorkflows = async () => {
  loading.value = true
  error.value = null

  const result = await fetchWorkflowsWithDesc()
  if (result.success) {
    yamlFiles.value = result.workflows
  } else {
    error.value = result.error
  }

  loading.value = false
}

defineExpose({
  loadWorkflows
})

const filteredFiles = computed(() => {
  const rawList = Array.isArray(yamlFiles.value) ? [...yamlFiles.value] : []
  const query = searchQuery.value.toLowerCase().trim()
  let result = rawList

  if (query) {
    result = rawList.filter((file) => {
      const name = (file?.name ?? '').toString().toLowerCase()
      const desc = (file?.description ?? '').toString().toLowerCase()
      const organization = (file?.organization ?? '').toString().toLowerCase()
      return name.includes(query) || desc.includes(query) || organization.includes(query)
    })
  }

  return result.sort((a, b) => {
    const nameA = a?.name ?? ''
    const nameB = b?.name ?? ''
    return nameA.localeCompare(nameB, 'zh')
  })
})

const groupedFiles = computed(() => {
  const groups = new Map()

  for (const file of filteredFiles.value) {
    const organization = (file?.organization || '').trim()
    const key = organization || '__ungrouped__'
    if (!groups.has(key)) {
      groups.set(key, {
        organization: key,
        label: organization || t('workflows.noFolder'),
        files: []
      })
    }
    groups.get(key).files.push(file)
  }

  return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label, 'zh'))
})

const availableOrganizations = computed(() => {
  const names = new Set()
  for (const file of yamlFiles.value) {
    const organization = String(file?.organization || '').trim()
    if (organization) {
      names.add(organization)
    }
  }
  return Array.from(names).sort((a, b) => a.localeCompare(b, 'zh'))
})

const moveGroupModalTitle = computed(() => {
  return moveGroupTargets.value.length > 1
    ? t('workflows.moveGroupBatchTitle')
    : t('workflows.moveGroupTitle')
})

const moveGroupSummary = computed(() => {
  const count = moveGroupTargets.value.length
  if (count > 1) {
    return t('workflows.moveGroupBatchSummary', {
      group: moveGroupSourceLabel.value || t('workflows.noFolder'),
      count
    })
  }
  return moveGroupTargets.value[0]?.name || moveGroupWorkflow.value?.name || ''
})

onMounted(() => {
  loadWorkflows()
})

const normalizeName = (fileName) => fileName?.replace?.('.yaml', '') ?? ''

const goToWorkflowView = (fileName, event = null) => {
  event?.currentTarget?.blur?.()
  const workflowName = normalizeName(fileName)
  if (props.useRouting) {
    router.push(`/workflows/${workflowName}`)
  }
  emit('select', workflowName)
}

const isSelected = (file) => {
  const name = normalizeName(file?.name)
  return props.selected && props.selected === name
}

const deleteWorkflowFile = async (file, event = null) => {
  event?.currentTarget?.blur?.()
  if (!file?.name) {
    return
  }
  const confirmed = window.confirm(t('workflows.deleteWorkflowConfirm', { name: file.name }))
  if (!confirmed) {
    return
  }
  const result = await deleteWorkflow(file.name)
  if (!result.success) {
    alert(result.message || t('workflows.deleteWorkflowFailed'))
    return
  }
  await loadWorkflows()
  if (isSelected(file)) {
    emit('select', '')
    if (props.useRouting) {
      router.push('/workflows')
    }
  }
}

const extractGraphIdFromPayload = (payload) => {
  if (!payload) return null
  const graphId = payload.fullYaml?.graph?.id
  if (!graphId) return null
  return String(graphId).trim()
}

const openFormGenerator = () => {
  showFormGenerator.value = true
}

const openMoveGroupModal = (file, event = null) => {
  event?.currentTarget?.blur?.()
  moveGroupWorkflow.value = file
  moveGroupTargets.value = file ? [file] : []
  moveGroupSourceLabel.value = file?.organization || t('workflows.noFolder')
  moveGroupName.value = String(file?.organization || '').trim()
  moveGroupError.value = ''
  showMoveGroupModal.value = true
}

const openMoveGroupModalForGroup = (group, event = null) => {
  event?.currentTarget?.blur?.()
  const groupKey = group?.organization || '__ungrouped__'
  const files = yamlFiles.value.filter((file) => {
    const organization = String(file?.organization || '').trim()
    return (organization || '__ungrouped__') === groupKey
  })
  moveGroupWorkflow.value = null
  moveGroupTargets.value = files
  moveGroupSourceLabel.value = group?.label || t('workflows.noFolder')
  moveGroupName.value = groupKey === '__ungrouped__' ? '' : String(group?.label || '').trim()
  moveGroupError.value = ''
  showMoveGroupModal.value = true
}

const closeMoveGroupModal = () => {
  showMoveGroupModal.value = false
  moveGroupWorkflow.value = null
  moveGroupTargets.value = []
  moveGroupSourceLabel.value = ''
  moveGroupName.value = ''
  moveGroupError.value = ''
  moveGroupSaving.value = false
}

const submitMoveGroup = async () => {
  const targets = moveGroupTargets.value.filter((file) => file?.name)
  if (!targets.length || moveGroupSaving.value) {
    return
  }
  moveGroupSaving.value = true
  moveGroupError.value = ''
  try {
    const nextGroupName = moveGroupName.value.trim()
    for (const target of targets) {
      const result = await updateWorkflowOrganization(target.name, nextGroupName)
      if (!result.success) {
        throw new Error(result.message || t('workflows.moveGroupFailed'))
      }
    }
    await loadWorkflows()
    closeMoveGroupModal()
  } catch (error) {
    moveGroupError.value = error?.message || t('workflows.moveGroupFailed')
  } finally {
    moveGroupSaving.value = false
  }
}

const clearMoveGroup = async () => {
  moveGroupName.value = ''
  await submitMoveGroup()
}

const toggleGroup = (groupKey) => {
  collapsedGroups.value = {
    ...collapsedGroups.value,
    [groupKey]: !collapsedGroups.value[groupKey]
  }
}

const isGroupCollapsed = (groupKey) => Boolean(collapsedGroups.value[groupKey])

const closeFormGenerator = () => {
  showFormGenerator.value = false
}

const handleFormGeneratorSubmit = async (payload) => {
  await loadWorkflows()
  showFormGenerator.value = false

  const graphId = extractGraphIdFromPayload(payload)
  if (!graphId) {
    return
  }

  const fileName = graphId.endsWith('.yaml') ? graphId : `${graphId}.yaml`
  goToWorkflowView(fileName)
}
</script>

<style scoped>
.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.list-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.toolbar-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--mv-ink);
}

.toolbar-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #6a7d80;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: none;
  border-radius: 999px;
  background: var(--mv-primary);
  color: #fffaf2;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(30, 100, 107, 0.18);
}

.create-plus {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
}

.search-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 250, 242, 0.9);
  border: 1px solid var(--mv-line);
}

.search-icon {
  display: inline-flex;
  color: #6b7d80;
}

.search-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: #18373d;
  font-size: 14px;
}

.groups-shell {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.workflow-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-header-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 18px;
  background: var(--mv-panel-muted);
  color: var(--mv-ink);
  cursor: pointer;
}

.group-batch-action {
  flex: 0 0 auto;
  padding: 0 12px;
  border: 1px solid rgba(30, 100, 107, 0.14);
  border-radius: 16px;
  background: rgba(255, 250, 242, 0.78);
  color: #1c6871;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.2;
  cursor: pointer;
  box-shadow: none;
}

.group-batch-action:hover {
  border-color: rgba(30, 100, 107, 0.28);
  background: #fffdf8;
  color: #143f46;
}

.group-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-arrow {
  color: #1c6871;
}

.group-name {
  font-size: 14px;
  font-weight: 700;
}

.group-count {
  font-size: 12px;
  color: #6c7c7f;
}

.group-files {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  text-align: left;
  padding: 16px;
  border: 1px solid var(--mv-line);
  border-radius: var(--mv-radius-md);
  background: rgba(255, 250, 242, 0.92);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.file-item:hover {
  transform: translateY(-1px);
  border-color: rgba(30, 100, 107, 0.24);
  background: #fffdf8;
  box-shadow: var(--mv-shadow-tight);
}

.file-item.active {
  border-color: rgba(30, 100, 107, 0.34);
  background: var(--mv-panel-green);
}

.file-item-top,
.file-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.file-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--mv-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-folder-badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(28, 104, 113, 0.1);
  color: #1c6871;
  font-size: 11px;
  font-weight: 700;
}

.file-description {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.65;
  color: #6c7c7f;
}

.file-meta {
  margin-top: 14px;
  font-size: 12px;
  font-weight: 700;
  color: #1c6871;
}

.file-action {
  flex: 0 0 auto;
  padding: 6px 10px;
  border: 1px solid rgba(30, 100, 107, 0.18);
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.86);
  color: #1c6871;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  cursor: pointer;
  box-shadow: none;
}

.file-action:hover {
  border-color: rgba(30, 100, 107, 0.32);
  background: #fffdf8;
  color: #143f46;
}

.file-action-danger {
  border-color: rgba(171, 69, 49, 0.18);
  color: #9c3c2e;
}

.file-action-danger:hover {
  border-color: rgba(171, 69, 49, 0.34);
  background: rgba(171, 69, 49, 0.08);
  color: #7d2c20;
}

.file-arrow {
  font-size: 18px;
}

.state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 34px 20px;
  border-radius: 24px;
  background: rgba(255, 250, 242, 0.72);
  color: var(--mv-ink-soft);
}

.state-card--empty {
  padding: 48px 20px;
}

.state-title {
  text-align: center;
  font-size: 14px;
  line-height: 1.7;
}

.spinner {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 3px solid rgba(28, 104, 113, 0.12);
  border-top-color: #1c6871;
  animation: spin 0.9s linear infinite;
}

.retry-button {
  padding: 10px 16px;
  border: none;
  border-radius: 999px;
  background: var(--mv-primary);
  color: #fffaf2;
  font-weight: 700;
  cursor: pointer;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(12, 29, 34, 0.28);
  backdrop-filter: blur(8px);
}

.group-modal {
  width: min(520px, 100%);
  border: 1px solid rgba(30, 100, 107, 0.14);
  border-radius: 28px;
  background: #fffaf2;
  color: var(--mv-ink);
  box-shadow: 0 24px 70px rgba(18, 51, 57, 0.22);
  overflow: hidden;
}

.group-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 26px 18px;
  border-bottom: 1px solid rgba(30, 100, 107, 0.1);
  background: linear-gradient(180deg, #fffdf8 0%, #fff6e8 100%);
}

.group-modal-eyebrow {
  margin-bottom: 8px;
  color: #1c6871;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.group-modal-header h3 {
  margin: 0;
  color: var(--mv-ink);
  font-size: 22px;
  line-height: 1.25;
}

.group-modal-header p {
  margin: 8px 0 0;
  color: #6c7c7f;
  font-size: 13px;
  line-height: 1.5;
}

.modal-close {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(30, 100, 107, 0.14);
  border-radius: 999px;
  background: #fffdf8;
  color: #36575d;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  box-shadow: none;
}

.modal-close:hover {
  border-color: rgba(30, 100, 107, 0.28);
  color: var(--mv-ink);
}

.group-modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 26px 8px;
}

.group-modal-body label {
  color: var(--mv-ink);
  font-size: 13px;
  font-weight: 800;
}

.group-input {
  width: 100%;
  min-height: 48px;
  padding: 0 16px;
  border: 1px solid rgba(30, 100, 107, 0.18);
  border-radius: 16px;
  background: #fffdf8;
  color: var(--mv-ink);
  font-size: 14px;
  outline: none;
}

.group-input:focus {
  border-color: rgba(30, 100, 107, 0.5);
  box-shadow: 0 0 0 4px rgba(30, 100, 107, 0.1);
}

.group-input::placeholder {
  color: #91a0a2;
}

.group-hint {
  color: #708285;
  font-size: 12px;
  line-height: 1.65;
}

.group-error {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(171, 69, 49, 0.1);
  color: #8f2f21;
  font-size: 13px;
  line-height: 1.5;
}

.group-modal-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  padding: 20px 26px 24px;
}

.group-secondary-button,
.group-primary-button {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.group-secondary-button {
  border: 1px solid rgba(30, 100, 107, 0.16);
  background: rgba(255, 253, 248, 0.9);
  color: #1c6871;
}

.group-secondary-button:hover {
  border-color: rgba(30, 100, 107, 0.3);
  background: #fffdf8;
}

.group-primary-button {
  border: none;
  background: var(--mv-primary);
  color: #fffaf2;
  box-shadow: 0 12px 24px rgba(30, 100, 107, 0.18);
}

.group-primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.file-fade-enter-active,
.file-fade-leave-active {
  transition: all 0.2s ease;
}

.file-fade-enter-from,
.file-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
