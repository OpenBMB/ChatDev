<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getNodeStyles } from '../utils/colorUtils.js'
import { spriteFetcher } from '../utils/spriteFetcher.js'

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
const dynamicStyles = computed(() => getNodeStyles(nodeType.value))

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
  <div class="workflow-node-container">
    <div v-if="props.sprite" class="workflow-node-sprite">
      <img :src="currentSprite" :alt="`${nodeId} sprite`" class="node-sprite-image" />
    </div>
    <div
      class="workflow-node"
      :class="{ 'workflow-node-active': isActive }"
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
</style>