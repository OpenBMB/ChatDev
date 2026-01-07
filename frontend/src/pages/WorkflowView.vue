<template>
  <div class="workflow-view">
    <div class="workflow-bg"></div>
    <div class="header">
      <!-- Back button disabled -->
      <!-- <button @click="goBack" class="back-button">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 12H5M5 12L12 19M5 12L12 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button> -->
      <h1 class="workflow-name">{{ workflowName }}</h1>
    </div>
    
    <div class="content">
      <!-- YAML Editor Tab -->
      <div v-if="activeTab === 'yaml'" class="yaml-editor">
        <div v-if="yamlParseError" class="yaml-error">
          YAML Parse Error: {{ yamlParseError }}
        </div>
        <textarea 
          v-model="yamlTextString" 
          class="yaml-textarea"
          :class="{ 'yaml-error-border': yamlParseError }"
          placeholder="Loading YAML content..."
          readonly
        ></textarea>
      </div>

      <!-- VueFlow Graph Tab -->
      <div
        v-if="activeTab === 'graph'"
        class="vueflow-container"
        ref="vueflowContainerRef"
      >
        <VueFlow
         v-model:nodes="nodes"
         v-model:edges="edges"
         :delete-key-code="false"
         :fit-view-on-init="true"
         class="vueflow-graph"
         @node-click="onNodeClick"
         @edge-click="onEdgeClick"
         @connect="onConnect"
         @node-drag-stop="onNodeDragStop"
         @pane-context-menu="onPaneContextMenu"
         @node-context-menu="onNodeContextMenu"
         @edge-context-menu="onEdgeContextMenu">
        <template #node-workflow-node="props">
          <WorkflowNode
            :id="props.id"
            :data="props.data"
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
        <Controls position="bottom-right"/>
        </VueFlow>

        <!-- Right-click context menu inside VueFlow container -->
        <transition name="fade">
          <div
            v-if="contextMenuVisible"
            class="context-menu"
            :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
            @click.stop
          >
            <!-- Pane context menu -->
            <template v-if="contextMenuType === 'pane'">
              <div
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); openCreateNodeModal(); }"
              >
                Create Node
              </div>
            </template>

            <!-- Node context menu -->
            <template v-else-if="contextMenuType === 'node'">
              <div
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onCopyNodeFromContext(); }"
              >
                Copy Node
              </div>
              <div
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onDeleteNodeFromContext(); }"
              >
                Delete Node
              </div>
            </template>

            <!-- Edge context menu -->
            <template v-else-if="contextMenuType === 'edge'">
              <div
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onDeleteEdgeFromContext(); }"
              >
                Delete Edge
              </div>
            </template>
          </div>
        </transition>
      </div>
    </div>

    <div class="tabs">
      <div class="tab-buttons">
        <button 
          :class="['tab', { active: activeTab === 'graph' }]"
          @click="activeTab = 'graph'"
        >
          Workflow Graph
        </button>
        <button 
          :class="['tab', { active: activeTab === 'yaml' }]"
          @click="activeTab = 'yaml'"
        >
          YAML Configuration
        </button>
      </div>
      <div v-if="activeTab === 'graph'" class="editor-actions">
        <button @click="openCreateNodeModal" class="glass-button">
          <span>Create Node</span>
        </button>
        <button @click="openConfigureGraphModal" class="glass-button">
          <span>Configure Graph</span>
        </button>
        <button @click="goToLaunch" class="launch-button-primary">
          <span>Launch</span>
        </button>
        
        <div
          class="menu-container"
          @mouseenter="showMenu = true"
          @mouseleave="showMenu = false"
        >
          <div
            class="menu-trigger"
            :class="{ 'menu-trigger-active': showMenu }"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 12H21M3 6H21M3 18H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <transition name="fade">
            <div v-if="showMenu" class="menu-dropdown">
              <div @click="openRenameWorkflowModal" class="menu-item">Rename Workflow</div>
              <div @click="openCopyWorkflowModal" class="menu-item">Copy Workflow</div>
              <div @click="openManageVarsModal" class="menu-item">Manage Variables</div>
              <div @click="openManageMemoriesModal" class="menu-item">Manage Memories</div>
              <div @click="openCreateEdgeModal" class="menu-item">Create Edge</div>
            </div>
          </transition>
        </div>
      </div>
    </div>

  </div>

  <FormGenerator
    v-if="showDynamicFormGenerator"
    :breadcrumbs="formGeneratorBreadcrumbs"
    :recursive="formGeneratorRecursive"
    :workflow-name="workflowName"
    :initial-yaml="formGeneratorInitialYaml ?? yamlContent"
    :initial-form-data="formGeneratorInitialFormData"
    :mode="formGeneratorMode"
    :field-filter="formGeneratorFieldFilter"
    :read-only-fields="formGeneratorReadOnlyFields"
    @close="closeDynamicFormGenerator"
    @submit="handleFormGeneratorSubmit"
    @copy="handleFormGeneratorCopy"
  />

  <!-- Rename Workflow Modal -->
  <div v-if="showRenameModal" class="modal-overlay" @click.self="closeRenameModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">Rename Workflow</h3>
        <button @click="closeRenameModal" class="close-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="rename-workflow-name" class="form-label">Workflow Name</label>
          <input
            id="rename-workflow-name"
            v-model="renameWorkflowName"
            type="text"
            class="form-input"
            placeholder="Enter new workflow name"
            @keyup.enter="handleRenameSubmit"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeRenameModal" class="cancel-button">Cancel</button>
        <button @click="handleRenameSubmit" class="submit-button" :disabled="!renameWorkflowName.trim()">Submit</button>
      </div>
    </div>
  </div>

  <!-- Copy Workflow Modal -->
  <div v-if="showCopyModal" class="modal-overlay" @click.self="closeCopyModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">Copy Workflow</h3>
        <button @click="closeCopyModal" class="close-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="copy-workflow-name" class="form-label">Workflow Name</label>
          <input
            id="copy-workflow-name"
            v-model="copyWorkflowName"
            type="text"
            class="form-input"
            placeholder="Enter new workflow name"
            @keyup.enter="handleCopySubmit"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeCopyModal" class="cancel-button">Cancel</button>
        <button @click="handleCopySubmit" class="submit-button" :disabled="!copyWorkflowName.trim()">Submit</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import '../utils/vueflow.css'
import WorkflowNode from '../components/WorkflowNode.vue'
import WorkflowEdge from '../components/WorkflowEdge.vue'
import StartNode from '../components/StartNode.vue'
import FormGenerator from '../components/FormGenerator.vue'
import yaml from 'js-yaml'
import { fetchYaml, fetchVueGraph, postVuegraphs, updateYaml, postYamlNameChange, postYamlCopy } from '../utils/apiFunctions'

const props = defineProps({
  workflowName: {
    type: String,
    required: true
  }
})
const emit = defineEmits(['refresh-workflows'])
const router = useRouter()
const { toObject, fromObject, fitView, getViewport } = useVueFlow()

const vueflowContainerRef = ref(null)
// Hovered node id for highlighting related edges
const hoveredNodeId = ref(null)

const onNodeHover = (nodeId) => {
  hoveredNodeId.value = nodeId || null
}
const onNodeLeave = (_nodeId) => {
  hoveredNodeId.value = null
}

