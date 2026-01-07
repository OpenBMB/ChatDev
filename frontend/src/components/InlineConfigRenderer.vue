<template>
  <div class="inline-config-renderer">
    <!-- Main Fields -->
    <div
      v-for="field in mainFields"
      :key="field.name + '-' + (modal.formData[field.name]?.type || '')"
      class="form-field-wrapper"
    >
      <DynamicFormField
        :field="field"
        :modal-id="modal.id"
        :form-data="modal.formData"
        :child-summaries="modal.childSummaries"
        :recursive="modal.recursive"
        :is-visible="isFieldVisible(modal, field)"
        :expand-inline="isInlineConfigField(field)"
        :can-open-conditional-child-modal="canOpenConditionalChildModal(modal, field)"
        :conditional-child-button-label="conditionalChildButtonLabel(modal, field)"
        :child-node-button-label="childNodeButtonLabel(modal, field)"
        :active-child-route="getActiveChildRoute(modal, field)"
        :is-read-only="isFieldReadOnly(field)" 
        @open-child-modal="(f, idx) => $emit('open-child-modal', modal.id, f, idx)"
        @open-conditional-child-modal="(f) => $emit('open-conditional-child-modal', modal.id, f)"
        @handle-enum-change="(f) => $emit('handle-enum-change', modal.id, f)"
        @open-var-modal="(fname) => $emit('open-var-modal', modal.id, fname)"
        @edit-var="(fname, key) => $emit('edit-var', modal.id, fname, key)"
        @delete-var="(fname, key) => $emit('delete-var', modal.id, fname, key)"
        @open-list-item-modal="(fname) => $emit('open-list-item-modal', modal.id, fname)"
        @delete-list-item="(fname, idx) => $emit('delete-list-item', modal.id, fname, idx)"
        @clear-child-entry="(fname) => $emit('clear-child-entry', modal.id, fname)"
        @delete-child-entry="(fname, idx) => $emit('delete-child-entry', modal.id, fname, idx)"
      />
    </div>

    <!-- Advanced Settings Toggle -->
    <div v-if="hasAdvancedFields" class="advanced-toggle">
      <button
        type="button"
        class="advanced-toggle-button"
        @click="$emit('toggle-advanced-fields', modal.id)"
      >
        Advanced Settings
        <span class="advanced-toggle-arrow">
          {{ modal.showAdvanced ? '▲' : '▼' }}
        </span>
      </button>
    </div>

    <!-- Inline Config Fields (Recursive) -->
    <div
      v-for="field in inlineFields"
      :key="field.name"
      class="form-field-wrapper"
      v-show="isFieldVisible(modal, field)"
    >
      <!-- Separator for the inline section -->
      <div 
        v-if="modal.inlineChildModals?.[field.name]"
        class="inline-config-section"
        :key="modal.inlineChildModals[field.name]?.id"
      >
        <div class="inline-separator"></div>
        
        <!-- Recursion: Render the child modal -->
        <InlineConfigRenderer
          :modal="modal.inlineChildModals[field.name]"
          @open-child-modal="(mid, f, idx) => $emit('open-child-modal', mid, f, idx)"
          @open-conditional-child-modal="(mid, f) => $emit('open-conditional-child-modal', mid, f)"
          @handle-enum-change="(mid, f) => $emit('handle-enum-change', mid, f)"
          @open-var-modal="(mid, fname) => $emit('open-var-modal', mid, fname)"
          @edit-var="(mid, fname, key) => $emit('edit-var', mid, fname, key)"
          @delete-var="(mid, fname, key) => $emit('delete-var', mid, fname, key)"
          @open-list-item-modal="(mid, fname) => $emit('open-list-item-modal', mid, fname)"
          @delete-list-item="(mid, fname, idx) => $emit('delete-list-item', mid, fname, idx)"
          @clear-child-entry="(mid, fname) => $emit('clear-child-entry', mid, fname)"
          @delete-child-entry="(mid, fname, idx) => $emit('delete-child-entry', mid, fname, idx)"
          @toggle-advanced-fields="(mid) => $emit('toggle-advanced-fields', mid)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import DynamicFormField from './DynamicFormField.vue'
import {
  isInlineConfigField,
  getDisplayFields,
  isFieldVisible,
  canOpenConditionalChildModal,
  conditionalChildButtonLabel,
  childNodeButtonLabel,
  getActiveChildRoute
} from '../utils/formUtils.js'

const props = defineProps({
  modal: {
    type: Object,
    required: true
  },
  readOnlyFields: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits([
  'open-child-modal',
  'open-conditional-child-modal',
  'handle-enum-change',
  'open-var-modal',
  'edit-var',
  'delete-var',
  'open-list-item-modal',
  'delete-list-item',
  'clear-child-entry',
  'delete-child-entry',
  'toggle-advanced-fields'
])

const allFields = computed(() => getDisplayFields(props.modal))

const mainFields = computed(() => {
  return allFields.value.filter(field => !isInlineConfigField(field))
})

const inlineFields = computed(() => {
  return allFields.value.filter(field => isInlineConfigField(field))
})

const hasAdvancedFields = computed(() => {
  return allFields.value.some(field => field.advance)
})

const isFieldReadOnly = (field) => {
  return props.readOnlyFields.includes(field.name)
}
</script>

<style scoped>
.advanced-toggle {
  display: flex;
  justify-content: flex-start;
  margin: 10px 0 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 10px;
}

.advanced-toggle-button {
  background: transparent;
  border: none;
  color: #a0c4ff;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.advanced-toggle-button:hover {
  text-decoration: underline;
}

.advanced-toggle-arrow {
  font-size: 10px;
}

.inline-config-section {
  margin-top: 8px;
  padding-left: 0; 
}

.inline-separator {
  height: 1px;
  background-color: rgba(255, 255, 255, 0.1);
  margin: 16px 0 20px;
}
</style>
