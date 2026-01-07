<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

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
</script>

<template>
  <div class="start-node" :style="{ opacity: data.opacity ?? 1 }">
    <div class="start-node-bubble" title="Start Node"></div>
    <!-- Provide source handle at right -->
    <Handle id="source" type="source" :position="Position.Right" class="start-node-handle" />
  </div>
</template>

<style scoped>
.start-node{
  display:flex;
  align-items:center;
  gap: 10px;
  padding:6px 6px;
  background: linear-gradient(90deg, #99ffeb, #60b7ff, #9096ff);
  background-size: 200% 100%;
  animation: gradientShift 5s ease-in-out infinite;
  color:#1a1a1a;
  border-radius:18px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.35);
  font-weight:600;
  font-size:13px;
  transition: opacity 0.10s ease-in-out;
}
.start-node-bubble{
  width:20px;
  height:20px;
  border-radius:50%;
  background: #f2f2f2;
  opacity:0.9;
  box-shadow: 0 2px 2px rgba(0,0,0,0.25);
}
.start-node-label{
  white-space:nowrap;
}
.start-node-handle{
  position:absolute;
  left:21px;
  width: 10px;
  height: 10px;
  background: linear-gradient(90deg, #99ffeb, #60b7ff, #9096ff);
  background-size: 200% 100%;
  animation: gradientShift 5s ease-in-out infinite;
  border: 1.5px solid #1a1a1a;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.start-node-handle:hover {
  filter: brightness(1.2);
}
@keyframes gradientShift {
  0%, 100% { background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
}
</style>


