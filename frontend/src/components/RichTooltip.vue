<template>
  <div 
    ref="wrapperRef"
    class="tooltip-wrapper"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
    @focus="handleFocus"
    @blur="handleBlur"
    @keydown.space.prevent="handleKeyboardActivate"
    @keydown.enter.prevent="handleKeyboardActivate"
    @keydown.escape="handleDismiss"
  >
    <slot></slot>
    
    <teleport to="body">
      <transition name="tooltip-fade">
        <div
          v-if="isVisible"
          ref="tooltipRef"
          class="rich-tooltip"
          :class="[`tooltip-${placement}`, { 'tooltip-keyboard-active': keyboardActive }]"
          :style="tooltipStyle"
          role="tooltip"
          :aria-hidden="!isVisible"
          @mouseenter="handleTooltipMouseEnter"
          @mouseleave="handleTooltipMouseLeave"
        >
          <div class="tooltip-content">
            <h4 v-if="content.title" class="tooltip-title">{{ content.title }}</h4>
            <p class="tooltip-description">{{ content.description }}</p>
            <ul v-if="content.examples && content.examples.length" class="tooltip-examples">
              <li v-for="(example, index) in content.examples" :key="index">{{ example }}</li>
            </ul>
            <a
              v-if="content.learnMoreUrl"
              :href="content.learnMoreUrl"
              target="_blank"
              rel="noopener"
              class="tooltip-learn-more"
              @click="handleLearnMore"
            >
              Learn More →
            </a>
          </div>
          <div class="tooltip-arrow" :data-placement="placement"></div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  content: {
    type: Object,
    required: true,
    validator: (value) => {
      return value && typeof value.description === 'string'
    }
  },
  delay: {
    type: Number,
    default: 500
  },
  placement: {
    type: String,
    default: 'top',
    validator: (value) => ['top', 'bottom', 'left', 'right'].includes(value)
  }
})

const isVisible = ref(false)
const tooltipRef = ref(null)
const wrapperRef = ref(null)
const tooltipStyle = ref({})
const hoverTimeout = ref(null)
const mouseInTooltip = ref(false)
const keyboardActive = ref(false)

const handleMouseEnter = () => {
  keyboardActive.value = false
  clearTimeout(hoverTimeout.value)
  hoverTimeout.value = setTimeout(() => {
    showTooltip()
  }, props.delay)
}

const handleMouseLeave = () => {
  clearTimeout(hoverTimeout.value)
  // Delay hiding to allow moving into tooltip
  setTimeout(() => {
    if (!mouseInTooltip.value) {
      hideTooltip()
    }
  }, 100)
}

const handleFocus = () => {
  // Don't auto-show on focus, wait for keyboard activation
}

const handleBlur = () => {
  if (keyboardActive.value) {
    hideTooltip()
    keyboardActive.value = false
  }
}

const handleKeyboardActivate = () => {
  keyboardActive.value = true
  showTooltip()
}

const handleDismiss = () => {
  hideTooltip()
  keyboardActive.value = false
}

const handleTooltipMouseEnter = () => {
  mouseInTooltip.value = true
}

const handleTooltipMouseLeave = () => {
  mouseInTooltip.value = false
  hideTooltip()
}

const handleLearnMore = () => {
  // Keep tooltip open when clicking learn more
  // The link will open in new tab
}

const showTooltip = async () => {
  isVisible.value = true
  await nextTick()
  calculatePosition()
}

const hideTooltip = () => {
  isVisible.value = false
  tooltipStyle.value = {}
}

const calculatePosition = () => {
  if (!tooltipRef.value || !wrapperRef.value) return

  const wrapper = wrapperRef.value.getBoundingClientRect()
  const tooltip = tooltipRef.value.getBoundingClientRect()
  const viewport = {
    width: window.innerWidth,
    height: window.innerHeight
  }

  const offset = 12 // Distance from target element
  let top = 0
  let left = 0
  let actualPlacement = props.placement

  // Calculate initial position based on preferred placement
  switch (props.placement) {
    case 'top':
      top = wrapper.top - tooltip.height - offset
      left = wrapper.left + (wrapper.width / 2) - (tooltip.width / 2)
      break
    case 'bottom':
      top = wrapper.bottom + offset
      left = wrapper.left + (wrapper.width / 2) - (tooltip.width / 2)
      break
    case 'left':
      top = wrapper.top + (wrapper.height / 2) - (tooltip.height / 2)
      left = wrapper.left - tooltip.width - offset
      break
    case 'right':
      top = wrapper.top + (wrapper.height / 2) - (tooltip.height / 2)
      left = wrapper.right + offset
      break
  }

  // Adjust if tooltip would go off-screen
  if (left < 10) {
    left = 10
  } else if (left + tooltip.width > viewport.width - 10) {
    left = viewport.width - tooltip.width - 10
  }

  if (top < 10) {
    // If it would go above viewport, flip to bottom
    if (props.placement === 'top') {
      top = wrapper.bottom + offset
      actualPlacement = 'bottom'
    } else {
      top = 10
    }
  } else if (top + tooltip.height > viewport.height - 10) {
    // If it would go below viewport, flip to top
    if (props.placement === 'bottom') {
      top = wrapper.top - tooltip.height - offset
      actualPlacement = 'top'
    } else {
      top = viewport.height - tooltip.height - 10
    }
  }

  tooltipStyle.value = {
    top: `${top}px`,
    left: `${left}px`
  }
}

// Listen to scroll and zoom events to dismiss tooltip
const handleScroll = () => {
  if (isVisible.value && !keyboardActive.value) {
    hideTooltip()
  }
}

const handleResize = () => {
  if (isVisible.value) {
    calculatePosition()
  }
}

onMounted(() => {
  // wrapperRef is now set via template ref, no need to query for it
  window.addEventListener('scroll', handleScroll, true)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  clearTimeout(hoverTimeout.value)
  window.removeEventListener('scroll', handleScroll, true)
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.tooltip-wrapper {
  display: inline-block;
  position: relative;
}

.rich-tooltip {
  position: fixed;
  z-index: 10000;
  max-width: 320px;
  background: rgba(26, 26, 26, 0.95);
  color: #f2f2f2;
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  font-size: 13px;
  line-height: 1.5;
  pointer-events: auto;
}

.tooltip-keyboard-active {
  outline: 2px solid #60b7ff;
  outline-offset: 2px;
}

.tooltip-content {
  position: relative;
}

.tooltip-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.tooltip-description {
  margin: 0 0 8px 0;
  color: #e0e0e0;
}

.tooltip-examples {
  margin: 8px 0;
  padding-left: 20px;
  color: #c0c0c0;
  font-size: 12px;
}

.tooltip-examples li {
  margin: 4px 0;
}

.tooltip-learn-more {
  display: inline-block;
  margin-top: 8px;
  color: #60b7ff;
  text-decoration: none;
  font-weight: 500;
  font-size: 12px;
  transition: color 0.2s;
}

.tooltip-learn-more:hover {
  color: #99ffeb;
  text-decoration: underline;
}

.tooltip-arrow {
  position: absolute;
  width: 10px;
  height: 10px;
  background: inherit;
  transform: rotate(45deg);
}

.tooltip-top .tooltip-arrow {
  bottom: -5px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
}

.tooltip-bottom .tooltip-arrow {
  top: -5px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
}

.tooltip-left .tooltip-arrow {
  right: -5px;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
}

.tooltip-right .tooltip-arrow {
  left: -5px;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.tooltip-fade-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.tooltip-fade-leave-to {
  opacity: 0;
}
</style>
