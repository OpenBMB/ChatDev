<template>
  <div class="workflow-list">
    <div class="header-container">
      <!-- Search Bar -->
      <div class="search-container">
        <span class="search-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <input 
          type="text" 
          v-model="searchQuery" 
          placeholder="Search" 
          class="search-input"
        />
      </div>

      <button class="btn create-btn" @click="openFormGenerator" title="Create New Workflow">
        <span>Create Workflow</span>
        <span class="plus-icon">+</span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>Loading workflows...</p>
    </div>
    
    <!-- Error State -->
    <div v-else-if="error" class="error-message">
      <div class="error-icon">⚠️</div>
      <p>{{ error }}</p>
      <button @click="loadWorkflows()" class="retry-button">Retry</button>
    </div>
    
    <!-- File List -->
    <div v-else class="file-list">
      <!-- Animation for search filter -->
      <transition-group
        name="file-fade"
        tag="div"
        class="file-list-inner"
      >
        <div 
          v-for="file in filteredFiles" 
          :key="file.name"
          :class="['file-item', { active: isSelected(file) }]"
          @click="goToWorkflowView(file.name)"
        >
          <div class="file-info">
            <div class="file-name">{{ file.name }}</div>
            <div class="file-description">{{ file.description }}</div>
          </div>
          <div class="file-arrow">→</div>
        </div>
      </transition-group>
      
      <!-- Empty State -->
      <div v-if="filteredFiles.length === 0" class="empty-state">
        <p>No workflow files found</p>
      </div>
    </div>

    <!-- FormGenerator Modal -->
    <!-- Teleport to body in WorkflowWorkbench -->
    <Teleport to="body">
      <FormGenerator
        v-if="showFormGenerator"
        :breadcrumbs="[{node: 'DesignConfig', field: 'graph'}]"
        :recursive="false"  
        @close="closeFormGenerator"
        @submit="handleFormGeneratorSubmit"
      />
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchWorkflowsWithDesc } from '../utils/apiFunctions.js'
import FormGenerator from '../components/FormGenerator.vue'

const router = useRouter()
const props = defineProps({
  selected: {
    type: String,
    default: ''
  },
  useRouting: {
    type: Boolean,
    default: true
  }
})
const emit = defineEmits(['select'])
const yamlFiles = ref([])
const loading = ref(false)
const error = ref(null)

const showFormGenerator = ref(false)
const searchQuery = ref('')

const loadWorkflows = async () => {
  loading.value = true
  error.value = null

  const result = await fetchWorkflowsWithDesc()
  if (result.success) {
    yamlFiles.value = result.workflows
  } else {
    error.value = result.error
  }

  loading.value = false
}

// Expose loadWorkflows method for parent components
defineExpose({
  loadWorkflows
})

const filteredFiles = computed(() => {
  const rawList = Array.isArray(yamlFiles.value) ? [...yamlFiles.value] : []

  const query = searchQuery.value.toLowerCase().trim()
  let result = rawList
  
  if (query) {
    result = rawList.filter(file => {
      const name = (file?.name ?? '').toString().toLowerCase()
      const desc = (file?.description ?? '').toString().toLowerCase()

      if (!name && !desc) return false

      return name.includes(query) || desc.includes(query)
    })
  }

  // Sort by name using localeCompare for Pinyin support
  return result.sort((a, b) => {
    const nameA = a?.name ?? ''
    const nameB = b?.name ?? ''
    return nameA.localeCompare(nameB, 'zh')
  })
})

onMounted(() => {
  loadWorkflows()
})

const normalizeName = (fileName) => fileName?.replace?.('.yaml', '') ?? ''

const goToWorkflowView = (fileName) => {
  const workflowName = normalizeName(fileName)
  if (props.useRouting) {
    router.push(`/workflows/${workflowName}`)
  }
  emit('select', workflowName)
}

const isSelected = (file) => {
  const name = normalizeName(file?.name)
  return props.selected && props.selected === name
}

const extractGraphIdFromPayload = (payload) => {
  if (!payload) return null
  const graphId = payload.fullYaml?.graph?.id
  if (!graphId) return null
  return String(graphId).trim()
}

const openFormGenerator = () => {
  showFormGenerator.value = true
}

const closeFormGenerator = () => {
  showFormGenerator.value = false
}

const handleFormGeneratorSubmit = async (payload) => {
  await loadWorkflows()
  showFormGenerator.value = false

  const graphId = extractGraphIdFromPayload(payload)
  console.log('Extracted graphId:', graphId)
  if (!graphId) {
    return
  }

  const fileName = graphId.endsWith('.yaml') ? graphId : `${graphId}.yaml`
  goToWorkflowView(fileName)
}
</script>

