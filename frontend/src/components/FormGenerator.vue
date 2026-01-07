<template>
  <template v-for="(modal, index) in modalStack" :key="modal.id">
    <div
      class="modal-overlay"
      :style="{ zIndex: 1000 + index }"
      @mousedown.self="modalMousedownTargets.set(modal.id, true)"
      @mouseup.self="modalMouseupTargets.set(modal.id, true)"
      @click.self="handleOverlayClick(modal.id)"
    >
      <div class="modal-content">
        <div class="modal-header">
          <div v-if="modal.formError" class="submit-error">
            {{ modal.formError }}
          </div>
          <button class="close-button" @click="closeModal(modal.id)">×</button>
        </div>
        <div class="modal-body">
          <div
            v-for="field in getMainDisplayFields(modal)"
            :key="field.name + '-' + (modal.formData[field.name]?.type || '')"
          >
            <!-- Main Field Rendering -->
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
              :is-read-only="isFieldReadOnly(field)"
              @open-child-modal="(f, idx) => openChildModal(modal.id, f, idx)"
              @clear-child-entry="(fname) => clearChildEntry(modal.id, fname)"
              @delete-child-entry="(fname, idx) => deleteChildEntry(modal.id, fname, idx)"
              @open-conditional-child-modal="(f) => openConditionalChildModal(modal.id, f)"
              @handle-enum-change="(f) => handleEnumChange(modal.id, f)"
              @open-var-modal="(fname) => openVarModal(modal.id, fname)"
              @edit-var="(fname, key) => editVar(modal.id, fname, key)"
              @delete-var="(fname, key) => deleteVar(modal.id, fname, key)"
              @open-list-item-modal="(fname) => openListItemModal(modal.id, fname)"
              @delete-list-item="(fname, idx) => deleteListItem(modal.id, fname, idx)"
            />
          </div>

          <!-- Advanced Settings Toggle (Between Normal Fields and Inline Config) -->
          <div
            v-if="modal.hasAdvancedFields"
            class="advanced-toggle"
          >
            <button
              type="button"
              class="advanced-toggle-button"
              @click="toggleAdvancedFields(modal.id)"
            >
              Advanced Settings
              <span class="advanced-toggle-arrow">
                {{ modal.showAdvanced ? '▲' : '▼' }}
              </span>
            </button>
          </div>

          <!-- Inline Config Fields (Rendered at bottom) -->
          <div
            v-for="field in getInlineDisplayFields(modal)"
            :key="field.name"
          >
              <!-- Inline Config Expansion -->
              <div
                v-if="isInlineConfigField(field) && modal.inlineChildModals?.[field.name]"
                class="inline-config-section"
                :key="modal.inlineChildModals[field.name]?.id"
              >
                <div class="inline-separator"></div>
                
                <!-- Recursion via InlineConfigRenderer -->
                <InlineConfigRenderer
                  :modal="modal.inlineChildModals[field.name]"
                  :read-only-fields="props.readOnlyFields"
                  @open-child-modal="(mid, f, idx) => openChildModal(mid, f, idx)"
                  @open-conditional-child-modal="(mid, f) => openConditionalChildModal(mid, f)"
                  @handle-enum-change="(mid, f) => handleEnumChange(mid, f)"
                  @open-var-modal="(mid, fname) => openVarModal(mid, fname)"
                  @edit-var="(mid, fname, key) => editVar(mid, fname, key)"
                  @delete-var="(mid, fname, key) => deleteVar(mid, fname, key)"
                  @open-list-item-modal="(mid, fname) => openListItemModal(mid, fname)"
                  @delete-list-item="(mid, fname, idx) => deleteListItem(mid, fname, idx)"
                  @clear-child-entry="(mid, fname) => clearChildEntry(mid, fname)"
                  @delete-child-entry="(mid, fname, idx) => deleteChildEntry(mid, fname, idx)"
                  @toggle-advanced-fields="(mid) => toggleAdvancedFields(mid)"
                />
              </div>
          </div>
        </div>
        <div class="submit-button-container">
          <button
            v-if="showCopyButton(modal)"
            @click="copyNode(modal.id)"
            class="add-child-button"
            :disabled="modal.submitting"
          >
            Copy Node
          </button>
          <button
            v-if="showDeleteButton(modal)"
            @click="deleteEntry(modal.id)"
            class="delete-button"
            :disabled="modal.submitting"
          >
            {{ deleteButtonLabel(modal) }}
          </button>
          <button
            @click="submitForm(modal.id)"
            class="submit-button"
            :disabled="modal.submitting"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  </template>

  <!-- Var edit modal -->
  <div v-if="showVarModal" class="modal-overlay modal-overlay-elevated" @click.self="closeVarModal">
    <div class="modal-content var-modal">
      <div class="modal-header">
        <button class="close-button" @click="closeVarModal">×</button>
      </div>
      <div class="modal-body">
        <div v-if="varFormError" class="submit-error">
          {{ varFormError }}
        </div>
        <div class="form-group">
          <label for="var-key">Key <span class="required-asterisk">*</span></label>
          <input
            id="var-key"
            v-model="varForm.key"
            type="text"
            class="form-input"
          />
        </div>
        <div class="form-group">
          <label for="var-value">Value <span class="required-asterisk">*</span></label>
          <input
            id="var-value"
            v-model="varForm.value"
            type="text"
            class="form-input"
          />
        </div>
        <div class="modal-actions">
          <button @click="closeVarModal" class="cancel-button">Cancel</button>
          <button @click="confirmVar" class="confirm-button">Confirm</button>
        </div>
      </div>
    </div>
  </div>

  <!-- List item edit modal -->
  <div
    v-if="showListItemModal"
    class="modal-overlay modal-overlay-elevated"
    @click.self="closeListItemModal"
  >
    <div class="modal-content list-item-modal">
      <div class="modal-header">
        <h3 class="modal-title">{{ editingListItemIndex !== null ? 'Edit Entry' : 'Add Entry' }}</h3>
        <button class="close-button" @click="closeListItemModal">×</button>
      </div>
      <div class="modal-body">
        <div v-if="listItemFormError" class="submit-error">
          {{ listItemFormError }}
        </div>
        <div class="form-group">
          <label for="list-item-value">Value <span class="required-asterisk">*</span></label>
          <input
            id="list-item-value"
            v-model="listItemForm.value"
            type="text"
            class="form-input"
          />
        </div>
        <div class="modal-actions">
          <button @click="closeListItemModal" class="cancel-button">Cancel</button>
          <button @click="confirmListItem" class="confirm-button">Confirm</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick, computed, onMounted, onBeforeUnmount } from 'vue'
import yaml from 'js-yaml'
import { fetchConfigSchema, postYaml, fetchWorkflowYAML, updateYaml } from '../utils/apiFunctions.js'
import { configStore } from '../utils/configStore.js'
import DynamicFormField from './DynamicFormField.vue'
import InlineConfigRenderer from './InlineConfigRenderer.vue'
import {
  isListField,
  hasChildRoutes,
  isInlineConfigField,
  getDisplayFields,
  isFieldVisible,
  canOpenConditionalChildModal,
  conditionalChildButtonLabel,
  childNodeButtonLabel,
  getActiveChildRoute,
  getConditionalChildKeyValue,
  getSchemaFields,
  determineRouteControllerField
} from '../utils/formUtils.js'

const props = defineProps({
  breadcrumbs: {
    type: Array,
    default: null
  },
  recursive: {
    type: Boolean,
    default: false
  },
  workflowName: {
    type: String,
    default: ''
  },
  initialYaml: {
    type: [Object, String],
    default: null
  },
  initialFormData: {
    type: [Object, Array],
    default: null
  },
  mode: {
    type: String,
    default: 'auto',
    validator: (value) => ['auto', 'create', 'edit'].includes(value)
  },
  readOnlyFields: {
    type: Array,
    default: () => []
  },
  fieldFilter: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'submit', 'copy'])

