import { reactive, watch } from 'vue'

const CONFIG_KEY = 'agent_config_settings'

export const defaultSettings = {
  AUTO_SHOW_ADVANCED: false,
  AUTO_EXPAND_MESSAGES: false,
  ENABLE_HELP_TOOLTIPS: true,
  UI_LANGUAGE: 'zh',
  MODEL_PROFILES: [],
  ACTIVE_MODEL_PROFILE_ID: ''
}

function sanitizeSettings(rawSettings = {}) {
  const merged = { ...defaultSettings, ...(rawSettings || {}) }
  if (!Array.isArray(merged.MODEL_PROFILES)) {
    merged.MODEL_PROFILES = []
  }
  if (!['zh', 'en'].includes(merged.UI_LANGUAGE)) {
    merged.UI_LANGUAGE = 'zh'
  }
  if (typeof merged.ACTIVE_MODEL_PROFILE_ID !== 'string') {
    merged.ACTIVE_MODEL_PROFILE_ID = ''
  }
  return merged
}

// Initialize state from localStorage
const stored = localStorage.getItem(CONFIG_KEY)
const initialState = stored
  ? sanitizeSettings(JSON.parse(stored))
  : { ...defaultSettings }

export const configStore = reactive(initialState)

// Watch for changes and save to localStorage
watch(configStore, (newVal) => {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(sanitizeSettings(newVal)))
}, { deep: true })
