<template>
  <div class="launch-view">
    <div class="launch-bg"></div>
    <div class="header">
      <h1>Labaratory</h1>
      <button class="settings-button" @click="showBatchSettingsModal()" title="Batch Settings">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
    </div>
    <div class="content">
      <!-- Left panel -->
      <div class="left-panel">
        <!-- Log area -->
        <div v-if="viewMode === 'terminal'" class="log-box">
          <div class="log-messages" ref="logMessagesRef">
            <div v-for="(logMessage, index) in logMessages" :key="index" class="log-message">
              <span :class="`log-timestamp log-timestamp-${logMessage.type}`">{{ logMessage.timestamp }}</span> : {{ logMessage.message }}
            </div>
            <div v-if="logMessages.length === 0" class="log-placeholder">
              Batch processing logs will appear here...
            </div>
          </div>
        </div>

        <!-- Dashboard area -->
        <div v-if="viewMode === 'dashboard'" class="dashboard-box">
          <div class="dashboard-content">
            <!-- Metrics Grid -->
            <div class="metrics-grid">
              <div class="metric-card" :class="{ 'status-active': status === 'In Progress' }">
                <div class="metric-title">Rows Completed</div>
                <div class="metric-value">{{ completedRows }}</div>
              </div>
              <div class="metric-card" :class="{ 'status-active': status === 'In Progress' }">
                <div class="metric-title">Total Time</div>
                <div class="metric-value">{{ totalTime }}</div>
              </div>
              <div class="metric-card" :class="{ 'status-active': status === 'In Progress' }">
                <div class="metric-title">Success Rate</div>
                <div class="metric-value">{{ successRate }}</div>
              </div>
              <div class="metric-card" :class="{ 'status-active': status === 'In Progress' }">
                <div class="metric-title">Current Status</div>
                <div class="metric-value" :class="{ 'status-active': status === 'In Progress' }">{{ computedStatus }}</div>
              </div>
            </div>

            <!-- Progress Bar -->
            <div class="progress-section">
              <div class="progress-label">Overall Progress</div>
              <div class="progress-bar" :style="{ '--process-width': progressPercentage + '%'}">
                <div class="progress-fill" :class="{ 'processing': status === 'In Progress' }" :style="{ width: progressPercentage + '%' }"></div>
              </div>
              <div class="progress-text">{{ progressPercentage }}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right panel -->
      <div class="right-panel">
        <div class="control-section">
          <label class="section-label">Workflow Selection</label>
      <div
        class="select-wrapper custom-file-selector"
        ref="fileSelectorWrapperRef"
      >
        <input
          ref="fileSelectorInputRef"
          v-model="fileSearchQuery"
          type="text"
          class="file-selector-input"
          :placeholder="loading ? 'Loading...' : 'Select YAML file...'"
          :disabled="loading || isWorkflowRunning"
          @focus="handleFileInputFocus"
          @input="handleFileInputChange"
          @keydown.enter.prevent="handleFileInputEnter"
          @blur="handleFileInputBlur"
        />
        <div class="select-arrow">▼</div>
        <Transition name="file-dropdown">
          <ul
            v-if="isFileDropdownOpen"
            class="file-dropdown"
          >
            <li
              v-for="workflow in filteredWorkflowFiles"
              :key="workflow.name"
              class="file-option"
              @mousedown.prevent="selectWorkflow(workflow.name)"
            >
              <span class="file-name">{{ workflow.name }}</span>
              <span
                v-if="workflow.description"
                class="file-desc"
              >
                {{ workflow.description }}
              </span>
            </li>
            <li
              v-if="!filteredWorkflowFiles.length"
              class="file-empty"
            >
              No results
            </li>
          </ul>
        </Transition>
      </div>

          <label class="section-label">Input File Selection</label>
          <div class="input-file-section">
            <div class="file-upload-wrapper">
              <input
                ref="inputFileInputRef"
                type="file"
                accept=".xlsx,.csv"
                class="hidden-file-input"
                @change="onInputFileSelected"
              />
              <button
                type="button"
                class="file-upload-button"
                :disabled="loading || isWorkflowRunning"
                @click="handleInputFileButtonClick"
              >
                {{ selectedInputFile ? selectedInputFile.name : 'Select input file...' }}
              </button>
            </div>
          </div>

          <div class="input-manual">
            <div class="manual-title" @click="showColumnGuideModal = true">
              Input File Format
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="info-icon">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <path d="M12 17h.01"></path>
              </svg>
            </div>
          </div>

          <label class="section-label">View</label>
          <div class="view-toggle">
            <button
              class="toggle-button"
              :class="{ active: viewMode === 'dashboard' }"
              @click="switchToDashboard"
            >
              Dashboard
            </button>
            <button
              class="toggle-button"
              :class="{ active: viewMode === 'terminal' }"
              @click="viewMode = 'terminal'"
            >
              Terminal
            </button>
          </div>



          <!-- Button area -->
          <div class="button-section">
            <button
              class="launch-button"
              :class="{ glow: shouldGlow, 'is-sending': isWorkflowRunning }"
              @click="handleButtonClick"
              :disabled="isLaunchButtonDisabled">
              {{ buttonLabel }}
            </button>

            <button
              class="cancel-button"
              :disabled="status !== 'In Progress'"
              @click="cancelBatchWorkflow"
            >
              Cancel
            </button>

            <button
              class="download-button"
              :disabled="status !== 'Batch completed' && status !== 'Batch cancelled'"
              @click="downloadLogs"
            >
              Download Logs
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <Transition name="image-modal">
    <div
      v-if="selectedArtifactImage"
      class="image-modal"
      @click.self="closeImageModal"
    >
      <div class="image-modal-content">
        <img
          :src="selectedArtifactImage.src"
          :alt="selectedArtifactImage.name"
          :click="closeImageModal"
        />
      </div>
    </div>
  </Transition>

  <SettingsModal
    :is-visible="showSettingsModal"
    @update:is-visible="showSettingsModal = $event"
  />

  <!-- Column Guide Modal -->
  <Transition name="modal">
    <div
      v-if="showColumnGuideModal"
      class="column-guide-modal-overlay"
      @click.self="showColumnGuideModal = false"
    >
      <div class="column-guide-modal">
        <div class="modal-content">
          <div class="manual-content">
            <div class="manual-item">
              Input file should contain at least <code>task</code> and/or <code>attachments</code> columns
            </div>
            <div class="manual-item">
              <code>id</code> - Must be unique, auto-generated if column not found
            </div>
            <div class="manual-item">
              <code>task</code> - Holds user input
            </div>
            <div class="manual-item">
              <code>vars</code> - JSON object containing key-value pairs of global variables
              <div class="manual-example">
                <pre>{{
JSON.stringify({"BASE_URL": "openai.com","API_KEY": "123"}, null, 2)
}}</pre>
              </div>
            </div>
            <div class="manual-item">
              <code>attachments</code> - JSON array containing absolute file paths of attachments for workflow
              <div class="manual-example">
                <pre>{{
JSON.stringify(["C:\\a_sheep.png"], null, 2)
}}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Batch Settings Modal -->
  <Transition name="modal">
    <div
      v-if="isBatchSettingsModalVisible"
      class="batch-settings-modal-overlay"
      @click.self="isBatchSettingsModalVisible = false"
    >
      <div class="batch-settings-modal">
        <div class="modal-content">
          <div class="modal-header">
            <h3>Batch Settings</h3>
            <button class="close-button" @click="isBatchSettingsModalVisible = false">×</button>
          </div>
          <div class="modal-body">
            <div class="settings-item">
              <label class="setting-label">Max. Parallel Launches</label>
              <input
                type="number"
                v-model.number="maxParallel"
                class="setting-input"
                min="1"
                max="50"
                step="1"
              />
              <p class="setting-desc">Maximum number of parallel workflow launches</p>
            </div>
            <div class="settings-item">
              <label class="setting-label">Log Level</label>
              <select v-model="logLevel" class="setting-select">
                <option v-for="level in logLevelOptions" :key="level" :value="level">
                  {{ level }}
                </option>
              </select>
              <p class="setting-desc">Logging verbosity level</p>
            </div>
          </div>
          <div class="modal-footer">
            <button class="cancel-button" @click="isBatchSettingsModalVisible = false">Cancel</button>
            <button class="confirm-button" @click="isBatchSettingsModalVisible = false">Save</button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { fetchWorkflowsWithDesc, fetchLogsZip, fetchWorkflowYAML, postFile, getAttachment, fetchVueGraph, postBatchWorkflow } from '../utils/apiFunctions.js'