// Stores all "layers" of forms
const modalStack = reactive([])
let modalIdCounter = 0

// Used to prevent undesired closure of modal
const modalMousedownTargets = new Map()
const modalMouseupTargets = new Map()

const yamlDumpOptions = Object.freeze({
  indent: 2,
  lineWidth: -1,
  noRefs: true,
  sortKeys: false
})

const baseYamlObject = ref(null)
const baseYamlString = ref('')
const baseYamlFilename = ref('')
const baseYamlLoading = ref(false)
const baseYamlError = ref(null)

const formMode = computed(() => {
  if (props.mode === 'create' || props.mode === 'edit') {
    return props.mode
  }
  return props.initialFormData ? 'edit' : 'create'
})

const normalizeWorkflowFilename = (name) => {
  if (!name) {
    return ''
  }
  if (name.endsWith('.yaml') || name.endsWith('.yml')) {
    return name
  }
  return `${name}.yaml`
}

const setBaseYamlFromSource = (source) => {
  if (!source) {
    baseYamlObject.value = null
    baseYamlString.value = ''
    return
  }
  try {
    let parsed = source
    if (typeof source === 'string') {
      parsed = yaml.load(source) || {}
    } else if (typeof source === 'object') {
      parsed = JSON.parse(JSON.stringify(source))
    } else {
      parsed = {}
    }
    baseYamlObject.value = parsed
    baseYamlString.value = yaml.dump(parsed ?? null, yamlDumpOptions)
  } catch (error) {
    console.error('Failed to set base YAML from provided source:', error)
    baseYamlObject.value = null
    baseYamlString.value = ''
  }
}

const loadBaseYamlFromServer = async (workflowName) => {
  if (!workflowName) {
    baseYamlFilename.value = ''
    baseYamlObject.value = null
    baseYamlString.value = ''
    return false
  }
  const filename = normalizeWorkflowFilename(workflowName)
  baseYamlLoading.value = true
  baseYamlError.value = null
  try {
    const yamlString = await fetchWorkflowYAML(filename)
    baseYamlString.value = yamlString || ''
    baseYamlObject.value = yamlString ? yaml.load(yamlString) || {} : {}
    baseYamlFilename.value = filename
    return true
  } catch (error) {
    console.error('Failed to load workflow YAML for FormGenerator:', error)
    baseYamlError.value = 'Failed to load workflow YAML'
    baseYamlObject.value = null
    baseYamlString.value = ''
    return false
  } finally {
    baseYamlLoading.value = false
  }
}

const ensureBaseYamlReady = async () => {
  if (!props.workflowName) {
    return true
  }
  if (baseYamlObject.value) {
    return true
  }
  if (baseYamlLoading.value) {
    return false
  }
  return loadBaseYamlFromServer(props.workflowName)
}

// Var modal state (for dict[str, Any] key-value fields)
const showVarModal = ref(false)
const editingVarIndex = ref(null)
const varFormError = ref(null)
const varForm = reactive({
  key: '',
  value: ''
})
const activeVarModalId = ref(null)
const activeVarFieldName = ref(null)

const hasDictEntries = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  return Object.keys(value).length > 0
}

// List item modal state
const showListItemModal = ref(false)
const editingListItemIndex = ref(null)
const listItemFormError = ref(null)
const currentListContext = reactive({
  modalId: null,
  fieldName: ''
})
const listItemForm = reactive({
  value: ''
})



const hasAdvancedField = (fields, fieldFilter = null, parentContext = null) => {
  if (!Array.isArray(fields)) {
    return false
  }

  let fieldsToCheck = fields

  // Apply fieldFilter if provided and we're in a top-level modal
  if (!parentContext && Array.isArray(fieldFilter) && fieldFilter.length > 0) {
    const allowed = new Set(fieldFilter)
    const nonInlineFields = fields.filter(field => !isInlineConfigField(field))
    fieldsToCheck = nonInlineFields.filter(field => allowed.has(field.name))
  }

  return fieldsToCheck.some(field => Boolean(field?.advance))
}



const getMainDisplayFields = (modal) => {
  const fields = getDisplayFields(modal)

  const nonInlineFields = fields.filter(field => !isInlineConfigField(field))

  // Apply optional field filter to top level,non-inline modal; child/inline modals see full schema
  if (!modal?.parentContext && Array.isArray(props.fieldFilter) && props.fieldFilter.length > 0) {
    const allowed = new Set(props.fieldFilter)
    return nonInlineFields.filter(field => allowed.has(field.name))
  }
  return nonInlineFields
}

const getInlineDisplayFields = (modal) => {
  const fields = getDisplayFields(modal)
  return fields.filter(field => isInlineConfigField(field))
}



const hasChildValue = (modal, field) => {
  if (!modal || !field) {
    return false
  }
  const value = modal.formData?.[field.name]
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return value !== null && value !== undefined && value !== ''
}



const findSchemaByNodeName = (nodeName) => {
  if (!nodeName) {
    return null
  }
  for (let i = modalStack.length - 1; i >= 0; i -= 1) {
    const entry = modalStack[i]
    if (entry?.schema?.node === nodeName) {
      return entry.schema
    }
  }
  return null
}

const findFieldSpecForBreadcrumb = (crumb) => {
  if (!crumb?.node || !crumb?.field) {
    return null
  }
  const schema = findSchemaByNodeName(crumb.node)
  if (!schema || !Array.isArray(schema.fields)) {
    return null
  }
  return schema.fields.find(field => field.name === crumb.field) || null
}

const wrapDataWithBreadcrumbs = (modal, data) => {
  const crumbs = Array.isArray(modal?.breadcrumbs) ? modal.breadcrumbs : []
  if (!crumbs.length) {
    return data
  }

  let currentValue = data
  for (let i = crumbs.length - 1; i >= 0; i -= 1) {
    const crumb = crumbs[i]
    if (!crumb?.field) {
      continue
    }

    const fieldSpec = findFieldSpecForBreadcrumb(crumb)
    const shouldWrapAsList = fieldSpec ? isListField(fieldSpec) : false
    let fieldValue = currentValue
    if (shouldWrapAsList && !Array.isArray(fieldValue)) {
      fieldValue = [fieldValue]
    }

    currentValue = {
      [crumb.field]: fieldValue
    }
  }

  return currentValue
}

const isPlainObject = (value) => Object.prototype.toString.call(value) === '[object Object]'

const cloneStructuredValue = (value) => {
  if (Array.isArray(value) || isPlainObject(value)) {
    return JSON.parse(JSON.stringify(value))
  }
  return value
}

const mergeYamlStructures = (target, source) => {
  if (source === undefined || source === null) {
    return target
  }
  if (target === undefined || target === null) {
    return cloneStructuredValue(source)
  }
  if (Array.isArray(target)) {
    if (Array.isArray(source)) {
      return [...target, ...source]
    }
    return [...target, cloneStructuredValue(source)]
  }
  if (Array.isArray(source)) {
    return source.map(item => cloneStructuredValue(item))
  }
  if (isPlainObject(target) && isPlainObject(source)) {
    const result = { ...target }
    Object.keys(source).forEach(key => {
      if (result[key] === undefined) {
        result[key] = cloneStructuredValue(source[key])
      } else {
        result[key] = mergeYamlStructures(result[key], source[key])
      }
    })
    return result
  }
  return source
}

const buildPartialYamlPayload = (modal, data) => {
  if (!modal) {
    return { structuredData: null, yamlString: null }
  }
  try {
    const structuredData = wrapDataWithBreadcrumbs(modal, data)
    const yamlString = yaml.dump(structuredData ?? null, yamlDumpOptions)
    console.log('Generated partial YAML:\n' + yamlString)
    return { structuredData, yamlString }
  } catch (error) {
    console.error('Failed to generate partial YAML:', error)
    return { structuredData: null, yamlString: null }
  }
}