const workflowName = ref('')
const activeTab = ref('graph')
const yamlContent = ref({}) // YAML object
const yamlTextString = ref('') // YAML string
const yamlParseError = ref(null)

const showDynamicFormGenerator = ref(false)
const showMenu = ref(false)
const formGeneratorBreadcrumbs = ref([])
const formGeneratorRecursive = ref(false)
const formGeneratorInitialYaml = ref(null)
const formGeneratorInitialFormData = ref(null)
const formGeneratorMode = ref('create')
const formGeneratorFieldFilter = ref([])
const formGeneratorReadOnlyFields = ref([])

// Modal states for rename and copy
const showRenameModal = ref(false)
const showCopyModal = ref(false)
const renameWorkflowName = ref('')
const copyWorkflowName = ref('')

const FORM_GENERATOR_CONFIG = Object.freeze({
  graph: [
    { node: 'DesignConfig', field: 'graph' }
  ],
  node: [
    { node: 'DesignConfig', field: 'graph' },
    { node: 'GraphDefinition', field: 'nodes' }
  ],
  edge: [
    { node: 'DesignConfig', field: 'graph' },
    { node: 'GraphDefinition', field: 'edges' }
  ],
  memory: [
    { node: 'DesignConfig', field: 'graph' }
  ],
  vars: [
    // Empty breadcrumbs for managing global vars
  ]
})

const cloneDeep = (value) => {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value === 'object') {
    return JSON.parse(JSON.stringify(value))
  }
  return value
}

// VueFlow nodes and edges
const nodes = ref([])

const edges = ref([])

const isCreatingConnection = ref(false)

// Start node ID
const START_NODE_ID = '__start'

// Context menu state
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const pendingNodePosition = ref(null)
const contextMenuType = ref('pane') // 'pane' | 'node' | 'edge'
const contextNodeId = ref(null)
const contextEdgeInfo = ref(null) // { from, to }

const hideContextMenu = () => {
  contextMenuVisible.value = false
}

const getFlowPositionFromEvent = (event) => {
  try {
    const viewport = getViewport()
    const container = vueflowContainerRef.value
    if (!viewport || !container || !event) {
      return getCentralPosition()
    }

    const rect = container.getBoundingClientRect()
    const screenX = event.clientX - rect.left
    const screenY = event.clientY - rect.top

    const x = (screenX - viewport.x) / viewport.zoom
    const y = (screenY - viewport.y) / viewport.zoom

    return { x, y }
  } catch (error) {
    console.warn('Failed to convert click position to flow coordinates:', error)
    return getCentralPosition()
  }
}

const onContainerContextMenu = (event) => {
  // Only respond to right-clicks inside the flow container
  if (!vueflowContainerRef.value) {
    return
  }

  // Store menu position relative to container (for UI)
  const rect = vueflowContainerRef.value.getBoundingClientRect()
  contextMenuX.value = event.clientX - rect.left
  contextMenuY.value = event.clientY - rect.top
  contextMenuType.value = 'pane'
  contextNodeId.value = null
  contextEdgeInfo.value = null
  contextMenuVisible.value = true

  // Pre-compute desired node position in flow coordinates
  pendingNodePosition.value = getFlowPositionFromEvent(event)
}

// Disable default pane context behaviour in VueFlow and use custom behaviour
const onPaneContextMenu = (params) => {
  const mouseEvent = params?.event || params
  mouseEvent?.preventDefault?.()
  if (!mouseEvent) return
  onContainerContextMenu(mouseEvent)
}

const onNodeContextMenu = (params) => {
  const mouseEvent = params?.event || params
  const node = params?.node || params?.event?.node || params
  if (!mouseEvent || !node?.id || !vueflowContainerRef.value) {
    return
  }
  mouseEvent.preventDefault?.()
  
  // Ignore context menu for start node, show dim animation
  if (node.id === START_NODE_ID) {
    dimStartNode()
    return
  }

  const rect = vueflowContainerRef.value.getBoundingClientRect()
  contextMenuX.value = mouseEvent.clientX - rect.left
  contextMenuY.value = mouseEvent.clientY - rect.top

  contextMenuType.value = 'node'
  contextNodeId.value = node.id
  contextEdgeInfo.value = null
  pendingNodePosition.value = null
  contextMenuVisible.value = true
}

const onEdgeContextMenu = (params) => {
  const mouseEvent = params?.event || params
  const edge = params?.edge || params?.event?.edge || params
  if (!mouseEvent || !edge || !vueflowContainerRef.value) {
    return
  }
  mouseEvent.preventDefault?.()

  const fromId = edge.data?.from || edge.source
  const toId = edge.data?.to || edge.target
  if (!fromId || !toId) {
    return
  }

  const rect = vueflowContainerRef.value.getBoundingClientRect()
  contextMenuX.value = mouseEvent.clientX - rect.left
  contextMenuY.value = mouseEvent.clientY - rect.top

  contextMenuType.value = 'edge'
  contextNodeId.value = null
  contextEdgeInfo.value = { from: fromId, to: toId }
  pendingNodePosition.value = null
  contextMenuVisible.value = true
}

const onGlobalClick = () => {
  // Clicks outside the menu will bubble to window and handled here
  // Clicks on the menu itself are stopped with @click.stop
  if (contextMenuVisible.value) {
    contextMenuVisible.value = false
  }
}

const dimStartNode = () => {
  const startNode = nodes.value.find(node => node.id === START_NODE_ID)
  if (!startNode) return

  const dimSpeed = 120 // milliseconds between opacity changes - slightly slower for smoothness
  const dimSteps = [1, 0.6, 1, 0.6, 1] // Full opacity -> dim -> full -> dim -> full

  dimSteps.forEach((opacity, index) => {
    setTimeout(() => {
      // Add opacity to node data for animation
      startNode.data = { ...startNode.data, opacity }
      
      // Force VueFlow to update by triggering reactivity
      nodes.value = [...nodes.value]
    }, index * dimSpeed)
  })
}

// Persist an updated YAML snapshot back to the server and refresh local state
const persistYamlSnapshot = async (snapshot) => {
  try {
    if (!workflowName.value) {
      return false
    }
    const yamlString = yaml.dump(snapshot ?? {})
    const result = await updateYaml(workflowName.value, yamlString)
    if (!result?.success) {
      console.error('Failed to update workflow YAML:', result?.message || result?.detail)
      return false
    }
    console.log("YAML snapshot successfully persisted through API")
    return true
  } catch (error) {
    console.error('Error persisting YAML snapshot:', error)
    return false
  }
}

const onCopyNodeFromContext = () => {
  const nodeId = contextNodeId.value
  if (!nodeId) {
    return
  }
  const yamlNodeContent = (yamlContent.value?.graph?.nodes || []).find(node => node.id === nodeId)
  if (!yamlNodeContent) {
    console.warn(`[WorkflowView] Node with id "${nodeId}" not found for copying`)
    return
  }
  handleFormGeneratorCopy({ initialFormData: yamlNodeContent })
}

