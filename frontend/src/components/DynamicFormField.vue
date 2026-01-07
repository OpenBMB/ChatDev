<template>
  <div class="form-field" v-show="isVisible">
    <template v-if="field.childNode">
      <div v-if="recursive" class="form-group form-group-inline child-node-group">
        <label>
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="child-node-container">
          <div class="child-node-controls">
            <button @click="$emit('open-child-modal', field)" class="add-child-button">
              <span class="plus-icon" aria-hidden="true">
                <!-- Edit icon when configured -->
                <svg
                  v-if="!isList && hasChildValue"
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <rect
                    x="3"
                    y="2"
                    width="8"
                    height="11"
                    rx="1"
                    ry="1"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.2"
                  />
                  <path
                    fill="currentColor"
                    d="M10.9 3.1a.9.9 0 0 1 1.27 0l.73.73a.9.9 0 0 1 0 1.27l-4.3 4.3-1.7.5.5-1.7 4.3-4.3z"
                  />
                </svg>
                <!-- Configure icon when not yet configured -->
                <svg
                  v-else
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fill="currentColor"
                    d="M8 2.5a.75.75 0 0 1 .75.75v4h4a.75.75 0 0 1 0 1.5h-4v4a.75.75 0 0 1-1.5 0v-4h-4a.75.75 0 0 1 0-1.5h4v-4A.75.75 0 0 1 8 2.5z"
                  />
                </svg>
              </span>
              {{ childNodeButtonLabel }}
            </button>
            <!-- Show clear button only when child is already configured ("Edit" mode) -->
            <button
              v-if="hasChildValue"
              class="clear-child-button"
              @click.stop="$emit('clear-child-entry', field.name)"
              title="Clear configuration"
            >
              ×
            </button>
          </div>
          <div
            v-if="isList && formData[field.name] && formData[field.name].length"
            class="child-node-list"
          >
            <div
              v-for="(childEntry, childIndex) in formData[field.name]"
              :key="childIndex"
              class="child-node-item-wrapper"
            >
              <div
                class="child-node-item"
                @click="$emit('open-child-modal', field, childIndex)"
              >
                <span class="child-node-name">
                  {{ describeChildEntry(childEntry, childIndex) }}
                </span>
                <div class="child-node-actions">
                  <button
                    class="delete-child-button"
                    @click.stop="$emit('delete-child-entry', field.name, childIndex)"
                    title="Delete child"
                  >
                    ×
                  </button>
                </div>
              </div>
              <div
                v-if="childSummaries[field.name] && childSummaries[field.name][childIndex]"
                class="child-node-summary"
              >
                {{ childSummaries[field.name][childIndex] }}
              </div>
            </div>
          </div>
          <div
            v-else-if="!isList && hasChildValue && childSummaries[field.name]"
            class="child-node-summary"
          >
            {{ childSummaries[field.name] }}
          </div>
        </div>
      </div>
    </template>

    <template v-else-if="hasChildRoutes">
      <!-- Logic for expanded inline config will go here in FormGenerator usage or via prop controls -->
      <!-- But for now, we implement standard behavior. The expanding logic will be handled by the parent using slots or a different prop -->
      
      <!-- Standard Popup Style (if not expanded) -->
      <div v-if="!expandInline" class="form-group form-group-inline child-node-group">
        <label>
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="child-node-container">
          <div class="child-node-controls">
            <button
              @click="$emit('open-conditional-child-modal', field)"
              class="add-child-button"
              :disabled="!canOpenConditionalChildModal"
            >
              <span class="plus-icon" aria-hidden="true">
                <!-- Edit icon when a child config already exists -->
                <svg
                  v-if="formData[field.name]"
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <rect
                    x="3"
                    y="2"
                    width="8"
                    height="11"
                    rx="1"
                    ry="1"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.2"
                  />
                  <path
                    fill="currentColor"
                    d="M10.9 3.1a.9.9 0 0 1 1.27 0l.73.73a.9.9 0 0 1 0 1.27l-4.3 4.3-1.7.5.5-1.7 4.3-4.3z"
                  />
                </svg>
                <!-- Configure/Add icon when not yet configured -->
                <svg
                  v-else
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fill="currentColor"
                    d="M8 2.5a.75.75 0 0 1 .75.75v4h4a.75.75 0 0 1 0 1.5h-4v4a.75.75 0 0 1-1.5 0v-4h-4a.75.75 0 0 1 0-1.5h4v-4A.75.75 0 0 1 8 2.5z"
                  />
                </svg>
              </span>
              {{ conditionalChildButtonLabel }}
            </button>
            <button
              v-if="hasChildValue"
              class="clear-child-button"
              @click.stop="$emit('clear-child-entry', field.name)"
              title="Clear configuration"
            >
              ×
            </button>
          </div>
          <div
            v-if="!canOpenConditionalChildModal"
            class="child-node-hint"
          >
            Please select a type and configure
          </div>
          <div
            v-if="hasChildValue && childSummaries[field.name]"
            class="child-node-summary"
          >
            {{ childSummaries[field.name] }}
          </div>
        </div>
      </div>
      
      <!-- Expanded Inline Style is NOT rendered here. The parent will check `expandInline` 
           and simply NOT render this button-based UI, and instead render the inline form. 
           Wait, if I am extracting this, I should support both or let parent handle the expanded part adjacent to this component?
           The requirement says: "display type selection" (which is a standard field), 
           then "display expanded config below".
           So the "config" field (which is `hasChildRoutes`) should be rendered DIFFERENTLY if expanded.
           If it's expanded, we might just want to render NOTHING for this field here, 
           and let the parent render the separator + sub-form?
           OR we render the separator + sub-form HERE? 
           But complex recursion logic is easier in parent.
           
           DECISION: If `expandInline` is true, this component renders NOTHING for the `childRoutes` field,
           because the content is rendered by the parent (the "separator" + "inline fields").
           Actually, the `type` field is a separate field. This component renders it.
           The `config` field IS the field with `childRoutes`.
           So if `expandInline` is true, we render NOTHING?
           Yes. The parent will detect this field and render the specialized inline UI instead.
           
           However, I need to make sure I don't break existing logic.
           If I pass `expandInline` prop:
      -->
      <div v-else-if="expandInline">
        <!-- Render nothing, parent handles it -->
      </div>
    </template>

    <template v-else>
      <!-- Choice dropdown fields-->
      <div v-if="field.enum && !isList" class="form-group">
        <label :for="`${modalId}-${field.name}`">
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="custom-select-wrapper" :class="{ 'select-disabled': isReadOnly }">
          <input
            :id="`${modalId}-${field.name}`"
            :value="inputValue"
            @input="onFilterInput"
            @focus="showDropdown = true"
            @blur="handleInputBlur"
            class="form-input custom-select-input"
            :readonly="isReadOnly"
            :class="{'input-readonly': isReadOnly}"
            placeholder="Type to filter options..."
            autocomplete="off"
          />
          <div v-if="showDropdown && !isReadOnly" class="custom-select-dropdown">
            <div
              v-if="!field.required"
              class="custom-select-option"
              :class="{ 'option-selected': formData[field.name] === null }"
              @mousedown="selectOption(null)"
            >
              None
            </div>
            <div
              v-for="option in filteredOptions"
              :key="typeof option === 'string' ? option : option.value"
              class="custom-select-option"
              :class="{ 'option-selected': formData[field.name] === (typeof option === 'string' ? option : option.value) }"
              :title="typeof option === 'string' ? '' : (option.description || '')"
              @mousedown="selectOption(typeof option === 'string' ? option : option.value)"
            >
              {{
                typeof option === 'string'
                  ? option
                  : (option.label || option.value)
              }}
            </div>
            <div v-if="filteredOptions.length === 0" class="custom-select-no-results">
              No options found
            </div>
          </div>
          <div class="custom-select-arrow" :class="{ 'arrow-open': showDropdown }">
            ▼
          </div>
        </div>
      </div>

      <!-- Multi-choice fields -->
      <div v-else-if="field.enum && isList" class="form-group">
        <label>
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="multi-select-options">
          <label
            v-for="option in (field.enumOptions || field.enum)"
            :key="typeof option === 'string' ? option : option.value"
            class="multi-select-option"
            :title="typeof option === 'string' ? '' : (option.description || '')"
          >
            <input
              type="checkbox"
              :value="typeof option === 'string' ? option : option.value"
              v-model="internalFormData[field.name]"
            />
            <span class="option-label">
              {{
                typeof option === 'string'
                  ? option
                  : (option.label || option.value)
              }}
            </span>
          </label>
        </div>
      </div>

      <!-- Boolean switch fields -->
      <div v-else-if="field.type === 'bool' && !isList" class="form-group">
        <div class="switch-wrapper">
          <label :for="`${modalId}-${field.name}`" class="switch-label-text">
            {{ field.displayName || field.name }}
            <span v-if="field.required" class="required-asterisk">*</span>
            <span
              v-if="field.description"
              class="help-icon"
              :title="field.description"
            >
              ?
            </span>
          </label>
          <label class="switch-container">
            <input
              type="checkbox"
              :id="`${modalId}-${field.name}`"
              :checked="formData[field.name] === true"
              @change="onBooleanSwitchChange($event.target.checked)"
              :disabled="isReadOnly"
            />
            <span class="switch-slider"></span>
          </label>
        </div>
      </div>

      <!-- String input fields -->
      <div v-else-if="field.type === 'str' && !isList" class="form-group">
        <label :for="`${modalId}-${field.name}`">
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <input
          :id="`${modalId}-${field.name}`"
          :value="formData[field.name]"
          @input="onInput($event.target.value)"
          type="text"
          class="form-input"
          :readonly="isReadOnly"
          :class="{'input-readonly': isReadOnly}"
        />
      </div>

      <!-- Multiline text fields -->
      <div v-else-if="field.type === 'text' && !isList" class="form-group">
        <label :for="`${modalId}-${field.name}`">
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <textarea
          :id="`${modalId}-${field.name}`"
          :value="formData[field.name]"
          @input="onInput($event.target.value)"
          class="form-textarea"
          rows="4"
          :readonly="isReadOnly"
          :class="{'input-readonly': isReadOnly}"
        />
      </div>

      <!-- Integer input fields -->
      <div v-else-if="field.type === 'int' && !isList" class="form-group">
        <label :for="`${modalId}-${field.name}`">
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <input
          :id="`${modalId}-${field.name}`"
          :value="formData[field.name]"
          @input="onInputNumber($event.target.value)"
          type="number"
          step="1"
          class="form-input"
          :readonly="isReadOnly"
          :class="{'input-readonly': isReadOnly}"
        />
      </div>

      <!-- Float input fields -->
      <div v-else-if="field.type === 'float' && !isList" class="form-group">
        <label :for="`${modalId}-${field.name}`">
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <input
          :id="`${modalId}-${field.name}`"
          :value="formData[field.name]"
          @input="onInputNumber($event.target.value)"
          type="number"
          step="any"
          class="form-input"
          :readonly="isReadOnly"
          :class="{'input-readonly': isReadOnly}"
        />
      </div>

      <!-- Key-value fields -->
      <div v-else-if="field.type === 'dict[str, Any]' || field.type === 'dict[str, str]'" class="form-group form-group-inline">
        <label>
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="vars-container">
          <button @click="$emit('open-var-modal', field.name)" class="add-var-button">
            <span class="plus-icon" aria-hidden="true">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill="currentColor"
                  d="M8 2.5a.75.75 0 0 1 .75.75v4h4a.75.75 0 0 1 0 1.5h-4v4a.75.75 0 0 1-1.5 0v-4h-4a.75.75 0 0 1 0-1.5h4v-4A.75.75 0 0 1 8 2.5z"
                />
              </svg>
            </span>
            Add key-value
          </button>
          <div
            v-if="formData[field.name] && hasDictEntries(formData[field.name])"
            class="vars-list"
          >
            <div
              v-for="(varValue, varKey) in formData[field.name]"
              :key="varKey"
              class="var-item"
              @click="$emit('edit-var', field.name, varKey)"
            >
              <span class="var-name">{{ varKey }}</span>
              <span class="var-separator">|</span>
              <span class="var-value">{{ varValue }}</span>
              <button
                class="delete-var-button"
                @click.stop="$emit('delete-var', field.name, varKey)"
                title="Delete variable"
              >
                ×
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- List of strings field -->
      <div v-else-if="isList && field.type.includes('str')" class="form-group form-group-inline">
        <label>
          {{ field.displayName || field.name }}
          <span v-if="field.required" class="required-asterisk">*</span>
          <span
            v-if="field.description"
            class="help-icon"
            :title="field.description"
          >
            ?
          </span>
        </label>
        <div class="list-container">
          <button @click="$emit('open-list-item-modal', field.name)" class="add-list-button">
            <span class="plus-icon" aria-hidden="true">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill="currentColor"
                  d="M8 2.5a.75.75 0 0 1 .75.75v4h4a.75.75 0 0 1 0 1.5h-4v4a.75.75 0 0 1-1.5 0v-4h-4a.75.75 0 0 1 0-1.5h4v-4A.75.75 0 0 1 8 2.5z"
                />
              </svg>
            </span>
            Add Entry
          </button>
          <div v-if="formData[field.name] && formData[field.name].length > 0" class="list-items">
            <div
              v-for="(item, index) in formData[field.name]"
              :key="index"
              class="list-item"
            >
              <span class="item-value">{{ item }}</span>
              <button
                class="delete-item-button"
                @click.stop="$emit('delete-list-item', field.name, index)"
                title="Delete item"
              >
                ×
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  field: {
    type: Object,
    required: true
  },
  modalId: {
    type: String,
    required: true
  },
  formData: {
    type: Object,
    required: true
  },
  childSummaries: {
    type: Object,
    default: () => ({})
  },
  recursive: {
    type: Boolean,
    default: false
  },
  isVisible: {
    type: Boolean,
    default: true
  },
  // If true, and this field is a childRoute config, render nothing (handled by parent inline)
  expandInline: {
    type: Boolean,
    default: false
  },
  // Helpers passed from parent or reimplemented
  canOpenConditionalChildModal: {
    type: Boolean,
    default: true
  },
  conditionalChildButtonLabel: {
    type: String,
    default: 'Configure'
  },
  activeChildRoute: {
    type: Object,
    default: null
  },
  isReadOnly: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:form-data',
  'open-child-modal',
  'clear-child-entry',
  'delete-child-entry',
  'open-conditional-child-modal',
  'handle-enum-change',
  'open-var-modal',
  'edit-var',
  'delete-var',
  'open-list-item-modal',
  'delete-list-item'
])

