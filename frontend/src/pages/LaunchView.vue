<template>
  <div class="launch-view">
    <div class="launch-bg"></div>
    <div class="header">
      <h1>Launch</h1>
      <button class="settings-button" @click="showSettingsModal = true" title="Settings">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
    </div>
    <div class="content">
      <!-- Left panel -->
      <div class="left-panel">
        <!-- Chat area -->
        <div v-show="viewMode === 'chat'" class="chat-box">
          <div class="chat-messages" ref="chatMessagesRef">
            <!-- Notifications and dialogues in order -->
            <div
              v-for="(message, index) in chatMessages"
              :key="`message-${index}`"
            >
              <!-- Notification -->
              <div
                v-if="['notification', 'warning', 'error'].includes(message.type)"
                class="chat-notification"
                :class="{
                  'chat-notification-warning': message.type === 'warning',
                  'chat-notification-error': message.type === 'error'
                }"
              >
                <div class="notification-content">
                  <div class="notification-text">{{ message.message }}</div>
                  <div class="message-timestamp">{{ formatTime(message.timestamp) }}</div>
                </div>
              </div>

              <!-- Dialogue -->
              <div
                v-else-if="message.type === 'dialogue'"
                class="dialogue"
                :class="{ 'dialogue-right': message.isRight }"
              >
                <div class="profile-picture">
                  <img :src="message.avatar" :alt="`Avatar ${index + 1}`" />
                </div>
                <div class="message-content">
                  <div class="user-name">
                    {{ message.name }}
                    <span class="message-timestamp">{{ formatTime(message.timestamp) }}</span>
                  </div>
                  <div
                    class="message-bubble"
                    :class="{ 'loading-bubble': message.isLoading }"
                  >
                  <CollapsibleMessage
                    v-if="message.text"
                    :html-content="renderMarkdown(message.text)"
                    :raw-content="message.text"
                    :default-expanded="configStore.AUTO_EXPAND_MESSAGES"
                  />

                  <TransitionGroup
                    v-if="message.loadingEntries && message.loadingEntries.length"
                    name="loading-entry"
                    tag="div"
                    class="loading-entries"
                  >
                    <div
                      v-for="entry in message.loadingEntries"
                      :key="entry.key"
                      class="loading-entry"
                      :class="{
                        'entry-running': entry.status === 'running',
                        'entry-done': entry.status === 'done'
                      }"
                    >
                      <span class="loading-entry-label">{{ entry.label }}</span>
                      <span class="loading-entry-duration">
                        {{ formatDuration(entry.startedAt, entry.endedAt || null) }}
                      </span>
                    </div>
                  </TransitionGroup>

                  <!-- Artifact image -->

                  <div
                    v-if="message.isArtifact && message.isImage"
                    class="artifact-image-wrapper"
                  >
                    <div
                      v-if="message.loading"
                      class="artifact-status"
                    >
                      Loading image...
                    </div>
                    <div
                      v-else-if="message.error"
                      class="artifact-status artifact-error"
                    >
                      {{ message.error }}
                    </div>
                    <div v-else>
                      <img
                        :src="message.dataUri"
                        :alt="message.fileName || 'image artifact'"
                        class="artifact-image"
                        role="button"
                        tabindex="0"
                        @click="openImageModal(message)"
                        @keydown.enter.prevent="openImageModal(message)"
                        @keydown.space.prevent="openImageModal(message)"
                      />
                      <div class="artifact-filename">
                        <img
                          v-if="getFilePreviewSrc(message)"
                          :src="getFilePreviewSrc(message)"
                          :alt="`${message.fileName} preview`"
                          class="artifact-filename-icon"
                        />
                        <span class="artifact-filename-text">{{ message.fileName }}</span>
                      </div>
                      <!-- Added unified download button for image artifacts -->
                      <button
                        class="artifact-download-button"
                        type="button"
                        :disabled="message.loading"
                        @click="downloadArtifact(message)"
                      >
                        Download
                      </button>
                    </div>
                  </div>

                  <!-- Artifact file download -->
                  <div
                    v-else-if="message.isArtifact && !message.isImage"
                    class="artifact-file-wrapper"
                  >
                    <div class="artifact-filename">
                      <img
                        v-if="getFilePreviewSrc(message)"
                        :src="getFilePreviewSrc(message)"
                        :alt="`${message.fileName} preview`"
                        class="artifact-filename-icon"
                      />
                      <span class="artifact-filename-text">{{ message.fileName }}</span>
                    </div>
                    <button
                      class="artifact-download-button"
                      type="button"
                      :disabled="message.loading"
                      @click="downloadArtifact(message)"
                    >
                      {{ message.loading ? 'Preparing...' : 'Download' }}
                    </button>
                  </div>

                  <!-- Model/tool call timer -->
                  <div
                    v-if="message.isLoading || message.duration"
                    class="loading-timer"
                  >
                    {{ message.isLoading ? formatDuration(message.startedAt) : message.duration }}
                  </div>
                </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-show="viewMode === 'graph'" class="graph-panel">
          <VueFlow class="vueflow-graph">
            <template #node-workflow-node="props">
              <WorkflowNode
                :id="props.id"
                :data="props.data"
                :is-active="activeNodes.includes(props.id)"
                :sprite="nodeSpriteMap.get(props.id) || ''"
                @hover="onNodeHover"
                @leave="onNodeLeave"
              />
            </template>
            <template #node-start-node="props">
              <StartNode :id="props.id" :data="props.data" />
            </template>
            <template #edge-workflow-edge="props">
              <WorkflowEdge
                :id="props.id"
                :source="props.source"
                :target="props.target"
                :source-x="props.sourceX"
                :source-y="props.sourceY"
                :target-x="props.targetX"
                :target-y="props.targetY"
                :source-position="props.sourcePosition"
                :target-position="props.targetPosition"
                :data="props.data"
                :marker-end="props.markerEnd"
                :animated="props.animated"
                :hovered-node-id="hoveredNodeId"
              />
            </template>
            <Background pattern-color="#aaa"/>
            <Controls position="bottom-left"/>
          </VueFlow>
        </div>

        <!-- Input area -->
        <div class="input-area">
          <div
            :class="['input-shell', { glow: shouldGlow, 'drag-active': isDragActive }]"
            @dragenter="handleDragEnter"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop"
          >
            <textarea
              v-model="taskPrompt"
              class="task-input"
              :disabled="!isConnectionReady || (isWorkflowRunning && status !== 'Waiting for input...')"
              placeholder="Please enter task prompt..."
              ref="taskInputRef"
              @keydown.enter="handleEnterKey"
              @paste="handlePaste"
            ></textarea>
            <div class="input-footer">
              <div class="input-footer-buttons">
                <div
                  class="attachment-upload"
                  @mouseenter="handleAttachmentHover(true)"
                  @mouseleave="handleAttachmentHover(false)"
                >
                  <div class="attachment-button-wrapper">
                    <button
                      type="button"
                      class="attachment-button"
                      :disabled="!isConnectionReady || !sessionId || isUploadingAttachment || (isWorkflowRunning && status !== 'Waiting for input...')"
                      @click="handleAttachmentButtonClick"
                    >
                      {{ isUploadingAttachment ? 'Uploading...' : 'Upload File' }}
                    </button>
                    <span
                      v-if="uploadedAttachments.length"
                      class="attachment-count"
                    >
                      {{ uploadedAttachments.length }}
                    </span>
                  </div>
                  <input
                    ref="attachmentInputRef"
                    type="file"
                    class="hidden-file-input"
                    @change="onAttachmentSelected"
                  />
                  <Transition name="attachment-popover">
                    <div
                      v-if="showAttachmentPopover"
                      class="attachment-modal"
                      @mouseenter="handleAttachmentHover(true)"
                      @mouseleave="handleAttachmentHover(false)"
                    >
                      <div
                        v-for="attachment in uploadedAttachments"
                        :key="attachment.attachmentId"
                        class="attachment-item"
                      >
                        <span class="attachment-name">{{ attachment.name }}</span>
                        <button
                          type="button"
                          class="remove-attachment"
                          @click.stop="removeAttachment(attachment.attachmentId)"
                        >
                          ×
                        </button>
                      </div>
                      <div
                        v-if="!uploadedAttachments.length"
                        class="attachment-empty"
                      >
                        No files uploaded
                      </div>
                    </div>
                  </Transition>
                </div>
                <button
                  v-if="false"
                  type="button"
                  class="microphone-button"
                  :class="{ 'recording': isRecording, 'pulsating': isRecording }"
                  :disabled="!isConnectionReady || !sessionId || isUploadingAttachment || (isWorkflowRunning && status !== 'Waiting for input...')"
                  @mousedown.prevent="startRecording"
                  @mouseup.prevent="stopRecording"
                  @mouseleave="handleMicrophoneMouseLeave"
                  @touchstart.prevent="startRecording"
                  @touchend.prevent="stopRecording"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z"
                      fill="currentColor"
                    />
                    <path
                      d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H7V12C7 14.76 9.24 17 12 17C14.76 17 17 14.76 17 12V10H19Z"
                      fill="currentColor"
                    />
                    <path
                      d="M11 22H13V20H11V22Z"
                      fill="currentColor"
                    />
                    <path
                      d="M6 19H18V21H6V19Z"
                      fill="currentColor"
                    />
                  </svg>
                </button>
              </div>
            </div>
            <div v-if="isDragActive" class="drag-overlay">
              <div class="drag-overlay-content">Drop files to upload</div>
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

          <label class="section-label">Status</label>
          <div class="status-display" :class="{ 'status-active': status === 'Running...' }">
            {{ status }}
          </div>

          <label class="section-label">View</label>
          <div class="view-toggle">
            <button
              class="toggle-button"
              :class="{ active: viewMode === 'chat' }"
              @click="viewMode = 'chat'"
            >
              Chat
            </button>
            <button
              class="toggle-button"
              :class="{ active: viewMode === 'graph' }"
              @click="switchToGraph"
            >
              Graph
            </button>
          </div>

          <!-- Button area -->
          <div class="button-section">
            <button
              class="launch-button"
              :class="{ glow: shouldGlow, 'is-sending': isWorkflowRunning }"
              @click="handleButtonClick"
              :disabled="loading || (isWorkflowRunning && !taskPrompt.trim()) || (!isWorkflowRunning && status !== 'Completed' && status !== 'Cancelled' && !isConnectionReady)">
              {{ buttonLabel }}
            </button>

            <button
              class="cancel-button"
              :disabled="status !== 'Running...'"
              @click="cancelWorkflow"
            >
              Cancel
            </button>

            <button
              class="download-button"
              :disabled="status !== 'Completed' && status !== 'Cancelled'"
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { fetchWorkflowsWithDesc, fetchLogsZip, fetchWorkflowYAML, postFile, getAttachment, fetchVueGraph } from '../utils/apiFunctions.js'
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