const cloneValue = (value) => {
  if (value === null || value === undefined) {
    return value
  }
  if (Array.isArray(value) || typeof value === 'object') {
    return JSON.parse(JSON.stringify(value))
  }
  return value
}

const isValueEmpty = (value) => {
  if (value === null || value === undefined) {
    return true
  }
  if (typeof value === 'string') {
    return value.trim() === ''
  }
  if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'bigint') {
    return false
  }
  if (Array.isArray(value)) {
    return value.length === 0
  }
  // Accept empty object ({}) as valid value
  if (typeof value === 'object') {
    return value === null || value === undefined
  }
  return false
}

const shouldValidateField = (modal, field) => {
  // Validate filtered fields in top level field if filter is applied
  if (
    !modal?.parentContext &&
    props.fieldFilter.length > 0 &&
    !props.fieldFilter.includes(field?.name)
  ) {
    return false
  }
  if (!modal?.recursive && field?.childNode) {
    return false
  }
  return true
}

const validateModalForm = (modal) => {
  if (!modal?.schema?.fields) {
    modal.formError = null
    return true
  }

  for (const field of modal.schema.fields) {
    if (!shouldValidateField(modal, field)) {
      continue
    }
    if (!field.required) {
      continue
    }

    const value = modal.formData[field.name]
    if (isValueEmpty(value)) {
      modal.formError = `"${field.displayName || field.name}" is required`
      return false
    }
  }

  modal.formError = null
  return true
}

const formatBreadcrumbs = (crumbs) => {
  if (!Array.isArray(crumbs)) {
    return []
  }
  return crumbs.map(crumb => ({ ...crumb }))
}

const isFieldReadOnly = (field) => {
  return props.readOnlyFields.includes(field.name)
}

const findModalById = (modalId) => {
  const searchState = (list) => {
    for (const modal of list) {
      if (modal.id === modalId) {
        return modal
      }
      if (modal.inlineChildModals) {
        // Recursive search in inline children
        const found = searchState(Object.values(modal.inlineChildModals))
        if (found) {
          return found
        }
      }
    }
    return null
  }
  return searchState(modalStack)
}

// Initializes form data
const createModalState = (
  schemaResponse,
  requestedBreadcrumbs,
  recursiveFlag,
  parentContext = null,
  initialData = null,
  options = {}
) => {
  const modalBreadcrumbs = Array.isArray(schemaResponse.breadcrumbs) && schemaResponse.breadcrumbs.length > 0
    ? schemaResponse.breadcrumbs.map(crumb => ({ ...crumb }))
    : requestedBreadcrumbs

  // Check if the schema is for "Manage Variables" or "Manage Memories"
  // Use all fields from the schema. Filtering for "Manage Vars" or "Manage Memory" 
  // is handled at the view layer by `getDisplayFields`. 
  // We do NOT want to filter the underlying schema/formData here, as that breaks "Create Workflow" 
  // which shares the same breadcrumb path but needs all fields.
  const schemaFields = Array.isArray(schemaResponse.fields) ? schemaResponse.fields : []

  const effectiveSchema = {
    ...schemaResponse,
    fields: schemaFields
  }

  const advancedFieldsPresent = hasAdvancedField(schemaFields, props.fieldFilter, parentContext)

  const derivedIsNewEntry = options?.isNewEntry ?? !initialData

  const modalState = reactive({
    id: `modal-${modalIdCounter++}`,
    schema: effectiveSchema,
    breadcrumbs: modalBreadcrumbs,
    recursive: recursiveFlag,
    formData: reactive({}),
    formError: null,
    submitting: false,
    parentContext,
    initialData: initialData ? cloneValue(initialData) : null,
    isNewEntry: Boolean(derivedIsNewEntry),
    showAdvanced: configStore.AUTO_SHOW_ADVANCED,
    hasAdvancedFields: advancedFieldsPresent,
    childSummaries: reactive({}), // Store summaries for child nodes
    inlineChildModals: reactive({}) // Store inline states for type+config handling
  })

  schemaFields.forEach(field => {
    if (field.childNode) {
      modalState.formData[field.name] = isListField(field) ? [] : null
      return
    }

    if (field.default !== undefined) {
      modalState.formData[field.name] = cloneValue(field.default)
    } else if (isListField(field)) {
      modalState.formData[field.name] = []
    } else if (field.type && field.type.startsWith('dict[')) {
      modalState.formData[field.name] = {}
    } else if (field.type === 'bool') {
      modalState.formData[field.name] = null
    } else if (field.type === 'int' || field.type === 'float') {
      modalState.formData[field.name] = null
    } else {
      modalState.formData[field.name] = ''
    }
  })

  if (initialData && typeof initialData === 'object') {
    Object.keys(initialData).forEach(key => {
      const fieldSpec = schemaFields.find(field => field.name === key)
      let value = cloneValue(initialData[key])

      // Normalize scalar values for list fields (e.g. YAML: "start: Data" for "list[str]")
      if (
        fieldSpec &&
        isListField(fieldSpec) &&
        value !== undefined &&
        value !== null &&
        !Array.isArray(value)
      ) {
        value = [value]
      }

      modalState.formData[key] = value
    })
  }

  // Record snapshot to determine if changes are made
  try {
    modalState.originalFormData = JSON.parse(JSON.stringify(modalState.formData ?? {}))
  } catch (e) {
    console.warn('[FormGenerator] Failed to snapshot original form data:', e)
    modalState.originalFormData = null
  }

  return modalState
}

