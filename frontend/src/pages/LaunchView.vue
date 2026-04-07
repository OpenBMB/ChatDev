<template>
  <div class="launch-view">
    <div class="launch-bg"></div>
    <div class="header">
      <div class="header-copy">
        <div class="header-eyebrow">{{ t('launch.eyebrow') }}</div>
        <h1>{{ t('launch.title') }}</h1>
        <p class="header-subtitle">{{ t('launch.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <button class="back-button" @click="goBackToWorkbench">
          {{ t('launch.backToWorkbench') }}
        </button>
        <div class="header-status-pill">{{ localizedStatus }}</div>
      <button class="settings-button" @click="showSettingsModal = true" :title="t('launch.settings')">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
      </div>
    </div>
    <div class="content">
      <!-- Left panel -->
      <div class="left-panel">
        <div v-if="viewMode === 'chat'" class="chat-panel chat-panel-fullscreen">
          <div class="chat-panel-content">
            <div class="chat-box">
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
                    :html-content="message.htmlContent || renderMarkdown(message.text)"
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
                      {{ t('launch.loadingImage') }}
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
                        :alt="message.fileName || t('launch.loadingImage')"
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
                        {{ t('launch.download') }}
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
                      {{ message.loading ? t('launch.preparing') : t('launch.download') }}
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
                  :placeholder="taskInputPlaceholder"
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
                          {{ isUploadingAttachment ? t('launch.uploading') : t('launch.uploadFile') }}
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
                            {{ t('launch.noFilesUploaded') }}
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
                  <div class="drag-overlay-content">{{ t('launch.dropFiles') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="graph-panel">
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

      </div>

      <!-- Right panel -->
      <div class="right-panel">
        <div class="control-section">
          <label class="section-label">{{ t('launch.runMode') }}</label>
          <div class="run-mode-grid">
            <button
              v-for="mode in launchModes"
              :key="mode.id"
              type="button"
              :class="['run-mode-card', { active: launchMode === mode.id }]"
              @click="handleLaunchModeClick(mode.id)"
            >
              <span class="run-mode-title">{{ mode.title }}</span>
              <span class="run-mode-desc">{{ mode.description }}</span>
            </button>
          </div>

          <label class="section-label">{{ t('launch.workflowSelection') }}</label>
      <div
        class="select-wrapper custom-file-selector"
        ref="fileSelectorWrapperRef"
      >
        <input
          ref="fileSelectorInputRef"
          v-model="fileSearchQuery"
          type="text"
          class="file-selector-input"
          :placeholder="loading ? t('launch.loadingSelection') : t('launch.selectWorkflow')"
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
              <span
                v-else-if="workflow.organization"
                class="file-desc"
              >
                {{ workflow.organization }}
              </span>
            </li>
            <li
              v-if="!filteredWorkflowFiles.length"
              class="file-empty"
            >
              {{ t('launch.noResults') }}
            </li>
          </ul>
        </Transition>
      </div>

          <label class="section-label">{{ t('launch.modelProfile') }}</label>
          <div class="select-wrapper">
            <select
              v-model="selectedModelProfileId"
              class="file-selector profile-selector"
              :disabled="isWorkflowRunning"
            >
              <option value="">{{ t('launch.useWorkflowDefaults') }}</option>
              <option
                v-for="profile in availableModelProfiles"
                :key="profile.id"
                :value="profile.id"
              >
                {{ profile.label || t('launch.unnamedProfile') }}
              </option>
            </select>
            <div class="select-arrow">▼</div>
          </div>
          <div class="profile-hint">
            {{ selectedProfileSummary }}
          </div>
          <div
            v-if="selectedModelProfile && workflowSupportsSelectedProfile"
            class="profile-hint profile-hint-success"
          >
            {{ t('launch.profileReferences') }}
            {{ supportedProfileVariableLabels.join(', ') }}
          </div>
          <div
            v-else-if="selectedModelProfile"
            class="profile-hint profile-hint-warning"
          >
            {{ t('launch.profileUnsupported') }}
          </div>
          <div
            v-else-if="!availableModelProfiles.length"
            class="profile-hint"
          >
            {{ t('launch.noProfilesHint') }}
          </div>

          <div class="launch-quick-row">
            <div class="status-display" :class="{ 'status-active': status === 'Running...' }">
              {{ localizedStatus }}
            </div>
            <div class="view-toggle">
              <button
                class="toggle-button"
                :class="{ active: viewMode === 'chat' }"
                @click="viewMode = 'chat'"
              >
                {{ t('launch.chat') }}
              </button>
              <button
                class="toggle-button"
                :class="{ active: viewMode === 'graph' }"
                @click="switchToGraph"
              >
                {{ t('launch.graph') }}
              </button>
            </div>
          </div>

          <div class="button-section">
            <button
              class="launch-button"
              :class="{ glow: shouldGlow, 'is-sending': isWorkflowRunning }"
              @click="handleButtonClick"
              :disabled="loading || (isWorkflowRunning && !taskPrompt.trim()) || (!isWorkflowRunning && status !== 'Completed' && status !== 'Cancelled' && !isConnectionReady)"
            >
              {{ buttonLabel }}
            </button>

            <button
              class="cancel-button"
              :disabled="status !== 'Running...'"
              @click="cancelWorkflow"
            >
              {{ t('launch.cancel') }}
            </button>

            <button
              class="download-button"
              :disabled="status !== 'Completed' && status !== 'Cancelled'"
              @click="downloadLogs"
            >
              {{ t('launch.downloadLogs') }}
            </button>
          </div>

          <button
            class="advanced-toggle-button"
            type="button"
            @click="showAdvancedPanel = !showAdvancedPanel"
          >
            {{ showAdvancedPanel ? t('launch.hideAdvancedPanel') : t('launch.showAdvancedPanel') }}
          </button>

          <TeamPanel
            v-if="showAdvancedPanel"
            :team-state="teamState"
            :token-usage="latestTokenUsage"
            :disabled="loading || !selectedFile"
            @save-goal="handleGoalSave"
            @save-plan="handlePlanSave"
            @save-memory="handleMemorySave"
            @create-approval="handleApprovalCreate"
            @resolve-approval="handleApprovalResolve"
            @accept-review-suggestion="handleAcceptReviewSuggestion"
            @dismiss-review-suggestion="handleDismissReviewSuggestion"
            @replay-from-task="handleReplayFromTask"
          />
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
import { t } from '../utils/i18n.js'
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true
})

const renderMarkdown = (text) => {
  return md.render(text || '')
}

const createEmptyTeamState = () => ({
  mode: 'human_governed',
  goal: '',
  workflow: {
    name: '',
    description: '',
    organization: '',
    team_mode: 'human_governed',
  },
  plan: {
    summary: '',
    tasks: [],
  },
  memory: {
    facts: [],
    assumptions: [],
    open_questions: [],
    decisions: [],
  },
  approvals: [],
  artifacts: {
    task_outputs: {},
    replay_context: {
      target_task_id: '',
      target_task_title: '',
      retained_tasks: [],
      retained_node_ids: [],
      text: '',
    },
    token_usage_snapshot: {
      total_usage: {},
      node_usages: {},
    },
    review: {
      last_directive: {},
    },
  },
  replay: {
    target_task_id: '',
    target_task_title: '',
    requested_at: null,
  },
  meta: {
    updated_at: null,
    source: 'local_seed',
  },
})

const normalizeLineList = (values) => {
  if (typeof values === 'string') {
    return values
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  if (!Array.isArray(values)) {
    return []
  }
  return values
    .map((item) => String(item || '').trim())
    .filter(Boolean)
}

const normalizeTaskList = (values) => {
  if (typeof values === 'string') {
    values = values.split('\n')
  }
  if (!Array.isArray(values)) {
    return []
  }
  return values
    .map((item, index) => {
      if (typeof item === 'object' && item !== null) {
        const title = String(item.title || item.text || '').trim()
        if (!title) return null
        return {
          id: String(item.id || `task-${index + 1}`),
          title,
          status: String(item.status || 'pending'),
          owner: String(item.owner || ''),
          node_id: String(item.node_id || item.owner || title),
          started_at: item.started_at || null,
          completed_at: item.completed_at || null,
          output_preview: String(item.output_preview || ''),
          output_size: Number(item.output_size || 0),
          reused_replay_output: Boolean(item.reused_replay_output),
          reused_at: item.reused_at || null,
          replay_injected_predecessors: Array.isArray(item.replay_injected_predecessors)
            ? item.replay_injected_predecessors.map((value) => String(value || '').trim()).filter(Boolean)
            : [],
          injected_at: item.injected_at || null,
        }
      }
      const title = String(item || '').trim()
      if (!title) return null
      return {
        id: `task-${index + 1}`,
        title,
        status: 'pending',
        owner: '',
        node_id: title,
        started_at: null,
        completed_at: null,
        output_preview: '',
        output_size: 0,
        reused_replay_output: false,
        reused_at: null,
        replay_injected_predecessors: [],
        injected_at: null,
      }
    })
    .filter(Boolean)
}

const normalizeArtifacts = (values) => {
  const taskOutputs = (values && typeof values === 'object' && values.task_outputs && typeof values.task_outputs === 'object')
    ? values.task_outputs
    : {}
  const replayContext = (values && typeof values === 'object' && values.replay_context && typeof values.replay_context === 'object')
    ? values.replay_context
    : {}
  const review = (values && typeof values === 'object' && values.review && typeof values.review === 'object')
    ? values.review
    : {}
  const tokenUsageSnapshot = (values && typeof values === 'object' && values.token_usage_snapshot && typeof values.token_usage_snapshot === 'object')
    ? values.token_usage_snapshot
    : {}
  const lastDirective = (review && typeof review.last_directive === 'object' && review.last_directive !== null)
    ? review.last_directive
    : {}

  return {
    task_outputs: Object.fromEntries(
      Object.entries(taskOutputs).map(([taskId, item]) => [
        String(taskId || '').trim(),
        {
          task_id: String(item?.task_id || taskId || '').trim(),
          node_id: String(item?.node_id || '').trim(),
          title: String(item?.title || '').trim(),
          status: String(item?.status || 'pending'),
          output_preview: String(item?.output_preview || ''),
          output_text: String(item?.output_text || ''),
          output_size: Number(item?.output_size || 0),
          reused_replay_output: Boolean(item?.reused_replay_output),
          reused_at: item?.reused_at || null,
          replay_injected_predecessors: Array.isArray(item?.replay_injected_predecessors)
            ? item.replay_injected_predecessors.map((value) => String(value || '').trim()).filter(Boolean)
            : [],
          injected_at: item?.injected_at || null,
          updated_at: item?.updated_at || null,
        },
      ]).filter(([taskId]) => Boolean(taskId))
    ),
    replay_context: {
      target_task_id: String(replayContext?.target_task_id || '').trim(),
      target_task_title: String(replayContext?.target_task_title || '').trim(),
      retained_tasks: Array.isArray(replayContext?.retained_tasks)
        ? replayContext.retained_tasks
            .map((item) => {
              if (!item || typeof item !== 'object') {
                return null
              }
              const taskId = String(item.task_id || '').trim()
              const title = String(item.title || taskId).trim()
              const preview = String(item.preview || '').trim()
              if (!taskId || !title) {
                return null
              }
              return {
                task_id: taskId,
                title,
                preview,
                node_id: String(item.node_id || '').trim(),
                output_text: String(item.output_text || '').trim(),
              }
            })
            .filter(Boolean)
        : [],
      retained_node_ids: Array.isArray(replayContext?.retained_node_ids)
        ? replayContext.retained_node_ids
            .map((item) => String(item || '').trim())
            .filter(Boolean)
        : [],
      text: String(replayContext?.text || '').trim(),
    },
    token_usage_snapshot: {
      total_usage: {
        input_tokens: Number(tokenUsageSnapshot?.total_usage?.input_tokens || 0),
        output_tokens: Number(tokenUsageSnapshot?.total_usage?.output_tokens || 0),
        total_tokens: Number(tokenUsageSnapshot?.total_usage?.total_tokens || 0),
      },
      node_usages: Object.fromEntries(
        Object.entries(tokenUsageSnapshot?.node_usages || {})
          .map(([nodeId, item]) => [
            String(nodeId || '').trim(),
            {
              input_tokens: Number(item?.input_tokens || 0),
              output_tokens: Number(item?.output_tokens || 0),
              total_tokens: Number(item?.total_tokens || 0),
            },
          ])
          .filter(([nodeId]) => Boolean(nodeId))
      ),
    },
    review: {
      last_directive: {
        reviewer_node_id: String(lastDirective?.reviewer_node_id || '').trim(),
        verdict: String(lastDirective?.verdict || '').trim(),
        approval_id: String(lastDirective?.approval_id || '').trim(),
        replay_target_id: String(lastDirective?.replay_target_id || '').trim(),
        replay_target_title: String(lastDirective?.replay_target_title || '').trim(),
        note: String(lastDirective?.note || '').trim(),
        created_at: lastDirective?.created_at || null,
      },
    },
  }
}

const normalizeApprovalList = (values) => {
  if (!Array.isArray(values)) {
    return []
  }
  return values
    .map((item) => {
      if (typeof item !== 'object' || item === null) {
        const title = String(item || '').trim()
        if (!title) return null
        return {
          id: `approval-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          title,
          status: 'open',
          blocking: false,
          note: '',
          created_at: Date.now(),
          resolved_at: null,
        }
      }
      const title = String(item.title || '').trim()
      if (!title) return null
      return {
        id: String(item.id || `approval-${Date.now()}-${Math.random().toString(16).slice(2)}`),
        title,
        status: item.status === 'resolved' ? 'resolved' : 'open',
        blocking: Boolean(item.blocking),
        note: String(item.note || ''),
        created_at: item.created_at || Date.now(),
        resolved_at: item.resolved_at || null,
      }
    })
    .filter(Boolean)
}

const normalizeTeamState = (state = {}) => {
  const base = createEmptyTeamState()
  const workflow = typeof state.workflow === 'object' && state.workflow !== null ? state.workflow : {}
  const plan = typeof state.plan === 'object' && state.plan !== null ? state.plan : {}
  const memory = typeof state.memory === 'object' && state.memory !== null ? state.memory : {}
  const meta = typeof state.meta === 'object' && state.meta !== null ? state.meta : {}

  return {
    mode: state.mode || base.mode,
    goal: String(state.goal || '').trim(),
    workflow: {
      name: String(workflow.name || '').trim(),
      description: String(workflow.description || '').trim(),
      organization: String(workflow.organization || '').trim(),
      team_mode: String(workflow.team_mode || state.mode || base.workflow.team_mode).trim() || base.workflow.team_mode,
    },
    plan: {
      summary: String(plan.summary || '').trim(),
      tasks: normalizeTaskList(plan.tasks),
    },
    memory: {
      facts: normalizeLineList(memory.facts),
      assumptions: normalizeLineList(memory.assumptions),
      open_questions: normalizeLineList(memory.open_questions),
      decisions: normalizeLineList(memory.decisions),
    },
    approvals: normalizeApprovalList(state.approvals),
    artifacts: normalizeArtifacts(state.artifacts),
    replay: {
      target_task_id: String(state?.replay?.target_task_id || '').trim(),
      target_task_title: String(state?.replay?.target_task_title || '').trim(),
      requested_at: state?.replay?.requested_at || null,
    },
    meta: {
      updated_at: meta.updated_at || null,
      source: meta.source || 'local_seed',
    },
  }
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
import TeamPanel from '../components/TeamPanel.vue'
import { buildWorkflowPath, getLastWorkflowName, normalizeStoredWorkflowName, setLastWorkflowName } from '../utils/workflowSession.js'

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
const selectedModelProfileId = ref(configStore.ACTIVE_MODEL_PROFILE_ID || '')

const availableModelProfiles = computed(() => (
  Array.isArray(configStore.MODEL_PROFILES) ? configStore.MODEL_PROFILES : []
))

const selectedModelProfile = computed(() => (
  availableModelProfiles.value.find((profile) => profile.id === selectedModelProfileId.value) || null
))

const teamState = ref(createEmptyTeamState())
const latestTokenUsage = ref({})

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
    htmlContent: '',
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
  runningLoadingEntries.value += 1
  if (runningLoadingEntries.value === 1) {
    startLoadingTimer()
  }
  return entry
}

// Finish a loading entry
const finishLoadingEntry = (nodeId, baseKey) => {
  const nodeState = nodesLoadingMessagesMap.get(nodeId)
  if (!nodeState || !baseKey) return null

  const key = nodeState.baseKeyToKey.get(baseKey)
  const entry = key ? nodeState.entryMap.get(key) : null
  if (!entry) return null

  const wasRunning = entry.status === 'running'
  entry.status = 'done'
  entry.endedAt = Date.now()
  nodeState.baseKeyToKey.delete(baseKey)
  if (wasRunning) {
    runningLoadingEntries.value = Math.max(0, runningLoadingEntries.value - 1)
    if (runningLoadingEntries.value === 0) {
      stopLoadingTimer()
    }
  }
  return entry
}

// Finish all running entries when a node ends or cancels
const finalizeAllLoadingEntries = (nodeState, endedAt = Date.now()) => {
  if (!nodeState) return
  let finishedCount = 0
  for (const entry of nodeState.entryMap.values()) {
    if (entry.status === 'running') {
      entry.status = 'done'
      entry.endedAt = endedAt
      finishedCount += 1
    }
  }
  nodeState.baseKeyToKey.clear()
  if (finishedCount) {
    runningLoadingEntries.value = Math.max(0, runningLoadingEntries.value - finishedCount)
    if (runningLoadingEntries.value === 0) {
      stopLoadingTimer()
    }
  }
}

// Global timer for updating loading bubble durations
const now = ref(Date.now())
let loadingTimerInterval = null
const runningLoadingEntries = ref(0)

const startLoadingTimer = () => {
  if (loadingTimerInterval) return
  loadingTimerInterval = setInterval(() => {
    now.value = Date.now()
  }, 1000)
}

const stopLoadingTimer = () => {
  if (!loadingTimerInterval) return
  clearInterval(loadingTimerInterval)
  loadingTimerInterval = null
}

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
const launchMode = ref('chat')
const showAdvancedPanel = ref(false)

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
  return workflowFiles.value.filter((workflow) => {
    const name = workflow.name?.toLowerCase?.() || ''
    const description = workflow.description?.toLowerCase?.() || ''
    const organization = workflow.organization?.toLowerCase?.() || ''
    return name.includes(query) || description.includes(query) || organization.includes(query)
  })
})

// Button label computed property
const buttonLabel = computed(() => {
  if (isWorkflowRunning.value) {
    return t('launch.send')
  }
  if (status.value === 'Completed' || status.value === 'Cancelled') {
    return t('launch.relaunch')
  }
  if (launchMode.value === 'task') {
    return t('launch.runOnce')
  }
  return t('launch.launch')
})

const taskInputPlaceholder = computed(() => {
  return launchMode.value === 'task'
    ? t('launch.taskRunPlaceholder')
    : t('launch.taskPlaceholder')
})

const launchModes = computed(() => [
  {
    id: 'chat',
    title: t('launch.modeChatTitle'),
    description: t('launch.modeChatDesc'),
  },
  {
    id: 'task',
    title: t('launch.modeTaskTitle'),
    description: t('launch.modeTaskDesc'),
  },
  {
    id: 'batch',
    title: t('launch.modeBatchTitle'),
    description: t('launch.modeBatchDesc'),
  },
])

const localizedStatus = computed(() => {
  const statusMap = t('launch.statusMap') || {}
  return statusMap[status.value] || status.value
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

const workflowPlaceholderSupport = computed(() => {
  const serialized = JSON.stringify(workflowYaml.value || {})
  return {
    modelName: serialized.includes('${MODEL_NAME}'),
    baseUrl: serialized.includes('${BASE_URL}'),
    apiKey: serialized.includes('${API_KEY}')
  }
})

const supportedProfileVariableLabels = computed(() => {
  const labels = []
  if (workflowPlaceholderSupport.value.modelName) labels.push('MODEL_NAME')
  if (workflowPlaceholderSupport.value.baseUrl) labels.push('BASE_URL')
  if (workflowPlaceholderSupport.value.apiKey) labels.push('API_KEY')
  return labels
})

const workflowSupportsSelectedProfile = computed(() => (
  supportedProfileVariableLabels.value.length > 0
))

const selectedProfileSummary = computed(() => {
  if (!selectedModelProfile.value) {
    return t('launch.waitingForDefaults')
  }

  const label = selectedModelProfile.value.label?.trim() || t('launch.unnamedProfile')
  const model = selectedModelProfile.value.modelName?.trim() || t('launch.noModelName')
  return `${label} · ${model}`
})

const selectedProfileExecutionVariables = computed(() => {
  if (!selectedModelProfile.value) {
    return null
  }

  const variables = {}
  const { modelName, baseUrl, apiKey } = selectedModelProfile.value
  if (modelName?.trim()) {
    variables.MODEL_NAME = modelName.trim()
  }
  if (baseUrl?.trim()) {
    variables.BASE_URL = baseUrl.trim()
  }
  if (apiKey?.trim()) {
    variables.API_KEY = apiKey.trim()
  }
  return Object.keys(variables).length ? variables : null
})

const canSyncTeamState = () => Boolean(
  ws &&
  sessionId &&
  selectedFile.value &&
  !['Waiting for workflow selection...', 'Waiting for file selection...', 'Connecting...', 'Waiting for launch...'].includes(status.value)
)

const applyTeamStateSnapshot = (nextState) => {
  teamState.value = normalizeTeamState(nextState)
}

const seedTeamStateFromWorkflow = () => {
  if (!selectedFile.value) {
    applyTeamStateSnapshot(createEmptyTeamState())
    return
  }

  const graph = workflowYaml.value?.graph || {}
  const seededTasks = (teamState.value?.plan?.tasks && teamState.value.plan.tasks.length)
    ? teamState.value.plan.tasks
    : (Array.isArray(graph.nodes)
        ? graph.nodes
            .map((node) => {
              const nodeId = String(node?.id || '').trim()
              if (!nodeId) return null
              return {
                id: nodeId,
                title: nodeId,
                status: 'pending',
                owner: nodeId,
                node_id: nodeId,
              }
            })
            .filter(Boolean)
        : [])
  applyTeamStateSnapshot({
    mode: graph.team_mode || 'human_governed',
    goal: teamState.value?.goal || taskPrompt.value.trim(),
    workflow: {
      name: selectedFile.value,
      description: graph.description || '',
      organization: graph.organization || '',
      team_mode: graph.team_mode || 'human_governed',
    },
    plan: {
      summary: teamState.value?.plan?.summary || graph.description || graph.initial_instruction || '',
      tasks: seededTasks,
    },
    memory: teamState.value?.memory || createEmptyTeamState().memory,
    approvals: teamState.value?.approvals || [],
    artifacts: teamState.value?.artifacts || createEmptyTeamState().artifacts,
    replay: teamState.value?.replay || createEmptyTeamState().replay,
    meta: {
      updated_at: Date.now(),
      source: 'local_seed',
    },
  })
}

const syncTeamStateToSession = () => {
  if (!canSyncTeamState()) {
    return
  }
  ws.send(JSON.stringify({
    type: 'team_state_update',
    data: {
      team_state: teamState.value,
    },
  }))
}

const handleGoalSave = (goal) => {
  applyTeamStateSnapshot({
    ...teamState.value,
    goal,
    meta: {
      updated_at: Date.now(),
      source: 'local_edit',
    },
  })
  syncTeamStateToSession()
}

const handlePlanSave = (plan) => {
  applyTeamStateSnapshot({
    ...teamState.value,
    plan,
    meta: {
      updated_at: Date.now(),
      source: 'local_edit',
    },
  })
  syncTeamStateToSession()
}

const handleMemorySave = (memory) => {
  applyTeamStateSnapshot({
    ...teamState.value,
    memory,
    meta: {
      updated_at: Date.now(),
      source: 'local_edit',
    },
  })
  syncTeamStateToSession()
}

const handleApprovalCreate = (approval) => {
  const nextApprovals = [
    ...(Array.isArray(teamState.value?.approvals) ? teamState.value.approvals : []),
    {
      id: `approval-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      created_at: Date.now(),
      resolved_at: null,
      ...approval,
    },
  ]
  applyTeamStateSnapshot({
    ...teamState.value,
    approvals: nextApprovals,
    meta: {
      updated_at: Date.now(),
      source: 'local_edit',
    },
  })
  syncTeamStateToSession()
}

const handleApprovalResolve = (approvalId) => {
  const nextApprovals = (teamState.value?.approvals || []).map((approval) => (
    approval.id === approvalId
      ? {
          ...approval,
          status: 'resolved',
          resolved_at: Date.now(),
        }
      : approval
  ))

  applyTeamStateSnapshot({
    ...teamState.value,
    approvals: nextApprovals,
    meta: {
      updated_at: Date.now(),
      source: 'local_edit',
    },
  })
  syncTeamStateToSession()
}

const handleAcceptReviewSuggestion = () => {
  const directive = teamState.value?.artifacts?.review?.last_directive || {}
  const approvalId = String(directive.approval_id || '').trim()
  if (!approvalId) {
    return
  }
  handleApprovalResolve(approvalId)
}

const handleDismissReviewSuggestion = () => {
  const directive = teamState.value?.artifacts?.review?.last_directive || {}
  const approvalId = String(directive.approval_id || '').trim()
  const nextApprovals = (teamState.value?.approvals || []).map((approval) => (
    approval.id === approvalId
      ? {
          ...approval,
          status: 'resolved',
          resolved_at: Date.now(),
          note: approval.note || t('team.reviewSuggestionDismissed'),
        }
      : approval
  ))

  applyTeamStateSnapshot({
    ...teamState.value,
    approvals: nextApprovals,
    artifacts: {
      ...(teamState.value?.artifacts || {}),
      review: {
        last_directive: {},
      },
      replay_context: createEmptyTeamState().artifacts.replay_context,
    },
    replay: createEmptyTeamState().replay,
    meta: {
      updated_at: Date.now(),
      source: 'local_review_dismiss',
    },
  })
  syncTeamStateToSession()
}

const handleReplayFromTask = (taskId) => {
  const tasks = normalizeTaskList(teamState.value?.plan?.tasks)
  const targetIndex = tasks.findIndex((task) => task.id === taskId)
  if (targetIndex < 0) {
    return
  }

  const targetTask = tasks[targetIndex]
  const replayTasks = tasks.map((task, index) => ({
    ...task,
    status: index < targetIndex ? 'done' : 'pending',
    started_at: index < targetIndex ? task.started_at || null : null,
    completed_at: index < targetIndex ? task.completed_at || Date.now() : null,
    output_preview: index < targetIndex ? task.output_preview || '' : '',
    output_size: index < targetIndex ? Number(task.output_size || 0) : 0,
  }))
  const currentArtifacts = teamState.value?.artifacts?.task_outputs || {}
  const replayArtifacts = Object.fromEntries(
    replayTasks
      .filter((task, index) => index < targetIndex)
      .map((task) => {
        const existingArtifact = currentArtifacts[task.id] || {}
        return [
          task.id,
          {
            task_id: task.id,
            node_id: task.node_id || task.owner || task.title,
            title: task.title,
            status: task.status,
            output_preview: task.output_preview || existingArtifact.output_preview || '',
            output_size: Number(task.output_size || existingArtifact.output_size || 0),
            updated_at: existingArtifact.updated_at || Date.now(),
          },
        ]
      })
  )

  applyTeamStateSnapshot({
    ...teamState.value,
    plan: {
      ...(teamState.value?.plan || {}),
      tasks: replayTasks,
    },
    artifacts: {
      task_outputs: replayArtifacts,
    },
    replay: {
      target_task_id: targetTask.id,
      target_task_title: targetTask.title,
      requested_at: Date.now(),
    },
    meta: {
      updated_at: Date.now(),
      source: 'local_replay_request',
    },
  })
  syncTeamStateToSession()
}

// const goBack = () => {
//   router.push('/workflows')
// }

const goBackToWorkbench = () => {
  const currentWorkflow = normalizeStoredWorkflowName(selectedFile.value || route.query?.workflow || getLastWorkflowName())
  router.push(buildWorkflowPath(currentWorkflow))
}

const goToBatchRun = () => {
  const currentWorkflow = normalizeStoredWorkflowName(selectedFile.value || route.query?.workflow || getLastWorkflowName())
  router.push({
    path: '/batch-run',
    query: currentWorkflow ? { workflow: `${currentWorkflow}.yaml` } : {},
  })
}

const handleLaunchModeClick = (modeId) => {
  if (modeId === 'batch') {
    goToBatchRun()
    return
  }
  launchMode.value = modeId
  viewMode.value = 'chat'
}

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
  setLastWorkflowName(normalizeStoredWorkflowName(fileName))
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

const syncSelectedModelProfile = () => {
  const profiles = availableModelProfiles.value
  if (!profiles.length) {
    selectedModelProfileId.value = ''
    return
  }

  if (profiles.some((profile) => profile.id === selectedModelProfileId.value)) {
    return
  }

  if (configStore.ACTIVE_MODEL_PROFILE_ID && profiles.some((profile) => profile.id === configStore.ACTIVE_MODEL_PROFILE_ID)) {
    selectedModelProfileId.value = configStore.ACTIVE_MODEL_PROFILE_ID
    return
  }

  selectedModelProfileId.value = profiles[0].id
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
  setLastWorkflowName(normalizeStoredWorkflowName(fileName))

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

  const htmlContent = renderMarkdown(text)
  chatMessages.value.push({
    type: 'dialogue',
    name: name,
    text: text,
    htmlContent,
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
    alert(t('launch.sessionNotReady'))
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
          alert(result?.message || t('launch.uploadFailed'))
        }
      } catch (error) {
        console.error('Failed to upload attachment:', error)
        alert(t('launch.uploadFailed'))
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
          alert(result?.message || t('launch.recordingUploadFailed'))
        }
      } catch (error) {
        console.error('Failed to upload recording:', error)
        alert(t('launch.recordingUploadFailed'))
      } finally {
        isUploadingAttachment.value = false
        cleanupRecording()
      }
    }

    mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event.error)
      alert(t('launch.recordingError'))
      cleanupRecording()
    }

    mediaRecorder.start()
    isRecording.value = true
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert(t('launch.microphoneAccessError'))
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
    name: message.fileName || t('launch.loadingImage')
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
    seedTeamStateFromWorkflow()
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
      addChatNotification(t('launch.noInitialInstruction'))
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
    addChatNotification(t('launch.yamlLoadFailed'))
    nodeSpriteMap.value.clear()
  }

  seedTeamStateFromWorkflow()

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
      alert(t('launch.chooseWorkflowAlert'))
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
        alert(t('launch.missingSession'))
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
    alert(t('launch.websocketError'))
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
watch(selectedFile, (newFile, oldFile) => {
  taskPrompt.value = ''
  fileSearchQuery.value = newFile || ''
  isFileSearchDirty.value = false

  if (newFile !== oldFile) {
    applyTeamStateSnapshot(createEmptyTeamState())
  }

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

watch(
  () => [
    configStore.ACTIVE_MODEL_PROFILE_ID,
    availableModelProfiles.value.map((profile) => profile.id).join('|')
  ],
  () => {
    syncSelectedModelProfile()
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  syncSelectedModelProfile()
  loadWorkflows()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  unlockBodyScroll()
  resetConnectionState()
  cleanupRecording()

  stopLoadingTimer()
  runningLoadingEntries.value = 0
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
    alert(t('launch.chooseWorkflowAlert'))
    return
  }

  const trimmedPrompt = taskPrompt.value.trim()
  const attachmentIds = uploadedAttachments.value.map((attachment) => attachment.attachmentId)
  const attachmentNames = uploadedAttachments.value.map(
    (attachment) => attachment.name || attachment.attachmentId
  )
  const executionVariables = selectedProfileExecutionVariables.value
  const currentTasks = normalizeTaskList(teamState.value?.plan?.tasks)
  const replayTargetId = String(teamState.value?.replay?.target_task_id || '').trim()
  const replayTargetIndex = replayTargetId
    ? currentTasks.findIndex((task) => task.id === replayTargetId)
    : -1
  const hasReplayTarget = replayTargetIndex >= 0
  const currentArtifacts = teamState.value?.artifacts?.task_outputs || {}
  const resetTasks = currentTasks.map((task, index) => ({
    ...task,
    status: hasReplayTarget && index < replayTargetIndex ? 'done' : 'pending',
    started_at: hasReplayTarget && index < replayTargetIndex ? task.started_at || null : null,
    completed_at: hasReplayTarget && index < replayTargetIndex ? task.completed_at || Date.now() : null,
    output_preview: hasReplayTarget && index < replayTargetIndex ? task.output_preview || '' : '',
    output_size: hasReplayTarget && index < replayTargetIndex ? Number(task.output_size || 0) : 0,
  }))
  const executionArtifacts = hasReplayTarget
    ? Object.fromEntries(
        resetTasks
          .filter((task, index) => index < replayTargetIndex)
          .map((task) => {
            const existingArtifact = currentArtifacts[task.id] || {}
            return [
              task.id,
              {
                task_id: task.id,
                node_id: task.node_id || task.owner || task.title,
                title: task.title,
                status: task.status,
                output_preview: task.output_preview || existingArtifact.output_preview || '',
                output_size: Number(task.output_size || existingArtifact.output_size || 0),
                updated_at: existingArtifact.updated_at || Date.now(),
              },
            ]
          })
      )
    : {}
  const executionTeamState = normalizeTeamState({
    ...teamState.value,
    goal: teamState.value?.goal || trimmedPrompt,
    workflow: {
      ...(teamState.value?.workflow || {}),
      name: selectedFile.value,
      description: workflowYaml.value?.graph?.description || teamState.value?.workflow?.description || '',
      organization: workflowYaml.value?.graph?.organization || teamState.value?.workflow?.organization || '',
      team_mode: workflowYaml.value?.graph?.team_mode || teamState.value?.workflow?.team_mode || 'human_governed',
    },
    plan: {
      ...(teamState.value?.plan || {}),
      tasks: resetTasks,
    },
    artifacts: {
      task_outputs: executionArtifacts,
      replay_context: hasReplayTarget
        ? {
            target_task_id: replayTargetId,
            target_task_title: String(teamState.value?.replay?.target_task_title || '').trim(),
            retained_tasks: resetTasks
              .filter((task, index) => index < replayTargetIndex && task.status === 'done')
              .map((task) => ({
                task_id: task.id,
                title: task.title,
                preview: task.output_preview || currentArtifacts[task.id]?.output_preview || '',
                node_id: task.node_id || task.owner || task.title,
                output_text: currentArtifacts[task.id]?.output_text || '',
              }))
              .filter((item) => item.preview || item.output_text),
            retained_node_ids: resetTasks
              .filter((task, index) => index < replayTargetIndex && task.status === 'done')
              .map((task) => String(task.node_id || task.owner || task.title || '').trim())
              .filter(Boolean),
            text: '',
          }
        : createEmptyTeamState().artifacts.replay_context,
    },
    replay: teamState.value?.replay || createEmptyTeamState().replay,
    meta: {
      updated_at: Date.now(),
      source: 'launch_request',
    },
  })
  applyTeamStateSnapshot(executionTeamState)
  latestTokenUsage.value = {}

  if (!trimmedPrompt && attachmentIds.length === 0) {
    alert(t('launch.choosePromptAlert'))
    return
  }

  if (
    !ws ||
    !isConnectionReady.value ||
    !sessionId
  ) {
    alert(t('launch.socketNotReadyAlert'))
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
        attachments: attachmentIds,
        variables: executionVariables,
        team_state: executionTeamState,
      })
    })

    if (response.ok) {
      // Clear uploaded attachments
      clearUploadedAttachments()

      const result = await response.json()
      console.log('Workflow launched: ', result)

      const fullMessage = []
      if (selectedModelProfile.value) {
        fullMessage.push(`${t('launch.modelProfileLabel')}: ${selectedProfileSummary.value}`)
      }
      if (trimmedPrompt) {
        fullMessage.push(trimmedPrompt)
      }
      if (executionTeamState?.replay?.target_task_title) {
        fullMessage.push(`${t('team.replayTarget')}: ${executionTeamState.replay.target_task_title}`)
      }
      if (attachmentNames.length) {
        fullMessage.push(`${t('launch.attachmentsLabel')}: ${attachmentNames.join(', ')}`)
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
      alert(`${t('launch.failedToLaunchPrefix')}: ${error.detail || t('common.unknownError')}`)
      shouldGlow.value = true
      if (isConnectionReady.value) {
        status.value = 'Waiting for launch...'
      }
    }
  } catch (error) {
    console.error('Error calling execute API:', error)
    status.value = 'Error'
    alert(`${t('launch.failedToExecutePrefix')}: ${error.message}`)
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
    alert(t('launch.fileDownloadFailed'))
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

  if (msg.type === 'team_state' || msg.type === 'team_state_initialized' || msg.type === 'team_state_updated') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    if (msg.type === 'team_state_initialized') {
      addChatNotification(t('team.teamStateReady'))
    }
  }

  if (msg.type === 'plan_created' || msg.type === 'plan_updated') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    } else if (msg.data?.plan) {
      applyTeamStateSnapshot({
        ...teamState.value,
        plan: msg.data.plan,
      })
    }
  }

  if (msg.type === 'memory_updated') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    } else if (msg.data?.memory) {
      applyTeamStateSnapshot({
        ...teamState.value,
        memory: msg.data.memory,
      })
    }
  }

  if (msg.type === 'replay_requested') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const replayTitle = msg.data?.replay?.target_task_title
    addChatNotification(
      replayTitle ? `${t('team.replaySelected')}: ${replayTitle}` : t('team.replaySelected')
    )
  }

  if (msg.type === 'replay_applied') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const replayTitle = msg.data?.replay?.target_task_title
    addChatNotification(
      replayTitle ? `${t('team.replayApplied')}: ${replayTitle}` : t('team.replayApplied')
    )
  }

  if (msg.type === 'review_replay_suggested') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const reviewer = msg.data?.review?.reviewer_node_id
    const replayTitle = msg.data?.review?.replay_target_title || msg.data?.replay?.target_task_title
    const baseText = reviewer
      ? `${t('team.reviewReplaySuggested')}: ${reviewer}`
      : t('team.reviewReplaySuggested')
    addChatNotification(
      replayTitle ? `${baseText} -> ${replayTitle}` : baseText,
      { type: 'warning' }
    )
  }

  if (msg.type === 'replay_context_attached') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const retainedCount = Array.isArray(msg.data?.replay_context?.retained_tasks)
      ? msg.data.replay_context.retained_tasks.length
      : 0
    const replayTitle = msg.data?.replay?.target_task_title
    const suffix = retainedCount ? ` (${retainedCount})` : ''
    addChatNotification(
      replayTitle
        ? `${t('team.replayContextAttached')}${suffix}: ${replayTitle}`
        : `${t('team.replayContextAttached')}${suffix}`
    )
  }

  if (msg.type === 'replay_ignored') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const replayTitle = msg.data?.replay?.target_task_title
    addChatNotification(
      replayTitle ? `${t('team.replayIgnored')}: ${replayTitle}` : t('team.replayIgnored'),
      { type: 'warning' }
    )
  }

  if (msg.type === 'approval_required') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const approvalTitle = msg.data?.approval?.title
    addChatNotification(
      approvalTitle ? `${t('team.approvalQueued')}: ${approvalTitle}` : t('team.approvalQueued'),
      { type: 'warning' }
    )
  }

  if (msg.type === 'approval_resolved') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const approvalTitle = msg.data?.approval?.title
    addChatNotification(
      approvalTitle ? `${t('team.approvalResolved')}: ${approvalTitle}` : t('team.approvalResolved')
    )
  }

  if (msg.type === 'approval_gate_waiting') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    status.value = 'Waiting for approval...'
  }

  if (msg.type === 'review_execution_paused') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    status.value = 'Waiting for approval...'
    addChatNotification(t('team.reviewExecutionPaused'), { type: 'warning' })
  }

  if (msg.type === 'approval_gate_resumed') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    status.value = 'Running...'
  }

  if (msg.type === 'review_replay_ready') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    status.value = 'Waiting for launch...'
    const replayTitle = msg.data?.replay?.target_task_title
    addChatNotification(
      replayTitle ? `${t('team.reviewReplayReady')}: ${replayTitle}` : t('team.reviewReplayReady')
    )
  }

  if (msg.type === 'review_replay_dismissed') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    status.value = 'Waiting for launch...'
    addChatNotification(t('team.reviewReplayDismissed'))
  }

  if (msg.type === 'task_status_changed') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
  }

  if (msg.type === 'task_reused') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const reusedTitle = msg.data?.task?.title || msg.data?.task?.id
    addChatNotification(
      reusedTitle ? `${t('team.taskReused')}: ${reusedTitle}` : t('team.taskReused')
    )
  }

  if (msg.type === 'task_dependencies_injected') {
    if (msg.data?.team_state) {
      applyTeamStateSnapshot(msg.data.team_state)
    }
    const taskTitle = msg.data?.task?.title || msg.data?.task?.id
    const predecessorCount = Array.isArray(msg.data?.predecessors) ? msg.data.predecessors.length : 0
    const suffix = predecessorCount ? ` (${predecessorCount})` : ''
    addChatNotification(
      taskTitle ? `${t('team.taskDependenciesInjected')}${suffix}: ${taskTitle}` : `${t('team.taskDependenciesInjected')}${suffix}`
    )
  }

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
            message.error = t('launch.loadImageFailed')
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
    latestTokenUsage.value = (msg.data?.token_usage && typeof msg.data.token_usage === 'object')
      ? msg.data.token_usage
      : {}
    applyTeamStateSnapshot({
      ...teamState.value,
      artifacts: {
        ...(teamState.value?.artifacts || {}),
        token_usage_snapshot: latestTokenUsage.value,
      },
    })
    sessionIdToDownload = sessionId
  }

  if (msg.type === 'workflow_handoff_started') {
    const handoff = msg.data?.handoff || {}
    status.value = 'Running...'
    isWorkflowRunning.value = true
    addChatNotification(t('launch.handoffStarted', { workflow: handoff.target_workflow || t('common.unnamed') }))
  }

  if (msg.type === 'workflow_handoff_completed') {
    const handoff = msg.data?.handoff || {}
    addChatNotification(t('launch.handoffCompleted', { workflow: handoff.target_workflow || t('common.unnamed') }))
    if (handoff.final_message) {
      addChatNotification(handoff.final_message)
    }
  }

  if (msg.type === 'workflow_handoff_failed') {
    const handoff = msg.data?.handoff || {}
    addChatNotification(t('launch.handoffFailed', {
      workflow: handoff.target_workflow || t('common.unnamed'),
      message: handoff.message || t('common.unknownError'),
    }), { type: 'error' })
  }

  if (msg.type === 'workflow_handoffs_completed') {
    const count = Array.isArray(msg.data?.handoffs) ? msg.data.handoffs.length : 0
    status.value = 'Completed'
    isWorkflowRunning.value = false
    addChatNotification(t('launch.handoffsCompleted', { count }))
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
  addChatNotification(t('launch.workflowCancelled'))
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
    alert(t('launch.logsDownloadFailed'))
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
  position: relative;
}