const deleteNodeById = async (nodeId) => {
  if (!nodeId) {
    return
  }
  const snapshot = snapshotYamlContent()
  if (!snapshot?.graph) {
    return
  }
  const nodesArr = Array.isArray(snapshot.graph.nodes) ? snapshot.graph.nodes : []
  const edgesArr = Array.isArray(snapshot.graph.edges) ? snapshot.graph.edges : []

  // Remove the node and its related edges
  const nextNodes = nodesArr.filter(node => node?.id !== nodeId)
  const nextEdges = edgesArr.filter(edge => edge?.from !== nodeId && edge?.to !== nodeId)
  
  // Remove node ID from graph.start/end
  const nextStart = Array.isArray(snapshot.graph.start)
    ? snapshot.graph.start.filter(id => id !== nodeId)
    : snapshot.graph.start
  const nextEnd = Array.isArray(snapshot.graph.end)
    ? snapshot.graph.end.filter(id => id !== nodeId)
    : snapshot.graph.end

  const nextSnapshot = {
    ...snapshot,
    graph: {
      ...snapshot.graph,
      nodes: nextNodes,
      edges: nextEdges,
      start: nextStart,
      end: nextEnd
    }
  }

  const ok = await persistYamlSnapshot(nextSnapshot)
  if (!ok) {
    return
  }

  await loadYamlFile()
  syncVueNodesAndEdgesData()
  await nextTick()
  await saveVueFlowGraph()
}

const deleteEdgeByEndpoints = async (fromId, toId) => {
  if (!fromId || !toId) {
    return
  }
  const snapshot = snapshotYamlContent()
  if (!snapshot?.graph || !Array.isArray(snapshot.graph.edges)) {
    return
  }

  let removed = false
  const nextEdges = snapshot.graph.edges.filter(edge => {
    if (!removed && edge?.from === fromId && edge?.to === toId) {
      removed = true
      return false
    }
    return true
  })

  // Delete from .start if edge is from Start Node
  let nextStart = snapshot.graph.start
  if (fromId === START_NODE_ID) {
    nextStart = Array.isArray(snapshot.graph.start)
      ? snapshot.graph.start.filter(id => id !== toId)
      : snapshot.graph.start

    // Empty start node array is not allowed
    const startArray = Array.isArray(nextStart) ? nextStart : []
    if (startArray.length === 0) {
      alert("At least one connection required from start node!")
      return
    }
  }

  const nextSnapshot = {
    ...snapshot,
    graph: {
      ...snapshot.graph,
      edges: nextEdges,
      start: nextStart
    }
  }

  const ok = await persistYamlSnapshot(nextSnapshot)
  if (!ok) {
    return
  }

  await loadYamlFile()
  syncVueNodesAndEdgesData()
  await nextTick()
  await saveVueFlowGraph()
}

const onDeleteNodeFromContext = async () => {
  const nodeId = contextNodeId.value
  contextNodeId.value = null
  const confirmed = window.confirm(`Are you sure you want to delete this node?`)
  if (!confirmed) {
    return
  }
  if (!nodeId) {
    return
  }
  await deleteNodeById(nodeId)
}

const onDeleteEdgeFromContext = async () => {
  const info = contextEdgeInfo.value
  contextEdgeInfo.value = null
  const confirmed = window.confirm(`Are you sure you want to delete this edge?`)
  if (!confirmed) {
    return
  }
  if (!info?.from || !info?.to) {
    return
  }
  await deleteEdgeByEndpoints(info.from, info.to)
}

const initializeWorkflow = async (name) => {
  if (!name) {
    return
  }
  workflowName.value = name
  console.log('Workflow initialized: ', workflowName.value)
  await loadYamlFile()
  loadAndSyncVueFlowGraph()
  await nextTick()
  fitView?.({ padding: 0.1 })
}

watch(
  () => props.workflowName,
  async (newName) => {
    await initializeWorkflow(newName)
  },
  { immediate: false }
)

onMounted(async () => {
  window.addEventListener('click', onGlobalClick)
  await initializeWorkflow(props.workflowName)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', onGlobalClick)
})

watch(activeTab, async (newTab) => {
  if (newTab === 'graph') {
    await nextTick()
    fitView?.({ padding: 0.1 })
  }
})

const saveVueFlowGraph = async () => {
  try {
    const flowObj = toObject()
    const key = workflowName.value
    const result = await postVuegraphs({
      filename: key,
      content: JSON.stringify(flowObj)
    })

    if (!result?.success) {
      console.error('Failed to save VueFlow graph:', result?.message || result?.detail)
      return false
    }
    return true
  } catch (error) {
    console.error('Failed to save VueFlow graph:', error)
    return false
  }
}

const loadAndSyncVueFlowGraph = async () => {
  try {
    const key = workflowName.value
    const result = await fetchVueGraph(key)

    if(result?.success === true) {
      console.log("Graph fetched successfully")
    }

    if (result?.status === 404) {
      // Not found in server storage, fallback
      console.log("No graph found, fallback to generation")
      await generateNodesAndEdges()
      return false
    }

    if (!result?.success) {
      console.error('Failed to load VueFlow graph:', result?.message || result?.detail)
      // Fallback if server error
      generateNodesAndEdges()
      return false
    }

    const content = result?.content
    if (content) {
      const flow = JSON.parse(content)
      if (flow) {
        fromObject(flow)
        await nextTick()
        syncVueNodesAndEdgesData()
        return true
      }
    }
  } catch (error) {
    console.error('Failed to load saved VueFlow graph:', error)
  }

  // If no VueFlow graph restored, fall back to manual generation
  await generateNodesAndEdges()
  return false
}

const loadYamlFile = async () => {
  try {
    if (!workflowName.value) {
      return
    }
    const result = await fetchYaml(workflowName.value)

    if (!result?.success) {
      console.error('Failed to load YAML file', result?.message || result?.detail)
      return
    }

    const yamlString = result.content ?? ''
    console.log('YAML content loaded successfully')

    // Parse YAML string to YAML object
    try {
      const parsed = yaml.load(yamlString)
      yamlContent.value = parsed || {}
      yamlTextString.value = yamlString
      yamlParseError.value = null
    } catch (parseError) {
      console.error('Error parsing YAML:', parseError)
      yamlParseError.value = parseError.message
      yamlTextString.value = yamlString
    }
  } catch (error) {
    console.error('Error loading YAML file: ', error)
  }
}

const getCentralPosition = () => {
  try {
    const viewport = getViewport()
    if (viewport && vueflowContainerRef.value) {
      // Get container dimensions
      const container = vueflowContainerRef.value
      const containerWidth = container.clientWidth || container.offsetWidth
      const containerHeight = container.clientHeight || container.offsetHeight
      
      const screenCenterX = containerWidth / 2
      const screenCenterY = containerHeight / 2
      
      // Convert screen coordinates to flow coordinates
      // Formula: flowCoord = (screenCoord - viewportOffset) / zoom
      const centerX = (screenCenterX - viewport.x) / viewport.zoom
      const centerY = (screenCenterY - viewport.y) / viewport.zoom
      
      return { x: centerX, y: centerY }
    }
  } catch (error) {
    console.warn('Failed to get viewport center, using default position:', error)
  }
  // Fallback to default center position
  return { x: 400, y: 300 }
}