const initializeChildSummaries = async (modal) => {
  if (!modal || !modal.schema || !Array.isArray(modal.schema.fields)) {
    return
  }

  const fields = modal.schema.fields

  for (const field of fields) {
    const fieldValue = modal.formData[field.name]

    // Handle childNode fields
    if (field.childNode) {
      if (isListField(field)) {
        // For list fields, generate summary for each entry
        if (Array.isArray(fieldValue) && fieldValue.length > 0) {
          const summaries = []
          for (let i = 0; i < fieldValue.length; i++) {
            const childData = fieldValue[i]
            if (childData && typeof childData === 'object') {
              try {
                const baseBreadcrumbs = modal.breadcrumbs
                  ? modal.breadcrumbs.map(crumb => ({ ...crumb }))
                  : []
                const nextBreadcrumbs = [
                  ...baseBreadcrumbs,
                  { node: modal.schema.node, field: field.name }
                ]
                const childSchemaResponse = await fetchConfigSchema(nextBreadcrumbs)
                const tempChildModal = {
                  schema: childSchemaResponse,
                  formData: childData
                }
                const summary = generateChildSummary(tempChildModal, childData)
                summaries.push(summary)
              } catch (error) {
                console.warn(`[FormGenerator] Failed to generate summary for child entry ${i} of field ${field.name}:`, error)
                summaries.push('')
              }
            } else {
              summaries.push('')
            }
          }
          modal.childSummaries[field.name] = summaries
        }
      } else {
        // For non-list child fields, generate summary for the single entry
        if (fieldValue && typeof fieldValue === 'object' && !Array.isArray(fieldValue)) {
          try {
            const baseBreadcrumbs = modal.breadcrumbs
              ? modal.breadcrumbs.map(crumb => ({ ...crumb }))
              : []
            const nextBreadcrumbs = [
              ...baseBreadcrumbs,
              { node: modal.schema.node, field: field.name }
            ]
            const childSchemaResponse = await fetchConfigSchema(nextBreadcrumbs)
            const tempChildModal = {
              schema: childSchemaResponse,
              formData: fieldValue
            }
            const summary = generateChildSummary(tempChildModal, fieldValue)
            modal.childSummaries[field.name] = summary
          } catch (error) {
            console.warn(`[FormGenerator] Failed to generate summary for child field ${field.name}:`, error)
            modal.childSummaries[field.name] = ''
          }
        }
      }
    }
    // Handle conditional child routes
    else if (hasChildRoutes(field)) {
      if (isListField(field)) {
        // For list fields, generate summary for each entry
        if (Array.isArray(fieldValue) && fieldValue.length > 0) {
          const summaries = []
          for (let i = 0; i < fieldValue.length; i++) {
            const childData = fieldValue[i]
            if (childData && typeof childData === 'object' && !Array.isArray(childData)) {
              try {
                const activeRoute = getActiveChildRoute(modal, field)
                if (activeRoute) {
                  const baseBreadcrumbs = modal.breadcrumbs
                    ? modal.breadcrumbs.map(crumb => ({ ...crumb }))
                    : []
                  const crumb = {
                    node: modal.schema.node,
                    field: field.name
                  }
                  if (activeRoute.childKey && Object.prototype.hasOwnProperty.call(activeRoute.childKey, 'value')) {
                    crumb.value = activeRoute.childKey.value
                  }
                  const nextBreadcrumbs = [...baseBreadcrumbs, crumb]
                  const childSchemaResponse = await fetchConfigSchema(nextBreadcrumbs)
                  const tempChildModal = {
                    schema: childSchemaResponse,
                    formData: childData
                  }
                  const summary = generateChildSummary(tempChildModal, childData)
                  summaries.push(summary)
                } else {
                  summaries.push('')
                }
              } catch (error) {
                console.warn(`[FormGenerator] Failed to generate summary for conditional child entry ${i} of field ${field.name}:`, error)
                summaries.push('')
              }
            } else {
              summaries.push('')
            }
          }
          modal.childSummaries[field.name] = summaries
        }
      } else {
        // For non-list conditional child fields
        if (fieldValue && typeof fieldValue === 'object' && !Array.isArray(fieldValue)) {
          try {
            const activeRoute = getActiveChildRoute(modal, field)
            if (activeRoute) {
              const baseBreadcrumbs = modal.breadcrumbs
                ? modal.breadcrumbs.map(crumb => ({ ...crumb }))
                : []
              const crumb = {
                node: modal.schema.node,
                field: field.name
              }
              if (activeRoute.childKey && Object.prototype.hasOwnProperty.call(activeRoute.childKey, 'value')) {
                crumb.value = activeRoute.childKey.value
              }
              const nextBreadcrumbs = [...baseBreadcrumbs, crumb]
              const childSchemaResponse = await fetchConfigSchema(nextBreadcrumbs)
              const tempChildModal = {
                schema: childSchemaResponse,
                formData: fieldValue
              }
              const summary = generateChildSummary(tempChildModal, fieldValue)
              modal.childSummaries[field.name] = summary
            }
          } catch (error) {
            console.warn(`[FormGenerator] Failed to generate summary for conditional child field ${field.name}:`, error)
            modal.childSummaries[field.name] = ''
          }
        }
      }
    }
  }

  // After initializing summaries, also initialize inline configs if available
  await updateInlineChildModals(modal)
}



const updateInlineChildModals = async (modal) => {
  if (!modal || !modal.schema?.fields) {
    return
  }
  
  for (const field of modal.schema.fields) {
    if (isInlineConfigField(field)) {
      const activeRoute = getActiveChildRoute(modal, field)
      
      if (activeRoute) {
        // Prepare breadcrumbs
        const baseBreadcrumbs = modal.breadcrumbs
          ? modal.breadcrumbs.map(crumb => ({ ...crumb }))
          : []
          
        const crumb = {
          node: modal.schema.node,
          field: field.name
        }
        
        if (activeRoute.childKey && Object.prototype.hasOwnProperty.call(activeRoute.childKey, 'value')) {
          crumb.value = activeRoute.childKey.value
        }
        
        const nextBreadcrumbs = [...baseBreadcrumbs, crumb]
        
        try {
           console.log('Fetching inline schema with breadcrumbs:', nextBreadcrumbs)
           // We fetch schema. If we already have a modal for this field, check if it matches? 
           // Simpler: Just re-generate if type changed.
           // How to detect type change efficiently without refetching always?
           // 'activeRoute' gives us the key.
           
           // We can check if existing inline modal corresponds to current selection.
           // However, 'generateForm' logic is complex.
           
           // Let's rely on fetchConfigSchema caching or speed.
           const schemaResponse = await fetchConfigSchema(nextBreadcrumbs)
           console.log('Inline schema response:', schemaResponse)
           
           // If we already have an inline modal, replace it ONLY if schema/type is different?
           // But form generator creates new state easily.
           
           // We should NOT destroy existing data if type hasn't changed.
           // The current updateInlineChildModals is called on generateForm.
           // But handleEnumChange also calls it.
           
           // Initialize data
           let initialData = modal.formData[field.name]
           if (!initialData) initialData = {} // or null
           
           // Create the modal state roughly
          const inlineModalState = createModalState(
            schemaResponse,
            nextBreadcrumbs,
            true, // Inline is recursive-like
            null, // parentContext? Inline modal is "part" of parent physically but logically separate state object.
            initialData
          )

          // Populate summaries for inline modal (mirrors behavior of main modal initialization)
          await initializeChildSummaries(inlineModalState)
          await updateInlineChildModals(inlineModalState)

          // We can use a watcher on the new inlineModalState.formData
          watch(
            () => inlineModalState.formData,
            (newVal) => {
              modal.formData[field.name] = newVal
            },
            { deep: true, immediate: true }
          )
           
           // Set parent context properly so validations work if needed?
           // Actually, validation of the parent should validate the child.
           // Currently `validateModalForm` only validates own fields.
           // If we have an inline child, we should validate it too!
           
           modal.inlineChildModals[field.name] = inlineModalState
           
        } catch (e) {
           console.error("Failed to load inline config schema", e)
        }
      } else {
        // No active route (e.g. type unselected), clear inline modal
        if (modal.inlineChildModals[field.name]) {
          delete modal.inlineChildModals[field.name]
        }
      }
    }
  }
}

const generateForm = async (
  breadcrumbsArg = [],
  recursiveFlag = false,
  parentContext = null,
  initialData = null,
  options = {}
) => {
  const formattedBreadcrumbs = formatBreadcrumbs(breadcrumbsArg)
  try {
     console.log("Fetching schema with breadcrumbs: ", formattedBreadcrumbs)
    // Obtain schema for form
    const response = await fetchConfigSchema(formattedBreadcrumbs)
    console.log("Schema response: ", response)

    // Use schema to create modal state
    const modalState = createModalState(
      response,
      formattedBreadcrumbs,
      recursiveFlag,
      parentContext,
      initialData,
      options
    )
    // Push modal state into stack
    modalStack.push(modalState)
    
    // Initialize summaries for child fields that already have data
    await initializeChildSummaries(modalState)
    
    return modalState.id
  } catch (error) {
    console.error('Error generating form:', error)
    throw error
  }
}

// Calls generateForm() when crumbs change
watch(() => props.breadcrumbs, async (newBreadcrumbs) => {
  if (!Array.isArray(newBreadcrumbs)) {
    return
  }
  try {
    await generateForm(newBreadcrumbs, props.recursive, null, props.initialFormData || null, {
      isNewEntry: formMode.value === 'create'
    })
  } catch (error) {
    console.error('Failed to initialize form generator:', error)
  }
}, { immediate: true })