/* Persistent Chat Panel */
.chat-panel {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 380px;
  max-width: 50%;
  z-index: 10;
  display: flex;
  flex-direction: row;
  pointer-events: none;
  transition: width 0.3s ease;
}

/* Full-screen chat mode */
.chat-panel-fullscreen {
  position: relative;
  width: 100%;
  max-width: 100%;
  flex: 1;
  flex-direction: column;
  pointer-events: auto;
  z-index: auto;
  min-height: 0;
}

.chat-panel-fullscreen .chat-panel-content {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(5px);
}

.chat-panel-collapsed {
  width: 0;
}

.chat-panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  pointer-events: auto;
  background: rgba(26, 26, 26, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  backdrop-filter: blur(12px);
  overflow: hidden;
  padding: 0;
}

.chat-panel-toggle {
  position: absolute;
  top: 12px;
  right: -32px;
  width: 28px;
  height: 28px;
  border-radius: 0 8px 8px 0;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-left: none;
  background: rgba(26, 26, 26, 0.92);
  backdrop-filter: blur(8px);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: auto;
  transition: all 0.2s ease;
  padding: 0;
  z-index: 11;
}

.chat-panel-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #f2f2f2;
}

.chat-panel-toggle svg {
  transition: transform 0.3s ease;
}