// Task input state
const taskPrompt = ref('')

// File selector state
const workflowFiles = ref([])
const selectedFile = ref('')
const fileSearchQuery = ref('')
const isFileSearchDirty = ref(false)
const isFileDropdownOpen = ref(false)
const fileSelectorWrapperRef = ref(null)
const fileSelectorInputRef = ref(null)

// Status state
const status = ref('Waiting for workflow selection...')
const loading = ref(false)

// Session ID for downloads
let sessionIdToDownload = null

// All notifications and dialogues
const chatMessages = ref([])
const chatMessagesRef = ref(null) // Extra ref

// Map in-progress model/tool call messages by node ID
// Map<nodeId, { message, entryMap, baseKeyToKey, counters }>
const nodesLoadingMessagesMap = new Map()

// Create or fetch the loading bubble for a node
const addTotalLoadingMessage = (nodeId) => {
  if (!nodeId) return null

  let nodeState = nodesLoadingMessagesMap.get(nodeId)
  if (nodeState) return nodeState

  let avatar
  if (nameToSpriteMap.value.has(nodeId)) {
    avatar = nameToSpriteMap.value.get(nodeId)
  } else {
    avatar = spriteFetcher.fetchSprite(nodeId, 'D', 1)
    nameToSpriteMap.value.set(nodeId, avatar)
  }

  const message = {
    type: 'dialogue',
    name: nodeId,
    text: '',
    avatar,
    isRight: false,
    isLoading: true,
    startedAt: Date.now(),
    timestamp: Date.now(),
    loadingEntries: []
  }

  chatMessages.value.push(message)

  nodeState = {
    message,
    entryMap: new Map(),
    baseKeyToKey: new Map(),
    counters: new Map()
  }
  nodesLoadingMessagesMap.set(nodeId, nodeState)
  return nodeState
}