watch(() => props.initialYaml, (newValue) => {
  if (newValue) {
    setBaseYamlFromSource(newValue)
    if (props.workflowName) {
      baseYamlFilename.value = normalizeWorkflowFilename(props.workflowName)
    }
  } else if (!props.workflowName) {
    baseYamlObject.value = null
    baseYamlString.value = ''
  }
}, { immediate: true, deep: true })

watch(() => props.workflowName, async (newName, oldName) => {
  if (!newName) {
    baseYamlFilename.value = ''
    if (!props.initialYaml) {
      baseYamlObject.value = null
      baseYamlString.value = ''
    }
    return
  }
  baseYamlFilename.value = normalizeWorkflowFilename(newName)
  if (props.initialYaml) {
    return
  }
  if (newName === oldName && baseYamlObject.value) {
    return
  }
  await loadBaseYamlFromServer(newName)
}, { immediate: true })

const handleOverlayClick = (modalId) => {
  // Only close if both mousedown and mouseup happen on overlay
  if (modalMousedownTargets.has(modalId) && modalMouseupTargets.has(modalId)) {
    modalMousedownTargets.delete(modalId)
    modalMouseupTargets.delete(modalId)
    closeModal(modalId)
  } else {
    modalMousedownTargets.delete(modalId)
    modalMouseupTargets.delete(modalId)
  }
}

const closeModal = (modalId) => {
  const lastModal = modalStack[modalStack.length - 1]
  if (!lastModal || lastModal.id !== modalId) {
    console.warn(`[FormGenerator] Attempted to close modal ${modalId} that is not on top of stack`)
    return
  }

  modalStack.pop()

  if (activeVarModalId.value === modalId) {
    closeVarModal()
  }

  if (currentListContext.modalId === modalId) {
    closeListItemModal()
  }

  if (modalStack.length === 0) {
    nextTick(() => emit('close'))
  }
}

const toggleAdvancedFields = (modalId) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  modal.showAdvanced = !modal.showAdvanced
}

const sanitizeFormData = (data) => JSON.parse(JSON.stringify(data ?? {}))

const hasModalChanges = (modal, payload) => {
  if (!modal) {
    return true
  }

  if (modal.isNewEntry) {
    return true
  }

  if (!modal.initialData || !modal.originalFormData) {
    return true
  }

  try {
    const original = sanitizeFormData(modal.originalFormData)
    const current = sanitizeFormData(payload)
    return JSON.stringify(original) !== JSON.stringify(current)
  } catch (e) {
    console.warn('[FormGenerator] Failed to compare form changes:', e)
    return true
  }
}

const generateChildSummary = (modal, formData) => {
  if (!modal || !modal.schema || !Array.isArray(modal.schema.fields)) {
    return ''
  }

  const summaryParts = []
  const fields = modal.schema.fields

  for (const field of fields) {
    const value = formData[field.name]
    const label = field.displayName || field.name

    if (field.childNode) {
      if (isListField(field)) {
        // For list fields, show number of entries configured 
        const entryCount = Array.isArray(value) ? value.length : 0
        if (entryCount > 0 && entryCount===1) {
          summaryParts.push(`${label}: 1 entry configured`)
        } else if (entryCount > 0 && entryCount > 1) {
          summaryParts.push(`${label}: ${entryCount} entries configured`)
        }
      } else {
        // For non-list fields, show configuration status 
        const isConfigured = value !== null && value !== undefined && value !== ''
        if (isConfigured) {
          summaryParts.push(`${label}: Configured`)
        }
      }
      continue
    }

    // Inline config fields (type + config pattern) summarize their active child schema.
    // Do this before empty checks
    if (isInlineConfigField(field) && modal.inlineChildModals?.[field.name]) {
      const inlineModal = modal.inlineChildModals[field.name]
      const inlineData = value ?? inlineModal.formData ?? {}
      const inlineSummary = generateChildSummary(inlineModal, inlineData)
      if (inlineSummary) {
        summaryParts.push(inlineSummary)
      }
      continue
    }

    // Skip empty values for non-childNode fields
    if (isValueEmpty(value)) {
      continue
    }

    let displayValue = ''
    if (Array.isArray(value)) {
      if (value.length === 0) {
        continue
      }
      // For arrays, show the values
      if (field.enum) {
        // Multi-select enum
        displayValue = value.map(v => {
          const option = field.enumOptions?.find(opt => 
            (typeof opt === 'string' ? opt : opt.value) === v
          ) || field.enum.find(opt => 
            (typeof opt === 'string' ? opt : opt.value) === v
          )
          return typeof option === 'string' ? option : (option?.label || option?.value || v)
        }).join(', ')
      } else {
        displayValue = value.join(', ')
      }
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      // For objects/dicts, show key-value pairs
      const entries = Object.entries(value)
      if (entries.length === 0) {
        continue
      }
      displayValue = entries.map(([k, v]) => `${k} => ${v}`).join(', ')
    } else if (typeof value === 'boolean') {
      displayValue = String(value)
    } else {
      displayValue = String(value)
    }

    summaryParts.push(`${label}: ${displayValue}`)
  }

  console.log('Summary array generated: ', summaryParts)
  return summaryParts.join('\n')
}

const applyChildResult = (context, childData, childModal) => {
  const parentModal = findModalById(context.parentModalId)
  if (!parentModal) {
    return
  }

  const targetField = context.parentFieldName
  
  // Generate summary from form data
  const summary = childModal ? generateChildSummary(childModal, childData) : ''

  if (context.isList) {
    if (!Array.isArray(parentModal.formData[targetField])) {
      parentModal.formData[targetField] = []
    }

    // Initialize summaries array if needed
    if (!Array.isArray(parentModal.childSummaries[targetField])) {
      parentModal.childSummaries[targetField] = []
    }

    if (typeof context.listIndex === 'number') {
      parentModal.formData[targetField][context.listIndex] = childData
      parentModal.childSummaries[targetField][context.listIndex] = summary
    } else {
      parentModal.formData[targetField].push(childData)
      parentModal.childSummaries[targetField].push(summary)
    }
    return
  }

  // For object type child fields, set to {} to allow submission of required empty child nodes
  if (typeof childData === 'object' && !Array.isArray(childData) && childData !== null && Object.keys(childData).length === 0) {
    parentModal.formData[targetField] = {}
    parentModal.childSummaries[targetField] = ''
  } else {
    parentModal.formData[targetField] = childData
    parentModal.childSummaries[targetField] = summary
  }
}

const resolveWorkflowFilename = () => {
  if (!modalStack.length) {
    return ''
  }

  const rootModal = modalStack.find(entry => !entry.parentContext) || modalStack[0]
  if (!rootModal?.formData) {
    return ''
  }

  const rawIdValue = rootModal.formData.id
  if (rawIdValue === undefined || rawIdValue === null) {
    return ''
  }

  const trimmedId = String(rawIdValue).trim()
  if (!trimmedId) {
    return ''
  }

  if (trimmedId.endsWith('.yaml') || trimmedId.endsWith('.yml')) {
    return trimmedId
  }

  return `${trimmedId}.yaml`
}

const resolveTargetFilename = () => {
  if (props.workflowName) {
    return normalizeWorkflowFilename(props.workflowName)
  }
  if (baseYamlFilename.value) {
    return baseYamlFilename.value
  }
  return resolveWorkflowFilename()
}

const saveWorkflowYaml = (filename, yamlString) => {
  if (props.workflowName) {
    return updateYaml(filename, yamlString)
  }
  return postYaml(filename, yamlString)
}

const getUpperBreadcrumbsField = (modal) => {
  const crumbs = Array.isArray(modal?.breadcrumbs) ? modal.breadcrumbs : []
  if (!crumbs.length) {
    return null
  }
  const last = crumbs[crumbs.length - 1] || {}
  return last.field || null
}

const normalizeIdValue = (value) => {
  if (value === undefined || value === null) {
    return ''
  }
  return String(value).trim()
}

