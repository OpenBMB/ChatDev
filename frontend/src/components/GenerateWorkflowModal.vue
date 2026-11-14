<template>
  <div class="modal-overlay" @click.self="close">
    <div class="modal-content generate-modal" role="dialog" aria-modal="true" aria-labelledby="generate-workflow-title">
      <div class="modal-header">
        <h3 id="generate-workflow-title">{{ $t('workflow_generate.title') }}</h3>
        <button class="close-button" :aria-label="$t('common.cancel')" @click="close">×</button>
      </div>

      <div class="modal-body">
        <template v-if="!yamlText">
          <label class="field-label" for="generate-description">{{ $t('workflow_generate.description_label') }}</label>
          <textarea
            id="generate-description"
            ref="descriptionRef"
            v-model="description"
            class="text-area description-input"
            :placeholder="$t('workflow_generate.description_placeholder')"
            :disabled="generating"
            @keydown.meta.enter.prevent="generate"
            @keydown.ctrl.enter.prevent="generate"
          ></textarea>
          <p class="field-hint">{{ $t('workflow_generate.description_hint') }}</p>

          <div v-if="generating" class="status-line" role="status">
            <span class="spinner" aria-hidden="true"></span>
            {{ $t('workflow_generate.generating', { seconds: elapsedSeconds }) }}
          </div>
          <p v-if="errorText" class="error-text" role="alert">
            <svg class="status-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>
            {{ errorText }}
          </p>
        </template>

        <template v-else>
          <p v-if="needsFixes" class="warning-text" role="alert">
            <svg class="status-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>
            {{ $t('workflow_generate.needs_fixes') }}
          </p>
          <label class="field-label" for="generate-yaml">{{ $t('workflow_generate.yaml_label') }}</label>
          <textarea id="generate-yaml" v-model="yamlText" class="text-area yaml-output" spellcheck="false"></textarea>

          <label class="field-label" for="generate-filename">{{ $t('workflow_generate.filename_label') }}</label>
          <div class="filename-row">
            <input id="generate-filename" v-model="filename" class="text-input" :aria-invalid="!filenameValid" />
            <span class="filename-suffix">.yaml</span>
          </div>
          <p v-if="!filenameValid" class="error-text">{{ $t('workflow_generate.filename_invalid') }}</p>
          <p v-if="errorText" class="error-text" role="alert">
            <svg class="status-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>
            {{ errorText }}
          </p>
        </template>
      </div>

      <div class="modal-footer">
        <template v-if="!yamlText">
          <button class="cancel-button" @click="close">{{ $t('common.cancel') }}</button>
          <button class="confirm-button" :disabled="generating || !description.trim()" @click="generate">
            {{ $t('workflow_generate.generate') }}
          </button>
        </template>
        <template v-else>
          <button class="cancel-button" :disabled="saving" @click="backToDescription">{{ $t('workflow_generate.back') }}</button>
          <button class="confirm-button" :disabled="saving || !filenameValid || !yamlText.trim()" @click="save">
            {{ saving ? $t('workflow_generate.saving') : $t('workflow_generate.save_and_open') }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import yaml from 'js-yaml'
import { generateWorkflowYaml, postYaml } from '../utils/apiFunctions.js'

const emit = defineEmits(['close', 'created'])
const { t } = useI18n()

const description = ref('')
const descriptionRef = ref(null)
const yamlText = ref('')
const filename = ref('')
const generating = ref(false)
const saving = ref(false)
const errorText = ref('')
const elapsedSeconds = ref(0)

let controller = null
let timer = null

// Same rule the server applies in validate_workflow_filename.
const filenameValid = computed(() => /^[a-zA-Z0-9._-]+$/.test(filename.value.trim()))
// The designer's edge processor prefixes YAML that failed validation with this comment.
const needsFixes = computed(() => yamlText.value.startsWith('# VALIDATION FAILED'))

const stopTimer = () => {
  clearInterval(timer)
  timer = null
}

const generate = async () => {
  if (generating.value || !description.value.trim()) return
  errorText.value = ''
  generating.value = true
  elapsedSeconds.value = 0
  timer = setInterval(() => { elapsedSeconds.value += 1 }, 1000)
  controller = new AbortController()
  try {
    const text = await generateWorkflowYaml(description.value.trim(), controller.signal)
    if (!text.trim()) throw new Error(t('workflow_generate.empty_result'))
    yamlText.value = text
    try {
      filename.value = String(yaml.load(text)?.graph?.id || '').trim()
    } catch {
      filename.value = ''
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      errorText.value = t('workflow_generate.request_failed', { reason: error.message })
    }
  } finally {
    stopTimer()
    generating.value = false
    controller = null
  }
}

const backToDescription = async () => {
  yamlText.value = ''
  errorText.value = ''
  await nextTick()
  descriptionRef.value?.focus()
}

const save = async () => {
  saving.value = true
  errorText.value = ''
  const name = filename.value.trim()
  const result = await postYaml(name, yamlText.value)
  saving.value = false
  if (result.success) {
    emit('created', `${name}.yaml`)
    return
  }
  const reason = result.detail || result.message
  errorText.value = t(result.status === 409 ? 'workflow_generate.save_conflict' : 'workflow_generate.save_failed', {
    reason: typeof reason === 'string' ? reason : JSON.stringify(reason)
  })
}

const close = () => {
  controller?.abort()
  emit('close')
}

// On window, not the overlay: focus falls back to <body> when a button disables itself.
const onKeydown = (event) => {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  descriptionRef.value?.focus()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  controller?.abort()
  stopTimer()
})
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