<style scoped>
.workflow-list {
  width: 100%;
  height: 100%;
  background-color: #1a1a1a; /* Match HomeView background */
  padding: 10px;
  box-sizing: border-box;
  font-family: 'Inter', sans-serif;
  color: #f2f2f2;
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}

.workflow-list::-webkit-scrollbar {
  display: none;
}

.workflow-list::before {
  content: '';
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

.header-container,
.file-list,
.loading,
.error-message,
.empty-state {
  position: relative;
  z-index: 1;
}

.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  width: 100%;
}

/* Search Bar Styles */
.search-container {
  display: flex;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  padding: 10px 12px;
  width: 80px;
  min-height: 20px;
  transition: all 0.3s ease;
  backdrop-filter: blur(5px);
}

.search-container:hover {
  background-color: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  width: 160px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.search-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  color: rgba(255, 255, 255, 0.4);
  transition: color 0.3s ease;
}

.search-container:focus-within .search-icon {
  color: #a0c4ff;
}

.search-input {
  background: transparent;
  border: none;
  color: #f2f2f2;
  font-size: 14px;
  font-weight: 500;
  width: 100%;
  outline: none;
  font-family: 'Inter', sans-serif;
}

.search-input::placeholder {
  color: rgba(235, 235, 235, 0.3);
}

/* Styled Add Button - Matching HomeView aesthetic */
.create-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  border: none;
  padding: 10px 16px;
  min-height: 40px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-decoration: none;
  color: #1a1a1a;
  
  /* Pastel Rainbow Gradient from HomeView */
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  background-size: 200% 100%;
  animation: gradientShift 4s ease-in-out infinite;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  position: relative;
  overflow: hidden;
}

.create-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

@keyframes gradientShift {
  0%, 100% { background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
}

.create-btn:active {
  transform: translateY(0);
}

.plus-icon {
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
}

/* File List Styles */
.file-list {
  display: flex;
  flex-direction: column;
  max-width: 1000px; /* Limit width for better readability on large screens */
  margin: 0 auto;
}

.file-list-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Filter animation */
.file-fade-enter-active,
.file-fade-leave-active {
  transition: all 0.2s ease;
}

/* Enter: fade in from bottom */
.file-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

/* Leave: fade out to top */
.file-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.file-fade-leave-active {
  position: absolute;
  width: 100%;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background-color: rgba(255, 255, 255, 0.03); /* Transparent card */
  border: 1px solid rgba(255, 255, 255, 0.1); /* Thin border */
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  /* overflow: hidden; */
  z-index: 1;
  backdrop-filter: blur(5px); /* Optional: adds glassmorphism feel */
}

.file-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.2);
}

.file-item.active {
  border-color: rgba(160, 196, 255, 0.5);
  box-shadow: 0 0 0 1px rgba(160, 196, 255, 0.35);
}

.file-item.active .file-arrow {
  color: #a0c4ff;
}

.file-item::before {
  content: '';
  position: absolute;
  inset: -2px;
  z-index: -1;
  border-radius: 18px;
  padding: 2px;
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  -webkit-mask: 
     linear-gradient(#fff 0 0) content-box, 
     linear-gradient(#fff 0 0);
  mask: 
     linear-gradient(#fff 0 0) content-box, 
     linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s ease;
  background-size: 400% 100%;
  animation: gradientShift 3s ease-in-out infinite;
  filter: blur(4px);
}

.file-item:hover::before {
  opacity: 1;
}

/* Removed the left border glow ::before pseudo-element */

.file-info {
  flex: 1;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: #f2f2f2;
  margin-bottom: 4px;
}

.file-description {
  color: rgba(235, 235, 235, 0.6);
  font-size: 12px;
  line-height: 1.4;
}

.file-arrow {
  color: rgba(235, 235, 235, 0.3);
  font-size: 20px;
  font-weight: 300;
  transition: transform 0.3s ease, color 0.3s ease;
  margin-left: 16px;
}

.file-item:hover .file-arrow {
  color: #a0c4ff;
  transform: translateX(4px);
}

/* Loading & Error States */
.loading, .error-message, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: rgba(235, 235, 235, 0.6);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #a0c4ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.retry-button {
  margin-top: 16px;
  padding: 10px 24px;
  background-color: #3a3a3a;
  color: #f2f2f2;
  border: none;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.retry-button:hover {
  background-color: #4a4a4a;
}
</style>
