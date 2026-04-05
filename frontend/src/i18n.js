import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zh from './locales/zh.json'

const CONFIG_KEY = 'agent_config_settings'
const stored = localStorage.getItem(CONFIG_KEY)
let savedLanguage = 'en'
if (stored) {
  try {
    savedLanguage = JSON.parse(stored).LANGUAGE || 'en'
  } catch (e) {}
}

const i18n = createI18n({
  locale: savedLanguage,
  fallbackLocale: 'en',
  messages: {
    en,
    zh
  },
  legacy: false,
  globalInjection: true
})

export default i18n
