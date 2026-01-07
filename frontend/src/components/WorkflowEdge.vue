<script setup>
import { computed, ref, nextTick, watch } from 'vue'
import { BaseEdge, EdgeLabelRenderer, getBezierPath, getSmoothStepPath, MarkerType } from '@vue-flow/core'
import { useVueFlow } from '@vue-flow/core'

const { findNode } = useVueFlow()

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  hoveredNodeId: {
    type: String,
    default: null,
  },
  source: {
    type: String,
    required: true,
  },
  target: {
    type: String,
    required: true,
  },
  sourceX: {
    type: Number,
    required: true,
  },
  sourceY: {
    type: Number,
    required: true,
  },
  targetX: {
    type: Number,
    required: true,
  },
  targetY: {
    type: Number,
    required: true,
  },
  sourcePosition: {
    type: String,
    required: true,
  },
  targetPosition: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    default: () => ({})
  },
  markerEnd: {
    type: [String, Object],
    default: MarkerType.ArrowClosed,
  },
  animated: {
    type: Boolean,
    default: false,
  },
  style: {
    type: Object,
    default: () => ({}),
  },
})

// Unified hover logic
const hoverState = computed(() => {
  const hovered = props.hoveredNodeId
  return {
    isEntry: hovered && hovered === props.target,
    isExit: hovered && hovered === props.source,
    isActive: !!(hovered && (hovered === props.target || hovered === props.source))
  }
})

const edgeMarkerEnd = computed(() => {
  const base = (typeof props.markerEnd === 'object' && props.markerEnd !== null)
    ? { type: MarkerType.Arrow, width: 18, height: 18, color: '#f2f2f2', strokeWidth: 2, ...props.markerEnd }
    : props.markerEnd

  const { isEntry, isExit } = hoverState.value

  if (isEntry) {
    // warm orange marker for incoming (entry) edges
    return { ...(typeof base === 'object' ? base : {}), color: '#ff8a00' }
  }
  if (isExit) {
    // cyan-turquoise marker for outgoing (exit) edges
    return { ...(typeof base === 'object' ? base : {}), color: '#00b8d8' }
  }

  return base
})

const edgeStyle = computed(() => {
  const baseStyle = {
    stroke: '#f2f2f2',
    strokeWidth: 1.2,
    ...props.style,
  }

  const { isEntry, isExit } = hoverState.value

  if (isEntry) {
    return {
      ...baseStyle,
      // warm yellow -> orange
      stroke: 'url(#incomingEdgeGradient)',
      strokeWidth: 1.4,
      transition: 'stroke 120ms ease, stroke-width 120ms ease',
    }
  }

  if (isExit) {
    return {
      ...baseStyle,
      // cyan -> turquoise
      stroke: 'url(#outgoingEdgeGradient)',
      strokeWidth: 1.4,
      transition: 'stroke 120ms ease, stroke-width 120ms ease',
    }
  }

  if (props.data?.trigger === false) {
    return {
      ...baseStyle,
      stroke: '#868686',
      strokeDasharray: '5, 5',
      animation: 'none',
    }
  }

  return baseStyle
})

// Ref for the animated overlay edge and animation handles
const animEdgeRef = ref(null)
let edgeAnimations = []
const labelAnimationDuration = ref(0) // Duration in ms for one dash cycle

const animEdgeStyle = computed(() => {
  const { isEntry, isExit } = hoverState.value

  if (isEntry) {
    return {
      stroke: 'url(#incomingEdgeGradient)',
      strokeWidth: 2.3,
      pointerEvents: 'none',
      filter: 'url(#incomingEdgeGlow)',
    }
  }

  if (isExit) {
    return {
      stroke: 'url(#outgoingEdgeGradient)',
      strokeWidth: 2.3,
      pointerEvents: 'none',
      filter: 'url(#outgoingEdgeGlow)',
    }
  }

  return { display: 'none' }
})

const isHovered = computed(() => hoverState.value.isActive)

watch(isHovered, async (val) => {
  if (val) {
    await nextTick()
    runEdgeAnimation()
  } else {
    cancelEdgeAnimation()
  }
})

