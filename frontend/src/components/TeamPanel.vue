<template>
  <section class="team-panel">
    <div class="panel-header">
      <div>
        <h3 class="panel-title">{{ t('team.title') }}</h3>
        <p class="panel-subtitle">{{ t('team.subtitle') }}</p>
      </div>
      <div class="panel-mode">{{ teamState?.workflow?.team_mode || teamState?.mode || 'human_governed' }}</div>
    </div>

    <div class="panel-section">
      <label class="section-label">{{ t('team.goal') }}</label>
      <textarea
        v-model="goalInput"
        class="panel-textarea"
        :placeholder="t('team.goalPlaceholder')"
        :disabled="disabled"
      ></textarea>
      <button class="panel-button" type="button" :disabled="disabled" @click="saveGoal">
        {{ t('team.saveGoal') }}
      </button>
    </div>

    <div v-if="hasTokenUsage" class="panel-section">
      <label class="section-label">{{ t('team.tokenUsage') }}</label>
      <div class="token-card">
        <div class="token-summary">
          <span>{{ t('team.tokenInput') }}: {{ formatNumber(tokenUsageSummary.input_tokens) }}</span>
          <span>{{ t('team.tokenOutput') }}: {{ formatNumber(tokenUsageSummary.output_tokens) }}</span>
          <span>{{ t('team.tokenTotal') }}: {{ formatNumber(tokenUsageSummary.total_tokens) }}</span>
        </div>
        <div v-if="hasReuseStats" class="token-summary token-summary-reuse">
          <span>{{ t('team.reusedTasksCount') }}: {{ formatNumber(reusedTaskCount) }}</span>
          <span>{{ t('team.estimatedSavedTokens') }}: {{ formatNumber(estimatedSavedTokens) }}</span>
        </div>
        <div v-if="reusedTokenBreakdown.length" class="token-hotspots">
          <div class="token-hotspots-title">{{ t('team.reuseBreakdown') }}</div>
          <div
            v-for="item in reusedTokenBreakdown"
            :key="item.taskId"
            class="token-hotspot-item token-hotspot-item-reuse"
          >
            <span>{{ item.title }}</span>
            <span>{{ formatNumber(item.savedTokens) }}</span>
          </div>
        </div>
        <div v-if="topTokenNodes.length" class="token-hotspots">
          <div class="token-hotspots-title">{{ t('team.tokenHotspots') }}</div>
          <div
            v-for="item in topTokenNodes"
            :key="item.nodeId"
            class="token-hotspot-item"
          >
            <span>{{ item.nodeId }}</span>
            <span>{{ formatNumber(item.totalTokens) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-section">
      <label class="section-label">{{ t('team.plan') }}</label>
      <label class="field-label">{{ t('team.planSummary') }}</label>
      <textarea
        v-model="planSummaryInput"
        class="panel-textarea panel-textarea-compact"
        :placeholder="t('team.planSummaryPlaceholder')"
        :disabled="disabled"
      ></textarea>
      <label class="field-label">{{ t('team.tasks') }}</label>
      <textarea
        v-model="planTasksInput"
        class="panel-textarea"
        :placeholder="t('team.tasksPlaceholder')"
        :disabled="disabled"
      ></textarea>
      <button class="panel-button" type="button" :disabled="disabled" @click="savePlan">
        {{ t('team.savePlan') }}
      </button>
      <div class="timeline-section">
        <label class="field-label">{{ t('team.timeline') }}</label>
        <div v-if="normalizedTasks.length" class="task-search-row">
          <input
            v-model="taskSearchQuery"
            type="text"
            class="panel-input task-search-input"
            :placeholder="t('team.taskSearchPlaceholder')"
          />
          <select v-model="selectedTaskOwner" class="panel-input task-owner-select">
            <option value="all">{{ t('team.taskOwnerAll') }}</option>
            <option
              v-for="owner in taskOwnerOptions.filter((owner) => owner !== 'all')"
              :key="owner"
              :value="owner"
            >
              {{ owner }}
            </option>
          </select>
        </div>
        <div v-if="normalizedTasks.length" class="task-filter-row">
          <button
            v-for="option in taskFilterOptions"
            :key="option.id"
            type="button"
            class="task-filter-chip"
            :class="{ 'is-active': taskFilter === option.id }"
            @click="taskFilter = option.id"
          >
            {{ t(option.labelKey) }}
          </button>
        </div>
        <div v-if="normalizedTasks.length" class="task-list">
          <div
            v-for="task in filteredTasks"
            :key="task.id"
            class="task-card"
            :class="{ 'is-affected': taskInjectedPredecessors(task).length > 0, 'is-focused': focusedTaskId === task.id }"
            @click="toggleFocusedTask(task.id)"
          >
            <div class="task-main">
              <div class="task-title">{{ task.title }}</div>
              <div v-if="task.owner" class="task-owner">{{ task.owner }}</div>
              <div v-if="taskOutputPreview(task)" class="task-output-preview">
                <span class="task-output-label">{{ t('team.outputSnapshot') }}</span>
                <span class="task-output-text">{{ taskOutputPreview(task) }}</span>
                <span v-if="taskOutputSize(task)" class="task-output-size">{{ formatOutputSize(taskOutputSize(task)) }}</span>
              </div>
              <div v-if="taskInjectedPredecessors(task).length" class="task-injected-dependencies">
                <span class="task-output-label">{{ t('team.injectedDependencies') }}</span>
                <span class="task-injected-list">{{ taskInjectedPredecessors(task).join(', ') }}</span>
              </div>
            </div>
            <div class="task-actions">
              <span class="task-badge" :class="taskBadgeClass(task.status)">
                {{ taskStatusLabel(task.status) }}
              </span>
              <span v-if="taskReused(task)" class="task-badge is-reused">
                {{ t('team.taskReused') }}
              </span>
              <button
                class="panel-button panel-button-inline task-replay-button"
                type="button"
                :disabled="disabled"
                @click.stop="replayFromTask(task.id)"
              >
                {{ t('team.replayFromHere') }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="normalizedTasks.length && !filteredTasks.length" class="empty-hint">{{ t('team.noFilteredTasks') }}</div>
        <div v-else-if="!normalizedTasks.length" class="empty-hint">{{ t('team.noTasks') }}</div>
        <div v-if="props.teamState?.replay?.target_task_title" class="empty-hint">
          {{ t('team.replayTarget') }}: {{ props.teamState.replay.target_task_title }}
        </div>
        <div v-if="latestReviewDirective.replay_target_title" class="review-directive-card">
          <div class="review-directive-title">
            {{ t('team.reviewReplaySuggested') }}: {{ latestReviewDirective.replay_target_title }}
          </div>
          <div v-if="reviewScopeSummary" class="review-directive-meta">
            {{ reviewScopeSummary }}
          </div>
          <div v-if="latestReviewDirective.reviewer_node_id" class="review-directive-meta">
            {{ latestReviewDirective.reviewer_node_id }}
          </div>
          <div v-if="latestReviewDirective.note" class="review-directive-note">
            {{ latestReviewDirective.note }}
          </div>
          <div v-if="reviewAffectedTasks.length" class="review-affected-section">
            <div class="review-affected-title">{{ t('team.reviewAffectedTasks') }}</div>
            <div class="review-affected-list">
              <button
                v-for="task in reviewAffectedTasks"
                :key="task.id"
                type="button"
                class="review-affected-chip"
                :class="{ 'is-focused': focusedTaskId === task.id }"
                @click.stop="focusTask(task.id)"
              >
                {{ task.title }}
              </button>
            </div>
          </div>
          <div v-if="reviewAffectedTasks.length" class="review-rework-cost">
            <div class="review-affected-title">{{ t('team.reviewReworkCost') }}</div>
            <div class="replay-context-meta">
              {{ t('team.impactedTasksCount') }}: {{ formatNumber(reviewAffectedTasks.length) }}
              ·
              {{ t('team.reviewEstimatedReworkTokens') }}: {{ formatNumber(reviewEstimatedReworkTokens) }}
              ·
              {{ t('team.reviewReusableTasks') }}: {{ formatNumber(reviewReusableTaskCount) }}
            </div>
            <div v-if="reviewReworkBreakdown.length" class="review-rework-breakdown">
              <div class="review-affected-title">{{ t('team.reviewReworkBreakdown') }}</div>
              <div
                v-for="item in reviewReworkBreakdown"
                :key="item.taskId"
                class="review-rework-item"
              >
                <span>{{ item.title }}</span>
                <span class="review-rework-item-meta">
                  {{ formatNumber(item.tokens) }}
                  <span v-if="item.reused" class="review-rework-reused">{{ t('team.reviewTaskReused') }}</span>
                </span>
              </div>
            </div>
          </div>
          <div class="review-directive-actions">
            <button
              class="panel-button panel-button-inline"
              type="button"
              :disabled="disabled"
              @click="acceptReviewSuggestion"
            >
              {{ t('team.acceptReviewSuggestion') }}
            </button>
            <button
              class="panel-button panel-button-inline review-dismiss-button"
              type="button"
              :disabled="disabled"
              @click="dismissReviewSuggestion"
            >
              {{ t('team.dismissReviewSuggestion') }}
            </button>
          </div>
        </div>
        <div v-if="replayRetainedTasks.length" class="replay-context-card">
          <div class="replay-context-title">
            {{ t('team.retainedOutputs') }}
          </div>
          <div v-if="retainedNodeCount" class="replay-context-meta">
            {{ t('team.retainedNodeCount') }}: {{ formatNumber(retainedNodeCount) }}
          </div>
          <div
            v-for="item in replayRetainedTasks"
            :key="item.task_id"
            class="replay-context-item"
          >
            <div class="replay-context-task">{{ item.title }}</div>
            <div v-if="item.node_id" class="replay-context-node">
              {{ t('team.replayNode') }}: {{ item.node_id }}
            </div>
            <div v-if="item.preview" class="replay-context-preview">{{ item.preview }}</div>
          </div>
        </div>
        <div v-if="visibleReplayDependencyRows.length" class="replay-context-card">
          <div class="replay-context-title">
            {{ t('team.replayDependencyView') }}
          </div>
          <div class="replay-context-meta">
            {{ t('team.impactedTasksCount') }}: {{ formatNumber(visibleReplayDependencyRows.length) }}
            ·
            {{ t('team.injectedDependencyCount') }}: {{ formatNumber(totalInjectedDependencies) }}
          </div>
          <div
            v-for="row in visibleReplayDependencyRows"
            :key="row.taskId"
            class="dependency-graph-row"
            :class="{ 'is-expanded': expandedDependencyTaskId === row.taskId, 'is-focused': focusedTaskId === row.taskId }"
            @click="toggleDependencyRow(row.taskId)"
          >
            <div class="dependency-predecessors">
              <span
                v-for="predecessor in row.predecessors"
                :key="`${row.taskId}-${predecessor}`"
                class="dependency-node dependency-node-source"
              >
                {{ predecessor }}
              </span>
            </div>
            <div class="dependency-arrow">{{ t('team.dependencyArrow') }}</div>
            <div class="dependency-node dependency-node-target">
              {{ row.taskTitle }}
            </div>
            <div v-if="expandedDependencyTaskId === row.taskId" class="dependency-row-details">
              <div class="dependency-row-detail">
                {{ t('common.status') }}: {{ taskStatusLabel(row.status) }}
              </div>
              <div v-if="row.outputPreview" class="dependency-row-detail">
                {{ t('team.outputSnapshot') }}: {{ row.outputPreview }}
              </div>
              <div class="dependency-row-detail dependency-row-toggle">
                {{ t('team.hideDependencyDetails') }}
              </div>
            </div>
            <div v-else class="dependency-row-toggle">
              {{ t('team.showDependencyDetails') }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-section">
      <label class="section-label">{{ t('team.memory') }}</label>
      <div class="memory-grid">
        <div class="memory-column">
          <label class="field-label">{{ t('team.facts') }}</label>
          <textarea v-model="factsInput" class="panel-textarea panel-textarea-compact" :placeholder="t('team.memoryPlaceholder')" :disabled="disabled"></textarea>
        </div>
        <div class="memory-column">
          <label class="field-label">{{ t('team.assumptions') }}</label>
          <textarea v-model="assumptionsInput" class="panel-textarea panel-textarea-compact" :placeholder="t('team.memoryPlaceholder')" :disabled="disabled"></textarea>
        </div>
        <div class="memory-column">
          <label class="field-label">{{ t('team.openQuestions') }}</label>
          <textarea v-model="openQuestionsInput" class="panel-textarea panel-textarea-compact" :placeholder="t('team.memoryPlaceholder')" :disabled="disabled"></textarea>
        </div>
        <div class="memory-column">
          <label class="field-label">{{ t('team.decisions') }}</label>
          <textarea v-model="decisionsInput" class="panel-textarea panel-textarea-compact" :placeholder="t('team.memoryPlaceholder')" :disabled="disabled"></textarea>
        </div>
      </div>
      <button class="panel-button" type="button" :disabled="disabled" @click="saveMemory">
        {{ t('team.saveMemory') }}
      </button>
    </div>

    <div class="panel-section">
      <label class="section-label">{{ t('team.approvals') }}</label>
      <div class="approval-create">
        <input
          v-model="approvalInput"
          class="panel-input"
          type="text"
          :placeholder="t('team.approvalPlaceholder')"
          :disabled="disabled"
          @keyup.enter="createApproval"
        />
        <label class="approval-blocking-toggle">
          <input v-model="approvalBlocking" type="checkbox" :disabled="disabled" />
          <span>{{ t('team.blocking') }}</span>
        </label>
        <button class="panel-button panel-button-inline" type="button" :disabled="disabled || !approvalInput.trim()" @click="createApproval">
          {{ t('team.addApproval') }}
        </button>
      </div>
      <div v-if="normalizedApprovals.length" class="approval-list">
        <div v-for="approval in normalizedApprovals" :key="approval.id" class="approval-card">
          <div class="approval-main">
            <div class="approval-title">{{ approval.title }}</div>
            <div class="approval-meta">
              <span class="approval-badge" :class="approval.status === 'resolved' ? 'is-resolved' : 'is-open'">
                {{ approval.status === 'resolved' ? t('team.resolved') : t('team.open') }}
              </span>
              <span v-if="approval.blocking" class="approval-badge is-blocking">
                {{ t('team.approvalBlocking') }}
              </span>
              <span v-if="approval.note" class="approval-note">{{ approval.note }}</span>
            </div>
          </div>
          <button
            v-if="approval.status !== 'resolved'"
            class="panel-button panel-button-inline"
            type="button"
            :disabled="disabled"
            @click="resolveApproval(approval.id)"
          >
            {{ t('team.markResolved') }}
          </button>
        </div>
      </div>
      <div v-else class="empty-hint">{{ t('team.noApprovals') }}</div>
    </div>

    <div class="panel-footer">{{ t('team.saveHint') }}</div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { t } from '../utils/i18n.js'

const props = defineProps({
  teamState: {
    type: Object,
    default: () => ({})
  },
  disabled: {
    type: Boolean,
    default: false
  },
  tokenUsage: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'save-goal',
  'save-plan',
  'save-memory',
  'create-approval',
  'resolve-approval',
  'accept-review-suggestion',
  'dismiss-review-suggestion',
  'replay-from-task'
])

const goalInput = ref('')
const planSummaryInput = ref('')
const planTasksInput = ref('')
const factsInput = ref('')
const assumptionsInput = ref('')
const openQuestionsInput = ref('')
const decisionsInput = ref('')
const approvalInput = ref('')
const approvalBlocking = ref(false)
const expandedDependencyTaskId = ref('')
const taskFilter = ref('all')
const focusedTaskId = ref('')
const taskSearchQuery = ref('')
const selectedTaskOwner = ref('all')

const taskFilterOptions = Object.freeze([
  { id: 'all', labelKey: 'team.taskFilters.all' },
  { id: 'affected', labelKey: 'team.taskFilters.affected' },
  { id: 'reused', labelKey: 'team.taskFilters.reused' },
  { id: 'running', labelKey: 'team.taskFilters.running' },
])

const syncInputs = (state) => {
  const nextState = state || {}
  goalInput.value = nextState?.goal || ''
  planSummaryInput.value = nextState?.plan?.summary || ''
  planTasksInput.value = Array.isArray(nextState?.plan?.tasks)
    ? nextState.plan.tasks.map((task) => task?.title || '').filter(Boolean).join('\n')
    : ''
  factsInput.value = Array.isArray(nextState?.memory?.facts) ? nextState.memory.facts.join('\n') : ''
  assumptionsInput.value = Array.isArray(nextState?.memory?.assumptions) ? nextState.memory.assumptions.join('\n') : ''
  openQuestionsInput.value = Array.isArray(nextState?.memory?.open_questions) ? nextState.memory.open_questions.join('\n') : ''
  decisionsInput.value = Array.isArray(nextState?.memory?.decisions) ? nextState.memory.decisions.join('\n') : ''
}

watch(
  () => props.teamState,
  (state) => {
    syncInputs(state)
  },
  { immediate: true, deep: true }
)

watch(filteredTasks, (tasks) => {
  const visibleTaskIds = new Set(tasks.map((task) => String(task?.id || '')))
  if (focusedTaskId.value && !visibleTaskIds.has(focusedTaskId.value)) {
    focusedTaskId.value = ''
    expandedDependencyTaskId.value = ''
  }
})

const normalizedApprovals = computed(() => (
  Array.isArray(props.teamState?.approvals) ? props.teamState.approvals : []
))

const normalizedTasks = computed(() => (
  Array.isArray(props.teamState?.plan?.tasks) ? props.teamState.plan.tasks : []
))

const taskOwnerOptions = computed(() => {
  const owners = normalizedTasks.value
    .map((task) => String(task?.owner || '').trim())
    .filter(Boolean)
  return ['all', ...Array.from(new Set(owners))]
})

const filteredTasks = computed(() => {
  const normalizedQuery = String(taskSearchQuery.value || '').trim().toLowerCase()
  if (taskFilter.value === 'affected') {
    return normalizedTasks.value
      .filter((task) => taskInjectedPredecessors(task).length > 0)
      .filter((task) => filterTaskByOwnerAndQuery(task, normalizedQuery))
  }
  if (taskFilter.value === 'reused') {
    return normalizedTasks.value
      .filter((task) => taskReused(task))
      .filter((task) => filterTaskByOwnerAndQuery(task, normalizedQuery))
  }
  if (taskFilter.value === 'running') {
    return normalizedTasks.value
      .filter((task) => String(task?.status || '') === 'running')
      .filter((task) => filterTaskByOwnerAndQuery(task, normalizedQuery))
  }
  return normalizedTasks.value.filter((task) => filterTaskByOwnerAndQuery(task, normalizedQuery))
})

const replayRetainedTasks = computed(() => (
  Array.isArray(props.teamState?.artifacts?.replay_context?.retained_tasks)
    ? props.teamState.artifacts.replay_context.retained_tasks
    : []
))

const replayDependencyRows = computed(() => (
  normalizedTasks.value
    .map((task) => ({
      taskId: String(task?.id || ''),
      taskTitle: String(task?.title || task?.id || '').trim(),
      predecessors: taskInjectedPredecessors(task),
      status: String(task?.status || 'pending'),
      outputPreview: taskOutputPreview(task),
    }))
    .filter((item) => item.taskId && item.taskTitle && item.predecessors.length)
))

const visibleReplayDependencyRows = computed(() => {
  const visibleTaskIds = new Set(filteredTasks.value.map((task) => String(task?.id || '')))
  return replayDependencyRows.value.filter((row) => visibleTaskIds.has(row.taskId))
})

const totalInjectedDependencies = computed(() => (
  visibleReplayDependencyRows.value.reduce((total, row) => total + row.predecessors.length, 0)
))

const retainedNodeCount = computed(() => {
  const retainedNodeIds = Array.isArray(props.teamState?.artifacts?.replay_context?.retained_node_ids)
    ? props.teamState.artifacts.replay_context.retained_node_ids
    : []
  return retainedNodeIds.filter((item) => String(item || '').trim()).length
})

const latestReviewDirective = computed(() => (
  (props.teamState?.artifacts?.review?.last_directive && typeof props.teamState.artifacts.review.last_directive === 'object')
    ? props.teamState.artifacts.review.last_directive
    : {}
))

const reviewAffectedTasks = computed(() => {
  const targetId = String(
    latestReviewDirective.value?.replay_target_id
    || props.teamState?.replay?.target_task_id
    || ''
  ).trim()
  if (!targetId) {
    return []
  }

  const targetIndex = normalizedTasks.value.findIndex((task) => {
    const taskId = String(task?.id || '').trim()
    const nodeId = String(task?.node_id || '').trim()
    return taskId === targetId || nodeId === targetId
  })
  if (targetIndex < 0) {
    return []
  }
  return normalizedTasks.value.slice(targetIndex)
})

const reviewScopeSummary = computed(() => {
  if (!reviewAffectedTasks.value.length) {
    return ''
  }
  if (reviewAffectedTasks.value.length === 1) {
    return t('team.reviewScopeSingleTask')
  }
  return t('team.reviewScopeMultiTask', { count: reviewAffectedTasks.value.length })
})

const reviewEstimatedReworkTokens = computed(() => {
  const nodeUsages = (tokenUsageSnapshot.value?.node_usages && typeof tokenUsageSnapshot.value.node_usages === 'object')
    ? tokenUsageSnapshot.value.node_usages
    : {}
  return reviewAffectedTasks.value.reduce((total, task) => {
    const taskKey = String(task?.node_id || task?.id || '').trim()
    const usage = nodeUsages[taskKey] || nodeUsages[String(task?.id || '').trim()] || {}
    return total + Number(usage?.total_tokens || 0)
  }, 0)
})

const reviewReusableTaskCount = computed(() => (
  reviewAffectedTasks.value.filter((task) => taskReused(task)).length
))

const reviewReworkBreakdown = computed(() => {
  const nodeUsages = (tokenUsageSnapshot.value?.node_usages && typeof tokenUsageSnapshot.value.node_usages === 'object')
    ? tokenUsageSnapshot.value.node_usages
    : {}
  return reviewAffectedTasks.value
    .map((task) => {
      const taskKey = String(task?.node_id || task?.id || '').trim()
      const usage = nodeUsages[taskKey] || nodeUsages[String(task?.id || '').trim()] || {}
      return {
        taskId: String(task?.id || taskKey || ''),
        title: String(task?.title || taskKey || '').trim(),
        tokens: Number(usage?.total_tokens || 0),
        reused: taskReused(task),
      }
    })
    .filter((item) => item.taskId && item.title)
    .sort((left, right) => right.tokens - left.tokens)
})

const tokenUsageSummary = computed(() => (
  (props.tokenUsage?.total_usage && typeof props.tokenUsage.total_usage === 'object')
    ? props.tokenUsage.total_usage
    : { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
))

const hasTokenUsage = computed(() => Number(tokenUsageSummary.value.total_tokens || 0) > 0)

const tokenUsageSnapshot = computed(() => (
  (props.teamState?.artifacts?.token_usage_snapshot && typeof props.teamState.artifacts.token_usage_snapshot === 'object')
    ? props.teamState.artifacts.token_usage_snapshot
    : { total_usage: {}, node_usages: {} }
))

const estimatedSavedTokens = computed(() => {
  const nodeUsages = (tokenUsageSnapshot.value?.node_usages && typeof tokenUsageSnapshot.value.node_usages === 'object')
    ? tokenUsageSnapshot.value.node_usages
    : {}
  return normalizedTasks.value
    .filter((task) => taskReused(task))
    .reduce((total, task) => {
      const taskKey = String(task?.node_id || task?.id || '').trim()
      const usage = nodeUsages[taskKey] || nodeUsages[String(task?.id || '').trim()] || {}
      return total + Number(usage?.total_tokens || 0)
    }, 0)
})

const reusedTaskCount = computed(() => (
  normalizedTasks.value.filter((task) => taskReused(task)).length
))

const reusedTokenBreakdown = computed(() => {
  const nodeUsages = (tokenUsageSnapshot.value?.node_usages && typeof tokenUsageSnapshot.value.node_usages === 'object')
    ? tokenUsageSnapshot.value.node_usages
    : {}

  return normalizedTasks.value
    .filter((task) => taskReused(task))
    .map((task) => {
      const taskKey = String(task?.node_id || task?.id || '').trim()
      const usage = nodeUsages[taskKey] || nodeUsages[String(task?.id || '').trim()] || {}
      return {
        taskId: String(task?.id || taskKey || ''),
        title: String(task?.title || taskKey || '').trim(),
        savedTokens: Number(usage?.total_tokens || 0),
      }
    })
    .filter((item) => item.taskId && item.title && item.savedTokens > 0)
    .sort((left, right) => right.savedTokens - left.savedTokens)
})

const hasReuseStats = computed(() => reusedTaskCount.value > 0 || estimatedSavedTokens.value > 0)

const topTokenNodes = computed(() => {
  const nodeUsages = (props.tokenUsage?.node_usages && typeof props.tokenUsage.node_usages === 'object')
    ? props.tokenUsage.node_usages
    : {}
  return Object.entries(nodeUsages)
    .map(([nodeId, usage]) => ({
      nodeId,
      totalTokens: Number(usage?.total_tokens || 0),
    }))
    .filter((item) => item.totalTokens > 0)
    .sort((left, right) => right.totalTokens - left.totalTokens)
    .slice(0, 5)
})

const taskOutputPreview = (task) => {
  if (task?.output_preview) {
    return task.output_preview
  }
  return props.teamState?.artifacts?.task_outputs?.[task?.id]?.output_preview || ''
}

const taskOutputSize = (task) => {
  if (task?.output_size) {
    return Number(task.output_size || 0)
  }
  return Number(props.teamState?.artifacts?.task_outputs?.[task?.id]?.output_size || 0)
}

const taskReused = (task) => {
  if (task?.reused_replay_output) {
    return true
  }
  return Boolean(props.teamState?.artifacts?.task_outputs?.[task?.id]?.reused_replay_output)
}

const taskInjectedPredecessors = (task) => {
  if (Array.isArray(task?.replay_injected_predecessors) && task.replay_injected_predecessors.length) {
    return task.replay_injected_predecessors
  }
  const artifact = props.teamState?.artifacts?.task_outputs?.[task?.id]
  return Array.isArray(artifact?.replay_injected_predecessors)
    ? artifact.replay_injected_predecessors
    : []
}

const filterTaskByOwnerAndQuery = (task, normalizedQuery) => {
  const owner = String(task?.owner || '').trim()
  if (selectedTaskOwner.value !== 'all' && owner !== selectedTaskOwner.value) {
    return false
  }
  if (!normalizedQuery) {
    return true
  }

  const haystack = [
    String(task?.title || ''),
    owner,
    String(task?.status || ''),
    taskOutputPreview(task),
    taskInjectedPredecessors(task).join(' '),
  ]
    .join(' ')
    .toLowerCase()

  return haystack.includes(normalizedQuery)
}

const splitLines = (text) => text
  .split('\n')
  .map((item) => item.trim())
  .filter(Boolean)

const saveGoal = () => {
  emit('save-goal', goalInput.value.trim())
}

const savePlan = () => {
  emit('save-plan', {
    summary: planSummaryInput.value.trim(),
    tasks: splitLines(planTasksInput.value).map((title, index) => ({
      id: `task-${index + 1}`,
      title,
      status: 'pending',
      owner: '',
      node_id: title,
    })),
  })
}

const saveMemory = () => {
  emit('save-memory', {
    facts: splitLines(factsInput.value),
    assumptions: splitLines(assumptionsInput.value),
    open_questions: splitLines(openQuestionsInput.value),
    decisions: splitLines(decisionsInput.value),
  })
}

const createApproval = () => {
  const title = approvalInput.value.trim()
  if (!title) {
    return
  }
  emit('create-approval', {
    title,
    status: 'open',
    blocking: approvalBlocking.value,
    note: '',
  })
  approvalInput.value = ''
  approvalBlocking.value = false
}

const resolveApproval = (approvalId) => {
  emit('resolve-approval', approvalId)
}

const taskStatusLabel = (status) => {
  if (status === 'running') return t('team.taskRunning')
  if (status === 'done') return t('team.taskDone')
  return t('team.taskPending')
}

const taskBadgeClass = (status) => {
  if (status === 'running') return 'is-running'
  if (status === 'done') return 'is-done'
  return 'is-pending'
}

const formatOutputSize = (size) => {
  const normalized = Number(size || 0)
  if (!normalized) {
    return ''
  }
  return `${normalized} chars`
}

const formatNumber = (value) => Number(value || 0).toLocaleString('en-US')

const replayFromTask = (taskId) => {
  emit('replay-from-task', taskId)
}

const acceptReviewSuggestion = () => {
  emit('accept-review-suggestion')
}

const dismissReviewSuggestion = () => {
  emit('dismiss-review-suggestion')
}

const toggleDependencyRow = (taskId) => {
  focusedTaskId.value = focusedTaskId.value === taskId ? '' : taskId
  expandedDependencyTaskId.value = expandedDependencyTaskId.value === taskId ? '' : taskId
}

const toggleFocusedTask = (taskId) => {
  focusedTaskId.value = focusedTaskId.value === taskId ? '' : taskId
}

const focusTask = (taskId) => {
  focusedTaskId.value = String(taskId || '').trim()
  expandedDependencyTaskId.value = focusedTaskId.value
}
</script>

<style scoped>
.team-panel {
  margin-top: 18px;
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  color: #f2f2f2;
}

.panel-subtitle {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
  line-height: 1.45;
}

.panel-mode {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(160, 196, 255, 0.12);
  color: #a0c4ff;
  font-size: 11px;
  white-space: nowrap;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.token-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(170, 255, 205, 0.08);
  border: 1px solid rgba(170, 255, 205, 0.12);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.token-summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
}

.token-summary-reuse {
  color: #99eaf9;
}

.token-hotspots {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.token-hotspots-title {
  color: #aaffcd;
  font-size: 11px;
  font-weight: 600;
}

.token-hotspot-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 11px;
}

.token-hotspot-item-reuse {
  color: #99eaf9;
}

.section-label {
  color: #f2f2f2;
  font-size: 13px;
  font-weight: 600;
}

.field-label {
  color: rgba(255, 255, 255, 0.6);
  font-size: 11px;
  font-weight: 500;
}

.panel-textarea,
.panel-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.22);
  color: #f2f2f2;
  font-size: 12px;
  box-sizing: border-box;
  resize: vertical;
}

.panel-textarea {
  min-height: 82px;
}

.panel-textarea-compact {
  min-height: 68px;
}

.panel-textarea:focus,
.panel-input:focus {
  outline: none;
  border-color: rgba(160, 196, 255, 0.35);
}

.panel-button {
  align-self: flex-start;
  padding: 8px 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #aaffcd, #99eaf9, #a0c4ff);
  color: #1a1a1a;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.panel-button:disabled {
  background: #3a3a3a;
  color: rgba(255, 255, 255, 0.35);
  cursor: not-allowed;
}

.panel-button-inline {
  align-self: auto;
  white-space: nowrap;
}

.timeline-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 8px;
}

.task-filter-chip {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.72);
  font-size: 11px;
  cursor: pointer;
}

.task-filter-chip.is-active {
  color: #f2f2f2;
  border-color: rgba(153, 234, 249, 0.35);
  background: rgba(153, 234, 249, 0.12);
}

.task-search-input,
.task-owner-select {
  min-height: 38px;
}

.review-directive-card {
  margin-top: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 213, 128, 0.1);
  border: 1px solid rgba(255, 213, 128, 0.18);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-directive-title {
  color: #ffd580;
  font-size: 11px;
  font-weight: 600;
}

.review-directive-meta {
  color: rgba(255, 255, 255, 0.62);
  font-size: 11px;
}

.review-directive-note {
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  line-height: 1.45;
  word-break: break-word;
}

.review-affected-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-rework-cost {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.review-rework-breakdown {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.review-rework-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
}

.review-rework-item-meta {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.review-rework-reused {
  color: #99eaf9;
}

.review-affected-title {
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  font-weight: 600;
}

.review-affected-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.review-affected-chip {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 213, 128, 0.2);
  background: rgba(255, 213, 128, 0.08);
  color: #ffd580;
  font-size: 11px;
  cursor: pointer;
}

.review-affected-chip.is-focused {
  border-color: rgba(170, 255, 205, 0.35);
  color: #aaffcd;
  background: rgba(170, 255, 205, 0.12);
}

.review-directive-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.review-dismiss-button {
  background: rgba(255, 255, 255, 0.08);
  color: #f2f2f2;
}

.replay-context-card {
  margin-top: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(160, 196, 255, 0.08);
  border: 1px solid rgba(160, 196, 255, 0.12);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.replay-context-title {
  color: #a0c4ff;
  font-size: 11px;
  font-weight: 600;
}

.replay-context-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.replay-context-meta,
.replay-context-node {
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
}

.replay-context-task {
  color: #f2f2f2;
  font-size: 11px;
  font-weight: 600;
}

.replay-context-preview {
  color: rgba(255, 255, 255, 0.72);
  font-size: 11px;
  line-height: 1.45;
  word-break: break-word;
}

.dependency-graph-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(120px, 0.8fr);
  gap: 10px;
  align-items: center;
  cursor: pointer;
  padding: 8px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.dependency-graph-row:first-of-type {
  border-top: none;
}

.dependency-graph-row.is-focused {
  background: rgba(153, 234, 249, 0.06);
  border-radius: 10px;
  padding-left: 8px;
  padding-right: 8px;
}

.dependency-predecessors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.dependency-node {
  display: inline-flex;
  align-items: center;
  padding: 6px 9px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.2;
}

.dependency-node-source {
  background: rgba(153, 234, 249, 0.12);
  color: #99eaf9;
}

.dependency-node-target {
  justify-content: center;
  background: rgba(170, 255, 205, 0.12);
  color: #aaffcd;
  font-weight: 600;
}

.dependency-arrow {
  color: rgba(255, 255, 255, 0.52);
  font-size: 11px;
  font-weight: 600;
}

.dependency-row-toggle {
  grid-column: 1 / -1;
  color: rgba(255, 255, 255, 0.52);
  font-size: 11px;
}

.dependency-row-details {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
}

.dependency-row-detail {
  color: rgba(255, 255, 255, 0.74);
  font-size: 11px;
  line-height: 1.45;
  word-break: break-word;
}

@media (max-width: 720px) {
  .task-search-row {
    grid-template-columns: 1fr;
  }

  .dependency-graph-row {
    grid-template-columns: 1fr;
  }

  .dependency-arrow {
    text-align: center;
  }
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
}

.task-card.is-affected {
  border: 1px solid rgba(153, 234, 249, 0.24);
  background: rgba(153, 234, 249, 0.06);
}

.task-card.is-focused {
  box-shadow: 0 0 0 1px rgba(170, 255, 205, 0.28) inset;
}

.task-main {
  min-width: 0;
}

.task-title {
  color: #f2f2f2;
  font-size: 12px;
  font-weight: 600;
}

.task-owner {
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.45);
  font-size: 11px;
}

.task-output-preview {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  line-height: 1.45;
}

.task-injected-dependencies {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  line-height: 1.45;
}

.task-output-label {
  color: rgba(160, 196, 255, 0.82);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.task-output-text {
  word-break: break-word;
}

.task-injected-list {
  word-break: break-word;
}

.task-output-size {
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
}

.task-badge {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.task-replay-button {
  padding: 6px 10px;
  font-size: 11px;
}

.task-badge.is-pending {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
}

.task-badge.is-running {
  background: rgba(160, 196, 255, 0.16);
  color: #a0c4ff;
}

.task-badge.is-done {
  background: rgba(170, 255, 205, 0.16);
  color: #aaffcd;
}

.task-badge.is-reused {
  background: rgba(153, 234, 249, 0.16);
  color: #99eaf9;
}

.memory-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.memory-column {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.approval-create {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.approval-blocking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  white-space: nowrap;
}

.approval-blocking-toggle input {
  accent-color: #ffd580;
}

.approval-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.approval-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
}

.approval-main {
  min-width: 0;
}

.approval-title {
  color: #f2f2f2;
  font-size: 12px;
  font-weight: 600;
}

.approval-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.approval-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.approval-badge.is-open {
  background: rgba(255, 213, 128, 0.14);
  color: #ffd580;
}

.approval-badge.is-resolved {
  background: rgba(170, 255, 205, 0.14);
  color: #aaffcd;
}

.approval-badge.is-blocking {
  background: rgba(255, 213, 128, 0.14);
  color: #ffd580;
}

.approval-note,
.empty-hint,
.panel-footer {
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
  line-height: 1.45;
}

.team-panel {
  margin-top: 20px;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 252, 246, 0.92) 0%, rgba(247, 242, 233, 0.88) 100%);
  border: 1px solid rgba(21, 58, 64, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.panel-title,
.section-label,
.task-title,
.approval-title,
.replay-context-task {
  color: #17353c;
}

.panel-subtitle,
.field-label,
.panel-mode,
.task-owner,
.approval-note,
.empty-hint,
.panel-footer,
.replay-context-meta,
.replay-context-node,
.review-directive-meta,
.review-affected-title,
.task-output-size {
  color: #647679;
}

.panel-mode {
  background: rgba(28, 104, 113, 0.1);
  color: #1c6871;
}

.panel-textarea,
.panel-input {
  background: rgba(255, 255, 255, 0.92);
  color: #17353c;
  border: 1px solid rgba(21, 58, 64, 0.1);
}

.panel-textarea:focus,
.panel-input:focus {
  border-color: rgba(28, 104, 113, 0.26);
  box-shadow: 0 0 0 3px rgba(28, 104, 113, 0.08);
}

.panel-button {
  background: linear-gradient(135deg, #19555c, #23707b, #e2b459);
  color: #ffffff;
}

.panel-button:disabled {
  background: #d8d4ca;
  color: #8d8b84;
}

.task-filter-chip,
.review-affected-chip,
.approval-badge,
.task-badge {
  border-width: 1px;
}

.task-filter-chip {
  background: rgba(255, 255, 255, 0.92);
  color: #5f7376;
  border-color: rgba(21, 58, 64, 0.08);
}

.task-filter-chip.is-active {
  color: #ffffff;
  border-color: #1f676d;
  background: #1f676d;
}

.token-card,
.review-directive-card,
.replay-context-card,
.task-card,
.approval-card {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(21, 58, 64, 0.08);
}

.task-card.is-affected {
  background: rgba(225, 244, 239, 0.92);
  border-color: rgba(28, 104, 113, 0.16);
}

.task-card.is-focused {
  box-shadow: 0 0 0 2px rgba(28, 104, 113, 0.12) inset;
}

.task-output-preview,
.task-injected-dependencies,
.review-directive-note,
.review-rework-item,
.replay-context-preview,
.token-summary,
.token-hotspot-item {
  color: #4f6569;
}

.task-output-label,
.token-hotspots-title,
.replay-context-title {
  color: #1c6871;
}

.task-badge.is-pending {
  background: #ece8df;
  color: #6a7a7d;
}

.task-badge.is-running {
  background: rgba(28, 104, 113, 0.12);
  color: #1c6871;
}

.task-badge.is-done {
  background: rgba(69, 146, 106, 0.14);
  color: #3f7e62;
}

.task-badge.is-reused {
  background: rgba(221, 180, 93, 0.16);
  color: #976c17;
}

.review-directive-card {
  background: rgba(251, 241, 214, 0.92);
  border-color: rgba(210, 157, 57, 0.18);
}

.review-directive-title,
.review-affected-chip {
  color: #9c6b12;
}

.review-dismiss-button {
  background: rgba(255, 255, 255, 0.86);
  color: #7f4a42;
  border: 1px solid rgba(127, 74, 66, 0.12);
}

.replay-context-card {
  background: rgba(236, 245, 242, 0.92);
  border-color: rgba(28, 104, 113, 0.12);
}

.dependency-graph-row {
  border-top-color: rgba(21, 58, 64, 0.06);
}

.dependency-graph-row.is-focused {
  background: rgba(225, 244, 239, 0.92);
}

.approval-blocking-toggle {
  color: #647679;
}

@media (max-width: 900px) {
  .team-panel {
    padding: 16px;
  }

  .task-search-row {
    grid-template-columns: 1fr;
  }
}
</style>