// Add a loading entry (model/tool call) and associate it with baseKey
const addLoadingEntry = (nodeId, baseKey, label) => {
  const nodeState = addTotalLoadingMessage(nodeId)
  if (!nodeState || !baseKey) return null

  const count = (nodeState.counters.get(baseKey) || 0) + 1
  nodeState.counters.set(baseKey, count)
  const key = `${baseKey}-${count}`

  const entry = {
    key,
    baseKey,
    label,
    status: 'running',
    startedAt: Date.now(),
    endedAt: null
  }

  nodeState.entryMap.set(key, entry)
  nodeState.baseKeyToKey.set(baseKey, key)
  nodeState.message.loadingEntries.push(entry)
  return entry
}

// Finish a loading entry
const finishLoadingEntry = (nodeId, baseKey) => {
  const nodeState = nodesLoadingMessagesMap.get(nodeId)
  if (!nodeState || !baseKey) return null

  const key = nodeState.baseKeyToKey.get(baseKey)
  const entry = key ? nodeState.entryMap.get(key) : null
  if (!entry) return null

  entry.status = 'done'
  entry.endedAt = Date.now()
  nodeState.baseKeyToKey.delete(baseKey)
  return entry
}

// Finish all running entries when a node ends or cancels
const finalizeAllLoadingEntries = (nodeState, endedAt = Date.now()) => {
  if (!nodeState) return
  for (const entry of nodeState.entryMap.values()) {
    if (entry.status === 'running') {
      entry.status = 'done'
      entry.endedAt = endedAt
    }
  }
  nodeState.baseKeyToKey.clear()
}

// Global timer for updating loading bubble durations
const now = ref(Date.now())
let loadingTimerInterval = null

// Map sprites for different roles
const nameToSpriteMap = ref(new Map())

// Map node IDs to sprites for graph display
const nodeSpriteMap = ref(new Map())

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

// Recording state
const isRecording = ref(false)
let mediaRecorder = null
let audioChunks = []
let audioStream = null

// WebSocket readiness state
const isConnectionReady = ref(false)
const showSettingsModal = ref(false)

// View mode
const viewMode = ref('chat')

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
  if (isWorkflowRunning.value) {
    return 'Send'
  }
  if (status.value === 'Completed' || status.value === 'Cancelled') {
    return 'Relaunch'
  }
  return 'Launch'
})

const clearUploadedAttachments = () => {
  uploadedAttachments.value = []
  showAttachmentPopover.value = false
  if (attachmentInputRef.value) {
    attachmentInputRef.value.value = ''
  }
}

// Reset the WebSocket connection and related state
const resetConnectionState = ({ closeSocket = true } = {}) => {
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
  activeNodes.value = []
  if (attachmentHoverTimeout) {
    clearTimeout(attachmentHoverTimeout)
    attachmentHoverTimeout = null
  }
  clearUploadedAttachments()
}

// Button state management
const isWorkflowRunning = ref(false)

// Active node list
const activeNodes = ref([])
// Hovered node id for highlighting related edges
const hoveredNodeId = ref(null)

const onNodeHover = (nodeId) => {
  hoveredNodeId.value = nodeId || null
}
const onNodeLeave = (_nodeId) => {
  hoveredNodeId.value = null
}

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

  selectedFile.value = fileName
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
  selectedFile.value = fileName
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
  fileSearchQuery.value = selectedFile.value || ''
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

// Add a dialogue entry
const addDialogue = (name, message) => {
  if (message === null || message === undefined) {
    return
  }
  const text = typeof message === 'string' ? message : String(message)
  if (!text.trim()) {
    return
  }
  let avatar
  if (nameToSpriteMap.value.has(name)) {
    avatar = nameToSpriteMap.value.get(name)
  } else {
    avatar = spriteFetcher.fetchSprite()
    nameToSpriteMap.value.set(name, avatar)
  }

  const isRight = name === "User"

  chatMessages.value.push({
    type: 'dialogue',
    name: name,
    text: text,
    avatar: avatar,
    isRight: isRight,
    timestamp: Date.now()
  })
}

// Add a notification (supports levels)
const addChatNotification = (message, { type = 'notification' } = {}) => {
  chatMessages.value.push({
    type,
    message,
    timestamp: Date.now()
  })
}