const resolveNodeIdForDeletion = (modal) => {
  const initialId = normalizeIdValue(props.initialFormData?.id)
  if (initialId) {
    return initialId
  }
  return normalizeIdValue(modal?.formData?.id)
}

// Removes related edges, start, end
const removeNodeRelatedYamlInfo = (yamlObject, nodeId) => {
  if (!nodeId || !yamlObject?.graph) {
    return
  }
  const edges = yamlObject.graph.edges
  if (!Array.isArray(edges)) {
    return
  }
  yamlObject.graph.edges = edges.filter(edge => edge?.from !== nodeId && edge?.to !== nodeId)
  
  // Remove node ID from graph.start/end
  if (Array.isArray(yamlObject.graph.start)) {
    yamlObject.graph.start = yamlObject.graph.start.filter(id => id !== nodeId)
  }
  if (Array.isArray(yamlObject.graph.end)) {
    yamlObject.graph.end = yamlObject.graph.end.filter(id => id !== nodeId)
  }
}

// Enhance validation to include inline children
const validateModalFormEnhanced = (modal) => {
  if (!validateModalForm(modal)) {
    return false
  }
  
  // Recursively validate inline children
  if (modal.inlineChildModals) {
    for (const key in modal.inlineChildModals) {
      const childModal = modal.inlineChildModals[key]
      if (!validateModalFormEnhanced(childModal)) {
         // Propagate error up if possible, or just return false.
         // Since UI shows error in the modal header, the child modal error needs to be shown?
         // Inline modal has its own error display capabilities? 
         // Actually `DynamicFormField` doesn't render headers. 
         // We might need to bubble the error to the parent.
         modal.formError = `Error in ${key}: ${childModal.formError || 'Invalid configuration'}`
         return false
      }
    }
  }
  return true
}

const isNodeOrEdgeModal = (modal) => {
  if (!modal || modal.parentContext) {
    return false
  }
  const field = getUpperBreadcrumbsField(modal)
  return field === 'nodes' || field === 'edges'
}

const showDeleteButton = (modal) => {
  if (!isNodeOrEdgeModal(modal)) {
    return false
  }
  // Only show delete when opened via initialFormData (editing existing nodes/edges)
  return props.initialFormData !== null && props.initialFormData !== undefined
}

const showCopyButton = (modal) => {
  if (!isNodeModal(modal)) {
    return false
  }
  // Prevent showing when creating node
  return props.initialFormData !== null && props.initialFormData !== undefined
}

const deleteButtonLabel = (modal) => {
  const field = getUpperBreadcrumbsField(modal)
  if (field === 'nodes') {
    return 'Delete Node'
  }
  if (field === 'edges') {
    return 'Delete Edge'
  }
  return 'Delete'
}

const isNodeModal = (modal) => {
  if (!modal || modal.parentContext) {
    return false
  }
  return getUpperBreadcrumbsField(modal) === 'nodes'
}

const getNodeIdChangeInfo = (modal, payload) => {
  if (!isNodeModal(modal)) {
    return null
  }
  const originalId = normalizeIdValue(modal?.initialData?.id)
  if (!originalId) {
    return null
  }
  const nextId = normalizeIdValue(payload?.id)
  if (!nextId || nextId === originalId) {
    return null
  }
  return {
    oldId: originalId,
    newId: nextId
  }
}

const applyNodeIdChangeToGraph = (yamlObject, oldId, newId) => {
  // Update edges
  if (!yamlObject?.graph?.edges || !Array.isArray(yamlObject.graph.edges)) {
    return
  }
  yamlObject.graph.edges.forEach(edge => {
    if (!edge) {
      return
    }
    if (edge.from === oldId) {
      edge.from = newId
    }
    if (edge.to === oldId) {
      edge.to = newId
    }
  })

  // Update start array
  if (Array.isArray(yamlObject.graph.start)) {
    yamlObject.graph.start = yamlObject.graph.start.map(id => id === oldId ? newId : id)
  }

  // Update end array
  if (Array.isArray(yamlObject.graph.end)) {
    yamlObject.graph.end = yamlObject.graph.end.map(id => id === oldId ? newId : id)
  }
}

const deleteEntry = async (modalId) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  if (!isNodeOrEdgeModal(modal)) {
    return
  }
  
  // Ask for user confirmation before deleting node/edge
  const collectionField = getUpperBreadcrumbsField(modal)
  const entityLabel = collectionField === 'nodes' ? 'node' : collectionField === 'edges' ? 'edge' : 'entry'
  const confirmed = window.confirm(`Are you sure you want to delete this ${entityLabel}?`)
  if (!confirmed) {
    return
  }

  modal.submitting = true
  modal.formError = null

  try {
    if (props.workflowName) {
      const ready = await ensureBaseYamlReady()
      if (!ready || !baseYamlObject.value) {
        modal.formError = baseYamlError.value || 'Failed to load existing workflow YAML'
        return
      }
    }

    // filename without the .yaml suffix
    const filename = resolveTargetFilename()
    if (!filename) {
      modal.formError = 'Graph ID is required to save workflow'
      return
    }

    const yamlObjectToSave = baseYamlObject.value
      ? cloneStructuredValue(baseYamlObject.value)
      : null

    if (!yamlObjectToSave) {
      modal.formError = 'No workflow context available for deletion'
      return
    }

    if (collectionField === 'nodes') {
      const targetNodeId = resolveNodeIdForDeletion(modal)
      if (!targetNodeId) {
        modal.formError = 'Node ID is required for deletion'
        return
      }
      removeNodeRelatedYamlInfo(yamlObjectToSave, targetNodeId)
    }

    const yamlString = yaml.dump(yamlObjectToSave ?? null, yamlDumpOptions)

    console.log('Full YAML after deletion:', yamlString)

    const result = await saveWorkflowYaml(filename, yamlString)
    if (!result.success) {
      modal.formError = result.detail || result.message || 'Failed to save workflow'
      return
    }

    baseYamlObject.value = cloneStructuredValue(yamlObjectToSave)
    baseYamlString.value = yamlString
    baseYamlFilename.value = filename

    emit('submit', {
      yaml: yamlString,
      structuredData: null,
      rawFormData: null,
      fullYaml: yamlObjectToSave
    })

    closeModal(modalId)
  } catch (error) {
    console.error('Error deleting entry:', error)
    modal.formError = 'Failed to delete entry'
  } finally {
    modal.submitting = false
  }
}

const copyNode = (modalId) => {
  const modal = findModalById(modalId)
  if (!modal || !isNodeModal(modal)) {
    return
  }

  const copiedData = sanitizeFormData(modal.formData)
  
  // Clear id field
  if (copiedData && typeof copiedData === 'object') {
    copiedData.id = ''
  }

  emit('copy', { initialFormData: copiedData })

  // Closes original modal
  closeModal(modalId)
}