.chat-panel-toggle .chevron-collapsed {
  transform: rotate(180deg);
}

.chat-panel-collapsed .chat-panel-toggle {
  right: -32px;
  left: auto;
}

/* Chat Box */
.chat-box {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
  word-break: break-word;
  overflow-wrap: anywhere;
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

.profile-selector {
  cursor: pointer;
}

.profile-hint {
  margin-top: -8px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
  line-height: 1.45;
}

.profile-hint code {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  color: #e3f1ff;
}

.profile-hint-success {
  color: rgba(170, 255, 205, 0.85);
}

.profile-hint-warning {
  color: rgba(255, 213, 128, 0.9);
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

.launch-view {
  min-height: 100vh;
  height: auto;
  padding: 18px;
  box-sizing: border-box;
  background:
    radial-gradient(circle at top left, rgba(33, 155, 141, 0.14), transparent 24%),
    radial-gradient(circle at 86% 16%, rgba(234, 192, 104, 0.18), transparent 28%),
    linear-gradient(180deg, #f6f3ea 0%, #ebe5d9 100%);
  color: #17353c;
}

.launch-bg {
  top: -120px;
  left: 8%;
  right: 8%;
  height: 380px;
  background: linear-gradient(90deg, rgba(52, 166, 153, 0.22), rgba(236, 197, 122, 0.2), rgba(85, 148, 185, 0.18));
  filter: blur(100px);
  opacity: 1;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  height: auto;
  min-height: 116px;
  padding: 26px 30px;
  border-radius: 30px;
  border: 1px solid rgba(14, 46, 52, 0.08);
  background: linear-gradient(135deg, rgba(22, 88, 95, 0.95) 0%, rgba(31, 104, 108, 0.94) 52%, rgba(238, 197, 120, 0.92) 140%);
  box-shadow: 0 24px 60px rgba(27, 54, 61, 0.16);
  backdrop-filter: none;
}

.header-copy {
  max-width: 760px;
}

.header-eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(244, 249, 246, 0.66);
}

.header h1 {
  margin: 10px 0 0;
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.04;
  color: #f8fcfa;
  letter-spacing: -0.03em;
}

.header-subtitle {
  margin: 12px 0 0;
  max-width: 620px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(244, 249, 246, 0.84);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-button {
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid rgba(250, 251, 248, 0.22);
  background: rgba(250, 251, 248, 0.14);
  color: #fffaf2;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  transition: transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
}

.back-button:hover {
  transform: translateY(-1px);
  background: rgba(250, 251, 248, 0.18);
  border-color: rgba(250, 251, 248, 0.3);
}

.header-status-pill,
.settings-button,
.back-button {
  box-shadow: none;
}

.header-status-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(250, 251, 248, 0.14);
  color: #fff7dc;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.settings-button {
  padding: 12px;
  border-radius: 16px;
  color: #fff4d1;
  background: rgba(250, 251, 248, 0.12);
}

.settings-button:hover {
  background: rgba(250, 251, 248, 0.18);
}

.content {
  gap: 18px;
  padding: 18px 0 0;
  min-height: 0;
}

.left-panel,
.right-panel {
  border-radius: 28px;
  background: rgba(255, 250, 243, 0.76);
  border: 1px solid rgba(21, 58, 64, 0.08);
  box-shadow: 0 24px 60px rgba(33, 55, 63, 0.08);
  backdrop-filter: blur(14px);
}

.left-panel {
  padding: 20px;
  min-height: 0;
}

.right-panel {
  padding: 20px;
}

.chat-panel {
  position: relative;
  width: 100%;
  max-width: none;
  min-height: 0;
  flex: 1;
  display: flex;
  pointer-events: auto;
}

.chat-panel-fullscreen {
  width: 100%;
  max-width: none;
  min-height: 0;
}

.chat-panel-content,
.chat-box {
  flex: 1;
  min-height: 0;
}

.graph-panel {
  flex: 1;
  min-height: 560px;
  overflow: hidden;
  border-radius: 20px;
}

.chat-panel-toggle {
  display: none !important;
}

.chat-panel,
.graph-panel,
.chat-box,
.input-shell,
.select-wrapper,
.status-display,
.view-toggle,
.control-section,
.workflow-legend,
.active-nodes-box {
  background: rgba(255, 255, 255, 0.74) !important;
  border: 1px solid rgba(22, 58, 64, 0.08) !important;
  color: #17353c;
  box-shadow: none;
}

.control-section {
  gap: 16px;
  padding: 18px;
  border-radius: 24px;
  overflow-y: auto;
}

.section-label,
.user-name,
.message-timestamp,
.profile-hint,
.no-active-nodes,
.artifact-status,
.loading-timer {
  color: #667a7e !important;
}

.control-section > .section-label:not(:first-child) {
  margin-top: 6px;
}

.run-mode-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.run-mode-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(22, 58, 64, 0.1);
  border-radius: 16px;
  background: rgba(255, 253, 248, 0.88);
  color: #17353c;
  text-align: left;
  cursor: pointer;
  box-shadow: none;
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.run-mode-card:hover {
  transform: translateY(-1px);
  border-color: rgba(31, 103, 109, 0.28);
  background: #fffdf8;
}

.run-mode-card.active {
  border-color: rgba(31, 103, 109, 0.42);
  background: rgba(222, 240, 232, 0.86);
}

.run-mode-title {
  color: #17353c;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.25;
}

.run-mode-desc {
  color: #6b7d80;
  font-size: 12px;
  line-height: 1.5;
}

.toggle-button,
.attachment-button,
.download-button,
.file-selector,
.file-selector-input,
.task-input {
  background: rgba(255, 255, 255, 0.92) !important;
  color: #17353c !important;
  border: 1px solid rgba(22, 58, 64, 0.1) !important;
}

.toggle-button.active {
  background: #1f676d !important;
  color: #ffffff !important;
  border-color: #1f676d !important;
}

.chat-notification,
.message-bubble,
.artifact-file-wrapper,
.artifact-image-wrapper,
.attachment-modal,
.file-dropdown {
  background: #fffdf8 !important;
  border: 1px solid rgba(22, 58, 64, 0.1) !important;
  color: #17353c !important;
}

.dialogue-right .message-bubble {
  background: linear-gradient(135deg, rgba(208, 240, 232, 0.92), rgba(245, 233, 196, 0.92)) !important;
  border-color: rgba(32, 109, 112, 0.16) !important;
}

.loading-entry,
.active-node-item {
  background: rgba(241, 246, 242, 0.94) !important;
  border: 1px solid rgba(25, 86, 92, 0.08) !important;
}

.loading-entry-label,
.message-text,
.notification-text,
.artifact-filename,
.attachment-name,
.file-name,
.file-desc {
  color: #17353c !important;
}

.attachment-empty,
.file-empty {
  color: #6b7d80 !important;
}

.launch-button {
  color: #ffffff;
  background: linear-gradient(135deg, #19555c, #23707b, #e2b459);
}

.cancel-button {
  color: #ffffff;
  background: linear-gradient(135deg, #b56049, #a14a42, #7e3838);
}

.download-button {
  color: #18464d !important;
}

.select-wrapper,
.status-display,
.view-toggle {
  border-radius: 16px !important;
}

.view-toggle {
  padding: 4px;
  gap: 6px;
}

.toggle-button {
  min-height: 42px;
  border-radius: 12px !important;
}

.profile-hint {
  margin-top: -2px;
  line-height: 1.6;
}

.launch-quick-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: stretch;
}

.button-section {
  margin-top: 4px;
  gap: 10px;
}

.advanced-toggle-button {
  width: 100%;
  min-height: 42px;
  padding: 10px 14px;
  border-radius: 14px;
  border: 1px solid rgba(24, 70, 77, 0.12);
  background: rgba(255, 255, 255, 0.88);
  color: #18464d;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.advanced-toggle-button:hover {
  background: rgba(241, 245, 242, 0.96);
  border-color: rgba(31, 103, 109, 0.18);
}

.launch-button,
.cancel-button,
.download-button {
  min-height: 46px;
  border-radius: 14px;
}

.artifact-download-button {
  color: #18464d;
  background: rgba(241, 245, 242, 0.96);
  border: 1px solid rgba(24, 70, 77, 0.12);
}

.image-modal {
  background: rgba(22, 33, 37, 0.42);
  backdrop-filter: blur(6px);
}

.image-modal-content {
  border-radius: 22px;
  background: rgba(255, 252, 246, 0.94);
  border: 1px solid rgba(22, 58, 64, 0.08);
}

:deep(.vue-flow__background) {
  background:
    radial-gradient(circle at 20% 20%, rgba(30, 126, 128, 0.08), transparent 20%),
    linear-gradient(180deg, #fffdf7 0%, #f3efe5 100%);
}

:deep(.vue-flow__controls) {
  box-shadow: 0 10px 24px rgba(27, 54, 61, 0.12);
  border-radius: 16px;
  overflow: hidden;
}

:deep(.vue-flow__controls button) {
  background: rgba(255, 251, 243, 0.96);
  color: #18464d;
  border-bottom: 1px solid rgba(22, 58, 64, 0.08);
}

@media (max-width: 980px) {
  .launch-view {
    padding: 14px;
  }

  .header {
    flex-direction: column;
  }

  .content {
    flex-direction: column;
  }

  .left-panel,
  .right-panel {
    padding: 16px;
  }

  .control-section {
    padding: 14px;
  }

  .launch-quick-row {
    grid-template-columns: 1fr;
  }
}
</style>