// Format a millisecond timestamp as mm:ss
const formatDuration = (startedAt, endedAt = null) => {
  if (!startedAt) {
    return ''
  }
  const end = endedAt ?? now.value
  const totalSeconds = Math.max(0, Math.floor((end - startedAt) / 1000))
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

const isAttachmentUploadAllowed = () => {
  if (!isConnectionReady.value || !sessionId || isUploadingAttachment.value) {
    return false
  }
  if (isWorkflowRunning.value && status.value !== 'Waiting for input...') {
    return false
  }
  return true
}

const handleAttachmentButtonClick = () => {
  if (!isAttachmentUploadAllowed()) {
    return
  }
  attachmentInputRef.value?.click()
}

const uploadFiles = async (files) => {
  if (!files || files.length === 0) {
    return
  }

  if (!sessionId) {
    alert('Session is not ready yet. Please wait for connection.')
    return
  }

  isUploadingAttachment.value = true
  try {
    for (const file of files) {
      try {
        const result = await postFile(sessionId, file)

        if (result?.success && result?.attachmentId) {
          console.log('File uploaded successfully:', result)
          uploadedAttachments.value.push(result)
        } else {
          console.error('File upload failed:', result)
          alert(result?.message || 'Failed to upload file')
        }
      } catch (error) {
        console.error('Failed to upload attachment:', error)
        alert('File upload failed, please try again.')
      }
    }
  } finally {
    isUploadingAttachment.value = false
  }
}

const onAttachmentSelected = async (event) => {
  const file = event.target?.files?.[0]
  if (event.target) {
    event.target.value = ''
  }

  if (!file) {
    return
  }

  await uploadFiles([file])
}

const removeAttachment = (attachmentId) => {
  uploadedAttachments.value = uploadedAttachments.value.filter(
    (attachment) => attachment.attachmentId !== attachmentId
  )
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

const handleAttachmentHover = (isHovering) => {
  if (isHovering) {
    if (attachmentHoverTimeout) {
      clearTimeout(attachmentHoverTimeout)
      attachmentHoverTimeout = null
    }

    if (uploadedAttachments.value.length > 0) {
      showAttachmentPopover.value = true
    }
    return
  }

  if (attachmentHoverTimeout) {
    clearTimeout(attachmentHoverTimeout)
  }

  attachmentHoverTimeout = setTimeout(() => {
    showAttachmentPopover.value = false
    attachmentHoverTimeout = null
  }, 140)
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
  if (event.key === 'Escape' && selectedArtifactImage.value) {
    closeImageModal()
  }
}

const handleEnterKey = (e) => {
  if (e.metaKey || e.ctrlKey) {
    // Check disabled state logically similar to button
    if (loading.value || (isWorkflowRunning.value && !taskPrompt.value.trim()) || (!isWorkflowRunning.value && status.value !== 'Completed' && status.value !== 'Cancelled' && !isConnectionReady.value)) {
       return
    }
    handleButtonClick()
  }
}

// Handle paste events, including file uploads
const handlePaste = async (event) => {
  // Check if upload is allowed
  if (!isAttachmentUploadAllowed()) {
    return
  }

  // Get clipboard data
  const clipboardData = event.clipboardData
  if (!clipboardData) {
    return
  }

  // Check whether the clipboard contains files
  const files = clipboardData.files
  if (!files || files.length === 0) {
    return
  }

  // Prevent default paste to avoid inserting text
  event.preventDefault()

  // Upload all pasted files
  await uploadFiles(files)
}

const isFileDragEvent = (event) => {
  const types = event?.dataTransfer?.types
  if (!types) {
    return false
  }
  return Array.from(types).includes('Files')
}

const handleDragEnter = (event) => {
  if (!isFileDragEvent(event) || !isAttachmentUploadAllowed()) {
    return
  }
  dragDepth += 1
  isDragActive.value = true
  event.preventDefault()
}

const handleDragOver = (event) => {
  if (!isFileDragEvent(event) || !isAttachmentUploadAllowed()) {
    return
  }
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

const handleDragLeave = (event) => {
  if (!isFileDragEvent(event)) {
    return
  }
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) {
    isDragActive.value = false
  }
}

const handleDrop = async (event) => {
  if (!isFileDragEvent(event)) {
    return
  }
  event.preventDefault()
  dragDepth = 0
  isDragActive.value = false

  if (!isAttachmentUploadAllowed()) {
    return
  }

  const files = Array.from(event.dataTransfer?.files || [])
  if (files.length === 0) {
    return
  }
  await uploadFiles(files)
}

// Handle YAML file selection
const handleYAMLSelection = async (fileName) => {
  if (!fileName) {
    workflowYaml.value = {}
    chatMessages.value = []
    setNodes([])
    setEdges([])
    nodeSpriteMap.value.clear()
    return
  }

  // Clear the chat
  chatMessages.value = []

  try {
    // Fetch YAML config and emit initial_instructions to the chat
    const yamlContentString = await fetchWorkflowYAML(fileName)
    const parsedYaml = yaml.load(yamlContentString)
    workflowYaml.value = parsedYaml || {}
    const initialInstructions = workflowYaml.value?.graph?.initial_instruction || ''

    if (initialInstructions) {
      addChatNotification(initialInstructions)
    } else {
      addChatNotification("No initial instructions provided")
    }

    // Prefetch sprites for all nodes in the workflow
    const yamlNodes = Array.isArray(workflowYaml.value?.graph?.nodes)
      ? workflowYaml.value.graph.nodes
      : []

    // Clear the previous node sprite map
    nodeSpriteMap.value.clear()

    // Fetch a sprite for each node
    for (const node of yamlNodes) {
      if (node.id) {
        const spritePath = spriteFetcher.fetchSprite(node.id, 'D', 1)
        nodeSpriteMap.value.set(node.id, spritePath)
      }
    }
  } catch (error) {
    console.error('Failed to load YAML file:', error)
    workflowYaml.value = {}
    addChatNotification("Failed to load YAML file")
    nodeSpriteMap.value.clear()
  }

  await loadVueFlowGraph({ fit: viewMode.value === 'graph' })
}

// Handle button clicks
const handleButtonClick = () => {
  if (isWorkflowRunning.value) {
    // If Send, send user input
    sendHumanInput()

    status.value = "Running..."
    shouldGlow.value = false
  } else if (status.value === 'Completed' || status.value === 'Cancelled') {
    // If Relaunch, restart the same workflow and re-enter Launch state
    if (!selectedFile.value) {
      alert('Please choose a workflow file！')
      return
    }

    resetConnectionState()
    status.value = 'Connecting...'
    handleYAMLSelection(selectedFile.value)
    establishWebSocketConnection()
  } else {
    // If Launch, start the workflow
    launchWorkflow()
  }
}

// Send human input
const sendHumanInput = () => {
  if (!ws) {
    return
  }

  const trimmedInput = taskPrompt.value.trim()
  const attachmentIds = uploadedAttachments.value.map((attachment) => attachment.attachmentId)
  const attachmentNames = uploadedAttachments.value.map(
    (attachment) => attachment.name || attachment.attachmentId
  )

  if (!trimmedInput && attachmentIds.length === 0) {
    return
  }

  const message = {
    type: 'human_input',
    data: {
      input: trimmedInput,
      attachments: attachmentIds
    }
  }

  clearUploadedAttachments()
  ws.send(JSON.stringify(message))

  const fullMessage = []
  if (trimmedInput) {
    fullMessage.push(trimmedInput)
  }
  if (attachmentNames.length) {
    fullMessage.push(`[[Attachments]]:\n ${attachmentNames.join(', ')}`)
  }

  if (fullMessage.length) {
    addDialogue('User', fullMessage.join('\n\n'))
  }

  taskPrompt.value = ''
}

// Establish a WebSocket connection
const establishWebSocketConnection = () => {
  // Reset any previous state before creating a new socket
  resetConnectionState()

  if (!selectedFile.value) {
    return
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const wsProtocol = baseUrl.startsWith('https') ? 'wss:' : 'ws:'
  const urlObj = new URL(baseUrl)
  const wsUrl = `${wsProtocol}//${urlObj.host}/ws`
  const socket = new WebSocket(wsUrl)
  ws = socket

  socket.onopen = () => {
    // Ignore events from stale sockets
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
      status.value = 'Waiting for launch...'

      nextTick(() => {
        taskInputRef.value?.focus()
      })
    } else {
      processMessage(msg)
    }
  }

  socket.onerror = (error) => {
    // Ignore errors from sockets that are no longer current
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
    if (status.value === 'Running...') {
      status.value = 'Disconnected'
    } else if (status.value === 'Connecting...' || status.value === 'Waiting for launch...') {
      status.value = 'Disconnected'
    }
    resetConnectionState({ closeSocket: false })
  }
}

// Watch for file selection changes
watch(selectedFile, (newFile) => {
  taskPrompt.value = ''
  fileSearchQuery.value = newFile || ''
  isFileSearchDirty.value = false

  if (!newFile) {
    resetConnectionState()
    status.value = 'Waiting for file selection...'
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

  // Start the global timer
  if (!loadingTimerInterval) {
    loadingTimerInterval = setInterval(() => {
      now.value = Date.now()
    }, 1000)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  unlockBodyScroll()
  resetConnectionState()
  cleanupRecording()

  if (loadingTimerInterval) {
    clearInterval(loadingTimerInterval)
    loadingTimerInterval = null
  }
})

const { fromObject, fitView, onPaneReady, onNodesInitialized, setNodes, setEdges, edges } = useVueFlow()

// Fit the view after the pane is ready or nodes are initialized
onPaneReady(() => {
  requestAnimationFrame(() => fitView?.({ padding: 0.1 }))
})
onNodesInitialized(() => {
  requestAnimationFrame(() => fitView?.({ padding: 0.1 }))
})

const syncNodeAndEdgeData = () => {
  try {
    const yamlNodes = workflowYaml.value?.graph?.nodes || []
    const yamlEdges = workflowYaml.value?.graph?.edges || []

    const yamlNodeById = new Map(
      Array.isArray(yamlNodes) ? yamlNodes.map(node => [node.id, node]) : []
    )
    const yamlEdgeByKey = new Map(
      Array.isArray(yamlEdges)
        ? yamlEdges.map(edge => [`${edge.from}-${edge.to}`, edge])
        : []
    )

    setNodes(existingNodes => {
      if (!Array.isArray(existingNodes)) {
        return existingNodes
      }
      return existingNodes.map(node => {
        const yamlNode = yamlNodeById.get(node.id)
        if (yamlNode) {
          return {
            ...node,
            data: yamlNode
          }
        }
        return node
      })
    })

    setEdges(existingEdges => {
      if (!Array.isArray(existingEdges)) {
        return existingEdges
      }
      return existingEdges.map(edge => {
        const key = `${edge.source}-${edge.target}`
        const yamlEdge = yamlEdgeByKey.get(key)
        if (yamlEdge) {
          return {
            ...edge,
            data: yamlEdge,
            markerEnd: {
              type: MarkerType.Arrow,
              width: 18,
              height: 18,
              color: '#f2f2f2',
              strokeWidth: 2,
            }
          }
        }
        return edge
      })
    })
  } catch (error) {
    console.error('Failed to sync graph data with YAML:', error)
  }
}

const generateNodesAndEdges = async ({ fit = false } = {}) => {
  try {
    const yamlNodes = Array.isArray(workflowYaml.value?.graph?.nodes)
      ? workflowYaml.value.graph.nodes
      : []
    const yamlEdges = Array.isArray(workflowYaml.value?.graph?.edges)
      ? workflowYaml.value.graph.edges
      : []

    const generatedNodes = yamlNodes.map((node, index) => ({
      id: node.id,
      type: 'workflow-node',
      label: node.id,
      position: {
        x: 20 + (index % 5) * 200,
        y: 10 + Math.floor(index / 5) * 150
      },
      data: node
    }))

    const generatedEdges = yamlEdges.map(edge => ({
      id: `${edge.from}-${edge.to}`,
      source: edge.from,
      target: edge.to,
      type: 'workflow-edge',
      markerEnd: {
        type: MarkerType.Arrow,
        width: 18,
        height: 18,
        color: '#f2f2f2',
        strokeWidth: 2,
      },
      data: edge
    }))

    setNodes(generatedNodes)
    setEdges(generatedEdges)
  } catch (error) {
    console.error('Error generating nodes and edges from YAML:', error)
  }

  if (fit && viewMode.value === 'graph') {
    await nextTick()
    fitView?.({ padding: 0.1 })
  }
}

const loadVueFlowGraph = async ({ fit = false } = {}) => {
  const selectionSnapshot = selectedFile.value
  const shouldFit = fit && viewMode.value === 'graph'

  const runFallback = async () => {
    if (selectedFile.value === selectionSnapshot) {
      await generateNodesAndEdges({ fit: shouldFit })
    }
    return false
  }

  if (!selectionSnapshot) {
    return await runFallback()
  }

  const key = selectionSnapshot.replace(/\.yaml$/i, '')
  if (!key) {
    return await runFallback()
  }

  try {
    const result = await fetchVueGraph(key)

    if (selectedFile.value !== selectionSnapshot) {
      return false
    }

    if (result?.status === 404) {
      return await runFallback()
    }

    if (!result?.success) {
      console.error('Failed to load VueFlow graph:', result?.message || result?.detail)
      return await runFallback()
    }

    if (selectedFile.value !== selectionSnapshot) {
      return false
    }

    const content = result?.content

    if (!content) {
      return await runFallback()
    }

    let flow
    try {
      flow = JSON.parse(content)
    } catch (parseError) {
      console.error('Failed to parse saved VueFlow graph:', parseError)
      return await runFallback()
    }

    fromObject?.(flow)
    await nextTick()

    if (selectedFile.value !== selectionSnapshot) {
      return false
    }

    syncNodeAndEdgeData()

    if (shouldFit) {
      await nextTick()

      if (selectedFile.value !== selectionSnapshot) {
        return false
      }

      fitView?.({ padding: 0.1 })
    }

    return true
  } catch (error) {
    console.error('Failed to load VueFlow graph:', error)
  }

  return await runFallback()
}

const switchToGraph = async () => {
  viewMode.value = 'graph'
  await nextTick()
  await loadVueFlowGraph({ fit: true })
}

const launchWorkflow = async () => {
  if (!selectedFile.value) {
    alert('Please choose a workflow file！')
    return
  }

  const trimmedPrompt = taskPrompt.value.trim()
  const attachmentIds = uploadedAttachments.value.map((attachment) => attachment.attachmentId)
  const attachmentNames = uploadedAttachments.value.map(
    (attachment) => attachment.name || attachment.attachmentId
  )

  if (!trimmedPrompt && attachmentIds.length === 0) {
    alert('Please enter task prompt or upload files.')
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
    const response = await fetch('/api/workflow/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        yaml_file: selectedFile.value,
        task_prompt: trimmedPrompt,
        session_id: sessionId,
        attachments: attachmentIds
      })
    })

    if (response.ok) {
      // Clear uploaded attachments
      clearUploadedAttachments()

      const result = await response.json()
      console.log('Workflow launched: ', result)

      const fullMessage = []
      if (trimmedPrompt) {
        fullMessage.push(trimmedPrompt)
      }
      if (attachmentNames.length) {
        fullMessage.push(`Attachments: ${attachmentNames.join(', ')}`)
      }
      if (fullMessage.length) {
        addDialogue('User', fullMessage.join('\n\n'))
      }

      taskPrompt.value = ''

      status.value = 'Running...'
      isWorkflowRunning.value = true
    } else {
      const error = await response.json().catch(() => ({}))
      console.error('Failed to launch workflow:', error)
      status.value = 'Failed'
      alert(`Failed to launch workflow: ${error.detail || 'Unknown error'}`)
      shouldGlow.value = true
      if (isConnectionReady.value) {
        status.value = 'Waiting for launch...'
      }
    }
  } catch (error) {
    console.error('Error calling execute API:', error)
    status.value = 'Error'
    alert(`Failed to call execute API: ${error.message}`)
    shouldGlow.value = true
    if (isConnectionReady.value) {
      status.value = 'Waiting for launch...'
    }
  }
}

// When workflow is finished or cancelled, re-enable glow
watch(status, (newStatus) => {
  if (newStatus === 'Completed' || newStatus === 'Cancelled') {
    shouldGlow.value = true
  }
})

const downloadArtifact = async (message) => {
  if (!sessionId || !message?.attachmentId) {
    return
  }
  try {
    // to support download for both code file and image file
    // If we already have dataUri (e.g., images preloaded), avoid toggling loading to prevent flicker
    let dataUri = message.dataUri
    if (!dataUri) {
      message.loading = true
      dataUri = await getAttachment(sessionId, message.attachmentId)
      if (!dataUri) {
        throw new Error('Empty attachment data')
      }
      // Cache here
      message.dataUri = dataUri
    }

    const link = document.createElement('a')
    link.href = dataUri
    link.download = message.fileName || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    console.error('Failed to download artifact:', error)
    alert('Failed to download file, please try again.')
  } finally {
    if (message.loading) {
      message.loading = false
    }
  }
}

// Handle edge condition messages and trigger sprite animation
const handleEdgeConditionMessage = (message) => {
  // Parse message format: "Edge condition met for Source Node -> Target Node"
  const edgeMatch = message.match(/Edge condition met for (.+) -> (.+)/)
  if (!edgeMatch) {
    console.warn('Could not parse edge condition message:', message)
    return
  }

  const sourceNode = edgeMatch[1].trim()
  const targetNode = edgeMatch[2].trim()

  console.log('Edge condition met:', { sourceNode, targetNode })

  // Find the edge in the VueFlow edges
  const edge = edges.value.find(e => e.source === sourceNode && e.target === targetNode)
  if (!edge) {
    return
  }

  // Trigger sprite animation along the edge
  animateSpriteAlongEdge(edge)
}

// Animate a sprite walking along an edge from source to target
const animateSpriteAlongEdge = (edge) => {
  // Get sprite for the source node (walking animation)
  let spriteSrc
  if (nameToSpriteMap.value.has(edge.source)) {
    spriteSrc = nameToSpriteMap.value.get(edge.source)
  } else {
    spriteSrc = spriteFetcher.fetchSprite(edge.source, 'D', 2) // Start with walking frame 2
    nameToSpriteMap.value.set(edge.source, spriteSrc)
  }

  // Find edge path element in DOM
  const edgeId = `${edge.source}-${edge.target}`
  const edgeElement = document.querySelector(`[data-id="${edgeId}"]`)
  if (!edgeElement) {
    console.warn('Edge element not found in DOM for:', edgeId)
    return
  }

  // Find the path element within the edge
  const pathElement = edgeElement.querySelector('path')
  if (!pathElement) {
    console.warn('Path element not found for edge:', edgeId)
    return
  }

  // Find the SVG element that contains this path
  const svgElement = pathElement.closest('svg')
  if (!svgElement) {
    console.warn('SVG element not found for path')
    return
  }

  // Get the total length of the path
  const pathLength = pathElement.getTotalLength()

  // Create an SVG image element for the sprite
  const spriteImage = document.createElementNS('http://www.w3.org/2000/svg', 'image')
  spriteImage.setAttribute('width', '32')
  spriteImage.setAttribute('height', '40')
  spriteImage.setAttribute('href', spriteSrc)
  spriteImage.setAttribute('x', '-16') // Center horizontally
  spriteImage.setAttribute('y', '-20') // Center vertically
  spriteImage.style.pointerEvents = 'none'

  // Add to the same SVG as the path
  svgElement.appendChild(spriteImage)

  // Determine left/right based on path start and end points
  const startPoint = pathElement.getPointAtLength(0)
  const endPoint = pathElement.getPointAtLength(pathLength)
  const direction = endPoint.x >= startPoint.x ? 'R' : 'L'

  // Animation duration based on path length (longer paths = more time)
  const duration = Math.min(Math.max(pathLength * 0.02, 2000), 4000) // 2-5 seconds

  let startTime = null
  let frame = 1

  const animate = (timestamp) => {
    if (!startTime) startTime = timestamp

    const elapsed = timestamp - startTime
    const progress = Math.min(elapsed / duration, 1)

    // Get point along the path in SVG coordinates
    const point = pathElement.getPointAtLength(progress * pathLength)

    // Position the sprite at the point (SVG coordinates work directly in the SVG element)
    spriteImage.setAttribute('transform', `translate(${point.x}, ${point.y})`)

    // Update walking animation frame: 1 -> 2 -> 1 -> 3 -> repeat
    const frameIndex = Math.floor(elapsed / 250) % 4
    let targetFrame
    if (frameIndex === 0 || frameIndex === 2) {
      targetFrame = 1
    } else if (frameIndex === 1) {
      targetFrame = 2
    } else {
      targetFrame = 3
    }

    if (frame !== targetFrame) {
      frame = targetFrame
      const newSprite = spriteFetcher.fetchSprite(edge.source, direction, frame)
      spriteImage.setAttribute('href', newSprite)
    }

    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      // Animation complete
      svgElement.removeChild(spriteImage)
    }
  }

  // Start animation
  requestAnimationFrame(animate)
}