const submitForm = async (modalId) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }

  if (!validateModalFormEnhanced(modal)) {
    return
  }

  const payload = sanitizeFormData(modal.formData)

  // Uncomment to skip process if no changes made to the form
  // if (!hasModalChanges(modal, payload)) {
  //   closeModal(modalId)
  //   return
  // }

  modal.submitting = true
  modal.formError = null
  try {
    // Note down node ID change if present
    const nodeIdChangeInfo = getNodeIdChangeInfo(modal, payload)

    if (modal.parentContext) {
      applyChildResult(modal.parentContext, payload, modal)
      closeModal(modalId)
      return
    }

    // Generate partial, updated YAML from form
    const { structuredData } = buildPartialYamlPayload(modal, payload)

    if (!structuredData) {
      modal.formError = 'Failed to generate YAML output'
      return
    }

    // Obtain full, original YAML from API
    if (props.workflowName) {
      const ready = await ensureBaseYamlReady()
      if (!ready || !baseYamlObject.value) {
        modal.formError = baseYamlError.value || 'Failed to load existing workflow YAML'
        return
      }
    }

    const filename = resolveTargetFilename()
    if (!filename) {
      modal.formError = 'Graph ID is required to save workflow'
      return
    }

    const baseYamlClone = baseYamlObject.value
      ? cloneStructuredValue(baseYamlObject.value)
      : null

    // Apply node ID change to full YAML if present
    if (baseYamlClone && nodeIdChangeInfo) {
      applyNodeIdChangeToGraph(baseYamlClone, nodeIdChangeInfo.oldId, nodeIdChangeInfo.newId)
    }

    // Merge partial YAML with full YAML
    const mergedYamlObject = baseYamlClone
      ? mergeYamlStructures(baseYamlClone, structuredData)
      : structuredData

    const yamlString = yaml.dump(mergedYamlObject ?? null, yamlDumpOptions)

    console.log('Full YAML:\n', yamlString)

    // Save updated, full YAML through API
    const result = await saveWorkflowYaml(filename, yamlString)
    if (!result.success) {
      modal.formError = result.detail || result.message || 'Failed to save workflow'
      return
    }

    console.log('Saved successfully')

    baseYamlObject.value = cloneStructuredValue(mergedYamlObject)
    baseYamlString.value = yamlString
    baseYamlFilename.value = filename

    emit('submit', {
      yaml: yamlString,
      structuredData,
      rawFormData: payload,
      fullYaml: mergedYamlObject
    })
    closeModal(modalId)
  } catch (error) {
    console.error('Error submitting form:', error)
    modal.formError = 'Failed to submit form, error:\n' + error
  } finally {
    modal.submitting = false
  }
}

// Press Enter to submit topmost modal, Esc to close
const handleKeystrokes = (event) => {
  if (event.key === 'Enter') {
    // Do not intercept Enter inside textarea to allow newlines
    const activeEl = document.activeElement
    if (activeEl && activeEl.tagName === 'TEXTAREA') {
      return
    }

    // Variables and list items are always top modal if exists so close them first
    if (showVarModal.value) {
      event.preventDefault()
      confirmVar()
      return
    }
    if (showListItemModal.value) {
      event.preventDefault()
      confirmListItem()
      return
    }

    const topModal = modalStack[modalStack.length - 1]
    if (!topModal || topModal.submitting) {
      return
    }

    event.preventDefault()
    submitForm(topModal.id)
  } else if (event.key === 'Escape' || event.key === 'Esc') {
    if (showVarModal.value) {
      event.preventDefault()
      closeVarModal()
      return
    }
    if (showListItemModal.value) {
      event.preventDefault()
      closeListItemModal()
      return
    }

    const topModal = modalStack[modalStack.length - 1]
    if (!topModal) {
      return
    }

    event.preventDefault()
    closeModal(topModal.id)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeystrokes)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeystrokes)
})



const describeChildEntry = (entry, field, index) => {
  if (entry && typeof entry === 'object') {
    if (entry.id) {
      return entry.id
    }
    if (entry.name) {
      return entry.name
    }
    if (entry.type) {
      return entry.type
    }
  }
  return `${field.childNode} #${index + 1}`
}

const openChildModal = async (modalId, field, listIndex = null) => {
  const parentModal = findModalById(modalId)
  if (!parentModal) {
    return
  }

  const baseBreadcrumbs = parentModal.breadcrumbs
    ? parentModal.breadcrumbs.map(crumb => ({ ...crumb }))
    : []

  const nextBreadcrumbs = [
    ...baseBreadcrumbs,
    { node: parentModal.schema.node, field: field.name }
  ]

  const context = {
    parentModalId: modalId,
    parentFieldName: field.name,
    isList: isListField(field)
  }

  if (typeof listIndex === 'number') {
    context.listIndex = listIndex
  }

  let initialData = null
  if (context.isList) {
    const existingList = parentModal.formData[field.name] || []
    if (typeof listIndex === 'number' && existingList[listIndex]) {
      initialData = existingList[listIndex]
    }
  } else if (parentModal.formData[field.name]) {
    initialData = parentModal.formData[field.name]
  }

  try {
    await generateForm(nextBreadcrumbs, true, context, initialData)
  } catch (error) {
    parentModal.formError = 'Failed to load child schema, error:\n' + error
  }
}

const openConditionalChildModal = async (modalId, field) => {
  const parentModal = findModalById(modalId)
  if (!parentModal) {
    return
  }

  const activeRoute = getActiveChildRoute(parentModal, field)
  if (!activeRoute) {
    return
  }

  const baseBreadcrumbs = parentModal.breadcrumbs
    ? parentModal.breadcrumbs.map(crumb => ({ ...crumb }))
    : []

  const crumb = {
    node: parentModal.schema.node,
    field: field.name
  }

  if (activeRoute.childKey && Object.prototype.hasOwnProperty.call(activeRoute.childKey, 'value')) {
    crumb.value = activeRoute.childKey.value
  }

  const nextBreadcrumbs = [...baseBreadcrumbs, crumb]

  const context = {
    parentModalId: modalId,
    parentFieldName: field.name,
    isList: isListField(field)
  }

  let initialData = null
  if (isListField(field)) {
    const existingList = parentModal.formData[field.name] || []
    initialData = Array.isArray(existingList) ? existingList : []
  } else if (parentModal.formData[field.name]) {
    initialData = parentModal.formData[field.name]
  }

  try {
    await generateForm(nextBreadcrumbs, true, context, initialData)
  } catch (error) {
    parentModal.formError = 'Failed to load child schema, error:\n' + error
  }
}

const deleteChildEntry = (modalId, fieldName, index) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  if (!Array.isArray(modal.formData[fieldName])) {
    return
  }
  modal.formData[fieldName].splice(index, 1)
  // Remove corresponding summary
  if (Array.isArray(modal.childSummaries[fieldName])) {
    modal.childSummaries[fieldName].splice(index, 1)
  }
}

const clearChildEntry = (modalId, fieldName) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  const current = modal.formData[fieldName]
  if (Array.isArray(current)) {
    modal.formData[fieldName] = []
    modal.childSummaries[fieldName] = []
  } else {
    modal.formData[fieldName] = null
    modal.childSummaries[fieldName] = ''
  }
}

const handleEnumChange = async (modalId, field) => {
  if (field.name !== 'type') {
    return
  }
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }

  const schemaFields = getSchemaFields(modal)
  schemaFields.forEach(schemaField => {
    if (!hasChildRoutes(schemaField)) {
      return
    }
    if (isListField(schemaField)) {
      modal.formData[schemaField.name] = []
    } else {
      modal.formData[schemaField.name] = null
    }
  })
  
  // Update inline modals after clearing data
  await updateInlineChildModals(modal)
}

// Variable functions for dict[str, Any] fields
const openVarModal = (modalId, fieldName) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  const currentValue = modal.formData[fieldName]
  if (!currentValue || typeof currentValue !== 'object' || Array.isArray(currentValue)) {
    modal.formData[fieldName] = {}
  }
  activeVarModalId.value = modalId
  activeVarFieldName.value = fieldName
  editingVarIndex.value = null
  resetVarForm()
  showVarModal.value = true
  varFormError.value = null
}

const closeVarModal = () => {
  showVarModal.value = false
  editingVarIndex.value = null
  activeVarModalId.value = null
  activeVarFieldName.value = null
  resetVarForm()
  varFormError.value = null
}

const resetVarForm = () => {
  varForm.key = ''
  varForm.value = ''
}

