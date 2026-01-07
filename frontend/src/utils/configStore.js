import { reactive, watch } from 'vue'

const CONFIG_KEY = 'agent_config_settings'

const defaultSettings = {
    AUTO_SHOW_ADVANCED: false,
    AUTO_EXPAND_MESSAGES: false
}

// Initialize state from localStorage
const stored = localStorage.getItem(CONFIG_KEY)
const initialState = stored ? { ...defaultSettings, ...JSON.parse(stored) } : { ...defaultSettings }

export const configStore = reactive(initialState)

// Watch for changes and save to localStorage
watch(configStore, (newVal) => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(newVal))
}, { deep: true })