const processMessage = async (msg) => {
  console.log('Message: ', msg)

  // Prompt for human input
  if (msg.type === 'human_input_required') {
    const fullMessage = msg.data.task_description + '\n\n' + msg.data.input
    addDialogue(`${msg.data.node_id}`, `${fullMessage}`)

    status.value = "Waiting for input..."
    shouldGlow.value = true
  }

  // Handle artifact messages (file/image output)
  if (msg.type === 'artifact_created') {
    const events = msg?.data?.events
    if (Array.isArray(events)) {
      for (const event of events) {
        const nodeName = event?.node_id || 'Artifact'
        const fileName = event?.file_name || 'artifact'
        const mimeType = event?.mime_type || ''
        const attachmentId = event?.attachment_id

        // Build the avatar
        let avatar
        if (nameToSpriteMap.value.has(nodeName)) {
          avatar = nameToSpriteMap.value.get(nodeName)
        } else {
          avatar = spriteFetcher.fetchSprite()
          nameToSpriteMap.value.set(nodeName, avatar)
        }

        const isRight = false

        const message = {
          // Treat message as dialogue
          type: 'dialogue',
          name: nodeName,
          text: '',
          avatar,
          isRight,

          // Add artifact-specific fields
          isArtifact: true,
          fileName,
          mimeType,
          attachmentId,
          isImage: !!mimeType && mimeType.includes('image'),
          dataUri: null,
          loading: true,
          error: null,
          timestamp: Date.now()
        }

        chatMessages.value.push(message)

        // Preload image content
        if (message.isImage && sessionId && attachmentId) {
          try {
            const dataUri = await getAttachment(sessionId, attachmentId)
            message.dataUri = dataUri
          } catch (error) {
            console.error('Failed to load image artifact:', error)
            message.error = 'Failed to load image'
          } finally {
            message.loading = false
          }
        } else {
          message.loading = false
        }
      }
    }
  }

  // Handle warning/error messages
  if (msg.type === 'log' && (msg.data.level === 'WARNING' || msg.data.level === 'ERROR')) {
    const notificationType = msg.data.level === 'WARNING' ? 'warning' : 'error'
    addChatNotification(msg.data.message, { type: notificationType })
  }

  // Handle log messages
  if (msg.type === 'log' && msg.data.level === 'INFO') {
    const eventType = msg.data.event_type
    const nodeId = msg.data.node_id

    // Node active
    if (eventType === 'NODE_START') {
      if (nodeId && !activeNodes.value.includes(nodeId)) {
        activeNodes.value.push(nodeId)
      }
    }

    // Model call
    else if (eventType === 'MODEL_CALL') {
      // Model call started
      if (msg.data.details.stage === "before") {
        const baseKey = `model-${msg.data.details.model_name || 'unknown'}`
        addLoadingEntry(nodeId, baseKey, `Model ${msg.data.details.model_name}`)
      }

      // Model call ended
      if (msg.data.details.stage === "after") {
        const baseKey = `model-${msg.data.details.model_name || 'unknown'}`
        finishLoadingEntry(nodeId, baseKey)
      }
    }

    // Tool call (a node may call tools multiple times)
    else if (eventType === 'TOOL_CALL') {
      // Tool call started
      if (msg.data.details.stage === "before") {
        const baseKey = `tool-${msg.data.details.tool_name || 'unknown'}`
        addLoadingEntry(nodeId, baseKey, `Tool ${msg.data.details.tool_name}`)
      }

      // Tool call ended
      if (msg.data.details.stage === "after") {
        const baseKey = `tool-${msg.data.details.tool_name || 'unknown'}`
        finishLoadingEntry(nodeId, baseKey)
      }
    }

    // Node ended (with output)
    else if (eventType === 'NODE_END') {
      if (nodeId) {
        // Remove from active node list
        const index = activeNodes.value.indexOf(nodeId)
        if (index > -1) {
          activeNodes.value.splice(index, 1)
        }

        const nodeState = nodesLoadingMessagesMap.get(nodeId)
        if (nodeState) {
          const endedAt = Date.now()
          finalizeAllLoadingEntries(nodeState, endedAt)
          nodeState.message.isLoading = false
          nodeState.message.duration = formatDuration(nodeState.message.startedAt, endedAt)
          nodesLoadingMessagesMap.delete(nodeId)
        }
      }

      addDialogue(`${nodeId}`, `${msg.data.details.output}`)
    }

    // Edge condition met - trigger sprite animation
    else if (msg.data.message && msg.data.message.includes('Edge condition met for')) {
      handleEdgeConditionMessage(msg.data.message)
    }

    // Other log messages
    else {
      addChatNotification(msg.data.message)
    }
  }

  // Workflow completed
  if (msg.type === 'workflow_completed') {
    addChatNotification(msg.data.summary)
    status.value = 'Completed'
    isWorkflowRunning.value = false
    sessionIdToDownload = sessionId
  }

  // Handle direct error messages (e.g., workflow execution errors)
  if (msg.type === 'error') {
    const errorMessage = msg.data?.message || 'Unknown error occurred'
    addChatNotification(errorMessage, { type: 'error' })
    status.value = 'Error'
    isWorkflowRunning.value = false
    sessionIdToDownload = sessionId
  }
}