import { configStore } from '../utils/configStore.js'
import { spriteFetcher } from '../utils/spriteFetcher.js'
import yaml from 'js-yaml'
import MarkdownIt from 'markdown-it'
import SettingsModal from '../components/SettingsModal.vue'
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true
})

const renderMarkdown = (text) => {
  return md.render(text || '')
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-GB', { hour12: false }) // HH:mm:ss
}

const formatLogTimestamp = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  const milliseconds = String(date.getMilliseconds()).padStart(3, '0')
  return `${month}/${day} - ${hours}:${minutes}:${seconds}.${milliseconds}`
}
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import '../utils/vueflow.css'
import WorkflowNode from '../components/WorkflowNode.vue'
import WorkflowEdge from '../components/WorkflowEdge.vue'
import StartNode from '../components/StartNode.vue'
import CollapsibleMessage from '../components/CollapsibleMessage.vue'

const router = useRouter()
const route = useRoute()

// Log box state
const logMessages = ref([])
const logMessagesRef = ref(null)

// Log message types
const LOG_TYPES = {
  COMPLETED: 'completed',
  FAILED: 'failed',
  DEFAULT: 'default'
}

// Task input state
const taskPrompt = ref('')

// File selector state
const workflowFiles = ref([])
const selectedYamlFile = ref('')
const fileSearchQuery = ref('')
const isFileSearchDirty = ref(false)
const isFileDropdownOpen = ref(false)
const fileSelectorWrapperRef = ref(null)
const fileSelectorInputRef = ref(null)

// Status state
const status = ref('Idle')
const loading = ref(false)

// Computed status from workflow and input file selection
const computedStatus = computed(() => {
  if (loading.value) return 'Loading...'
  if (status.value === 'Pending workflow selection') return status.value
  if (!selectedYamlFile.value) return 'Pending workflow selection'
  if (!selectedInputFile.value) return 'Pending file selection'
  return status.value
})

// Session ID for downloads
let sessionIdToDownload = null

// Input glow state
const shouldGlow = ref(false)
const taskInputRef = ref(null)
const attachmentInputRef = ref(null)
const uploadedAttachments = ref([])
const isDragActive = ref(false)
const showAttachmentPopover = ref(false)
const isUploadingAttachment = ref(false)
let attachmentHoverTimeout = null
const selectedArtifactImage = ref(null)
let dragDepth = 0

// Input file selection state
const selectedInputFile = ref(null)
const inputFileInputRef = ref(null)

// Recording state
const isRecording = ref(false)
let mediaRecorder = null
let audioChunks = []
let audioStream = null

// WebSocket readiness state
const isConnectionReady = ref(false)
const showSettingsModal = ref(false)
const isBatchSettingsModalVisible = ref(false)
const showColumnGuideModal = ref(false)

// Batch settings
const maxParallel = ref(5)
const logLevel = ref('INFO')
const logLevelOptions = ['INFO', 'DEBUG', 'WARNING', 'ERROR', 'CRITICAL']

// View mode
const viewMode = ref('dashboard')

// Dashboard metrics
const totalRowsCount = ref(0)
const completedRowsCount = ref(0)
const successfulTasks = ref(0)
const failedTasks = ref(0)
const batchStartTime = ref(null)
const batchEndTime = ref(null)

// Timer update interval
let timerInterval = null
const currentTime = ref(Date.now())

// Timer functions
const startTimer = () => {
  if (timerInterval) return
  timerInterval = setInterval(() => {
    currentTime.value = Date.now()
  }, 10) // Update every 10ms
}