function runEdgeAnimation() {
  const pathEl = animEdgeRef.value?.pathEl
  if (!pathEl) return

  const totalLength = pathEl.getTotalLength()
  const dash = 12
  pathEl.style.strokeDasharray = `${dash} ${Math.round(dash * 2.5)}`
  pathEl.style.strokeDashoffset = '0'

  const duration = Math.min(Math.max(totalLength * 6, 8000), 8000)

  // Dash offset animation (infinite loop)
  const dashAnim = pathEl.animate(
    [{ strokeDashoffset: '0' }, { strokeDashoffset: `-${totalLength}` }],
    { duration: duration * totalLength / 150, iterations: Infinity, easing: 'linear' }
  )

  // Pulse opacity to enhance glow effect
  const glowAnim = pathEl.animate(
    [{ strokeOpacity: 2 }, { strokeOpacity: 1 }, { strokeOpacity: 2 }],
    { duration: Math.max(600, Math.round(duration / 2)), iterations: Infinity, easing: 'ease-in-out' }
  )

  edgeAnimations = [dashAnim, glowAnim]

  // Calculate label animation duration based on dash cycle speed
  // Dash cycle = dash + gap. Here gap is approx 2.5 * dash.
  // We approximate wavelength as dash + gap ≈ 3.5 * dash
  // Since dash ≈ L/10, Wavelength ≈ 0.35 * L
  // Velocity = L / duration
  // Duration of one wavelength passing = Wavelength / Velocity = (0.35 L) / (L / duration) = 0.35 * duration
  labelAnimationDuration.value = duration * 0.35
}

function cancelEdgeAnimation() {
  edgeAnimations.forEach((a) => a.cancel && a.cancel())
  edgeAnimations = []
  if (animEdgeRef.value?.pathEl) {
    animEdgeRef.value.pathEl.style.strokeDashoffset = '0'
    animEdgeRef.value.pathEl.style.strokeOpacity = '1'
    animEdgeRef.value.pathEl.style.strokeDasharray = ''
  }
  labelAnimationDuration.value = 0
}

function getArcMidpoint({
  startX,
  startY,
  endX,
  endY,
  radiusX,
  radiusY,
  xAxisRotation = 0,
  largeArcFlag = 0,
  sweepFlag = 0,
}) {
  let rx = Math.abs(radiusX)
  let ry = Math.abs(radiusY)

  if (!rx || !ry) {
    return null
  }

  const phi = (xAxisRotation * Math.PI) / 180
  const cosPhi = Math.cos(phi)
  const sinPhi = Math.sin(phi)

  const dx = (startX - endX) / 2
  const dy = (startY - endY) / 2

  const x1p = cosPhi * dx + sinPhi * dy
  const y1p = -sinPhi * dx + cosPhi * dy

  let lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
  if (lambda > 1) {
    const scale = Math.sqrt(lambda)
    rx *= scale
    ry *= scale
  }

  const rxSq = rx * rx
  const rySq = ry * ry
  const x1pSq = x1p * x1p
  const y1pSq = y1p * y1p
  const denom = rxSq * y1pSq + rySq * x1pSq

  if (denom === 0) {
    return null
  }

  let factor = (rxSq * rySq - denom) / denom
  factor = Math.max(0, factor)

  const coef = (largeArcFlag === sweepFlag ? -1 : 1) * Math.sqrt(factor)

  const cxp = coef * ((rx * y1p) / ry)
  const cyp = coef * (-(ry * x1p) / rx)

  const cx = cosPhi * cxp - sinPhi * cyp + (startX + endX) / 2
  const cy = sinPhi * cxp + cosPhi * cyp + (startY + endY) / 2

  const angleBetween = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

  const v1x = (x1p - cxp) / rx
  const v1y = (y1p - cyp) / ry
  const v2x = (-x1p - cxp) / rx
  const v2y = (-y1p - cyp) / ry

  let startAngle = angleBetween(1, 0, v1x, v1y)
  let sweep = angleBetween(v1x, v1y, v2x, v2y)

  if (!sweepFlag && sweep > 0) {
    sweep -= 2 * Math.PI
  } else if (sweepFlag && sweep < 0) {
    sweep += 2 * Math.PI
  }

  const midAngle = startAngle + sweep / 2

  const midX = cosPhi * rx * Math.cos(midAngle) - sinPhi * ry * Math.sin(midAngle) + cx
  const midY = sinPhi * rx * Math.cos(midAngle) + cosPhi * ry * Math.sin(midAngle) + cy

  if (!Number.isFinite(midX) || !Number.isFinite(midY)) {
    return null
  }

  return { x: midX, y: midY }
}