// Computed property to allow v-model binding with mutation of prop object (common in complex forms)
// OR better, just use props.formData[field.name] directly as Vue 3 proxies allow it, though strict mode warns.
// For FormGenerator, we generally mutate the reactive modal object.
const internalFormData = computed(() => props.formData)

// Custom select filtering state
const showDropdown = ref(false)
const filterText = ref('')

const isList = computed(() => {
  return props.field.type && props.field.type.includes('list[')
})

const hasChildRoutes = computed(() => {
  return Array.isArray(props.field?.childRoutes) && props.field.childRoutes.length > 0
})

const hasChildValue = computed(() => {
  const value = props.formData?.[props.field.name]
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return value !== null && value !== undefined && value !== ''
})

const childNodeButtonLabel = computed(() => {
  if (isList.value) {
    return `Add Entry`
  }
  return props.formData[props.field.name] ? `Edit ${props.field.childNode}` : `Configure ${props.field.childNode}`
})

// Filtered options for custom select
const filteredOptions = computed(() => {
  const options = props.field.enumOptions || props.field.enum || []
  if (!filterText.value.trim()) {
    return options
  }
  const filter = filterText.value.toLowerCase()
  return options.filter(option => {
    const label = typeof option === 'string' ? option : (option.label || option.value)
    return label.toLowerCase().includes(filter)
  })
})