const stopTimer = () => {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

const completedRows = computed(() => {
  if (totalRowsCount.value === 0) return '-'
  return `${completedRowsCount.value}/${totalRowsCount.value}`
})

const totalTime = computed(() => {
  if (!batchStartTime.value) return '00:00:00:00'

  const endTime = batchEndTime.value || currentTime.value
  const duration = endTime - batchStartTime.value
  const hours = Math.floor(duration / (1000 * 60 * 60))
  const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((duration % (1000 * 60)) / 1000)
  const centiseconds = Math.floor((duration % 1000) / 10)

  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${centiseconds.toString().padStart(2, '0')}`
})

const successRate = computed(() => {
  const totalProcessed = successfulTasks.value + failedTasks.value
  if (totalProcessed === 0) return '0%'
  const rate = (successfulTasks.value / totalProcessed) * 100
  return `${Math.round(rate)}%`
})

const progressPercentage = computed(() => {
  if (totalRowsCount.value === 0) return 0
  return Math.round((completedRowsCount.value / totalRowsCount.value) * 100)
})

// WebSocket reference
let ws = null
let sessionId = null

const filteredWorkflowFiles = computed(() => {
  // If the file search box is untouched, return all workflows
  if (!isFileSearchDirty.value) {
    return workflowFiles.value
  }
  const query = fileSearchQuery.value.trim().toLowerCase()
  if (!query) {
    return workflowFiles.value
  }
  return workflowFiles.value.filter((workflow) =>
    workflow.name?.toLowerCase().includes(query)
  )
})

// Button label computed property
const buttonLabel = computed(() => {
  if (status.value === 'Batch completed' || status.value === 'Batch cancelled') {
    return 'Relaunch'
  }
  return 'Launch'
})

// Computed button state
const isLaunchButtonDisabled = computed(() => {
  if (loading.value) return true
  if (status.value === 'Batch completed' || status.value === 'Batch cancelled') return false
  if (!isConnectionReady.value) return true
  if (!selectedYamlFile.value || !selectedInputFile.value) return true
  return false
})

const clearUploadedAttachments = () => {
  uploadedAttachments.value = []
  showAttachmentPopover.value = false
  if (attachmentInputRef.value) {
    attachmentInputRef.value.value = ''
  }
}

// Reset the WebSocket connection and related state
const resetConnectionState = ({ closeSocket = true, clearInputFile = true } = {}) => {
  if (closeSocket && ws) {
    try {
      ws.close()
    } catch (closeError) {
      console.warn('Failed to close WebSocket:', closeError)
    }
  }

  ws = null
  sessionId = null
  isConnectionReady.value = false
  shouldGlow.value = false
  isWorkflowRunning.value = false

  // Stop the timer
  stopTimer()

  // Reset metrics
  totalRowsCount.value = 0
  completedRowsCount.value = 0
  successfulTasks.value = 0
  failedTasks.value = 0
  batchStartTime.value = null
  batchEndTime.value = null

  if (attachmentHoverTimeout) {
    clearTimeout(attachmentHoverTimeout)
    attachmentHoverTimeout = null
  }

  if (clearInputFile) {
    removeInputFile()
  }
}

// Button state management
const isWorkflowRunning = ref(false)

// Current workflow YAML content
const workflowYaml = ref({})

// const goBack = () => {
//   router.push('/workflows')
// }

const applyWorkflowFromRoute = () => {
  let workflowParam = route.query?.workflow || route.query?.file || route.query?.name
  if (Array.isArray(workflowParam)) {
    workflowParam = workflowParam[0]
  }
  if (!workflowParam || typeof workflowParam !== 'string') {
    return
  }

  let fileName = workflowParam.trim()
  if (!fileName) {
    return
  }
  if (!fileName.toLowerCase().endsWith('.yaml')) {
    fileName = `${fileName}.yaml`
  }

  selectedYamlFile.value = fileName
  fileSearchQuery.value = fileName
  isFileSearchDirty.value = false
}

// Load workflow list
const loadWorkflows = async () => {
  loading.value = true
  const result = await fetchWorkflowsWithDesc()
  loading.value = false

  if (result.success) {
    workflowFiles.value = result.workflows
    applyWorkflowFromRoute()
  } else {
    console.error('Failed to load workflows:', result.error)
  }
}

const openFileDropdown = () => {
  if (loading.value || isWorkflowRunning.value) {
    return
  }
  isFileDropdownOpen.value = true
}

const handleFileInputFocus = () => {
  isFileSearchDirty.value = false
  openFileDropdown()
  if (fileSearchQuery.value?.trim()) {
    nextTick(() => fileSelectorInputRef.value?.select())
  }
}

const handleFileInputChange = () => {
  if (loading.value || isWorkflowRunning.value) {
    return
  }
  isFileSearchDirty.value = true
  openFileDropdown()
}

const closeFileDropdown = () => {
  isFileDropdownOpen.value = false
}

const selectWorkflow = (fileName) => {
  if (!fileName) {
    return
  }
  selectedYamlFile.value = fileName
  fileSearchQuery.value = fileName
  isFileSearchDirty.value = false
  closeFileDropdown()

  // Avoid focusing on element after selection
  fileSelectorInputRef.value?.blur()

  router.push({
    query: {
      ...route.query,
      workflow: fileName
    }
  })
}

const handleFileInputEnter = () => {
  const [firstMatch] = filteredWorkflowFiles.value
  if (firstMatch) {
    selectWorkflow(firstMatch.name)
  }
}

const resetFileSearchQuery = () => {
  fileSearchQuery.value = selectedYamlFile.value || ''
  isFileSearchDirty.value = false
}

const handleFileInputBlur = () => {
  setTimeout(() => {
    if (!isFileDropdownOpen.value) {
      resetFileSearchQuery()
    }
  }, 120)
}

const handleClickOutside = (event) => {
  if (
    isFileDropdownOpen.value &&
    fileSelectorWrapperRef.value &&
    !fileSelectorWrapperRef.value.contains(event.target)
  ) {
    closeFileDropdown()
    resetFileSearchQuery()
  }
}

// Add a log entry
const addLogMessage = (message, type = LOG_TYPES.DEFAULT) => {
  const timestamp = formatLogTimestamp(Date.now())
  logMessages.value.push({
    timestamp,
    message,
    type
  })
}

const removeAttachment = (attachmentId) => {
  uploadedAttachments.value = uploadedAttachments.value.filter(
    (attachment) => attachment.attachmentId !== attachmentId
  )
}

// Input file selection methods
const handleInputFileButtonClick = () => {
  if (loading.value || isWorkflowRunning.value) {
    return
  }
  inputFileInputRef.value?.click()
}

const onInputFileSelected = (event) => {
  const file = event.target?.files?.[0]
  if (event.target) {
    event.target.value = ''
  }

  if (!file) {
    return
  }

  // Validate file type
  const allowedExtensions = ['.xlsx', '.csv']
  const fileName = file.name.toLowerCase()
  const isValidType = allowedExtensions.some(ext => fileName.endsWith(ext))

  if (!isValidType) {
    alert('Please select a valid file (.xlsx or .csv)')
    return
  }

  selectedInputFile.value = file
}

const removeInputFile = () => {
  selectedInputFile.value = null
  if (inputFileInputRef.value) {
    inputFileInputRef.value.value = ''
  }
}

const startRecording = async () => {
  if (!isConnectionReady.value || !sessionId || isUploadingAttachment.value || isRecording.value) {
    return
  }

  // Add global listeners to ensure recording stops even if mouse leaves button
  window.addEventListener('mouseup', stopRecordingGlobal)
  window.addEventListener('touchend', stopRecordingGlobal)

  try {
    // Request microphone access
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })

    // Check for MP3 support, fallback to webm
    const mimeTypes = ['audio/mpeg', 'audio/wav', 'audio/webm', 'audio/ogg']
    let selectedMimeType = 'audio/webm'

    for (const mimeType of mimeTypes) {
      if (MediaRecorder.isTypeSupported(mimeType)) {
        selectedMimeType = mimeType
        break
      }
    }

    mediaRecorder = new MediaRecorder(audioStream, {
      mimeType: selectedMimeType
    })

    audioChunks = []

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }

    mediaRecorder.onstop = async () => {
      if (audioChunks.length === 0) {
        cleanupRecording()
        return
      }

      // Create blob from audio chunks
      const audioBlob = new Blob(audioChunks, { type: selectedMimeType })

      // Generate filename with current time
      const now = new Date()
      const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, -5)
      const filename = `recording_${timestamp}.${selectedMimeType.split('/')[1]}`

      // Create File object from blob
      const audioFile = new File([audioBlob], filename, { type: selectedMimeType })

      // Upload the file
      try {
        isUploadingAttachment.value = true
        const result = await postFile(sessionId, audioFile)

        if (result?.success && result?.attachmentId) {
          console.log('Recording uploaded successfully:', result)
          uploadedAttachments.value.push(result)
        } else {
          console.error('Recording upload failed:', result)
          alert(result?.message || 'Failed to upload recording')
        }
      } catch (error) {
        console.error('Failed to upload recording:', error)
        alert('Recording upload failed, please try again.')
      } finally {
        isUploadingAttachment.value = false
        cleanupRecording()
      }
    }

    mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event.error)
      alert('Recording error occurred')
      cleanupRecording()
    }

    mediaRecorder.start()
    isRecording.value = true
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert('Failed to access microphone. Please check permissions.')
    cleanupRecording()
  }
}

const stopRecording = () => {
  if (mediaRecorder && isRecording.value && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    isRecording.value = false
  }
  removeGlobalListeners()
}

const stopRecordingGlobal = () => {
  stopRecording()
}

const removeGlobalListeners = () => {
  window.removeEventListener('mouseup', stopRecordingGlobal)
  window.removeEventListener('touchend', stopRecordingGlobal)
}

const handleMicrophoneMouseLeave = (event) => {
  // If mouse leaves while recording, don't stop (let global listener handle it)
  // This allows recording to continue if user drags outside button
}

// Cleans up stored recorded audios
const cleanupRecording = () => {
  removeGlobalListeners()
  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop())
    audioStream = null
  }
  mediaRecorder = null
  audioChunks = []
  isRecording.value = false
}

const lockBodyScroll = () => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = 'hidden'
  }
}

const unlockBodyScroll = () => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = ''
  }
}

const openImageModal = (message) => {
  if (!message || message.loading || !message.dataUri) {
    return
  }
  selectedArtifactImage.value = {
    src: message.dataUri,
    name: message.fileName || 'Artifact image'
  }
  lockBodyScroll()
}

const closeImageModal = () => {
  if (!selectedArtifactImage.value) {
    return
  }
  selectedArtifactImage.value = null
  unlockBodyScroll()
}

const handleKeydown = (event) => {
  if (event.key === 'Escape') {
    if (selectedArtifactImage.value) {
      closeImageModal()
    } else if (showColumnGuideModal.value) {
      showColumnGuideModal.value = false
    } else if (isBatchSettingsModalVisible.value) {
      isBatchSettingsModalVisible.value = false
    }
  }
}

// Show batch settings modal
const showBatchSettingsModal = () => {
  isBatchSettingsModalVisible.value = true
}

// Handle YAML file selection
const handleYAMLSelection = async (fileName) => {
  if (!fileName) {
    workflowYaml.value = {}
    logMessages.value = []
    setNodes([])
    setEdges([])
    nodeSpriteMap.value.clear()

    // Reset metrics
    totalRowsCount.value = 0
    completedRowsCount.value = 0
    successfulTasks.value = 0
    failedTasks.value = 0
    batchStartTime.value = null
    batchEndTime.value = null

    return
  }

  // Clear the log messages
  logMessages.value = []
}

// Handle button clicks
const handleButtonClick = () => {
  if (status.value === 'Batch completed' || status.value === 'Batch cancelled') {
    // If Relaunch, restart the same workflow and re-enter Launch state
    if (!selectedYamlFile.value) {
      alert('Please choose a workflow file！')
      return
    }

    if (!selectedInputFile.value) {
      alert('Please select an input file (.xlsx or .csv)')
      return
    }

    resetConnectionState()
    status.value = 'Connecting...'
    handleYAMLSelection(selectedYamlFile.value)
    establishWebSocketConnection()
  } else {
    // If Launch, start the workflow
    launchBatchWorkflow()
  }
}

// Establish a WebSocket connection
const establishWebSocketConnection = () => {
  // Reset any previous state before creating a new socket
  resetConnectionState()

  if (!selectedYamlFile.value) {
    return
  }

  const apiBase = import.meta.env.VITE_API_BASE_URL || ''
  // Defaults: same-origin (works with Vite dev proxy)
  const defaultScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  let scheme = defaultScheme
  let host = window.location.host

  // In production, prefer explicit API base if provided
  if (!import.meta.env.DEV && apiBase) {
    try {
      const api = new URL(apiBase, window.location.origin)
      scheme = api.protocol === 'https:' ? 'wss:' : 'ws:'
      host = api.host
    } catch {
      // keep defaults
    }
  }

  const wsUrl = `${scheme}//${host}/ws`
  const socket = new WebSocket(wsUrl)
  ws = socket

  // Ignore events from stale sockets
  socket.onopen = () => {
    if (ws !== socket) return
    console.log('WebSocket connected')
  }

  socket.onmessage = (event) => {
    // Ignore messages from sockets that are no longer current
    if (ws !== socket) return

    const msg = JSON.parse(event.data)

    if (msg.type === 'connection') {
      sessionId = msg.data?.session_id || null
      console.log('Connected with session: ', sessionId)

      if (!sessionId) {
        status.value = 'Connection error'
        alert('Missing session information from server.')
        resetConnectionState()
        return
      }

      isConnectionReady.value = true
      shouldGlow.value = true
      status.value = 'Pending launch'

      nextTick(() => {
        taskInputRef.value?.focus()
      })
    } else {
      processBatchMessage(msg)
    }
  }

  // Ignore errors from sockets that are no longer current
  socket.onerror = (error) => {
    if (ws !== socket) return

    console.error('WebSocket error:', error)
    status.value = 'Connection error'
    alert('WebSocket connection error!')
    resetConnectionState({ closeSocket: false })
  }

  socket.onclose = () => {
    // Ignore close events from sockets that are no longer current
    if (ws !== socket) return

    console.log('WebSocket closed')
    if (status.value === 'In Progress') {
      status.value = 'Disconnected'
    } else if (status.value === 'Connecting...' || status.value === 'Pending launch') {
      status.value = 'Disconnected'
    }
    resetConnectionState({ closeSocket: false, clearInputFile: false })
  }
}

// Watch for file selection changes
watch(selectedYamlFile, (newFile) => {
  taskPrompt.value = ''
  fileSearchQuery.value = newFile || ''
  isFileSearchDirty.value = false

  if (!newFile) {
    resetConnectionState()
    status.value = 'Pending file selection'
    handleYAMLSelection(newFile)
    return
  }

  resetConnectionState()
  status.value = 'Connecting...'
  handleYAMLSelection(newFile)
  establishWebSocketConnection()
})

watch(
  () => uploadedAttachments.value.length,
  (length) => {
    if (!length) {
      showAttachmentPopover.value = false
    }
  }
)

// When called from Launch in WorkflowView, auto pass in corresponding workflow
watch(
  () => route.query?.workflow,
  () => {
    applyWorkflowFromRoute()
  }
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  loadWorkflows()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  unlockBodyScroll()
  resetConnectionState()
  cleanupRecording()
  stopTimer()
})

// Toggle to dashboard
const switchToDashboard = async () => {
  viewMode.value = 'dashboard'
  await nextTick()
}

const launchBatchWorkflow = async () => {
  if (!selectedYamlFile.value) {
    alert('Please choose a workflow file！')
    return
  }

  if (!selectedInputFile.value) {
    alert('Please select an input file (.xlsx or .csv)')
    return
  }

  if (
    !ws ||
    !isConnectionReady.value ||
    !sessionId
  ) {
    alert('WebSocket connection is not ready yet.')
    return
  }

  shouldGlow.value = false
  status.value = 'Launching...'

  try {
    const result = await postBatchWorkflow({
      file: selectedInputFile.value,
      sessionId: sessionId,
      yamlFile: selectedYamlFile.value,
        maxParallel: maxParallel.value,
      logLevel: logLevel.value
    })

    if (result.success) {
      console.log('Batch workflow launched: ', result)
      status.value = 'In Progress'
      isWorkflowRunning.value = true
    } else {
      console.error('Failed to launch batch workflow:', result)
      status.value = 'Failed'
      alert(`Failed to launch batch workflow: ${result.detail || result.message || 'Unknown error'}`)
      shouldGlow.value = true
      if (isConnectionReady.value) {
        status.value = 'Pending launch'
      }
    }
  } catch (error) {
    console.error('Error calling batch workflow API:', error)
    status.value = 'Error'
    alert(`Failed to call batch workflow API: ${error.message}`)
    shouldGlow.value = true
    if (isConnectionReady.value) {
      status.value = 'Pending launch'
    }
  }
}

// When workflow is finished or cancelled, re-enable glow
watch(status, (newStatus) => {
  if (newStatus === 'Batch completed' || newStatus === 'Batch cancelled') {
    shouldGlow.value = true
  }
})

// Processes different types of messages
const processBatchMessage = async (msg) => {
  console.log('Batch Message: ', msg)

  // Batch completed
  if (msg.type === 'batch_completed') {
    const message = `Batch processing finished, ${msg.data.succeeded} tasks succeeded, ${msg.data.failed} tasks failed`
    addLogMessage(message, LOG_TYPES.DEFAULT)

    // Update metrics
    successfulTasks.value = msg.data.succeeded
    failedTasks.value = msg.data.failed
    completedRowsCount.value = msg.data.succeeded + msg.data.failed
    batchEndTime.value = Date.now()

    // Stop the timer
    stopTimer()

    status.value = 'Batch completed'
    isWorkflowRunning.value = false
    sessionIdToDownload = sessionId
  }

  // Handle batch processing messages
  if (msg.type === 'batch_started') {
    const message = `Batch processing started with total of ${msg.data.total} rows...`
    addLogMessage(message, LOG_TYPES.DEFAULT)

    // Initialize metrics
    totalRowsCount.value = msg.data.total
    completedRowsCount.value = 0
    successfulTasks.value = 0
    failedTasks.value = 0
    batchStartTime.value = Date.now()
    batchEndTime.value = null

    // Start the timer
    startTimer()
  }

  if (msg.type === 'batch_task_started') {
    const message = `[ID ${msg.data.task_id}, Row ${msg.data.row_index}] launched`
    addLogMessage(message, LOG_TYPES.DEFAULT)
  }

  if (msg.type === 'batch_task_completed') {
    const message = `[ID ${msg.data.task_id}, Row ${msg.data.row_index}] completed, ${msg.data.duration_ms}ms spent, total ${msg.data.token_usage.total_usage.total_tokens} tokens used`
    addLogMessage(message, LOG_TYPES.COMPLETED)

    // Update metrics
    completedRowsCount.value++
    successfulTasks.value++
  }

  if (msg.type === 'batch_task_failed') {
    const message = `[ID ${msg.data.task_id}, Row ${msg.data.row_index}] failed, Error: ${msg.data.error}`
    addLogMessage(message, LOG_TYPES.FAILED)

    // Update metrics
    completedRowsCount.value++
    failedTasks.value++
  }
}

// Cancel the currently running workflow
const cancelBatchWorkflow = () => {
  if (!isWorkflowRunning.value || !ws) {
    return
  }
  addLogMessage('Batch cancelled', LOG_TYPES.DEFAULT)

  // Finalize metrics
  batchEndTime.value = Date.now()

  // Stop the timer
  stopTimer()

  status.value = 'Batch cancelled'
  isWorkflowRunning.value = false
  sessionIdToDownload = sessionId

  try {
    ws.close()
  } catch (closeError) {
    console.warn('Failed to close WebSocket:', closeError)
  }
}

// Download logs
const downloadLogs = async () => {
  if (!sessionIdToDownload) {
    return
  }
  try {
    await fetchLogsZip(sessionIdToDownload)
  } catch (error) {
    console.error('Download failed:', error)
    alert('Download failed, please try again later')
  }
}

// Auto-scroll to bottom
watch(
  () => logMessages.value.length,
  async () => {
    await nextTick()
    if (logMessagesRef.value) {
      logMessagesRef.value.scrollTop = logMessagesRef.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.launch-view {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  color: #f2f2f2;
  font-family: 'Inter', sans-serif;
  position: relative;
  overflow: hidden;
}

.launch-bg {
  position: fixed;
  top: -150px;
  left: 0;
  right: 0;
  height: 500px;
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  filter: blur(120px);
  opacity: 0.15;
  z-index: 0;
  pointer-events: none;
}

.header {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 40px;
  background-color: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(5px);
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

.header h1 {
  margin: 0;
  color: #f2f2f2;
  font-size: 18px;
  font-weight: 600;
}

.back-button {
  padding: 8px;
  margin-right: 16px;
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  outline: none;
}

.back-button:hover {
  color: #f2f2f2;
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
  padding: 20px;
  gap: 20px;
  position: relative;
  z-index: 1;
}

/* Left Panel */
.left-panel {
  flex: 3;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0; /* Prevents overflow */
}

/* Log Box */
.log-box {
  flex: 1;
  background-color: rgba(25, 25, 25, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(5px);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

/* Dashboard Box */
.dashboard-box {
  flex: 1;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(5px);
}

.dashboard-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  color: #e7e7e7;
  display: flex;
  flex-direction: column;
  gap: 20px;
  font-size: 14px;
  line-height: 1.4;
  justify-content: space-between;
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 8px;
}

.metric-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  backdrop-filter: blur(2px);
  transition: all 0.3s ease;
}

.metric-card.status-active {
  border-color: #aaffcd;
  box-shadow: 0 0 15px rgba(153, 234, 249, 0.3);
  animation: borderPulse 4s ease-in-out infinite alternate;
}

.metric-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.metric-value {
  font-size: 16px;
  font-weight: 700;
  color: #f2f2f2;
}

/* Progress Section */
.progress-section {
  margin-top: 8px;
}

.progress-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  margin-bottom: 8px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
  position: relative;
}

.progress-fill.processing::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    rgba(255, 255, 255, 0.8) 60%,
    rgba(255, 255, 255, 0.3) 70%,
    transparent 100%
  );
  animation: wavePulse 1.8s ease-in-out infinite;
  border-radius: 4px;
}

.progress-fill {
  position: relative;
  height: 100%;
  background: linear-gradient(90deg, #aaffcd, #99eaf9, #a0c4ff);
  background-size: 200% 100%;
  animation: gradientShift 3s ease-in-out infinite;
  transition: width 0.3s ease;
  overflow: hidden;
}

.progress-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  text-align: center;
  font-weight: 500;
}

.log-messages::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.log-messages::-webkit-scrollbar-track {
  background: transparent;
}
.log-messages::-webkit-scrollbar-thumb {
  background-color: rgba(160, 160, 160, 0.28);
  border-radius: 8px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
.log-messages::-webkit-scrollbar-thumb:hover {
  background-color: rgba(160, 160, 160, 0.48);
}

.log-messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  color: #e7e7e7;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  line-height: 1.4;
}

.log-message {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-timestamp {
  font-weight: 500;
}

.log-timestamp-completed {
  color: #6bff75;
}

.log-timestamp-failed {
  color: #ff8080;
}

.log-timestamp-default {
  color: #88e4f8;
}

.log-placeholder {
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
  text-align: center;
  margin-top: 20px;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Dialogue Messages */
.dialogue {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.dialogue-right {
  flex-direction: row-reverse;
}

.message-content {
  flex: 1;
  max-width: 85%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  /* Shrink to fit content */
  align-items: flex-start;
}

.dialogue-right .message-content {
  /* Right-side fit logic */
  align-items: flex-end;
}

.user-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
  margin: 0 4px;
}

.dialogue-right .user-name {
  text-align: right;
}

.profile-picture {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
}

.profile-picture img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 20%;
}

.message-bubble {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  border-top-left-radius: 2px;
  padding: 0 16px;
  position: relative;
  transition: all 0.2s ease;
}

.dialogue-right .message-bubble {
  background: linear-gradient(135deg, rgba(160, 196, 255, 0.15), rgba(189, 178, 255, 0.15));
  border-color: rgba(160, 196, 255, 0.3);
  border-top-left-radius: 12px;
  border-top-right-radius: 2px;
}

.loading-bubble {
  border-color: #aaffcd;
  background-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 12px rgba(153, 234, 249, 0.35);
  animation: borderPulse 3s ease-in-out infinite alternate;
  animation: bubbleGlow 3s ease-in-out infinite alternate;
}

@keyframes bubbleGlow {
  0% {
    box-shadow: 0 0 6px rgba(153, 234, 249, 0.35);
  }
  50% {
    box-shadow: 0 0 12px rgba(153, 234, 249, 0.35);
  }
}

.loading-timer {
  margin-left: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.loading-entries {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 10px 0 4px;
  padding: 2px 0;
  border-radius: 10px;
}

.loading-entry {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  position: relative;
  backdrop-filter: blur(4px);
}

.loading-entry-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.loading-entry-duration {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.entry-running {
  border-color: #aaffcd;
  box-shadow: 0 0 8px rgba(153, 234, 249, 0.25);
  animation: loadingEntryPulse 2.6s ease-in-out infinite;
}

.entry-done {
  border-color: rgba(255, 255, 255, 0.15);
  opacity: 0.8;
}

/* Fade-slide-in animation for entries */
.loading-entry-enter-active,
.loading-entry-leave-active {
  transition: all 0.22s ease-out;
}

.loading-entry-enter-from,
.loading-entry-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.loading-entry-enter-to,
.loading-entry-leave-from {
  opacity: 1;
  transform: translateY(0);
}

@keyframes loadingEntryPulse {
  0% {
    box-shadow: 0 0 4px rgba(153, 234, 249, 0.18);
    border-color: rgba(153, 234, 249, 0.6);
    background: rgba(255, 255, 255, 0.06);
  }
  50% {
    box-shadow: 0 0 10px rgba(153, 234, 249, 0.38);
    border-color: rgba(170, 255, 205, 0.9);
    background: rgba(255, 255, 255, 0.09);
  }
  100% {
    box-shadow: 0 0 4px rgba(153, 234, 249, 0.18);
    border-color: rgba(153, 234, 249, 0.6);
    background: rgba(255, 255, 255, 0.06);
  }
}

.message-text {
  color: #f2f2f2;
  font-size: 14px;
  line-height: 1.5;
  word-wrap: break-word;
  white-space: pre-wrap;
}

/* Artifact wrappers */
.artifact-image-wrapper {
  padding: 10px 0;
}

.artifact-file-wrapper {
  padding: 10px 0;
}

.artifact-image {
  max-width: 260px;
  max-height: 200px;
  display: block;
  cursor: zoom-in;
  border-radius: 6px;
  padding: 0 0 10px 0;
}

.artifact-filename {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  gap: 6px;
}

.artifact-filename-icon {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  object-fit: cover;
  flex-shrink: 0;
}

.artifact-filename-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-download-button {
  margin-top: 15px;
  padding: 4px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.06);
  color: #f2f2f2;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.artifact-download-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}

.artifact-download-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.artifact-status {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.artifact-status.artifact-error {
  color: #ff8080;
}


.microphone-button {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  padding: 0;
  outline: none;
  position: relative;
}

.microphone-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.4);
  color: #f2f2f2;
}

.microphone-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.microphone-button.recording {
  background: rgba(255, 255, 255, 0.1);
  border-color: #aaffcd;
  color: #f2f2f2;
}

.microphone-button.pulsating {
  animation: microphonePulse 2s ease-in-out infinite;
}

@keyframes microphonePulse {
  0% {
    box-shadow:
      0 0 0 0 rgba(170, 255, 205, 0.7),
      0 0 0 0 rgba(153, 234, 249, 0.5);
    border-color: #aaffcd;
  }
  50% {
    box-shadow:
      0 0 0 12px rgba(170, 255, 205, 0),
      0 0 0 6px rgba(153, 234, 249, 0.3);
    border-color: #99eaf9;
  }
  100% {
    box-shadow:
      0 0 0 24px rgba(170, 255, 205, 0),
      0 0 0 18px rgba(153, 234, 249, 0);
    border-color: #aaffcd;
  }
}

.attachment-upload {
  position: relative;
}

.attachment-button-wrapper {
  position: relative;
  display: inline-block;
}

.attachment-button {
  padding: 6px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.attachment-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.4);
  color: #f2f2f2;
}

.attachment-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden-file-input {
  display: none;
}

.attachment-count {
  position: absolute;
  top: -8px;
  right: -6px;
  background: #99eaf9;
  color: #1a1a1a;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 10px;
}

/* Input File Selection */
.input-file-section {
  margin-bottom: 16px;
}

.file-upload-wrapper {
  position: relative;
}

.file-upload-button {
  width: 100%;
  padding: 10px 12px;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  font-weight: 400;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-upload-button:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.file-upload-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Input Manual */
.input-manual {
  margin-bottom: 16px;
}

.manual-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 600;
  margin-bottom: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.2s ease;
}

.manual-title:hover {
  color: rgba(255, 255, 255, 0.6);
}

.info-icon {
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.manual-title:hover .info-icon {
  opacity: 0.8;
}

.manual-content {
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.4;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.manual-item {
  margin-bottom: 8px;
  color: rgba(255, 255, 255, 0.7);
}

.manual-item:last-child {
  margin-bottom: 0;
}

.manual-item code {
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  color: #a0c4ff;
  font-weight: 500;
}

.manual-example {
  margin-top: 6px;
  margin-left: 16px;
}

.manual-example pre {
  background-color: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.8);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  overflow-x: auto;
  margin: 4px 0 0 0;
}

.file-info-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.remove-file-button {
  background: transparent;
  border: none;
  color: #99eaf9;
  cursor: pointer;
  padding: 0 6px;
  font-size: 16px;
  line-height: 1;
  margin-left: 8px;
  border-radius: 3px;
  transition: background-color 0.2s;
}

.remove-file-button:hover {
  background: rgba(153, 234, 249, 0.1);
}

/* Attachment Modal */
.attachment-modal {
  position: absolute;
  right: 0;
  bottom: calc(100% + 10px);
  width: 240px;
  background: #252525;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.attachment-name {
  font-size: 12px;
  color: #e0e0e0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-attachment {
  border: none;
  background: transparent;
  color: #99eaf9;
  cursor: pointer;
  padding: 0 4px;
}

/* Right Panel */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 250px;
}

.control-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  backdrop-filter: blur(5px);
}

.section-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 600;
  margin-top: 4px;
}

/* Custom Select */
.select-wrapper {
  position: relative;
}

.custom-file-selector {
  position: relative;
}

.file-selector,
.file-selector-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  padding-right: 30px;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f2f2f2;
  font-size: 14px;
  appearance: none;
  color: #f2f2f2;
}