// Get the path for the edge
const path = computed(() => {
  // First obtain source and target node dimensions
  const sourceNode = findNode(props.source)
  const targetNode = findNode(props.target)
  const sourceHeight = sourceNode?.dimensions.height
  const sourceWidth = sourceNode?.dimensions.width
  const targetHeight = targetNode?.dimensions.height
  const targetWidth = targetNode?.dimensions.width

  // Check if this is a self-loop edge (source === target)
  const isSelfLoop = props.source === props.target
  
  // Check if target node is to the left of source node
  const isLeftwardEdge = props.targetX < props.sourceX

  // Check if path can point from top/bottom of source node to target handle
  const isSourceNodeToTargetHandle = props.targetX >= props.sourceX - sourceWidth / 2
                    && props.targetX < props.sourceX

  // Check if path can point from source handle to top/bottom of target node
  const isSourceHandleToTargetNode = (props.targetX >= props.sourceX
                    && props.targetX < props.sourceX + sourceWidth / 4) &&
                    (Math.abs(props.targetY - props.sourceY) > (targetHeight + sourceHeight) / 2)


  // Check if path can point from top/bottom of source node to top/bottom of target node
  const isSourceNodeToTargetNode = props.targetX >= props.sourceX - sourceWidth
                    && props.targetX < props.sourceX - sourceWidth / 2
  
  if (isSelfLoop) {
    const startX = props.sourceX - sourceWidth / 6
    const startY = props.sourceY - sourceHeight / 2

    const endX = props.targetX + targetWidth / 6
    const endY = props.targetY - targetHeight / 2

    // For self-loop edges, create a circular path using SVG arc
    const radiusX = Math.abs(startX - endX) * 0.2
    const radiusY = 20
    
    // Calculate the arc path
    const arcPath = `M ${startX - 5} ${startY} A ${radiusX} ${radiusY} 0 1 0 ${endX + 5} ${endY}`
    
    // Calculate label position (center of the arc)
    const labelX = (startX + endX) / 2
    const labelY = Math.min(startY, endY) - radiusY - 20
    
    return [arcPath, labelX, labelY]
  }

  else if (isSourceNodeToTargetNode) {
    let adjustedSourceX = props.sourceX - sourceWidth / 2 - 1
    let adjustedSourceY = props.sourceY
    let adjustedTargetX = props.targetX + targetWidth / 2 + 1
    let adjustedTargetY = props.targetY

    if (props.targetY > props.sourceY) {
      adjustedSourceY = props.sourceY + sourceHeight / 2
      adjustedTargetY = props.targetY - targetHeight / 2 - 1
    } else {
      adjustedSourceY = props.sourceY - sourceHeight / 2
      adjustedTargetY = props.targetY + targetHeight / 2 + 1
    }

    return getBezierPath({
      sourceX: adjustedSourceX,
      sourceY: adjustedSourceY,
      targetX: adjustedTargetX,
      targetY: adjustedTargetY,
      sourcePosition: props.sourcePosition,
      targetPosition: props.targetPosition,
    })
  }

  else if (isSourceNodeToTargetHandle) {
      let adjustedSourceX = props.sourceX - sourceWidth / 2
      let adjustedSourceY = props.sourceY

      const isTargetBelowSource = props.targetY > props.sourceY
      if (isTargetBelowSource) {
        adjustedSourceY = props.sourceY + sourceHeight / 2
      } else {
        adjustedSourceY = props.sourceY - sourceHeight / 2
      }

      return getBezierPath({
        sourceX: adjustedSourceX,
        sourceY: adjustedSourceY,
        targetX: props.targetX,
        targetY: props.targetY,
        sourcePosition: props.sourcePosition,
        targetPosition: props.targetPosition,
      })
  }

  else if (isSourceHandleToTargetNode) {
      let adjustedTargetX = props.targetX + targetWidth / 2
      let adjustedTargetY = props.targetY

      const isTargetBelowSource = props.targetY > props.sourceY
      if (isTargetBelowSource) {
        adjustedTargetY = props.targetY - targetHeight / 2
      } else {
        adjustedTargetY = props.targetY + targetHeight / 2
      }

      return getBezierPath({
        sourceX: props.sourceX,
        sourceY: props.sourceY,
        targetX: adjustedTargetX,
        targetY: adjustedTargetY,
        sourcePosition: props.sourcePosition,
        targetPosition: props.targetPosition,
      })
  }
  
  else if (isLeftwardEdge) {
    // Determine clockwise (1) or counterclockwise (0) based on vertical position
    const isClockwise = props.targetY > props.sourceY
    
    // Adjust coordinates based on clockwise direction
    let adjustedSourceX = props.sourceX
    let adjustedSourceY = props.sourceY
    let adjustedTargetX = props.targetX
    let adjustedTargetY = props.targetY
    
    if (isClockwise) {
      adjustedSourceX = props.sourceX - sourceWidth / 2.05
      adjustedSourceY = props.sourceY + sourceHeight / 2
      adjustedTargetX = props.targetX + targetWidth / 2.05
      adjustedTargetY = props.targetY + targetHeight / 2
    } else {
      adjustedSourceX = props.sourceX - sourceWidth / 2.05
      adjustedSourceY = props.sourceY - sourceHeight / 2
      adjustedTargetX = props.targetX + targetWidth / 2.05 
      adjustedTargetY = props.targetY - targetHeight / 2
    }
    
    const radiusMultiplier = (isLeftwardEdge && !isClockwise) ? 1.1 : 1.1
    const radiusX = Math.abs(adjustedSourceX - adjustedTargetX) * 0.55 * radiusMultiplier
    const radiusY = Math.abs(adjustedSourceY - adjustedTargetY) * 0.70 * radiusMultiplier + 110
    
    const sweepFlag = isClockwise ? 1 : 0
    
    // Calculate the arc path
    const arcPath = `M ${adjustedSourceX} ${adjustedSourceY} A ${radiusX} ${radiusY} 1 0 ${sweepFlag} ${adjustedTargetX} ${adjustedTargetY}`
    
    const fallbackLabelX = (adjustedSourceX + adjustedTargetX) / 2
    const fallbackLabelY = (adjustedSourceY + adjustedTargetY) / 2

    const arcMidpoint = getArcMidpoint({
      startX: adjustedSourceX,
      startY: adjustedSourceY,
      endX: adjustedTargetX,
      endY: adjustedTargetY,
      radiusX,
      radiusY,
      xAxisRotation: 1,
      largeArcFlag: 0,
      sweepFlag,
    })

    const labelX = arcMidpoint?.x ?? fallbackLabelX
    const labelY = arcMidpoint?.y ?? fallbackLabelY
    
    return [arcPath, labelX, labelY]
  }
  
  // Default to bezier path for non-loopback and non-leftward edges
  return getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  })
})