// Cancel the currently running workflow
const cancelWorkflow = () => {
  if (!isWorkflowRunning.value || !ws) {
    return
  }
  addChatNotification('Workflow cancelled')
  status.value = 'Cancelled'
  isWorkflowRunning.value = false
  sessionIdToDownload = sessionId

  // Finish all loading messages
  const endedAt = Date.now()
  for (const [nodeId, nodeState] of nodesLoadingMessagesMap.entries()) {
    if (nodeState?.message) {
      finalizeAllLoadingEntries(nodeState, endedAt)
      nodeState.message.isLoading = false
      nodeState.message.duration = formatDuration(nodeState.message.startedAt, endedAt)
      nodesLoadingMessagesMap.delete(nodeId)
    }
  }

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

// Return a preview by file name/type (data URI). Images return thumbnails; others return an extension icon.
const getFilePreviewSrc = (message) => {
  try {
    const fileName = message?.fileName || ''
    const mimeType = message?.mimeType || ''
    if (message?.isImage && message?.dataUri) {
      // Use existing image data as the preview thumbnail
      return message.dataUri
    }
    return getPreviewIconByExt(fileName, mimeType)
  } catch (e) {
    return ''
  }
}

const getPreviewIconByExt = (fileName = '', mimeType = '') => {
  const ext = (fileName.split('.').pop() || '').toLowerCase()
  const isImg = mimeType.includes('image') || ['png','jpg','jpeg','gif','webp','svg','bmp','tiff','ico'].includes(ext)

  if (isImg) return svgIconDataUri('IMG', '#9b59b6')

  const map = {
    pdf: ['PDF', '#e74c3c'],
    doc: ['DOC', '#3498db'], docx: ['DOC', '#3498db'],
    xls: ['XLS', '#2ecc71'], xlsx: ['XLS', '#2ecc71'], csv: ['CSV', '#27ae60'],
    ppt: ['PPT', '#e67e22'], pptx: ['PPT', '#e67e22'],
    txt: ['TXT', '#7f8c8d'], log: ['LOG', '#7f8c8d'], md: ['MD', '#95a5a6'],
    json: ['JSON', '#f1c40f'], yaml: ['YML', '#f39c12'], yml: ['YML', '#f39c12'],
    zip: ['ZIP', '#8e44ad'], rar: ['ZIP', '#8e44ad'], '7z': ['ZIP', '#8e44ad'], tar: ['ZIP', '#8e44ad'], gz: ['ZIP', '#8e44ad'],
    py: ['PY', '#3572A5'], js: ['JS', '#f1e05a'], ts: ['TS', '#3178c6'], jsx: ['JSX', '#61dafb'], tsx: ['TSX', '#61dafb'],
    html: ['HTML', '#e34c26'], css: ['CSS', '#563d7c'], scss: ['SCSS', '#c6538c'],
    mp3: ['AUD', '#27ae60'], wav: ['AUD', '#27ae60'], flac: ['AUD', '#27ae60'],
    mp4: ['VID', '#8e44ad'], mov: ['VID', '#8e44ad'], avi: ['VID', '#8e44ad'], mkv: ['VID', '#8e44ad']
  }

  const [label, color] = map[ext] || ['FILE', '#95a5a6']
  return svgIconDataUri(label, color)
}

const svgIconDataUri = (label, bgColor) => {
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
  <svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 48 48'>
    <defs>
      <style>
        .t{font: 700 16px \"Inter, Arial\"; fill: #f2f2f2}
      </style>
    </defs>
    <rect x='0' y='0' width='48' height='48' rx='8' ry='8' fill='${bgColor}' />
    <text x='50%' y='58%' text-anchor='middle' class='t'>${(label || '').toUpperCase().slice(0,4)}</text>
  </svg>`
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

// Auto-scroll to bottom
watch(
  () => chatMessages.value.length,
  async () => {
    await nextTick()
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
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

/* Chat Box */
.chat-box {
  flex: 1;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(5px);
}

.chat-messages::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}
.chat-messages::-webkit-scrollbar-thumb {
  background-color: rgba(160, 160, 160, 0.28);
  border-radius: 8px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
.chat-messages::-webkit-scrollbar-thumb:hover {
  background-color: rgba(160, 160, 160, 0.48);
}

.chat-messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Chat Notification */
.chat-notification {
  display: flex;
  justify-content: center;
  margin: 10px 0;
}

.notification-content {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 8px 16px;
  max-width: 80%;
  animation: slideIn 0.3s ease-out;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.notification-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  font-weight: 500;
  text-align: center;
}

.chat-notification-warning .notification-content {
  background: rgba(255, 204, 0, 0.12);
  border-color: rgba(255, 204, 0, 0.4);
}

.chat-notification-warning .notification-text {
  color: #ffe082;
}

.chat-notification-error .notification-content {
  background: rgba(255, 82, 82, 0.12);
  border-color: rgba(255, 82, 82, 0.4);
}

.chat-notification-error .notification-content {
  color: #ffcccc;
}

.message-timestamp {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-left: 8px;
  flex-shrink: 0;
}

.chat-notification .message-timestamp {
  margin-left: 0;
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.3);
}

.dialogue-right .message-timestamp {
  margin-left: 0;
  margin-right: 8px;
}

.user-name {
  display: flex;
  align-items: baseline;
  justify-content: flex-start;
}

.dialogue-right .user-name {
  flex-direction: row-reverse;
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

/* Input Area */
.input-area {
  flex: 0 0 auto;
  min-height: 120px;
}

.input-shell {
  height: 100%;
  display: flex;
  flex-direction: row;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  transition: all 0.3s ease;
  backdrop-filter: blur(5px);
  position: relative;
}

.input-shell:focus-within {
  border-color: rgba(255, 255, 255, 0.3);
  background-color: rgba(255, 255, 255, 0.05);
}

.input-shell.glow {
  border-color: #aaffcd;
  box-shadow: 0 0 15px rgba(153, 234, 249, 0.3);
  animation: borderPulse 4s ease-in-out infinite alternate;
}

.input-shell.drag-active {
  border-color: rgba(153, 234, 249, 0.9);
  background-color: rgba(153, 234, 249, 0.08);
  box-shadow: 0 0 20px rgba(153, 234, 249, 0.35);
}

.drag-overlay {
  position: absolute;
  inset: 6px;
  border-radius: 10px;
  border: 1px dashed rgba(153, 234, 249, 0.6);
  background: rgba(10, 20, 24, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.drag-overlay-content {
  font-size: 12px;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: rgba(153, 234, 249, 0.95);
}

@keyframes borderPulse {
  0% { border-color: #aaffcd; box-shadow: 0 0 0px rgba(170, 255, 205, 0.15); }
  50% { border-color: #99eaf9; box-shadow: 0 0 8px rgba(153, 234, 249, 0.35); }
   100% { border-color: #a0c4ff; box-shadow: 0 0 0px rgba(160, 196, 255, 0.2); }
}

.task-input {
  flex: 1;
  padding: 16px;
  border: none;
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  resize: none;
  outline: none;
  background: transparent;
  color: #f2f2f2;
  line-height: 1.5;
}

.task-input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.input-footer {
  display: flex;
  justify-content: flex-end;
  padding: 10px 12px 10px 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.input-footer-buttons {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-direction: column;
  height: 100%;
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
}

.status-active {
  color: #a0c4ff;
  background: rgba(160, 196, 255, 0.1);
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

/* Graph Panel */
.graph-panel {
  flex: 1;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  backdrop-filter: blur(5px);
}

.vueflow-graph {
  width: 100%;
  height: 100%;
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
</style>