// Computed input value for custom select
const inputValue = computed(() => {
  if (showDropdown.value) {
    return filterText.value
  }
  return getSelectedLabel()
})

// Helpers
const hasDictEntries = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  return Object.keys(value).length > 0
}

const describeChildEntry = (entry, index) => {
  if (entry && typeof entry === 'object') {
    if (entry.id) return entry.id
    if (entry.name) return entry.name
    if (entry.type) return entry.type
  }
  return `${props.field.childNode} #${index + 1}`
}

// Input handlers
const onInput = (value) => {
  props.formData[props.field.name] = value
}

const onInputNumber = (value) => {
    // Check if empty string
    if (value === "") {
        props.formData[props.field.name] = null
        return
    }
  props.formData[props.field.name] = Number(value)
}

const onBooleanSwitchChange = (checked) => {
  props.formData[props.field.name] = checked
}

// Custom select methods
const onFilterInput = (event) => {
  filterText.value = event.target.value
  showDropdown.value = true
}

const handleInputBlur = () => {
  // Delay hiding dropdown to allow option selection
  setTimeout(() => {
    showDropdown.value = false
    filterText.value = ''
  }, 200)
}

const selectOption = (value) => {
  props.formData[props.field.name] = value
  showDropdown.value = false
  filterText.value = ''
  emit('handle-enum-change', props.field)
}