// Extract path components from computed result
const edgePath = computed(() => path.value[0])
const labelX = computed(() => path.value[1])
const labelY = computed(() => path.value[2])

// Get edge label text depending on function/keyword
const edgeLabel = computed(() => {
  const condition = props.data?.condition
  if (condition === undefined || condition === null) {
    return ''
  }

  if (typeof condition === 'object' && condition !== null && condition.type) {
    if (condition.type === 'function') {
      // Don't show label for default condition
      const name = condition.config?.name || ''
      if (name === 'true') {
        return ''
      }
      return name
    } else if (condition.type === 'keyword') {
      // Format keyword condition: "Includes:", "Excludes:", "Regex:"
      const parts = []
      const config = condition.config || {}
      
      if (config.any && Array.isArray(config.any) && config.any.length > 0) {
        parts.push(`Includes: ${config.any.join(', ')}`)
      }
      if (config.none && Array.isArray(config.none) && config.none.length > 0) {
        parts.push(`Excludes: ${config.none.join(', ')}`)
      }
      if (config.regex && Array.isArray(config.regex) && config.regex.length > 0) {
        parts.push(`Regex: ${config.regex.join(', ')}`)
      }
      
      return parts.join('\n')
    }
  }
  
  return ''
})

const edgeLabelKey = computed(() => `${props.id}-${edgeLabel.value}`)