const editVar = (modalId, fieldName, key) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  const dict = modal.formData[fieldName]
  if (!dict || typeof dict !== 'object' || Array.isArray(dict)) {
    return
  }
  if (!Object.prototype.hasOwnProperty.call(dict, key)) {
    return
  }
  activeVarModalId.value = modalId
  activeVarFieldName.value = fieldName
  editingVarIndex.value = key
  varForm.key = key || ''
  varForm.value = dict[key] != null ? String(dict[key]) : ''
  showVarModal.value = true
  varFormError.value = null
}

const validateVarForm = (modal) => {
  if (!varForm.key.trim()) {
    varFormError.value = 'Key is required'
    return false
  }
  if (!varForm.value.trim()) {
    varFormError.value = 'Value is required'
    return false
  }

  const fieldName = activeVarFieldName.value
  if (!fieldName) {
    varFormError.value = 'Invalid field context'
    return false
  }

  const currentValue = modal.formData[fieldName]
  if (!currentValue || typeof currentValue !== 'object' || Array.isArray(currentValue)) {
    modal.formData[fieldName] = {}
  }

  const trimmedKey = varForm.key.trim()
  if (
    Object.prototype.hasOwnProperty.call(modal.formData[fieldName], trimmedKey) &&
    editingVarIndex.value !== trimmedKey
  ) {
    varFormError.value = 'Key already exists'
    return false
  }

  return true
}

const confirmVar = () => {
  varFormError.value = null
  const modal = findModalById(activeVarModalId.value)
  const fieldName = activeVarFieldName.value
  if (!modal || !fieldName) {
    return
  }

  if (!validateVarForm(modal)) {
    return
  }

  const dict = modal.formData[fieldName]
  const newKey = varForm.key.trim()
  const newValue = varForm.value.trim()

  if (editingVarIndex.value !== null) {
    const originalKey = editingVarIndex.value
    if (originalKey !== newKey && Object.prototype.hasOwnProperty.call(dict, originalKey)) {
      delete dict[originalKey]
    }
  }

  dict[newKey] = newValue

  closeVarModal()
}

const deleteVar = (modalId, fieldName, key) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  const dict = modal.formData[fieldName]
  if (!dict || typeof dict !== 'object' || Array.isArray(dict)) {
    return
  }
  if (Object.prototype.hasOwnProperty.call(dict, key)) {
    delete dict[key]
  }
}

// List item functions
const openListItemModal = (modalId, fieldName) => {
  const modal = findModalById(modalId)
  if (!modal) {
    return
  }
  if (!Array.isArray(modal.formData[fieldName])) {
    modal.formData[fieldName] = []
  }
  currentListContext.modalId = modalId
  currentListContext.fieldName = fieldName
  editingListItemIndex.value = null
  resetListItemForm()
  showListItemModal.value = true
  listItemFormError.value = null
}

const closeListItemModal = () => {
  showListItemModal.value = false
  editingListItemIndex.value = null
  currentListContext.modalId = null
  currentListContext.fieldName = ''
  resetListItemForm()
  listItemFormError.value = null
}

const resetListItemForm = () => {
  listItemForm.value = ''
}

const validateListItemForm = () => {
  if (!listItemForm.value.trim()) {
    listItemFormError.value = 'Value is required'
    return false
  }
  return true
}

const confirmListItem = () => {
  listItemFormError.value = null
  const modal = findModalById(currentListContext.modalId)
  if (!modal) {
    return
  }

  if (!validateListItemForm()) {
    return
  }

  const itemValue = listItemForm.value.trim()

  if (editingListItemIndex.value !== null) {
    modal.formData[currentListContext.fieldName][editingListItemIndex.value] = itemValue
  } else {
    modal.formData[currentListContext.fieldName].push(itemValue)
  }

  closeListItemModal()
}

const deleteListItem = (modalId, fieldName, index) => {
  const modal = findModalById(modalId)
  if (!modal || !Array.isArray(modal.formData[fieldName])) {
    return
  }
  modal.formData[fieldName].splice(index, 1)
}

defineExpose({
  generateForm
})
</script>

<style scoped>
/* Backdrop to match other views */
.modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at top, rgba(160, 196, 255, 0.18), transparent 55%),
    radial-gradient(circle at bottom, rgba(153, 234, 249, 0.25), transparent 55%),
    rgba(0, 0, 0, 0.6);
  z-index: 1000;
  font-family: 'Inter', sans-serif;
}

.modal-overlay-elevated {
  z-index: 3000;
}

/* Core modal container – glassmorphism similar to WorkflowList / Launch / WorkflowView */
.modal-content {
  display: flex;
  flex-direction: column;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  background-color: rgba(33, 33, 33, 0.92);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
  overflow: visible;
  backdrop-filter: blur(10px);
}

.modal-header {
  flex-shrink: 0;
  height: 12px;
  display: flex;
  align-items: center;
  padding: 8px 8px;
  background-color: transparent;
  border-bottom: none;
}

.modal-body {
  flex: 1;
  padding: 15px 20px 30px 15px;
  max-height: none;
  overflow-y: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  scrollbar-width: none;
}

.modal-body::-webkit-scrollbar { display: none; }

.close-button {
  margin-left: auto;
  background: transparent;
  border: none;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: color 0.2s ease, transform 0.15s ease;
  padding: 14px 14px;
}

.close-button:hover {
  color: #ffffff;
  transform: scale(1.05);
}

.submit-error {
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 8px;
  background-color: rgba(255, 68, 68, 0.12);
  border: 1px solid rgba(255, 68, 68, 0.6);
  border-radius: 10px;
  color: #ff8888;
  font-size: 13px;
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
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Courier New', monospace;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background-color: rgba(10, 10, 10, 0.6);
  color: #f2f2f2;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background-color: rgba(10, 10, 10, 0.6);
  color: #f2f2f2;
  font-size: 14px;
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

.submit-button-container {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin: 12px 20px 12px;
}

/* Gradient primary button similar to LaunchView */
.submit-button {
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  background: linear-gradient(135deg, #aaffcd, #99eaf9, #a0c4ff);
  background-size: 200% 100%;
  animation: gradientShift 4s ease-in-out infinite;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.submit-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.35);
}

.submit-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.delete-button {
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(135deg, #e07152, #dc5d4c, #bd4a4a);
  background-size: 200% 100%;
  color: #1a1a1a;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  animation: gradientShift 4s ease-in-out infinite;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.delete-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.35);
}

.delete-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

/* Variables styles */
.vars-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
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

.advanced-toggle {
  margin: 12px 0 12px;
  text-align: right;
}

.advanced-toggle-button {
  background: transparent;
  border: none;
  color: #a0c4ff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: color 0.2s ease;
}

.advanced-toggle-button:hover {
  color: #b9d0ff;
}

.advanced-toggle-arrow {
  font-size: 11px;
}

/* Modal variants for VAR & list dialogs */
.var-modal,
.list-item-modal {
  max-width: 520px;
}

.modal-title {
  color: #f2f2f2;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
  margin-bottom: 12px;
}

.cancel-button,
.confirm-button {
  padding: 8px 20px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: background-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
}

.cancel-button {
  background-color: rgba(90, 90, 90, 0.9);
  color: #f2f2f2;
}

.cancel-button:hover {
  background-color: rgba(110, 110, 110, 0.95);
}

.confirm-button {
  background: linear-gradient(135deg, #aaffcd, #99eaf9, #a0c4ff);
  color: #1a1a1a;
}

.confirm-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.35);
}

@keyframes gradientShift {
  0%,
  100% {
    background-position: 0% 0%;
  }
  50% {
    background-position: 100% 0%;
  }
}
.inline-config-section {
  margin-top: 12px;
  margin-bottom: 24px;
  margin-left: 4px; /* Slight indent */
}

.inline-separator {
  height: 3px;
  background-color: rgba(255, 255, 255, 0.3);
  margin-bottom: 16px;
  width: 100%;
}
</style>