const updateNodesAndEdgesFromYaml = (preserveExistingLayout = false) => {
  try {
    const yamlNodes = Array.isArray(yamlContent.value?.graph?.nodes)
      ? yamlContent.value.graph.nodes
      : []
    const yamlEdges = Array.isArray(yamlContent.value?.graph?.edges)
      ? yamlContent.value.graph.edges
      : []

    const currentNodes = nodes.value || []
    const currentEdges = edges.value || []

    const existingNodeById = preserveExistingLayout
      ? new Map(currentNodes.map(node => [node.id, node]))
      : null
    const existingEdgeByKey = preserveExistingLayout
      ? new Map(currentEdges.map(edge => [`${edge.source}-${edge.target}`, edge]))
      : null
    
      // Compute node positions using a simple topological layering
      // This arranges nodes by levels (distance from sources)
      // Ignore backward/cycle edges for cyclic graphs
      try {
        const nodeIds = (yamlNodes || []).map(n => n?.id).filter(Boolean)

        // Build adjacency and indegree
        const adj = new Map()
        const indegree = new Map()
        nodeIds.forEach(id => {
          adj.set(id, new Set())
          indegree.set(id, 0)
        })

        ;(yamlEdges || []).forEach(e => {
          if (!e || !e.from || !e.to) return
          if (!adj.has(e.from) || !adj.has(e.to)) return
          adj.get(e.from).add(e.to)
          indegree.set(e.to, (indegree.get(e.to) || 0) + 1)
        })

        // Kahn's algorithm to compute levels
        const levelById = new Map()
        const q = []
        nodeIds.forEach(id => {
          if ((indegree.get(id) || 0) === 0) {
            q.push(id)
            levelById.set(id, 0)
          }
        })

        // Heuristic: if the graph has no indegree-0 nodes (pure cycle),
        // pick the first node declared in YAML `graph.start` as a pseudo-source
        // so Kahn's algorithm can proceed and assign at least one level.
        if (q.length === 0) {
          try {
            const yamlStartList = Array.isArray(yamlContent.value?.graph?.start)
              ? yamlContent.value.graph.start
              : []
            const firstStart = yamlStartList.find(s => nodeIds.includes(s))
            if (firstStart) {
              // Force indegree to zero and seed the queue so at least one node gets level 0
              indegree.set(firstStart, 0)
              q.push(firstStart)
              levelById.set(firstStart, 0)
            }
          } catch (e) {
            // ignore and fall back later
          }
        }

        while (q.length) {
          const id = q.shift()
          const baseLevel = levelById.get(id) || 0
          const neighbors = adj.get(id) || new Set()
          for (const nb of neighbors) {
            const prev = levelById.get(nb) ?? 0
            const newLevel = Math.max(prev, baseLevel + 1)
            levelById.set(nb, newLevel)
            indegree.set(nb, indegree.get(nb) - 1)
            if (indegree.get(nb) === 0) q.push(nb)
          }
        }

        
        const predecessors = new Map()
        nodeIds.forEach(id => predecessors.set(id, new Set()))
        ;(yamlEdges || []).forEach(e => {
          if (!e || !e.from || !e.to) return
          if (!predecessors.has(e.to)) return
          predecessors.get(e.to).add(e.from)
        })

        let changed = true
        let iterations = 0
        const maxIterations = nodeIds.length + 5
        while (changed && iterations < maxIterations) {
          changed = false
          iterations++
          nodeIds.forEach(id => {
            if (levelById.has(id)) return
            const preds = predecessors.get(id) || new Set()
            const predLevels = Array.from(preds).map(p => levelById.get(p)).filter(l => typeof l === 'number')
            if (predLevels.length) {
              const lvl = Math.max(...predLevels) + 1
              levelById.set(id, lvl)
              changed = true
            }
          })
        }

        // Any remaining unassigned nodes -> fallback to level 0
        nodeIds.forEach(id => {
          if (!levelById.has(id)) levelById.set(id, 0)
        })

        // Group nodes by level and compute positions (simple grid per level)
        const buckets = new Map()
        for (const [id, lvl] of levelById.entries()) {
          if (!buckets.has(lvl)) buckets.set(lvl, [])
          buckets.get(lvl).push(id)
        }

        const positions = new Map()
        const levelKeys = Array.from(buckets.keys()).sort((a, b) => a - b)
        const spacingX = 280
        const spacingY = 120
        const startX = 50
        const startY = 50

        levelKeys.forEach(lvl => {
          const ids = buckets.get(lvl) || []
          const x = startX + lvl * spacingX
          let currentY = startY
          // Apply a slight Y offset (+/-10) to the first node in each layer to avoid exact horizontal alignments
          const layerOffset = (lvl % 2 === 0) ? -30 : 30
          ids.forEach((id, idx) => {
            const yPos = currentY + (idx === 0 ? layerOffset : 0)
            positions.set(id, { x, y: yPos })
            currentY += spacingY
          })
        })

        // Build nextNodes respecting preserveExistingLayout where possible
        const nextNodes = yamlNodes.map((yamlNode, index) => {
          const id = yamlNode?.id
          if (!id) return null
          if (preserveExistingLayout && existingNodeById?.has(id)) {
            const existingNode = existingNodeById.get(id)
            return {
              ...existingNode,
              id,
              label: id,
              data: yamlNode
            }
          }

          const pos = positions.get(id) || getCentralPosition()
          return {
            id,
            type: 'workflow-node',
            label: id,
            position: pos,
            data: yamlNode
          }
        }).filter(Boolean)

        nodes.value = nextNodes
      } catch (err) {
        console.error('Failed to compute topological layout, falling back to center positions:', err)
        // Fallback to previous behavior
        const nextNodes = yamlNodes.map((yamlNode, index) => ({
          id: yamlNode.id,
          type: 'workflow-node',
          label: yamlNode.id,
          position: getCentralPosition(),
          data: yamlNode
        }))
        nodes.value = nextNodes
      }

    // Build edges from YAML (preserve layout where possible)
    const nextYamlEdges = yamlEdges.map(yamlEdge => {
      const key = `${yamlEdge.from}-${yamlEdge.to}`
      const baseEdge = preserveExistingLayout && existingEdgeByKey?.has(key)
        ? existingEdgeByKey.get(key)
        : {
            id: key,
            source: yamlEdge.from,
            target: yamlEdge.to,
            type: 'workflow-edge'
          }

      return {
        ...baseEdge,
        id: key,
        source: yamlEdge.from,
        target: yamlEdge.to,
        data: yamlEdge,
        markerEnd: {
          type: MarkerType.Arrow,
          width: 16,
          height: 16,
          // Set color to match with edge
          color: (yamlEdge && yamlEdge.trigger === false) ? '#868686' : '#f2f2f2',
          strokeWidth: 1.5,
        },
      }
    })
    // Nodes in .start
    const declaredStartSet = new Set(Array.isArray(yamlContent.value?.graph?.start) ? yamlContent.value.graph.start : [])

    // Create visual-only start node (reuse existing if present)
    let startNode = null
    if (preserveExistingLayout && existingNodeById?.has(START_NODE_ID)) {
      startNode = { ...existingNodeById.get(START_NODE_ID), id: START_NODE_ID, type: 'start-node', data: { id: START_NODE_ID, label: 'Start' } }
    } else {
      try {
        // Place start node to the left of the leftmost column
        const yamlNodesInGraph = (nodes.value || []).filter(n => n && n.id !== START_NODE_ID)
        if (yamlNodesInGraph.length) {
          const xs = yamlNodesInGraph.map(n => (n?.position && typeof n.position.x === 'number') ? n.position.x : getCentralPosition().x)
          const minX = Math.min(...xs)
          // Find nodes in that left column
          const tol = 1
          const leftColumn = yamlNodesInGraph.filter(n => Math.abs((n?.position?.x || 0) - minX) <= tol)
          const ys = leftColumn.map(n => (n?.position && typeof n.position.y === 'number') ? n.position.y : getCentralPosition().y)
          const avgY = ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : getCentralPosition().y
          const startXOffset = -100
          const startYOffset = 80
          startNode = {
            id: START_NODE_ID,
            type: 'start-node',
            label: 'Start',
            position: { x: minX + startXOffset, y: avgY + startYOffset },
            data: { id: START_NODE_ID, label: 'Start' }
          }
        } else {
          startNode = {
            id: START_NODE_ID,
            type: 'start-node',
            label: 'Start',
            position: getCentralPosition(),
            data: { id: START_NODE_ID, label: 'Start' }
          }
        }
      } catch (err) {
        console.warn('Failed to compute start node position, falling back to center:', err)
        startNode = {
          id: START_NODE_ID,
          type: 'start-node',
          label: 'Start',
          position: getCentralPosition(),
          data: { id: START_NODE_ID, label: 'Start' }
        }
      }
    }

    // Build start edges to YAML nodes that are declared in graph.start
    const startEdges = (yamlNodes || []).map(yamlNode => {
      if (!yamlNode?.id) return null
      if (!declaredStartSet.has(yamlNode.id)) return null

      const key = `${START_NODE_ID}-${yamlNode.id}`
      const baseEdge = preserveExistingLayout && existingEdgeByKey?.has(key)
        ? existingEdgeByKey.get(key)
        : {
            id: key,
            source: START_NODE_ID,
            target: yamlNode.id,
            type: 'workflow-edge'
          }

        return {
        ...baseEdge,
        id: key,
        source: START_NODE_ID,
        target: yamlNode.id,
        data: { from: START_NODE_ID, to: yamlNode.id },
        markerEnd: {
          type: MarkerType.Arrow,
          width: 16,
          height: 16,
          color: '#f2f2f2',
          strokeWidth: 1.5,
        },
        animated: false
      }
    }).filter(Boolean)

    // Combine YAML edges with visual start edges (preserve any existing non-yaml edges)
    edges.value = [
      // keep any existing edges that are not YAML edges (e.g., visual-only) when preserving layout
      // but always exclude previous Start edges so they are replaced by the newly computed ones
      ...(preserveExistingLayout ? currentEdges.filter(e => {
        const k = `${e.source}-${e.target}`
        // drop if it's a YAML-defined edge or a previous Start edge
        const isYamlEdge = nextYamlEdges.some(ne => ne.id === k)
        const isStartEdge = e.source === START_NODE_ID
        // Also drop if it looks like a YAML edge (has data.from/to) but isn't in nextYamlEdges (stale)
        const isStaleYamlEdge = e.data?.from && e.data?.to
        return !isYamlEdge && !isStartEdge && !isStaleYamlEdge
      }) : []),
      ...nextYamlEdges,
      ...startEdges
    ]

    // Ensure start node is present in nodes list (preserving layout if asked)
    if (!nodes.value.some(n => n.id === START_NODE_ID)) {
      nodes.value = [startNode, ...nodes.value]
    } else {
      // if present, ensure the start node data/type is correct
      nodes.value = nodes.value.map(n => n.id === START_NODE_ID ? startNode : n)
    }
  } catch (error) {
    console.error('Error syncing nodes and edges from YAML:', error)
  }
}

