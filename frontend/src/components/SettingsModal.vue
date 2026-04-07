<template>
  <Transition name="modal-fade">
    <div v-if="isVisible" class="modal-overlay" @click.self="close">
      <div class="modal-content settings-modal">
        <div class="modal-header">
          <h3>{{ t('settings.title') }}</h3>
          <button class="close-button" @click="close">×</button>
        </div>

        <div class="modal-body">
          <section class="settings-section">
            <h4 class="section-title">{{ t('settings.interface') }}</h4>

            <div class="settings-item">
              <div class="language-row">
                <label class="field-label">{{ t('settings.language') }}</label>
                <div class="language-buttons">
                  <button
                    type="button"
                    class="language-button"
                    :class="{ active: localConfig.UI_LANGUAGE === 'zh' }"
                    @click="localConfig.UI_LANGUAGE = 'zh'"
                  >
                    {{ t('settings.chinese') }}
                  </button>
                  <button
                    type="button"
                    class="language-button"
                    :class="{ active: localConfig.UI_LANGUAGE === 'en' }"
                    @click="localConfig.UI_LANGUAGE = 'en'"
                  >
                    {{ t('settings.english') }}
                  </button>
                </div>
              </div>
            </div>

            <div class="settings-item">
              <label class="checkbox-label">
                <input type="checkbox" v-model="localConfig.AUTO_SHOW_ADVANCED">
                {{ t('settings.autoShowAdvanced') }}
              </label>
              <p class="setting-desc">{{ t('settings.autoShowAdvancedDesc') }}</p>
            </div>

            <div class="settings-item">
              <label class="checkbox-label">
                <input type="checkbox" v-model="localConfig.AUTO_EXPAND_MESSAGES">
                {{ t('settings.autoExpandMessages') }}
              </label>
              <p class="setting-desc">{{ t('settings.autoExpandMessagesDesc') }}</p>
            </div>

            <div class="settings-item">
              <label class="checkbox-label">
                <input type="checkbox" v-model="localConfig.ENABLE_HELP_TOOLTIPS">
                {{ t('settings.enableHelpTooltips') }}
              </label>
              <p class="setting-desc">{{ t('settings.enableHelpTooltipsDesc') }}</p>
            </div>
          </section>

          <section class="settings-section">
            <div class="section-heading">
              <div>
                <h4 class="section-title">{{ t('settings.modelProfiles') }}</h4>
                <p class="section-note">
                  {{ t('settings.modelProfilesDesc') }}
                  <br>
                  <code>MODEL_NAME</code>, <code>BASE_URL</code>, and <code>API_KEY</code>.
                </p>
              </div>
              <button class="add-profile-button" type="button" @click="addProfile">{{ t('settings.addProfile') }}</button>
            </div>

            <div v-if="!localConfig.MODEL_PROFILES.length" class="empty-profiles">
              {{ t('settings.noProfiles') }}
            </div>

            <div v-else class="profile-list">
              <article
                v-for="profile in localConfig.MODEL_PROFILES"
                :key="profile.id"
                class="profile-card"
                :class="{ active: localConfig.ACTIVE_MODEL_PROFILE_ID === profile.id }"
              >
                <div class="profile-card-header">
                  <label class="default-radio">
                    <input
                      :checked="localConfig.ACTIVE_MODEL_PROFILE_ID === profile.id"
                      name="default-model-profile"
                      type="radio"
                      @change="setActiveProfile(profile.id)"
                    >
                    <span>{{ t('settings.useAsDefault') }}</span>
                  </label>
                  <button class="remove-profile-button" type="button" @click="removeProfile(profile.id)">
                    {{ t('common.remove') }}
                  </button>
                </div>

                <div class="profile-grid">
                  <label class="profile-field">
                    <span>{{ t('settings.profileName') }}</span>
                    <input v-model.trim="profile.label" type="text" :placeholder="t('settings.profileNamePlaceholder')" />
                  </label>

                  <label class="profile-field">
                    <span>{{ t('settings.modelName') }}</span>
                    <input v-model.trim="profile.modelName" type="text" :placeholder="t('settings.modelNamePlaceholder')" />
                  </label>

                  <label class="profile-field profile-field-full">
                    <span>{{ t('settings.baseUrl') }}</span>
                    <input v-model.trim="profile.baseUrl" type="text" :placeholder="t('settings.baseUrlPlaceholder')" />
                  </label>

                  <label class="profile-field profile-field-full">
                    <span>{{ t('settings.apiKey') }}</span>
                    <input v-model.trim="profile.apiKey" type="password" :placeholder="t('settings.apiKeyPlaceholder')" />
                  </label>
                </div>
              </article>
            </div>
          </section>

          <section class="settings-section">
            <div class="section-heading">
              <div>
                <h4 class="section-title">{{ t('settings.clawhubTitle') }}</h4>
                <p class="section-note">{{ t('settings.clawhubDesc') }}</p>
              </div>
              <button class="secondary-button" type="button" @click="loadClawHubPacks">
                {{ t('settings.refreshClawhub') }}
              </button>
            </div>

            <div class="settings-item">
              <p class="setting-desc setting-desc-inline">
                {{ clawhubAvailable ? t('settings.clawhubAvailable') : t('settings.clawhubMissing') }}
              </p>
            </div>

            <div v-if="clawhubNotes.length" class="notes-list">
              <span v-for="note in clawhubNotes" :key="note" class="note-chip">{{ note }}</span>
            </div>

            <div v-if="clawhubPacks.length" class="pack-list">
              <article v-for="pack in clawhubPacks" :key="pack.id" class="pack-card">
                <div class="pack-card-header">
                  <div>
                    <h5>{{ pack.title || pack.id }}</h5>
                    <p>{{ pack.description }}</p>
                  </div>
                  <span class="pack-count">{{ t('settings.packSkillCount', { count: pack.skills?.length || 0 }) }}</span>
                </div>

                <div v-if="pack.skills?.length" class="skill-chip-list">
                  <span v-for="skill in pack.skills" :key="`${pack.id}-${skill}`" class="skill-chip">{{ skill }}</span>
                </div>

                <div v-if="pack.recommended_mcp_presets?.length" class="recommended-mcp">
                  <span class="recommended-label">{{ t('settings.recommendedMcp') }}</span>
                  <div class="skill-chip-list">
                    <span
                      v-for="preset in pack.recommended_mcp_presets"
                      :key="`${pack.id}-${preset}`"
                      class="skill-chip skill-chip-accent"
                    >
                      {{ preset }}
                    </span>
                  </div>
                </div>

                <div v-if="pack.recommended_workflow_templates?.length" class="recommended-mcp">
                  <span class="recommended-label">{{ t('settings.recommendedTemplates') }}</span>
                  <div class="skill-chip-list">
                    <span
                      v-for="templateId in pack.recommended_workflow_templates"
                      :key="`${pack.id}-${templateId}`"
                      class="skill-chip"
                    >
                      {{ getTemplateTitleById(templateId) }}
                    </span>
                  </div>
                </div>

                <div class="pack-actions">
                  <button
                    v-if="pack.recommended_mcp_details?.length"
                    class="secondary-button"
                    type="button"
                    @click="openMcpInjectionFlow(pack.recommended_mcp_details)"
                  >
                    {{ t('settings.injectRecommendedMcpSet') }}
                  </button>
                  <button
                    v-if="pack.recommended_workflow_templates?.length"
                    class="secondary-button"
                    type="button"
                    @click="openPackTemplates(pack)"
                  >
                    {{ t('settings.openRecommendedTemplates') }}
                  </button>
                  <button
                    class="secondary-button"
                    type="button"
                    :disabled="installingPackId === pack.id"
                    @click="handleInstallPack(pack.id, true)"
                  >
                    {{ t('settings.dryRunInstall') }}
                  </button>
                  <button
                    class="confirm-button"
                    type="button"
                    :disabled="installingPackId === pack.id"
                    @click="handleInstallPack(pack.id, false)"
                  >
                    {{ installingPackId === pack.id ? t('settings.installing') : t('settings.installPack') }}
                  </button>
                </div>
              </article>
            </div>

            <div v-else class="empty-profiles">
              {{ t('settings.noClawhubPacks') }}
            </div>

            <div class="settings-item">
              <div class="section-heading section-heading-tight">
                <div>
                  <h4 class="section-title">{{ t('settings.mcpPresetsTitle') }}</h4>
                  <p class="section-note">{{ t('settings.mcpPresetsDesc') }}</p>
                </div>
                <button class="secondary-button" type="button" @click="loadMcpPresetStatuses">
                  {{ t('settings.refreshMcpStatus') }}
                </button>
              </div>

              <div v-if="mcpPresets.length" class="pack-list">
                <article v-for="preset in mcpPresets" :key="preset.id" class="pack-card">
                  <div class="pack-card-header">
                    <div>
                      <h5>{{ preset.title || preset.id }}</h5>
                      <p>{{ preset.description }}</p>
                    </div>
                    <div class="preset-badge-stack">
                      <span class="pack-count">{{ preset.mode }}</span>
                      <span
                        class="preset-status-badge"
                        :class="{
                          'is-online': getMcpPresetStatus(preset.id)?.protocol_ready,
                          'is-warn': getMcpPresetStatus(preset.id)?.online && !getMcpPresetStatus(preset.id)?.protocol_ready,
                          'is-offline': getMcpPresetStatus(preset.id) && !getMcpPresetStatus(preset.id)?.online
                        }"
                      >
                        {{
                          !getMcpPresetStatus(preset.id)
                            ? t('settings.mcpStatusUnknown')
                            : getMcpPresetStatus(preset.id)?.protocol_ready
                              ? t('settings.mcpStatusReady')
                              : getMcpPresetStatus(preset.id)?.online
                                ? t('settings.mcpStatusReachable')
                              : t('settings.mcpStatusOffline')
                        }}
                      </span>
                    </div>
                  </div>
                  <div class="preset-meta-list">
                    <div class="preset-meta-row">
                      <span class="recommended-label">{{ t('settings.mcpServer') }}</span>
                      <code>{{ preset.server }}</code>
                    </div>
                    <div class="preset-meta-row">
                      <span class="recommended-label">{{ t('settings.mcpSetupHint') }}</span>
                      <span class="preset-meta-text">{{ preset.setup_hint }}</span>
                    </div>
                    <div v-if="getMcpPresetStatus(preset.id)?.reason" class="preset-meta-row">
                      <span class="recommended-label">{{ t('settings.mcpNetworkReason') }}</span>
                      <span class="preset-meta-text">{{ getMcpPresetStatus(preset.id)?.reason }}</span>
                    </div>
                    <div v-if="getMcpPresetStatus(preset.id)" class="preset-meta-row">
                      <span class="recommended-label">{{ t('settings.mcpProtocolReason') }}</span>
                      <span class="preset-meta-text">
                        {{
                          getMcpPresetStatus(preset.id)?.protocol_ready
                            ? t('settings.mcpListToolsOk', { count: getMcpPresetStatus(preset.id)?.tool_count || 0 })
                            : getMcpPresetStatus(preset.id)?.protocol_reason || t('settings.mcpStatusUnknown')
                        }}
                      </span>
                    </div>
                  </div>
                  <div class="pack-actions">
                    <button
                      class="secondary-button"
                      type="button"
                      @click="openMcpInjectionFlow(preset)"
                    >
                      {{ t('settings.injectMcpPreset') }}
                    </button>
                    <button
                      class="secondary-button"
                      type="button"
                      @click="copyMcpSnippet(preset)"
                    >
                      {{ t('settings.copyMcpSnippet') }}
                    </button>
                  </div>
                </article>
              </div>
              <div v-else class="empty-profiles">
                {{ t('settings.noMcpPresets') }}
              </div>
            </div>

            <div class="settings-item">
              <div class="section-heading section-heading-tight">
                <div>
                  <h4 class="section-title">{{ t('settings.availableSkills') }}</h4>
                  <p class="section-note">{{ t('settings.availableSkillsDesc') }}</p>
                </div>
              </div>

              <div v-if="installedSkills.length" class="installed-skills-list">
                <div v-for="skill in installedSkills" :key="skill.path" class="installed-skill-row">
                  <div>
                    <strong>{{ skill.name }}</strong>
                    <p>{{ skill.description }}</p>
                  </div>
                  <span class="skill-source-badge">
                    {{ skill.source === 'workspace' ? t('settings.workspaceSkill') : t('settings.bundledSkill') }}
                  </span>
                </div>
              </div>
              <div v-else class="empty-profiles">
                {{ t('settings.noInstalledSkills') }}
              </div>
            </div>

            <div v-if="clawhubOutput" class="install-output">
              <div class="install-output-header">
                <h5>{{ t('settings.installOutput') }}</h5>
              </div>
              <pre>{{ clawhubOutput }}</pre>
            </div>
          </section>
        </div>

        <div class="modal-footer">
          <button class="cancel-button" @click="close">{{ t('common.cancel') }}</button>
          <button class="confirm-button" @click="save">{{ t('common.save') }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { configStore, defaultSettings } from '../utils/configStore.js'
import { t } from '../utils/i18n.js'
import { fetchClawHubStarterPacks, fetchMcpPresetStatuses, installClawHubStarterPack } from '../utils/apiFunctions.js'
import { workflowTemplates } from '../utils/workflowTemplates.js'

const props = defineProps({
  isVisible: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:isVisible', 'close'])
const route = useRoute()
const router = useRouter()

const clone = (value) => JSON.parse(JSON.stringify(value))

const createProfile = () => ({
  id: (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `profile_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
  label: '',
  modelName: '',
  baseUrl: '',
  apiKey: ''
})

const normalizeProfiles = (profiles) => {
  if (!Array.isArray(profiles)) {
    return []
  }

  return profiles.map((profile) => ({
    id: profile?.id || createProfile().id,
    label: typeof profile?.label === 'string' ? profile.label : '',
    modelName: typeof profile?.modelName === 'string' ? profile.modelName : '',
    baseUrl: typeof profile?.baseUrl === 'string' ? profile.baseUrl : '',
    apiKey: typeof profile?.apiKey === 'string' ? profile.apiKey : ''
  }))
}

const buildLocalState = (source) => {
  const settings = {
    ...clone(defaultSettings),
    ...clone(source || {})
  }
  settings.MODEL_PROFILES = normalizeProfiles(settings.MODEL_PROFILES)
  if (!settings.MODEL_PROFILES.some((profile) => profile.id === settings.ACTIVE_MODEL_PROFILE_ID)) {
    settings.ACTIVE_MODEL_PROFILE_ID = settings.MODEL_PROFILES[0]?.id || ''
  }
  return settings
}

const localConfig = reactive(buildLocalState(configStore))
const clawhubPacks = ref([])
const clawhubNotes = ref([])
const installedSkills = ref([])
const clawhubAvailable = ref(false)
const clawhubOutput = ref('')
const installingPackId = ref('')
const mcpPresets = ref([])
const mcpPresetStatuses = ref({})
const getTemplateTitleById = (templateId) => {
  const template = workflowTemplates.find((item) => item.id === templateId)
  if (!template) {
    return templateId
  }
  return template.titleKey ? t(template.titleKey) : template.title || templateId
}

const loadClawHubPacks = async () => {
  const result = await fetchClawHubStarterPacks()
  if (!result.success) {
    clawhubOutput.value = result.message || t('common.unknownError')
    return
  }
  clawhubPacks.value = result.packs
  mcpPresets.value = result.mcpPresets || []
  clawhubNotes.value = result.notes
  installedSkills.value = result.installedSkills
  clawhubAvailable.value = result.clawhubAvailable
}

const loadMcpPresetStatuses = async () => {
  const result = await fetchMcpPresetStatuses()
  if (!result.success) {
    return
  }
  const nextStatuses = {}
  for (const item of result.statuses || []) {
    if (!item?.id) {
      continue
    }
    nextStatuses[item.id] = item
  }
  mcpPresetStatuses.value = nextStatuses
}

const getMcpPresetStatus = (presetId) => mcpPresetStatuses.value[presetId] || null

watch(() => props.isVisible, (visible) => {
  if (!visible) {
    return
  }
  Object.assign(localConfig, buildLocalState(configStore))
  loadClawHubPacks()
  loadMcpPresetStatuses()
})

const setActiveProfile = (profileId) => {
  localConfig.ACTIVE_MODEL_PROFILE_ID = profileId
}

const addProfile = () => {
  const profile = createProfile()
  localConfig.MODEL_PROFILES.push(profile)
  if (!localConfig.ACTIVE_MODEL_PROFILE_ID) {
    localConfig.ACTIVE_MODEL_PROFILE_ID = profile.id
  }
}

const removeProfile = (profileId) => {
  const nextProfiles = localConfig.MODEL_PROFILES.filter((profile) => profile.id !== profileId)
  localConfig.MODEL_PROFILES = nextProfiles
  if (localConfig.ACTIVE_MODEL_PROFILE_ID === profileId) {
    localConfig.ACTIVE_MODEL_PROFILE_ID = nextProfiles[0]?.id || ''
  }
}

const close = () => {
  emit('update:isVisible', false)
  emit('close')
}

const closeForNavigation = async () => {
  close()
  await nextTick()
  await new Promise((resolve) => window.requestAnimationFrame(resolve))
}

const handleInstallPack = async (packId, dryRun = false) => {
  installingPackId.value = packId
  clawhubOutput.value = ''
  const result = await installClawHubStarterPack({ packs: [packId], dryRun })
  clawhubOutput.value = result.success
    ? result.output || t('settings.installComplete')
    : result.message || t('common.unknownError')
  if (Array.isArray(result.installedSkills)) {
    installedSkills.value = result.installedSkills
  }
  await loadClawHubPacks()
  installingPackId.value = ''
}

const openPackTemplates = async (pack) => {
  const templateIds = Array.isArray(pack?.recommended_workflow_templates)
    ? pack.recommended_workflow_templates.filter(Boolean)
    : []
  await closeForNavigation()
  await router.push({
    path: '/workflows/skills',
    query: {
      openTemplates: '1',
      recommendedPack: pack?.id || '',
      recommendedTemplates: templateIds.join(',')
    }
  })
}

const openMcpInjectionFlow = async (presetOrPresets) => {
  const presets = (Array.isArray(presetOrPresets) ? presetOrPresets : [presetOrPresets])
    .map((item) => ({
      id: String(item?.id || '').trim(),
      title: String(item?.title || item?.id || '').trim(),
      mode: String(item?.mode || 'mcp_remote').trim(),
      prefix: String(item?.prefix || '').trim(),
      server: String(item?.server || '').trim(),
    }))
    .filter((item) => item.id && item.server)

  if (!presets.length) {
    return
  }

  const currentWorkflowName = String(route.params?.name || '').trim()
  const targetWorkflow = currentWorkflowName || 'skills'
  await closeForNavigation()
  await router.push({
    path: `/workflows/${targetWorkflow}`,
    query: {
      injectMcpPreset: presets[0]?.id || '',
      injectMcpPayload: encodeURIComponent(JSON.stringify(presets)),
    }
  })
}

const copyMcpSnippet = async (preset) => {
  const payload = preset?.tooling_snippet
  if (!payload) {
    clawhubOutput.value = t('settings.mcpSnippetMissing')
    return
  }

  const snippet = `tooling:\n  - ${JSON.stringify(payload, null, 2).replace(/\n/g, '\n    ')}`

  try {
    await navigator.clipboard.writeText(snippet)
    clawhubOutput.value = `${t('settings.copiedMcpSnippet')}\n\n${snippet}`
  } catch (_error) {
    clawhubOutput.value = `${t('settings.copyFailed')}\n\n${snippet}`
  }
}

const save = () => {
  const normalized = buildLocalState(localConfig)
  Object.assign(configStore, normalized)
  close()
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(2px);
}

.modal-content.settings-modal {
  width: min(880px, 94vw) !important;
  max-height: 86vh;
  background: #1e1e1e;
  border-radius: 12px;
  border: 1px solid #333;
  color: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #333;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-button {
  background: none;
  border: none;
  color: #888;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-button:hover {
  color: #fff;
}

.modal-body {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #f2f2f2;
}

.section-note {
  margin: 6px 0 0;
  color: #8b949e;
  font-size: 13px;
  line-height: 1.5;
}

.section-note code {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  color: #d6ecff;
}

.language-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.field-label {
  color: #e0e0e0;
  font-size: 14px;
  font-weight: 500;
}

.language-buttons {
  display: flex;
  gap: 8px;
}

.language-button {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #d8e2f0;
  border-radius: 999px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 12px;
}

.language-button.active {
  background: rgba(79, 172, 254, 0.18);
  border-color: rgba(79, 172, 254, 0.7);
  color: #f2f8ff;
}

.settings-item {
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.settings-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #e0e0e0;
  font-size: 15px;
  cursor: pointer;
  user-select: none;
  margin-bottom: 6px;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #4facfe;
  cursor: pointer;
}

.setting-desc {
  margin-left: 26px;
  color: #8b949e;
  font-size: 13px;
  line-height: 1.4;
  margin-top: 0;
  margin-bottom: 0;
}

.add-profile-button,
.secondary-button,
.confirm-button {
  background: #4facfe;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.add-profile-button:hover,
.secondary-button:hover,
.confirm-button:hover {
  background: #3a9cfa;
}

.setting-desc-inline {
  margin-left: 0;
}

.empty-profiles {
  border: 1px dashed rgba(160, 196, 255, 0.25);
  border-radius: 10px;
  padding: 16px;
  color: #8b949e;
  font-size: 13px;
  line-height: 1.5;
}

.profile-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.profile-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  padding: 14px;
}

.profile-card.active {
  border-color: rgba(79, 172, 254, 0.65);
  box-shadow: 0 0 0 1px rgba(79, 172, 254, 0.2);
}

.profile-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.default-radio {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #d8e2f0;
  font-size: 13px;
}

.default-radio input {
  accent-color: #4facfe;
}

.remove-profile-button {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #d8e2f0;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.remove-profile-button:hover {
  background: rgba(255, 255, 255, 0.05);
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.profile-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.profile-field span {
  color: #bfc8d4;
  font-size: 12px;
  font-weight: 500;
}

.profile-field input {
  width: 100%;
  box-sizing: border-box;
  background: #151515;
  border: 1px solid #333;
  color: #f2f2f2;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}

.profile-field input:focus {
  outline: none;
  border-color: #4facfe;
  box-shadow: 0 0 0 1px rgba(79, 172, 254, 0.25);
}

.profile-field-full {
  grid-column: 1 / -1;
}

.pack-list,
.installed-skills-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pack-card,
.installed-skill-row,
.install-output {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  padding: 14px;
}

.pack-card-header,
.install-output-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.pack-card-header h5,
.install-output-header h5 {
  margin: 0;
  font-size: 14px;
}

.pack-card-header p,
.installed-skill-row p {
  margin: 6px 0 0;
  color: #8b949e;
  font-size: 13px;
  line-height: 1.5;
}

.pack-count,
.skill-source-badge,
.note-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  background: rgba(79, 172, 254, 0.12);
  color: #d7ecff;
  border: 1px solid rgba(79, 172, 254, 0.24);
}

.skill-chip-list,
.notes-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.recommended-mcp {
  margin-top: 12px;
}

.recommended-label {
  display: inline-flex;
  margin-bottom: 8px;
  color: #8b949e;
  font-size: 12px;
}

.preset-meta-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.preset-badge-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.preset-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #d8e2f0;
  background: rgba(255, 255, 255, 0.06);
}

.preset-status-badge.is-online {
  color: #8df3cf;
  background: rgba(89, 211, 163, 0.16);
  border-color: rgba(89, 211, 163, 0.28);
}

.preset-status-badge.is-warn {
  color: #f1bf63;
  background: rgba(241, 191, 99, 0.16);
  border-color: rgba(241, 191, 99, 0.26);
}

.preset-status-badge.is-offline {
  color: #ffb8a9;
  background: rgba(255, 125, 97, 0.14);
  border-color: rgba(255, 125, 97, 0.24);
}

.preset-meta-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preset-meta-row code {
  display: inline-flex;
  width: fit-content;
  padding: 7px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #d7ecff;
  font-size: 12px;
}

.preset-meta-text {
  color: #d8e2f0;
  font-size: 13px;
  line-height: 1.5;
}

.skill-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #d8e2f0;
  font-size: 12px;
}

.skill-chip-accent {
  background: rgba(79, 172, 254, 0.1);
  color: #d7ecff;
  border: 1px solid rgba(79, 172, 254, 0.24);
}

.pack-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.installed-skill-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.section-heading-tight {
  margin-bottom: 12px;
}

.install-output pre {
  margin: 10px 0 0;
  padding: 14px;
  border-radius: 10px;
  background: #151515;
  color: #d8e2f0;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.modal-footer {
  padding: 16px 20px;
  border-top: 1px solid #333;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-button {
  background: transparent;
  color: #ccc;
  border: 1px solid #444;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.cancel-button:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  border-color: #666;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-leave-active {
  pointer-events: none;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@media (max-width: 720px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .section-heading {
    flex-direction: column;
  }
}

.modal-overlay {
  background: rgba(22, 33, 37, 0.42);
  backdrop-filter: blur(6px);
}

.modal-content.settings-modal {
  background: rgba(255, 252, 246, 0.97);
  border: 1px solid rgba(21, 58, 64, 0.08);
  border-radius: 26px;
  color: #17353c;
  box-shadow: 0 30px 70px rgba(27, 54, 61, 0.16);
}

.modal-header,
.modal-footer {
  border-color: rgba(21, 58, 64, 0.08);
}

.modal-header h3,
.section-title,
.field-label,
.profile-field span,
.default-radio,
.checkbox-label {
  color: #17353c;
}

.modal-body {
  padding: 24px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-section {
  gap: 18px;
  padding: 18px 18px 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.settings-item {
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(21, 58, 64, 0.08);
}

.setting-desc,
.section-note,
.empty-profiles {
  color: #647679;
}

.language-button,
.remove-profile-button,
.cancel-button,
.profile-field input {
  background: rgba(255, 255, 255, 0.94);
  color: #17353c;
  border: 1px solid rgba(21, 58, 64, 0.1);
}

.language-button.active {
  background: rgba(31, 103, 109, 0.12);
  border-color: rgba(31, 103, 109, 0.24);
  color: #1f676d;
}

.add-profile-button,
.secondary-button,
.confirm-button {
  background: linear-gradient(135deg, #19555c, #23707b, #e2b459);
  color: #ffffff;
  border-radius: 999px;
  padding: 10px 16px;
}

.secondary-button {
  background: rgba(31, 103, 109, 0.08);
  color: #1f676d;
  border: 1px solid rgba(31, 103, 109, 0.16);
}

.profile-list {
  gap: 16px;
}

.profile-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(250, 252, 249, 0.9);
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.profile-card.active {
  border-color: rgba(31, 103, 109, 0.24);
  box-shadow: 0 0 0 3px rgba(31, 103, 109, 0.06);
}

.profile-card-header {
  margin-bottom: 14px;
}

.profile-grid {
  gap: 14px;
}

.profile-field {
  gap: 8px;
}

.profile-field input {
  border-radius: 12px;
  padding: 12px 14px;
}

.cancel-button:hover,
.remove-profile-button:hover,
.language-button:hover,
.secondary-button:hover {
  background: rgba(237, 246, 242, 0.96);
  border-color: rgba(31, 103, 109, 0.16);
  color: #17353c;
}

.pack-card,
.installed-skill-row,
.install-output {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.pack-card-header p,
.installed-skill-row p,
.setting-desc-inline {
  color: #647679;
}

.pack-count,
.skill-source-badge,
.note-chip {
  background: rgba(31, 103, 109, 0.08);
  border-color: rgba(31, 103, 109, 0.14);
  color: #1f676d;
}

.skill-chip {
  background: rgba(237, 246, 242, 0.9);
  color: #17353c;
}

.recommended-label {
  color: #647679;
}

.preset-meta-row code {
  background: rgba(237, 246, 242, 0.9);
  color: #1f676d;
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.preset-meta-text {
  color: #617477;
}

.preset-status-badge {
  color: #617477;
  background: rgba(237, 246, 242, 0.9);
  border-color: rgba(21, 58, 64, 0.08);
}

.preset-status-badge.is-online {
  color: #1f7a5c;
  background: rgba(98, 201, 158, 0.14);
  border-color: rgba(98, 201, 158, 0.22);
}

.preset-status-badge.is-warn {
  color: #9c6b12;
  background: rgba(233, 193, 101, 0.16);
  border-color: rgba(233, 193, 101, 0.24);
}

.preset-status-badge.is-offline {
  color: #b14c36;
  background: rgba(214, 128, 97, 0.14);
  border-color: rgba(214, 128, 97, 0.2);
}

.skill-chip-accent {
  background: rgba(31, 103, 109, 0.08);
  color: #1f676d;
  border: 1px solid rgba(31, 103, 109, 0.14);
}

.install-output pre {
  background: #f7fbf9;
  color: #28474e;
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.settings-modal,
.settings-modal * {
  -webkit-text-fill-color: currentColor;
}

.settings-modal .close-button {
  color: #617477;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(21, 58, 64, 0.1);
  border-radius: 999px;
  width: 34px;
  height: 34px;
}

.settings-modal .close-button:hover {
  color: #17353c;
  background: #ffffff;
  border-color: rgba(31, 103, 109, 0.18);
}

.settings-modal .modal-footer {
  background: rgba(255, 252, 246, 0.97);
}

.settings-modal .confirm-button,
.settings-modal .add-profile-button {
  color: #ffffff;
}

.settings-modal input,
.settings-modal select,
.settings-modal textarea {
  background: #ffffff;
  color: #17353c;
}
</style>