.file-selector-input {
  cursor: text;
}

.file-selector:hover:not(:disabled),
.file-selector-input:hover:not(:disabled),
.file-selector-input:focus {
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.file-selector:disabled,
.file-selector-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.select-arrow {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.3);
  pointer-events: none;
  font-size: 10px;
}

.file-dropdown {
  position: absolute;
  top: calc(100%);
  left: 0;
  right: 0;
  margin-top: 1px;
  background-color: #252525;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.45);
  max-height: 260px;
  overflow-y: auto;
  z-index: 5;
  padding: 6px 0;
}

.file-dropdown::-webkit-scrollbar {
  display: none;
}

.file-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 14px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.file-option:hover {
  background: rgba(255, 255, 255, 0.06);
}

.file-name {
  color: #f2f2f2;
  font-size: 12px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-desc {
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
}

.file-empty {
  padding: 12px 14px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  text-align: center;
}

.file-dropdown-enter-active,
.file-dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.file-dropdown-enter-from,
.file-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Status Display */
.status-display {
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  text-align: center;
  transition: all 0.3s ease;
  font-weight: 500;
}

/* View Toggle */
.view-toggle {
  display: flex;
  background: rgba(0, 0, 0, 0.2);
  padding: 4px;
  border-radius: 8px;
}

.toggle-button {
  flex: 1;
  padding: 6px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  border-radius: 6px;
  font-size: 13px;
  transition: all 0.2s ease;
}

.toggle-button.active {
  background: rgba(255, 255, 255, 0.1);
  color: #f2f2f2;
  font-weight: 500;
}


/* Active Nodes */
.active-nodes-display {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 10px;
  overflow-y: auto;
  min-height: 100px;
}

.no-active-nodes {
  color: rgba(255, 255, 255, 0.3);
  font-size: 13px;
  text-align: center;
  margin-top: 10px;
}

.active-node-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  font-size: 13px;
}