const getSelectedLabel = () => {
  const currentValue = props.formData[props.field.name]
  if (currentValue === null || currentValue === undefined) {
    return ''
  }

  const options = props.field.enumOptions || props.field.enum || []
  const selectedOption = options.find(option => {
    const optionValue = typeof option === 'string' ? option : option.value
    return optionValue === currentValue
  })

  if (selectedOption) {
    return typeof selectedOption === 'string'
      ? selectedOption
      : (selectedOption.label || selectedOption.value)
  }

  return currentValue
}
</script>

<style scoped>
.form-field {
  margin-bottom: 18px;
}

.form-group {
  margin-bottom: 18px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  color: #f2f2f2;
  font-weight: 500;
  font-size: 13px;
}

.form-group-inline {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.form-group-inline label {
  margin-bottom: 0;
  flex-shrink: 0;
  min-width: 96px;
}

.form-group-inline > *:not(label) {
  flex: 1;
}

.required-asterisk {
  color: #ff6b6b;
  margin-left: 4px;
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-left: 6px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  font-size: 11px;
  line-height: 1;
  cursor: default;
  color: rgba(242, 242, 242, 0.7);
  background-color: transparent;
  transition: all 0.2s ease;
}

.help-icon:hover {
  border-color: #a0c4ff;
  color: #a0c4ff;
}

.form-input,
.form-select,
.form-textarea,
.multi-select-options input[type='checkbox'] {
  font-family: 'Inter', sans-serif;
}

.form-input {
  width: 100%;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background-color: rgba(10, 10, 10, 0.6);
  color: #f2f2f2;
  font-size: 13px;
  box-sizing: border-box;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.form-textarea {
  width: 100%;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background-color: rgba(10, 10, 10, 0.6);
  color: #f2f2f2;
  font-size: 13px;
  box-sizing: border-box;
  min-height: 80px;
  resize: vertical;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.form-textarea:focus {
  outline: none;
  border-color: #a0c4ff;
  background-color: rgba(15, 15, 15, 0.85);
  box-shadow: 0 0 0 1px rgba(160, 196, 255, 0.5);
}

.form-input:focus {
  outline: none;
  border-color: #a0c4ff;
  background-color: rgba(15, 15, 15, 0.85);
  box-shadow: 0 0 0 1px rgba(160, 196, 255, 0.5);
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.form-select {
  width: 100%;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background-color: rgba(10, 10, 10, 0.6);
  color: #f2f2f2;
  font-size: 13px;
  box-sizing: border-box;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.form-select:focus {
  outline: none;
  border-color: #a0c4ff;
  background-color: rgba(15, 15, 15, 0.85);
}

/* Switch Styles */
.switch-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 38px; /* Match input height roughly */
}

.switch-label-text {
  margin-bottom: 0 !important; /* Override label margin */
}

.switch-container {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  margin-left: 12px;
}

.switch-container input {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.14);
  transition: .4s;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.switch-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}

input:checked + .switch-slider {
  background-color: #a0c4ff;
  border-color: #4facfe;
}

input:focus + .switch-slider {
  box-shadow: 0 0 1px #4facfe;
}

input:checked + .switch-slider:before {
  transform: translateX(20px);
}

.form-select option {
  background-color: #252525;
  color: #f2f2f2;
}

.multi-select-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.multi-select-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background-color: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.14);
  font-size: 12px;
  color: rgba(242, 242, 242, 0.9);
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.multi-select-option:hover {
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(160, 196, 255, 0.6);
}

.option-label {
  white-space: nowrap;
}

/* Variables styles */
.vars-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-readonly {
  background-color: rgba(255, 255, 255, 0.05); /* Slightly lighter background to indicate disabled-ish but readable */
  border-color: rgba(255, 255, 255, 0.05);
  cursor: text; /* Allow text selection */
  color: rgba(242, 242, 242, 0.6);
}

.input-readonly:focus {
  border-color: rgba(255, 255, 255, 0.05);
  box-shadow: none;
}

.vars-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.var-name {
  flex: 0 0 auto;
  font-weight: 600;
  min-width: 90px;
  margin-left: 10px;
  font-size: 12px;
}

.var-separator {
  font-size: 12px;
  color: #858585;
  margin: 0 5px;
}

.var-value {
  flex: 1;
  color: #d2d2d2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.delete-var-button {
  background: transparent;
  border: none;
  color: #999;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
  line-height: 1;
  margin-left: 8px;
}

.delete-var-button:hover {
  color: #ff6b6b;
}

/* List items styles */
.list-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.var-item,
.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 420px;
  padding: 7px 12px;
  background-color: rgba(90, 90, 90, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  color: #f2f2f2;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  gap: 12px;
}

.var-item:hover,
.list-item:hover {
  background-color: rgba(110, 110, 110, 0.95);
  border-color: rgba(160, 196, 255, 0.7);
}

.item-value {
  flex: 1;
}

.delete-item-button {
  background: transparent;
  border: none;
  color: #999;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
  line-height: 1;
  margin-left: 8px;
}

.delete-item-button:hover {
  color: #ff6b6b;
}

.child-node-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.child-node-controls {
  display: flex;
  align-items: center;
  gap: 5px;
}

.clear-child-button {
  background: transparent;
  border: none;
  color: #999;
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
  line-height: 1;
}

.clear-child-button:hover {
  color: #ff6b6b;
}

.add-child-button,
.add-list-button,
.add-var-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background-color: rgba(255, 255, 255, 0.14);
  color: rgba(242, 242, 242, 0.9);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}

.add-child-button:hover,
.add-list-button:hover,
.add-var-button:hover {
  background-color: rgba(255, 255, 255, 0.08);
}

.add-child-button .plus-icon,
.add-list-button .plus-icon,
.add-var-button .plus-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}

