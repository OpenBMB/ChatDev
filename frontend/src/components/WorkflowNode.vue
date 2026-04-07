<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getNodeStyles } from '../utils/colorUtils.js'
import { spriteFetcher } from '../utils/spriteFetcher.js'
import RichTooltip from './RichTooltip.vue'
import { getNodeHelp } from '../utils/helpContent.js'
import { configStore } from '../utils/configStore.js'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  isActive: {
    type: Boolean,
    default: false,
  },
  isHighlighted: {
    type: Boolean,
    default: false,
  },
  sprite: {
    type: String,
    default: '',
  },
})

// Expose hover events so parent can highlight edges
defineEmits(['hover', 'leave'])

// Walking animation state
const walkingFrame = ref(2) // Start with frame 2
let walkingInterval = null

// Compute properties for reactivity
const nodeType = computed(() => props.data?.type || 'unknown')
const nodeId = computed(() => props.data?.id || props.id)
const nodeDescription = computed(() => props.data?.description || '')
const isActive = computed(() => props.isActive)
const isHighlighted = computed(() => props.isHighlighted)
const dynamicStyles = computed(() => getNodeStyles(nodeType.value))
const mcpPrefixes = computed(() => {
  const tooling = Array.isArray(props.data?.config?.tooling) ? props.data.config.tooling : []
  const seen = new Set()
  const result = []

  for (const item of tooling) {
    const type = String(item?.type || '').trim()
    if (type !== 'mcp_remote' && type !== 'mcp_local') {
      continue
    }
    const prefix = String(item?.prefix || type).trim()
    if (!prefix || seen.has(prefix)) {
      continue
    }
    seen.add(prefix)
    result.push(prefix)
  }

  return result
})
const visibleMcpBadges = computed(() => mcpPrefixes.value.slice(0, 3))
const hiddenMcpBadgeCount = computed(() => Math.max(0, mcpPrefixes.value.length - visibleMcpBadges.value.length))

const nodeHelpContent = computed(() => getNodeHelp(nodeType.value))

const shouldShowTooltip = computed(() => configStore.ENABLE_HELP_TOOLTIPS && nodeHelpContent.value)

// Compute the current sprite path based on active state and walking frame
const currentSprite = computed(() => {
  if (!props.sprite) return ''

  if (isActive.value) {
    // When active, use walking frames (2 and 3)
    return spriteFetcher.fetchSprite(nodeId.value, 'D', walkingFrame.value)
  } else {
    // When not active, use the original frame (1)
    return props.sprite
  }
})

// Start/stop walking animation based on active state
const startWalking = () => {
  if (walkingInterval) return

  walkingInterval = setInterval(() => {
    walkingFrame.value = walkingFrame.value === 2 ? 3 : 2
  }, 500) // Alternate every 500ms
}

const stopWalking = () => {
  if (walkingInterval) {
    clearInterval(walkingInterval)
    walkingInterval = null
  }
  walkingFrame.value = 2 // Reset to frame 2
}

// Watch for active state changes
watch(isActive, (newActive) => {
  if (newActive) {
    startWalking()
  } else {
    stopWalking()
  }
})

// Cleanup on unmount
onUnmounted(() => {
  stopWalking()
})
</script>

<template>
  <RichTooltip v-if="shouldShowTooltip" :content="nodeHelpContent" placement="top">
    <div class="workflow-node-container">
      <div v-if="props.sprite" class="workflow-node-sprite">
        <img :src="currentSprite" :alt="`${nodeId} sprite`" class="node-sprite-image" />
      </div>
      <div
        class="workflow-node"
        :class="{ 'workflow-node-active': isActive, 'workflow-node-highlighted': isHighlighted }"
        :data-type="nodeType"
        :style="dynamicStyles"
        @mouseenter="$emit('hover', nodeId)"
        @mouseleave="$emit('leave', nodeId)"
      >
        <div class="workflow-node-header">
          <span class="workflow-node-type">{{ nodeType }}</span>
          <span class="workflow-node-id">{{ nodeId }}</span>
        </div>
        <div v-if="nodeDescription" class="workflow-node-description">
          {{ nodeDescription }}
        </div>
        <div v-if="visibleMcpBadges.length" class="workflow-node-badges">
          <span
            v-for="prefix in visibleMcpBadges"
            :key="`${nodeId}-${prefix}`"
            class="workflow-node-badge"
          >
            {{ prefix }}
          </span>
          <span v-if="hiddenMcpBadgeCount > 0" class="workflow-node-badge workflow-node-badge-more">
            +{{ hiddenMcpBadgeCount }}
          </span>
        </div>

        <Handle
          id="source"
          type="source"
          :position="Position.Right"
          class="workflow-node-handle"
        />
        <Handle
          id="target"
          type="target"
          :position="Position.Left"
          class="workflow-node-handle"
        />
      </div>
    </div>
  </RichTooltip>
  <div v-else class="workflow-node-container">
    <div v-if="props.sprite" class="workflow-node-sprite">
      <img :src="currentSprite" :alt="`${nodeId} sprite`" class="node-sprite-image" />
    </div>
    <div
      class="workflow-node"
      :class="{ 'workflow-node-active': isActive, 'workflow-node-highlighted': isHighlighted }"
      :data-type="nodeType"
      :style="dynamicStyles"
      @mouseenter="$emit('hover', nodeId)"
      @mouseleave="$emit('leave', nodeId)"
    >
      <div class="workflow-node-header">
        <span class="workflow-node-type">{{ nodeType }}</span>
        <span class="workflow-node-id">{{ nodeId }}</span>
      </div>
      <div v-if="nodeDescription" class="workflow-node-description">
        {{ nodeDescription }}
      </div>
      <div v-if="visibleMcpBadges.length" class="workflow-node-badges">
        <span
          v-for="prefix in visibleMcpBadges"
          :key="`${nodeId}-${prefix}`"
          class="workflow-node-badge"
        >
          {{ prefix }}
        </span>
        <span v-if="hiddenMcpBadgeCount > 0" class="workflow-node-badge workflow-node-badge-more">
          +{{ hiddenMcpBadgeCount }}
        </span>
      </div>

      <Handle
        id="source"
        type="source"
        :position="Position.Right"
        class="workflow-node-handle"
      />
      <Handle
        id="target"
        type="target"
        :position="Position.Left"
        class="workflow-node-handle"
      />
    </div>
  </div>
</template>

<style scoped>
.workflow-node-container {
  position: relative;
}

.workflow-node-description {
  /* Ensure long descriptions wrap instead of overflowing */
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-width: 200px;
  display: block;
}

.workflow-node-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  max-width: 200px;
}

.workflow-node-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  background: rgba(31, 103, 109, 0.12);
  border: 1px solid rgba(31, 103, 109, 0.18);
  color: #1f676d;
}

.workflow-node-badge-more {
  background: rgba(227, 180, 89, 0.12);
  border-color: rgba(227, 180, 89, 0.18);
  color: #9c6b12;
}

.workflow-node-sprite {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
}

.node-sprite-image {
  width: 32px;
  height: 40px;
  object-fit: contain;
}

:deep(.workflow-node-highlighted) {
  box-shadow: 0 0 0 4px rgba(31, 103, 109, 0.18), 0 18px 36px rgba(31, 103, 109, 0.18);
  border-color: rgba(31, 103, 109, 0.55) !important;
}
</style>