.node-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #99eaf9;
  box-shadow: 0 0 6px #99eaf9;
}

/* Button Section */
.button-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cancel-button {
  padding: 12px 14px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  background: linear-gradient(
    135deg,
    #e07152,
    #dc5d4c,
    #bd4a4a
  );
  background-size: 200% 100%;
  animation: gradientShift 6s ease-in-out infinite;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.cancel-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

.cancel-button:disabled {
  background: #3a3a3a;
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}

.launch-button {
  padding: 14px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  background: linear-gradient(
        135deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  background-size: 200% 100%;
  animation: gradientShift 6s ease-in-out infinite;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.launch-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

.launch-button:disabled {
  background: #3a3a3a;
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}

.launch-button.glow {
  animation: glowPulse 3s ease-in-out infinite, gradientShift 6s ease-in-out infinite;
}

/* Markdown Styles moved to CollapsibleMessage.vue */

@keyframes gradientShift {
  0%, 100% { background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
}

@keyframes glowPulse {
  0% { box-shadow: 0 0 0 0 rgba(160, 196, 255, 0.4); }
  50% { box-shadow: 0 0 0 5px rgba(153, 234, 249, 0); }
  100% { box-shadow: 0 0 0 0 rgba(160, 196, 255, 0); }
}

@keyframes borderPulse {
  0% { border-color: #aaffcd; box-shadow: 0 0 0px rgba(170, 255, 205, 0.15); }
  50% { border-color: #99eaf9; box-shadow: 0 0 8px rgba(153, 234, 249, 0.35); }
  100% { border-color: #a0c4ff; box-shadow: 0 0 0px rgba(160, 196, 255, 0.2); }
}

@keyframes wavePulse {
  0% {
    left: -100%;
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
  100% {
    left: 100%;
    opacity: 0;
  }
}

.download-button {
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  color: #f2f2f2;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.download-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.download-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}


.image-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.image-modal-content {
  position: relative;
  max-width: 95vw;
  max-height: 95vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  background: rgba(26, 26, 26, 0.9);
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.image-modal-content img {
  max-width: 70vw;
  max-height: 65vh;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
}

.image-modal-enter-active,
.image-modal-leave-active {
  transition: opacity 0.2s ease;
}

.image-modal-enter-from,
.image-modal-leave-to {
  opacity: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.settings-button {
  background: transparent;
  border: none;
  color: #a0c4ff;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.settings-button:hover {
  background-color: rgba(160, 196, 255, 0.1);
}

/* Column Guide Modal */
.column-guide-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.column-guide-modal {
  background: #252525;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  max-width: 550px;
  width: 90vw;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
}

.modal-content {
  padding: 24px;
  max-height: calc(80vh - 48px);
  overflow-y: auto;
}

/* Modal animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* Batch Settings Modal */
.batch-settings-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.batch-settings-modal {
  background: #252525;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  max-width: 500px;
  width: 90vw;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
}

.batch-settings-modal .modal-content {
  padding: 0;
  max-height: calc(80vh - 48px);
  overflow-y: auto;
}

.batch-settings-modal .modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.batch-settings-modal .modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #f2f2f2;
}

.batch-settings-modal .close-button {
  background: none;
  border: none;
  color: #888;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.2s ease;
}

.batch-settings-modal .close-button:hover {
  color: #fff;
}

.batch-settings-modal .modal-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.batch-settings-modal .settings-item {
  margin-bottom: 24px;
}

.batch-settings-modal .settings-item:last-child {
  margin-bottom: 0;
}

.batch-settings-modal .setting-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #f2f2f2;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.batch-settings-modal .setting-input {
  width: 86px;
  padding: 10px 12px;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f2f2f2;
  font-size: 14px;
  transition: all 0.2s ease;
}

.batch-settings-modal .setting-input:focus {
  outline: none;
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.batch-settings-modal .setting-select {
  padding: 10px 12px;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f2f2f2;
  font-size: 14px;
  transition: all 0.2s ease;
  cursor: pointer;
}

.batch-settings-modal .setting-select:focus {
  outline: none;
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.batch-settings-modal .setting-select option {
  background-color: #1a1a1a;
  color: #f2f2f2;
}

.batch-settings-modal .setting-desc {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  line-height: 1.4;
}

.batch-settings-modal .modal-footer {
  padding: 16px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.batch-settings-modal .confirm-button {
  background: #4facfe;
  color: #fff;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.batch-settings-modal .confirm-button:hover {
  background: #3a9cfa;
}

.batch-settings-modal .cancel-button {
  background: transparent;
  color: #ccc;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.batch-settings-modal .cancel-button:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.3);
}
</style>