const labelStyle = computed(() => {
  // Base style
  const s = {
    position: 'absolute',
    transform: `translate(-50%, -50%) translate(${labelX.value}px, ${labelY.value}px)`,
    pointerEvents: 'none',
    backgroundColor: 'rgba(10, 10, 10, 0.9)',
    color: 'rgba(240, 240, 240, 1)',
    padding: '4px 6px',
    borderRadius: '3px',
    border: '1px solid #f2f2f2',
    fontSize: '12px',
    whiteSpace: 'pre-line',
    textAlign: 'center',
    lineHeight: '1.4',
    transition: 'border-color 200ms ease, box-shadow 200ms ease, color 200ms ease',
  }

  const { isEntry, isExit } = hoverState.value

  if (isEntry) {
    s.borderColor = '#ff8a00'
    s.color = '#ffdec2'
  } else if (isExit) {
    s.borderColor = '#00b8d8'
    s.color = '#c2f8ff'
  }

  // Inject CSS var for animation duration
  if (labelAnimationDuration.value > 0) {
    s['--label-anim-duration'] = `${labelAnimationDuration.value}ms`
  }

  return s
})
</script>

<template>
  <!-- Invisible SVG defs to provide gradients for edge strokes -->
  <svg style="position: absolute; width: 0; height: 0; overflow: hidden;" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="incomingEdgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#FFD97A" />
        <stop offset="60%" stop-color="#FFB84D" />
        <stop offset="100%" stop-color="#FF6A00" />
      </linearGradient>
      <linearGradient id="outgoingEdgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#00F5D4" />
        <stop offset="60%" stop-color="#00C7E6" />
        <stop offset="100%" stop-color="#00A0FF" />
      </linearGradient>
      <filter id="incomingEdgeGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>
        <feFlood flood-color="#FF8A00" flood-opacity="0.65" result="color"/>
        <feComposite in="color" in2="blur" operator="in" result="glow"/>
        <feMerge>
          <feMergeNode in="glow"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <filter id="outgoingEdgeGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>
        <feFlood flood-color="#00B8D8" flood-opacity="0.65" result="color"/>
        <feComposite in="color" in2="blur" operator="in" result="glow"/>
        <feMerge>
          <feMergeNode in="glow"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
  </svg>
  <BaseEdge
    :id="id"
    :path="edgePath"
    :marker-end="edgeMarkerEnd"
    :style="edgeStyle"
    :animated=false
  />
  <!-- Animated overlay edge (on top of base) -->
  <BaseEdge
    ref="animEdgeRef"
    :id="`${id}-anim`"
    :path="edgePath"
    :style="animEdgeStyle"
    :animated="false"
    class="nodrag nopan"
  />
  <EdgeLabelRenderer v-if="edgeLabel">
    <div
      :key="edgeLabelKey"
      :style="labelStyle"
      :class="{ 'animated-label': labelAnimationDuration > 0, 'nodrag': true, 'nopan': true }"
    >
      {{ edgeLabel }}
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
@keyframes edge-dash {
  to { stroke-dashoffset: -20; }
}

@keyframes edge-glow {
  0%, 100% { stroke-opacity: 1; }
  50% { stroke-opacity: 0.65; }
}

@keyframes label-pulse {
  0%, 100% {
    box-shadow: 0 0 1px inset rgba(255, 255, 255, 0);
    background-color: rgba(10, 10, 10, 0.95);
  }
  50% {
    box-shadow: 0 0 8px inset currentColor;
    background-color: rgba(10, 10, 10, 0.95);
  }
}

.animated-label {
  animation: label-pulse var(--label-anim-duration) infinite linear;
}
</style>
