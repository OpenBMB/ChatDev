<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import RichTooltip from './RichTooltip.vue'
import { helpContent } from '../utils/helpContent.js'
import { configStore } from '../utils/configStore.js'

const props = defineProps({
  id: {
    type: String,
    required: true
  },
  data: {
    type: Object,
    default: () => ({})
  }
})

const shouldShowTooltip = computed(() => configStore.ENABLE_HELP_TOOLTIPS)
</script>

<template>
  <RichTooltip v-if="shouldShowTooltip" :content="helpContent.startNode" placement="right">
    <div class="start-node" :style="{ opacity: data.opacity ?? 1 }">
      <div class="start-node-bubble"></div>
      <span class="start-node-label">Start</span>
      <!-- Provide source handle at right -->
      <Handle id="source" type="source" :position="Position.Right" class="start-node-handle" />
    </div>
  </RichTooltip>
  <div v-else class="start-node" :style="{ opacity: data.opacity ?? 1 }">
    <div class="start-node-bubble"></div>
    <span class="start-node-label">Start</span>
    <!-- Provide source handle at right -->
    <Handle id="source" type="source" :position="Position.Right" class="start-node-handle" />
  </div>
</template>

<style scoped>
.start-node{
  display:flex;
  align-items:center;
  gap: 10px;
  padding:8px 12px;
  background: linear-gradient(135deg, #f5edd2, #dff2ea);
  color:#164850;
  border: 1px solid rgba(23, 72, 80, 0.12);
  border-radius:18px;
  box-shadow: 0 10px 24px rgba(27,54,61,0.10);
  font-weight:700;
  font-size:13px;
  transition: opacity 0.10s ease-in-out, transform 0.2s ease;
}
.start-node-bubble{
  width:18px;
  height:18px;
  border-radius:50%;
  background: linear-gradient(135deg, #1f676d, #e2b459);
  box-shadow: 0 4px 10px rgba(31,103,109,0.24);
}
.start-node-label{
  white-space:nowrap;
  letter-spacing: 0.02em;
}
.start-node-handle{
  position:absolute;
  left:24px;
  width: 10px;
  height: 10px;
  background: #1f676d;
  border: 2px solid #fffdf8;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.start-node-handle:hover {
  filter: brightness(1.08);
}
</style>