const generateNodesAndEdges = async (options = {}) => {
  updateNodesAndEdgesFromYaml(false)

  // Save generated graph at nextTick
  try {
    await nextTick()
    if (options.fit) {
      fitView?.({ padding: 0.1 })
    }
    await saveVueFlowGraph()
  } catch (err) {
    console.warn('Failed to persist generated VueFlow graph:', err)
  }
}

const syncVueNodesAndEdgesData = () => {
  updateNodesAndEdgesFromYaml(true)
}

const updateVueFlowNodeId = (oldId, newId) => {
  if (!oldId || !newId || oldId === newId) {
    return
  }

  nodes.value = (nodes.value || []).map(node => {
    if (node.id !== oldId) {
      return node
    }
    return {
      ...node,
      id: newId,
      label: newId,
      data: node.data
        ? { ...node.data, id: newId }
        : { id: newId }
    }
  })

  edges.value = (edges.value || []).map(edge => {
    let source = edge.source
    let target = edge.target
    let edgeChanged = false

    if (source === oldId) {
      source = newId
      edgeChanged = true
    }

    if (target === oldId) {
      target = newId
      edgeChanged = true
    }

    let nextData = edge.data
    if (edge.data) {
      const nextFrom = edge.data.from === oldId ? newId : edge.data.from
      const nextTo = edge.data.to === oldId ? newId : edge.data.to

      if (nextFrom !== edge.data.from || nextTo !== edge.data.to) {
        nextData = {
          ...edge.data,
          from: nextFrom,
          to: nextTo
        }
      }
    }

    const nextEdge = {
      ...edge,
      source,
      target,
      data: nextData
    }

    if (edgeChanged) {
      nextEdge.id = `${source}-${target}`
    }

    return nextEdge
  })

  // Update node ID in graph.start
  if (yamlContent.value?.graph?.start && Array.isArray(yamlContent.value.graph.start)) {
    yamlContent.value.graph.start = yamlContent.value.graph.start.map(startNodeId =>
      startNodeId === oldId ? newId : startNodeId
    )
  }

  // Same for graph.end
  if (yamlContent.value?.graph?.end && Array.isArray(yamlContent.value.graph.end)) {
    yamlContent.value.graph.end = yamlContent.value.graph.end.map(endNodeId =>
      endNodeId === oldId ? newId : endNodeId
    )
  }
}

// FormGenerator integration
const snapshotYamlContent = () => cloneDeep(yamlContent.value ?? null)

// Build YAML without specific node
const buildYamlWithoutNode = (nodeId) => {
  const snapshot = snapshotYamlContent()
  if (!snapshot?.graph?.nodes || !Array.isArray(snapshot.graph.nodes)) {
    return snapshot
  }
  snapshot.graph.nodes = snapshot.graph.nodes.filter(node => node?.id !== nodeId)
  return snapshot
}

const buildYamlWithoutEdge = (fromId, toId) => {
  const snapshot = snapshotYamlContent()
  if (!snapshot?.graph?.edges || !Array.isArray(snapshot.graph.edges)) {
    return snapshot
  }
  let removed = false
  snapshot.graph.edges = snapshot.graph.edges.filter(edge => {
    if (!removed && edge?.from === fromId && edge?.to === toId) {
      removed = true
      return false
    }
    return true
  })
  return snapshot
}

const buildYamlWithoutVars = () => {
  const snapshot = snapshotYamlContent()
  if (!snapshot || typeof snapshot !== 'object') {
    return snapshot
  }
  if (!Object.prototype.hasOwnProperty.call(snapshot, 'vars')) {
    return snapshot
  }
  const sanitized = { ...snapshot }
  delete sanitized.vars
  return sanitized
}