.generate-modal {
  width: 760px;
  max-width: 92vw;
  max-height: 90vh;
  background: #1e1e1e;
  border-radius: 8px;
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
  font-weight: 500;
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

.close-button:hover,
.close-button:focus-visible {
  color: #fff;
}

.modal-body {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  color: #e0e0e0;
  font-size: 15px;
  margin-top: 8px;
}

.field-label:first-child {
  margin-top: 0;
}

.field-hint {
  margin: 0;
  color: #8b949e;
  font-size: 13px;
  line-height: 1.4;
}

.text-area,
.text-input {
  width: 100%;
  box-sizing: border-box;
  background: #2a2a2a;
  border: 1px solid #444;
  color: #fff;
  border-radius: 4px;
  padding: 10px;
  font-size: 14px;
  font-family: inherit;
}

.text-area:focus,
.text-input:focus {
  outline: 2px solid #4facfe;
  outline-offset: 1px;
  border-color: #4facfe;
}

.text-area::placeholder {
  color: #9aa0a6;
}

.description-input {
  min-height: 140px;
  resize: vertical;
  line-height: 1.5;
}

.yaml-output {
  min-height: 320px;
  resize: vertical;
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
  tab-size: 2;
}

.filename-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filename-suffix {
  color: #8b949e;
  font-size: 14px;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #e0e0e0;
  font-size: 14px;
  margin-top: 4px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #4facfe;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-text,
.warning-text {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.4;
}

.error-text {
  color: #ff8a8a;
  white-space: pre-line;
}

.warning-text {
  color: #ffd27a;
}

.status-icon {
  flex: none;
  width: 16px;
  height: 16px;
  margin-top: 1px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.modal-footer {
  padding: 16px 20px;
  border-top: 1px solid #333;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.confirm-button {
  background: #4facfe;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.confirm-button:hover:not(:disabled) {
  background: #3a9cfa;
}

.cancel-button {
  background: transparent;
  color: #ccc;
  border: 1px solid #444;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.cancel-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  border-color: #666;
}

.confirm-button:disabled,
.cancel-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.confirm-button:focus-visible,
.cancel-button:focus-visible {
  outline: 2px solid #4facfe;
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 2.4s;
  }
}
</style>