.add-child-button .plus-icon svg,
.add-list-button .plus-icon svg,
.add-var-button .plus-icon svg {
  display: block;
}

.add-child-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: rgba(255, 255, 255, 0.1);
  background-color: rgba(74, 74, 74, 0.8);
  color: rgba(200, 200, 200, 0.7);
}

.child-node-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.child-node-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 14px;
  background-color: rgba(90, 90, 90, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  color: #f2f2f2;
  font-size: 13px;
  gap: 12px;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.child-node-item:hover {
  background-color: rgba(110, 110, 110, 0.95);
  border-color: rgba(160, 196, 255, 0.7);
}

.child-node-name {
  flex: 1;
}

.child-node-actions {
  display: flex;
  gap: 8px;
}

.child-node-item-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.child-node-summary {
  padding: 6px 12px;
  margin-left: 0;
  background-color: rgba(60, 60, 60, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: rgba(200, 200, 200, 0.85);
  font-size: 12px;
  line-height: 1.4;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: pre-line;
}

.edit-child-button,
.delete-child-button {
  padding: 6px 10px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.edit-child-button {
  background-color: rgba(117, 117, 117, 0.95);
  color: #f2f2f2;
}

.edit-child-button:hover {
  background-color: rgba(136, 136, 136, 0.98);
}

.delete-child-button {
  background-color: rgba(90, 90, 90, 0.9);
  color: #f2f2f2;
}

.delete-child-button:hover {
  background-color: rgba(110, 110, 110, 0.95);
}

.child-node-hint {
  padding: 6px 8px;
  color: rgba(189, 189, 189, 0.9);
  font-size: 12px;
}

/* Custom select styles */

.custom-select-wrapper {
  position: relative;
}

.custom-select-input {
  cursor: pointer;
}

.custom-select-input:focus {
  cursor: text;
}

.custom-select-arrow {
  position: absolute;
  right: 12px;
  top: 18px;
  transform: translateY(-50%);
  color: rgba(242, 242, 242, 0.7);
  font-size: 12px;
  pointer-events: none;
  transition: transform 0.2s ease;
}

.custom-select-arrow.arrow-open {
  transform: translateY(-50%) rotate(180deg);
}

.custom-select-dropdown {
  position: static;
  max-height: 200px;
  overflow-y: auto;
  background-color: rgba(25, 25, 25, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  margin-top: 2px;
  width: 100%;
}

.custom-select-option {
  padding: 6px 6px;
  cursor: pointer;
  color: #f2f2f2;
  font-size: 13px;
  transition: background-color 0.2s ease;
}

.custom-select-option:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.custom-select-option.option-selected {
  background-color: rgba(160, 196, 255, 0.2);
  color: #a0c4ff;
  font-weight: 500;
}

.custom-select-no-results {
  padding: 10px 12px;
  color: rgba(189, 189, 189, 0.7);
  font-size: 12px;
  text-align: center;
  font-style: italic;
}

.select-disabled .custom-select-input {
  cursor: not-allowed;
}
</style>