const buildYamlWithoutMemory = () => {
  const snapshot = snapshotYamlContent()
  if (!snapshot?.graph) {
    return snapshot
  }
  if (Object.prototype.hasOwnProperty.call(snapshot.graph, 'memory')) {
    const newGraph = { ...snapshot.graph }
    delete newGraph.memory
    snapshot.graph = newGraph
  }
  return snapshot
}

const buildYamlWithoutGraph = () => {
  const snapshot = snapshotYamlContent()
  if (!snapshot || typeof snapshot !== 'object') {
    return snapshot
  }
  if (!Object.prototype.hasOwnProperty.call(snapshot, 'graph')) {
    return snapshot
  }
  const sanitized = { ...snapshot }
  delete sanitized.graph
  return sanitized
}

const autoAddStartEdge = async (nextNodeId) => {
  const workflowNodes = (yamlContent.value?.graph?.nodes || []).filter(node => node?.id !== START_NODE_ID)
  if (workflowNodes.length === 1 && workflowNodes[0]?.id === nextNodeId) {
    const snapshot = snapshotYamlContent()
    if (!snapshot?.graph) {
      snapshot.graph = {}
    }
    if (!Array.isArray(snapshot.graph.start)) {
      snapshot.graph.start = []
    }
    if (!snapshot.graph.start.includes(nextNodeId)) {
      // Add node
      snapshot.graph.start.push(nextNodeId)
      const ok = await persistYamlSnapshot(snapshot)
      if (ok) {
        await loadYamlFile()
        syncVueNodesAndEdgesData()
        await nextTick()
      }
    }
  }
}

const openDynamicFormGenerator = (type, options = {}) => {
  const config = FORM_GENERATOR_CONFIG[type]
  if (!config) {
    console.error(`[FormGenerator] Unknown type: ${type}`)
    return
  }
  formGeneratorBreadcrumbs.value = config.map(crumb => ({ ...crumb }))
  formGeneratorRecursive.value = options.recursive ?? true

  const resolvedMode = typeof options.mode === 'string' && ['create', 'edit'].includes(options.mode)
    ? options.mode
    : (options.initialFormData ? 'edit' : 'create')
  formGeneratorMode.value = resolvedMode

  const hasCustomYaml = Object.prototype.hasOwnProperty.call(options, 'initialYaml')
  const yamlSource = hasCustomYaml ? options.initialYaml : yamlContent.value
  formGeneratorInitialYaml.value = yamlSource ? cloneDeep(yamlSource) : null

  if (Object.prototype.hasOwnProperty.call(options, 'initialFormData')) {
    formGeneratorInitialFormData.value = options.initialFormData
      ? cloneDeep(options.initialFormData)
      : null
  } else {
    formGeneratorInitialFormData.value = null
  }

  formGeneratorFieldFilter.value = options.fieldFilter ?? []
  formGeneratorReadOnlyFields.value = options.readOnlyFields ?? []

  showDynamicFormGenerator.value = true
}

const closeDynamicFormGenerator = () => {
  showDynamicFormGenerator.value = false
  formGeneratorBreadcrumbs.value = []
  formGeneratorInitialYaml.value = null
  formGeneratorInitialFormData.value = null
  formGeneratorMode.value = 'create'
  formGeneratorFieldFilter.value = null
  formGeneratorReadOnlyFields.value = []
}

const handleFormGeneratorSubmit = async (payload) => {
  try {
    const previousNodeId = formGeneratorInitialFormData.value?.id
    const nextNodeId = payload?.rawFormData?.id

    //Update VueFlow node ID based on updated YAML if change present
    if (previousNodeId && nextNodeId && previousNodeId !== nextNodeId) {
      updateVueFlowNodeId(previousNodeId, nextNodeId)
    }

    await loadYamlFile()
    syncVueNodesAndEdgesData()
    // Ensure VueFlow internal state is updated from v-model bindings
    // before taking a snapshot to be saved into vuegraphs.db
    await nextTick()

    // If we opened the FormGenerator from a right-click context menu while creating
    // a new node, place that node at the stored position.
    if (formGeneratorMode.value === 'create' && pendingNodePosition.value && nextNodeId) {
      const newNode = (nodes.value || []).find(node => node.id === nextNodeId)
      if (newNode) {
        newNode.position = {
          x: pendingNodePosition.value.x,
          y: pendingNodePosition.value.y
        }
      }
      pendingNodePosition.value = null
    }

    // Auto-connect start node to new node
    if (formGeneratorMode.value === 'create' && nextNodeId) {
      await autoAddStartEdge(nextNodeId)
    }

    await saveVueFlowGraph()
  } catch (error) {
    console.error('Error refreshing workflow after dynamic form submission:', error)
  } finally {
    closeDynamicFormGenerator()
  }
}

const handleFormGeneratorCopy = (payload) => {
  try {
    const copied = payload?.initialFormData ? cloneDeep(payload.initialFormData) : null
    if (copied && typeof copied === 'object') {
      copied.id = ''
    }

    // @close of original modal calls closeDynamicFormGenerator()
    // Defer new "create node" modal to the next tick to avoid being closed
    setTimeout(() => {
      openDynamicFormGenerator('node', {
        mode: 'create',
        initialFormData: copied
      })
    }, 0)
  } catch (error) {
    console.error('Error copying node:', error)
  }
}

const openNodeEditor = (nodeId) => {
  if (!nodeId) {
    return
  }
  const yamlNodeContent = (yamlContent.value?.graph?.nodes || []).find(node => node.id === nodeId)
  if (!yamlNodeContent) {
    console.warn(`[WorkflowView] Node with id "${nodeId}" not found for editing`)
    return
  }
  // Pass YAML without specific node to the FormGenerator to "recreate" the node
  const sanitizedYaml = buildYamlWithoutNode(nodeId)
  openDynamicFormGenerator('node', {
    initialYaml: sanitizedYaml,
    initialFormData: yamlNodeContent,
    mode: 'edit'
  })
}

const openEdgeEditor = (fromId, toId, fallbackData = null) => {
  if (!fromId || !toId) {
    return
  }
  const yamlEdge = (yamlContent.value?.graph?.edges || []).find(edge => edge.from === fromId && edge.to === toId)
  const edgeData = yamlEdge || (fallbackData ? cloneDeep(fallbackData) : null)
  if (!edgeData) {
    console.warn(`[WorkflowView] Edge "${fromId}-${toId}" not found for editing`)
    return
  }
  const sanitizedYaml = buildYamlWithoutEdge(fromId, toId)
  openDynamicFormGenerator('edge', {
    initialYaml: sanitizedYaml,
    initialFormData: edgeData,
    mode: 'edit'
  })
}

// Create Node functions
const openCreateNodeModal = () => {
  // Set position to center of graph when creating from 'Create Node'
  pendingNodePosition.value = getCentralPosition()
  openDynamicFormGenerator('node', { mode: 'create' })
}

const openManageVarsModal = () => {
  const currentVars = yamlContent.value?.vars || null
  const sanitizedYaml = buildYamlWithoutVars()
  openDynamicFormGenerator('vars', {
    recursive: false,
    initialYaml: sanitizedYaml,
    initialFormData: currentVars ? { vars: currentVars } : null,
    mode: currentVars ? 'edit' : 'create',
    fieldFilter: ['vars']
  })
}

const openManageMemoriesModal = () => {
  const currentMemories = yamlContent.value?.graph?.memory || null
  const sanitizedYaml = buildYamlWithoutMemory()
  openDynamicFormGenerator('memory', {
    initialYaml: sanitizedYaml,
    initialFormData: currentMemories ? { memory: currentMemories } : null,
    mode: currentMemories ? 'edit' : 'create',
    fieldFilter: ['memory']
  })
}

const openConfigureGraphModal = () => {
  const currentGraph = yamlContent.value?.graph || null
  const sanitizedYaml = buildYamlWithoutGraph()
  openDynamicFormGenerator('graph', {
    recursive: false,
    initialYaml: sanitizedYaml,
    initialFormData: currentGraph,
    mode: currentGraph ? 'edit' : 'create',
    fieldFilter: null,
    readOnlyFields: ['id']
  })
}

const onNodeClick = (event) => {
  if (isCreatingConnection.value) {
    return
  }
  const clickedNode = event?.node || event
  if (!clickedNode?.id) {
    return
  }

  // Ignore left click for start node but show dim animation
  if (clickedNode.id === START_NODE_ID) {
    dimStartNode()
    return
  }

  openNodeEditor(clickedNode.id)
}

const onEdgeClick = (event) => {
  const clickedEdge = event?.edge || event
  if (!clickedEdge?.id) {
    return
  }

  const fromId = clickedEdge.data?.from || clickedEdge.source || ''
  const toId = clickedEdge.data?.to || clickedEdge.target || ''

  // Ignore start node edge
  if (fromId === START_NODE_ID || toId === START_NODE_ID) {
    return
  }
  if (!fromId || !toId) {
    return
  }

  const fallbackData = {
    from: fromId,
    to: toId
  }

  if (clickedEdge.data?.condition !== undefined) {
    fallbackData.condition = clickedEdge.data.condition
  }

  if (clickedEdge.data?.trigger !== undefined) {
    fallbackData.trigger = clickedEdge.data.trigger
  }

  openEdgeEditor(fromId, toId, fallbackData)
}

// Autosave when moving nodes
const onNodeDragStop = () => {
  saveVueFlowGraph()
}

const onConnect = async (connection) => {
  if (!connection?.source || !connection?.target) {
    return
  }

  // Set flag to avoid opening node edit modal
  isCreatingConnection.value = true

  // Special handling for StartNode connections
  if (connection.source === START_NODE_ID) {
    // Add target node to graph.start array instead of opening FormGenerator
    const snapshot = snapshotYamlContent()
    if (!snapshot?.graph) {
      setTimeout(() => {
        isCreatingConnection.value = false
      }, 10)
      return
    }

    // Ensure graph.start exists as an array
    if (!Array.isArray(snapshot.graph.start)) {
      snapshot.graph.start = []
    }

    // Add target node to start array if not already present
    if (!snapshot.graph.start.includes(connection.target)) {
      snapshot.graph.start.push(connection.target)

      // Persist the updated YAML
      const ok = await persistYamlSnapshot(snapshot)
      if (ok) {
        await loadYamlFile()
        syncVueNodesAndEdgesData()
        await nextTick()
        await saveVueFlowGraph()
      }
    }

    setTimeout(() => {
      isCreatingConnection.value = false
    }, 10)
    return
  }

  // Do not open modal if edge already exists
  const yamlEdges = yamlContent.value?.graph?.edges || []
  const edgeAlreadyExistsInYaml = yamlEdges.some(
    e => e.from === connection.source && e.to === connection.target
  )
  const edgeAlreadyExistsInGraph = edges.value.some(
    e => e.source === connection.source && e.target === connection.target
  )
  if (edgeAlreadyExistsInYaml || edgeAlreadyExistsInGraph) {
    setTimeout(() => {
      isCreatingConnection.value = false
    }, 10)
    return
  }

  // Remove the automatically created edge (VueFlow may optimistically add one)
  const autoCreatedEdgeIndex = edges.value.findIndex(
    edge => edge.source === connection.source && edge.target === connection.target
  )
  if (autoCreatedEdgeIndex !== -1) {
    edges.value.splice(autoCreatedEdgeIndex, 1)
  }

  openDynamicFormGenerator('edge', {
    initialFormData: {
      from: connection.source,
      to: connection.target,
      condition: {
        type: 'function',
        config: {
          name: 'true'
        }
      },
      trigger: true
    },
    mode: 'create'
  })

  // Reset flag after a short delay so click handlers stay disabled
  setTimeout(() => {
    isCreatingConnection.value = false
  }, 100)
}

// Create Edge functions
const openCreateEdgeModal = () => {
  openDynamicFormGenerator('edge', { mode: 'create' })
}

const goToLaunch = () => {
  if (!workflowName.value) {
    return
  }
  const fileName = workflowName.value.endsWith('.yaml')
    ? workflowName.value
    : `${workflowName.value}.yaml`

  const resolved = router.resolve({
    path: '/launch',
    query: { workflow: fileName }
  })

  window.open(resolved.href, '_blank', 'noopener')
}

// Modal functions for rename and copy workflow
const openRenameWorkflowModal = () => {
  showMenu.value = false
  renameWorkflowName.value = workflowName.value.replace('.yaml', '')
  showRenameModal.value = true
}

const closeRenameModal = () => {
  showRenameModal.value = false
  renameWorkflowName.value = ''
}

const handleRenameSubmit = async () => {
  if (!renameWorkflowName.value.trim()) {
    return
  }

  const newName = renameWorkflowName.value.trim()
  const result = await postYamlNameChange(workflowName.value, newName)

  if (result.success) {
    // Handle VueGraph rename
    const oldWorkflowKey = workflowName.value.replace('.yaml', '')
    const newWorkflowKey = newName

    // Save VueGraph into new workflow
    try {
      const oldVueGraphResult = await fetchVueGraph(oldWorkflowKey)
      if (oldVueGraphResult.success && oldVueGraphResult.content) {
        const saveResult = await postVuegraphs({
          filename: newWorkflowKey,
          content: oldVueGraphResult.content
        })
        if (!saveResult.success) {
          console.warn('Failed to rename VueGraph:', saveResult.message)
        }
      }
    } catch (error) {
      console.warn('Error handling VueGraph rename:', error)
    }

    alert(result.message)
    closeRenameModal()

    // Refresh workflow list first
    emit('refresh-workflows')

    // Small delay to allow workflow list to refresh before navigating
    await new Promise(resolve => setTimeout(resolve, 500))

    // Navigate to the renamed workflow
    const newWorkflowName = result.filename || `${newName}.yaml`
    const workflowNameWithoutExtension = newWorkflowName.replace('.yaml', '')
    router.push({ path: `/workflows/${workflowNameWithoutExtension}` })
  } else {
    alert(result.error?.message || 'Failed to rename workflow')
  }
}

const openCopyWorkflowModal = () => {
  showMenu.value = false
  copyWorkflowName.value = workflowName.value.replace('.yaml', '') + '_copy'
  showCopyModal.value = true
}

const closeCopyModal = () => {
  showCopyModal.value = false
  copyWorkflowName.value = ''
}

const handleCopySubmit = async () => {
  if (!copyWorkflowName.value.trim()) {
    return
  }

  const newName = copyWorkflowName.value.trim()
  const result = await postYamlCopy(workflowName.value, newName)

  if (result.success) {
    // Handle VueGraph copy
    const sourceWorkflowKey = workflowName.value.replace('.yaml', '')
    const targetWorkflowKey = newName

    try {
      // Load the VueGraph for the source workflow
      const sourceVueGraphResult = await fetchVueGraph(sourceWorkflowKey)
      if (sourceVueGraphResult.success && sourceVueGraphResult.content) {
        // Save the VueGraph with the new workflow name
        const saveResult = await postVuegraphs({
          filename: targetWorkflowKey,
          content: sourceVueGraphResult.content
        })
        if (!saveResult.success) {
          console.warn('Failed to copy VueGraph:', saveResult.message)
        }
      }
    } catch (error) {
      console.warn('Error handling VueGraph copy:', error)
    }

    alert(result.message)
    closeCopyModal()

    // Refresh workflow list first
    emit('refresh-workflows')

    // Small delay to allow workflow list to refresh before navigating
    await new Promise(resolve => setTimeout(resolve, 500))

    // Navigate to the copied workflow
    const newWorkflowName = result.filename || `${newName}.yaml`
      const workflowNameWithoutExtension = newWorkflowName.replace('.yaml', '')
    router.push({ path: `/workflows/${workflowNameWithoutExtension}` })
  } else {
    alert(result.message || result.error?.message || 'Failed to copy workflow')
  }
}
</script>

<style scoped>
.workflow-view {
  width: 100%;
  height: calc(100vh - 55px);
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  color: #f2f2f2;
  font-family: 'Inter', sans-serif;
  position: relative;
  overflow: hidden;
}

.workflow-bg {
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

.content {
  position: relative;
  z-index: 1;
}

.header,
.tabs {
  position: relative;
  z-index: 2;
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
  background: transparent;
  color: #f2f2f2;
  border-color: transparent;
}

.back-button:focus,
.back-button:focus-visible {
  outline: none;
  border-color: transparent;
}

.workflow-name {
  color: #f2f2f2;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.tabs {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 50px;
  background-color: rgba(255, 255, 255, 0.02);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(5px);
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 2;
}

.tab-buttons {
  display: flex;
  gap: 4px;
  height: 100%;
}

.tab {
  padding: 0 20px;
  height: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  font-family: 'Inter', sans-serif;
  color: #8e8e8e;
  font-weight: 500;
  transition: color 0.2s ease;
  position: relative;
}

.tab:hover {
  color: #f2f2f2;
}

.tab.active {
  background: linear-gradient(
    135deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 500;
}

.editor-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 100%;
}

/* Glass Button - Matching WorkflowList entries */
  .glass-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background-color: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #f2f2f2;
  font-size: 14px;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(5px);
}

.launch-button-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #1a1a1a;
  font-size: 14px;
  font-weight: 600;
  background: linear-gradient(
    135deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  background-size: 200% 100%;
  animation: gradientShift 6s ease-in-out infinite;
  backdrop-filter: blur(5px);
  position: relative;
  z-index: 1;
}

.launch-button-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  opacity: 0.9;
}

.glass-button:hover {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.05);
}

@keyframes gradientShift {
  0%, 100% { background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
}

.glass-button::before {
  content: '';
  position: absolute;
  inset: -2px;
  z-index: -1;
  border-radius: 14px;
  padding: 2px;
  background: linear-gradient(
    135deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  -webkit-mask: 
     linear-gradient(#f2f2f2 0 0) content-box, 
     linear-gradient(#f2f2f2 0 0);
  mask: 
     linear-gradient(#f2f2f2 0 0) content-box, 
     linear-gradient(#f2f2f2 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s ease;
  background-size: 200% 100%;
  animation: gradientShift 6s ease-in-out infinite;
  filter: blur(4px);
}

.glass-button:hover::before {
  opacity: 1;
}

.btn-icon {
  font-size: 16px;
}

/* Menu Dropdown */
.menu-container {
  position: relative;
  z-index: 3;
  height: 100%;
}

.menu-trigger {
  width: 40px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: rgba(255, 255, 255, 0.7);
}

.menu-dropdown {
  position: absolute;
  bottom: 100%;
  right: 0;
  background: rgba(60, 60, 60, 0.99);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 8px;
  min-width: 180px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  z-index: 3;
}

.menu-item {
  padding: 10px 16px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: #f2f2f2;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.content {
  flex: 1;
  overflow: hidden;
  position: relative;
  min-height: 0;
}

.yaml-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.yaml-error {
  padding: 12px 20px;
  background-color: rgba(255, 68, 68, 0.1);
  border-bottom: 1px solid rgba(255, 68, 68, 0.3);
  color: #ff8888;
  font-size: 14px;
  margin: 0;
}

.yaml-textarea {
  flex: 1;
  padding: 20px;
  border: none;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  background: transparent;
  color: #d4d4d4;
}

.yaml-textarea::-webkit-scrollbar {
  display: none;
}

.yaml-error-border {
  border: 2px solid #ff4444 !important;
}

.vueflow-container {
  height: 100%;
  width: 100%;
  background-color: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(5px);
  z-index: 1;
  position: relative;
}

.vueflow-graph {
  width: 100%;
  height: 100%;
}

.context-menu {
  position: absolute;
  min-width: 160px;
  background: rgba(40, 40, 40, 0.98);
  border-radius: 10px;
  padding: 6px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  z-index: 5;
}

.context-menu-item {
  padding: 8px 12px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.context-menu-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: #f2f2f2;
}

/* Modal Styles - Matching FormGenerator modal-content */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  display: flex;
  flex-direction: column;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  background-color: rgba(33, 33, 33, 0.92);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
  overflow: hidden;
  backdrop-filter: blur(10px);
}

.modal-header {
  flex-shrink: 0;
  height: 28px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  background-color: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.modal-title {
  color: #f2f2f2;
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  flex: 1;
}

.close-button {
  margin-left: auto;
  background: transparent;
  border: none;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.6);
  transition: color 0.2s ease;
}

.close-button:hover {
  color: #f2f2f2;
}

.modal-body {
  flex: 1;
  padding: 20px;
  max-height: none;
  overflow-y: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  scrollbar-width: none;
}

.modal-body::-webkit-scrollbar {
  display: none;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  color: #f2f2f2;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
}

.form-input {
  width: 90%;
  padding: 12px 16px;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f2f2f2;
  font-size: 14px;
  font-family: 'Inter', sans-serif;
  outline: none;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.form-input:focus {
  border-color: rgba(170, 255, 205, 0.5);
  background-color: rgba(255, 255, 255, 0.08);
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.modal-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  background-color: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.cancel-button,
.submit-button {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Inter', sans-serif;
}

.cancel-button {
  background-color: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
}

.cancel-button:hover {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
  color: #f2f2f2;
}

.submit-button {
  background: linear-gradient(135deg, #aaffcd, #99eaf9, #a0c4ff);
  border: none;
  color: #1a1a1a;
  font-weight: 600;
}

.submit-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.submit-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
</style>
