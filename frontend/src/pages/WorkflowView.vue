<template>
  <div class="workflow-view" :class="{ 'workflow-view--embedded': embedded }">
    <div v-if="!embedded" class="workflow-bg"></div>
    <div class="header" :class="{ 'header--embedded': embedded }">
      <div class="header-copy">
        <div v-if="!embedded" class="header-eyebrow">{{ t('workflowView.eyebrow') }}</div>
        <h1 class="workflow-name">{{ workflowName }}</h1>
        <p v-if="!embedded" class="header-subtitle">{{ t('workflowView.subtitle') }}</p>
      </div>
      <div v-if="!embedded" class="header-chip">{{ activeTab === 'graph' ? t('workflowView.workflowGraph') : t('workflowView.yamlConfig') }}</div>
    </div>

    <div v-if="injectionFocusNodeId" class="injection-focus-banner">
      <div class="injection-focus-copy">
        <strong>{{ t('workflowView.mcpInjectionBannerTitle', { node: injectionFocusNodeId }) }}</strong>
        <span>{{ t('workflowView.mcpInjectionBannerDesc') }}</span>
      </div>
      <div class="injection-focus-actions">
        <button class="glass-button" @click="openInjectedNodeEditor">{{ t('workflowView.mcpInjectionOpenNode') }}</button>
        <button class="glass-button" @click="clearInjectionFocus">{{ t('workflowView.mcpInjectionDismiss') }}</button>
      </div>
    </div>

    <div class="content">
      <!-- YAML Editor Tab -->
      <div v-if="activeTab === 'yaml'" class="yaml-editor">
        <div v-if="yamlParseError" class="yaml-error">
          {{ t('workflowView.yamlParseError') }}: {{ yamlParseError }}
        </div>
        <textarea 
          v-model="yamlTextString" 
          class="yaml-textarea"
          :class="{ 'yaml-error-border': yamlParseError }"
          :placeholder="t('workflowView.loadingYaml')"
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
            :is-highlighted="injectionFocusNodeId === props.id"
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
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.createNode" placement="right">
                <div
                  class="context-menu-item"
                  @click.stop="() => { hideContextMenu(); openCreateNodeModal(); }"
                >
                  {{ t('workflowView.createNode') }}
                </div>
              </RichTooltip>
              <div
                v-else
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); openCreateNodeModal(); }"
              >
                {{ t('workflowView.createNode') }}
              </div>
            </template>

            <!-- Node context menu -->
            <template v-else-if="contextMenuType === 'node'">
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.copyNode" placement="right">
                <div
                  class="context-menu-item"
                  @click.stop="() => { hideContextMenu(); onCopyNodeFromContext(); }"
                >
                  {{ t('workflowView.copyNode') }}
                </div>
              </RichTooltip>
              <div
                v-else
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onCopyNodeFromContext(); }"
              >
                {{ t('workflowView.copyNode') }}
              </div>
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.deleteNode" placement="right">
                <div
                  class="context-menu-item"
                  @click.stop="() => { hideContextMenu(); onDeleteNodeFromContext(); }"
                >
                  {{ t('workflowView.deleteNode') }}
                </div>
              </RichTooltip>
              <div
                v-else
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onDeleteNodeFromContext(); }"
              >
                {{ t('workflowView.deleteNode') }}
              </div>
            </template>

            <!-- Edge context menu -->
            <template v-else-if="contextMenuType === 'edge'">
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.deleteEdge" placement="right">
                <div
                  class="context-menu-item"
                  @click.stop="() => { hideContextMenu(); onDeleteEdgeFromContext(); }"
                >
                  {{ t('workflowView.deleteEdge') }}
                </div>
              </RichTooltip>
              <div
                v-else
                class="context-menu-item"
                @click.stop="() => { hideContextMenu(); onDeleteEdgeFromContext(); }"
              >
                {{ t('workflowView.deleteEdge') }}
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
          {{ t('workflowView.workflowGraph') }}
        </button>
        <button 
          :class="['tab', { active: activeTab === 'yaml' }]"
          @click="activeTab = 'yaml'"
        >
          {{ t('workflowView.yamlConfig') }}
        </button>
      </div>
      <div v-if="activeTab === 'graph'" class="editor-actions">
        <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.createNodeButton" placement="bottom">
          <button @click="openCreateNodeModal" class="glass-button">
            <span>{{ t('workflowView.createNode') }}</span>
          </button>
        </RichTooltip>
        <button v-else @click="openCreateNodeModal" class="glass-button">
          <span>{{ t('workflowView.createNode') }}</span>
        </button>
        <button @click="openTemplateModal" class="glass-button">
          <span>{{ t('workflowView.applyTemplate') }}</span>
        </button>
        <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.configureGraph" placement="bottom">
          <button @click="openConfigureGraphModal" class="glass-button">
            <span>{{ t('workflowView.configureGraph') }}</span>
          </button>
        </RichTooltip>
        <button v-else @click="openConfigureGraphModal" class="glass-button">
          <span>{{ t('workflowView.configureGraph') }}</span>
        </button>
        <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.launch" placement="bottom">
          <button @click="goToLaunch" class="launch-button-primary">
            <span>{{ t('workflowView.launch') }}</span>
          </button>
        </RichTooltip>
        <button v-else @click="goToLaunch" class="launch-button-primary">
          <span>{{ t('workflowView.launch') }}</span>
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
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.renameWorkflow" placement="left">
                <div @click="openRenameWorkflowModal" class="menu-item">{{ t('workflowView.renameWorkflow') }}</div>
              </RichTooltip>
              <div v-else @click="openRenameWorkflowModal" class="menu-item">{{ t('workflowView.renameWorkflow') }}</div>
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.copyWorkflow" placement="left">
                <div @click="openCopyWorkflowModal" class="menu-item">{{ t('workflowView.copyWorkflow') }}</div>
              </RichTooltip>
              <div v-else @click="openCopyWorkflowModal" class="menu-item">{{ t('workflowView.copyWorkflow') }}</div>
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.manageVariables" placement="left">
                <div @click="openManageVarsModal" class="menu-item">{{ t('workflowView.manageVariables') }}</div>
              </RichTooltip>
              <div v-else @click="openManageVarsModal" class="menu-item">{{ t('workflowView.manageVariables') }}</div>
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.manageMemories" placement="left">
                <div @click="openManageMemoriesModal" class="menu-item">{{ t('workflowView.manageMemories') }}</div>
              </RichTooltip>
              <div v-else @click="openManageMemoriesModal" class="menu-item">{{ t('workflowView.manageMemories') }}</div>
              <div @click="openManageTriggersModal" class="menu-item">{{ t('workflowView.manageTriggers') }}</div>
              <RichTooltip v-if="shouldShowTooltip" :content="helpContent.contextMenu.createEdge" placement="left">
                <div @click="openCreateEdgeModal" class="menu-item">{{ t('workflowView.createEdge') }}</div>
              </RichTooltip>
              <div v-else @click="openCreateEdgeModal" class="menu-item">{{ t('workflowView.createEdge') }}</div>
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
        <h3 class="modal-title">{{ t('workflowView.renameTitle') }}</h3>
        <button @click="closeRenameModal" class="close-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="rename-workflow-name" class="form-label">{{ t('workflowView.workflowName') }}</label>
          <input
            id="rename-workflow-name"
            v-model="renameWorkflowName"
            type="text"
            class="form-input"
            :placeholder="t('workflowView.enterWorkflowName')"
            @keyup.enter="handleRenameSubmit"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeRenameModal" class="cancel-button">{{ t('common.cancel') }}</button>
        <button @click="handleRenameSubmit" class="submit-button" :disabled="!renameWorkflowName.trim()">{{ t('common.submit') }}</button>
      </div>
    </div>
  </div>

  <!-- Copy Workflow Modal -->
  <div v-if="showCopyModal" class="modal-overlay" @click.self="closeCopyModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">{{ t('workflowView.copyTitle') }}</h3>
        <button @click="closeCopyModal" class="close-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="copy-workflow-name" class="form-label">{{ t('workflowView.workflowName') }}</label>
          <input
            id="copy-workflow-name"
            v-model="copyWorkflowName"
            type="text"
            class="form-input"
            :placeholder="t('workflowView.enterWorkflowName')"
            @keyup.enter="handleCopySubmit"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeCopyModal" class="cancel-button">{{ t('common.cancel') }}</button>
        <button @click="handleCopySubmit" class="submit-button" :disabled="!copyWorkflowName.trim()">{{ t('common.submit') }}</button>
      </div>
    </div>
  </div>

  <div v-if="showTemplateModal" class="modal-overlay" @click.self="closeTemplateModal">
    <div class="modal-content template-modal">
      <div class="modal-header">
        <h3 class="modal-title">{{ t('workflowView.templatesTitle') }}</h3>
        <div class="template-header-actions">
          <button type="button" class="template-toolbar-button" @click="exportCurrentWorkflowTemplate">
            {{ t('workflowView.exportTemplate') }}
          </button>
          <button type="button" class="template-toolbar-button" @click="triggerTemplateImport">
            {{ t('workflowView.importTemplate') }}
          </button>
          <button @click="closeTemplateModal" class="close-button">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
      <div class="modal-body">
        <p class="template-intro">{{ t('workflowView.templatesSubtitle') }}</p>
        <input
          v-model="templateSearchQuery"
          type="text"
          class="template-search-input"
          :placeholder="t('workflowView.templateSearchPlaceholder')"
        />
        <div class="template-category-row">
          <button
            v-for="category in templateCategories"
            :key="category.id"
            class="template-category-chip"
            :class="{ 'is-active': selectedTemplateCategory === category.id }"
            @click="selectedTemplateCategory = category.id"
          >
            {{ t(category.labelKey) }}
          </button>
        </div>
        <div class="template-grid">
          <div
            v-for="templateItem in filteredWorkflowTemplates"
            :key="templateItem.id"
            class="template-card"
            :class="{ 'is-recommended': isRecommendedTemplate(templateItem.id) }"
            role="button"
            tabindex="0"
            @click="applyTemplate(templateItem.id)"
            @keydown.enter.prevent="applyTemplate(templateItem.id)"
            @keydown.space.prevent="applyTemplate(templateItem.id)"
          >
            <div class="template-card-header">
              <div class="template-card-title">{{ getTemplateTitle(templateItem) }}</div>
              <button
                type="button"
                class="template-favorite-button"
                :class="{ 'is-active': isTemplateFavorite(templateItem.id) }"
                @click.stop="toggleTemplateFavorite(templateItem.id)"
              >
                {{ isTemplateFavorite(templateItem.id) ? '★' : '☆' }}
              </button>
            </div>
            <div class="template-card-meta-row">
              <span v-if="isRecommendedTemplate(templateItem.id)" class="template-card-meta is-recommended">
                {{ recommendedPackId ? t('workflowView.recommendedPackBadge', { pack: recommendedPackId }) : t('workflowView.recommendedTemplateBadge') }}
              </span>
              <span v-if="isTemplateFavorite(templateItem.id)" class="template-card-meta is-favorite">
                {{ t('workflowView.favoriteBadge') }}
              </span>
              <span v-if="isTemplateRecent(templateItem.id)" class="template-card-meta is-recent">
                {{ t('workflowView.recentBadge') }}
              </span>
              <span v-if="templateUsageCount(templateItem.id) > 0" class="template-card-meta is-usage">
                {{ t('workflowView.templateUsedCount', { count: templateUsageCount(templateItem.id) }) }}
              </span>
            </div>
            <div class="template-card-category">{{ getTemplateCategoryLabel(templateItem) }}</div>
            <div class="template-card-description">{{ getTemplateDescription(templateItem) }}</div>
            <div v-if="getTemplateTags(templateItem).length" class="template-tag-row">
              <span
                v-for="tag in getTemplateTags(templateItem)"
                :key="`${templateItem.id}-${tag}`"
                class="template-tag-chip"
              >
                {{ tag }}
              </span>
            </div>
            <div v-if="isLocalImportedTemplate(templateItem)" class="template-card-library-actions">
              <button
                type="button"
                class="template-library-button"
                @click.stop="togglePinImportedTemplate(templateItem.id)"
              >
                {{ isPinnedImportedTemplate(templateItem.id) ? t('workflowView.unpinImportedTemplate') : t('workflowView.pinImportedTemplate') }}
              </button>
              <button
                type="button"
                class="template-library-button"
                @click.stop="renameImportedTemplate(templateItem.id)"
              >
                {{ t('workflowView.renameImportedTemplate') }}
              </button>
              <button
                type="button"
                class="template-library-button is-danger"
                @click.stop="deleteImportedTemplate(templateItem.id)"
              >
                {{ t('workflowView.deleteImportedTemplate') }}
              </button>
            </div>
            <div class="template-card-action">{{ t('workflowView.useThisTemplate') }}</div>
          </div>
        </div>
        <div v-if="!filteredWorkflowTemplates.length" class="template-empty-state">
          {{ t('common.noResults') }}
        </div>
        <div v-if="pendingImportedTemplate" class="template-import-preview">
          <div class="template-import-preview-title">{{ t('workflowView.templateImportPreview') }}</div>
          <div class="template-import-preview-meta">
            {{ pendingImportedTemplate.fileName }}
          </div>
          <div class="template-import-preview-meta">
            {{ t('workflowView.workflowName') }}: {{ pendingImportedTemplate.workflowName }}
          </div>
          <div class="template-import-preview-meta">
            {{ t('workflowView.templateImportStats', {
              nodes: pendingImportedTemplate.nodeCount,
              edges: pendingImportedTemplate.edgeCount,
              start: pendingImportedTemplate.startCount
            }) }}
          </div>
          <div v-if="pendingImportedTemplate.startNodes.length" class="template-import-preview-meta">
            {{ t('workflowView.templateImportStartNodes') }}: {{ pendingImportedTemplate.startNodes.join(', ') }}
          </div>
          <div v-if="pendingImportedTemplate.tags.length" class="template-import-preview-meta">
            {{ t('workflowView.templateImportTags') }}: {{ pendingImportedTemplate.tags.join(', ') }}
          </div>
          <div v-if="pendingImportedTemplate.edgeSummaries.length" class="template-import-node-list">
            <div class="template-import-node-list-title">{{ t('workflowView.templateImportEdgesPreview') }}</div>
            <div
              v-for="edge in pendingImportedTemplate.edgeSummaries"
              :key="edge.id"
              class="template-import-edge-item"
            >
              <span class="template-import-edge-endpoint">{{ edge.from }}</span>
              <span class="template-import-edge-arrow">-></span>
              <span class="template-import-edge-endpoint">{{ edge.to }}</span>
            </div>
            <div v-if="pendingImportedTemplate.remainingEdgeCount > 0" class="template-import-preview-meta">
              {{ t('workflowView.templateImportMoreEdges', { count: pendingImportedTemplate.remainingEdgeCount }) }}
            </div>
          </div>
          <div v-if="pendingImportedTemplate.nodeSummaries.length" class="template-import-node-list">
            <div class="template-import-node-list-title">{{ t('workflowView.templateImportNodesPreview') }}</div>
            <div
              v-for="node in pendingImportedTemplate.nodeSummaries"
              :key="node.id"
              class="template-import-node-item"
            >
              <div class="template-import-node-main">
                <span class="template-import-node-id">{{ node.id }}</span>
                <span class="template-import-node-type">{{ node.type }}</span>
              </div>
              <div v-if="node.summary" class="template-import-node-summary">{{ node.summary }}</div>
            </div>
            <div v-if="pendingImportedTemplate.remainingNodeCount > 0" class="template-import-preview-meta">
              {{ t('workflowView.templateImportMoreNodes', { count: pendingImportedTemplate.remainingNodeCount }) }}
            </div>
          </div>
          <div
            class="template-import-preview-status"
            :class="{ 'is-valid': pendingImportedTemplate.isValid, 'is-invalid': !pendingImportedTemplate.isValid }"
          >
            {{ pendingImportedTemplate.validationMessage }}
          </div>
          <div class="template-import-preview-actions">
            <button
              type="button"
              class="template-toolbar-button"
              :disabled="!pendingImportedTemplate.isValid"
              @click="applyImportedTemplate"
            >
              {{ t('workflowView.applyImportedTemplate') }}
            </button>
            <button
              type="button"
              class="template-toolbar-button"
              @click="clearTemplateImportPreview"
            >
              {{ t('common.cancel') }}
            </button>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeTemplateModal" class="cancel-button">{{ t('common.cancel') }}</button>
      </div>
    </div>
  </div>
  <input
    ref="templateImportInputRef"
    type="file"
    accept="application/json,.json"
    class="template-import-input"
    @change="handleTemplateImport"
  />

  <div v-if="showMcpInjectionModal" class="modal-overlay" @click.self="closeMcpInjectionModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">{{ t('workflowView.mcpInjectionTitle') }}</h3>
        <button @click="closeMcpInjectionModal" class="close-button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <p class="template-intro">
          {{ t('workflowView.mcpInjectionDesc') }}
        </p>
        <div class="template-import-preview-meta">
          {{ t('workflowView.mcpInjectionPresetLabel') }}: {{ pendingMcpInjectionLabel }}
        </div>
        <div v-if="pendingMcpInjectionPresets.length" class="template-tag-row">
          <span
            v-for="preset in pendingMcpInjectionPresets"
            :key="`${preset.id}-${preset.server}`"
            class="template-tag-chip"
          >
            {{ preset.title || preset.id }} · {{ preset.prefix }}
          </span>
        </div>
        <div class="form-group">
          <label class="form-label" for="mcp-injection-node">{{ t('workflowView.mcpInjectionTargetLabel') }}</label>
          <select id="mcp-injection-node" v-model="selectedMcpInjectionNodeId" class="form-input">
            <option v-for="node in availableAgentNodesForInjection" :key="node.id" :value="node.id">
              {{ node.id }}
            </option>
          </select>
        </div>
      </div>
      <div class="modal-footer">
        <button @click="closeMcpInjectionModal" class="cancel-button">{{ t('common.cancel') }}</button>
        <button
          @click="applyMcpInjection"
          class="submit-button"
          :disabled="!selectedMcpInjectionNodeId"
        >
          {{ t('workflowView.mcpInjectionApply') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import RichTooltip from '../components/RichTooltip.vue'
import yaml from 'js-yaml'
import { fetchYaml, fetchVueGraph, postVuegraphs, updateYaml, postYamlNameChange, postYamlCopy } from '../utils/apiFunctions'
import { helpContent } from '../utils/helpContent.js'
import { configStore } from '../utils/configStore.js'
import { t } from '../utils/i18n.js'
import { workflowTemplates, buildWorkflowTemplate } from '../utils/workflowTemplates.js'

const shouldShowTooltip = computed(() => configStore.ENABLE_HELP_TOOLTIPS)

const props = defineProps({
  workflowName: {
    type: String,
    required: true
  },
  embedded: {
    type: Boolean,
    default: false
  }
})
const emit = defineEmits(['refresh-workflows'])
const route = useRoute()
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
const showTemplateModal = ref(false)
const templateImportInputRef = ref(null)
const pendingImportedTemplate = ref(null)
const renameWorkflowName = ref('')
const copyWorkflowName = ref('')
const selectedTemplateCategory = ref('all')
const templateSearchQuery = ref('')
const templateFavorites = ref([])
const templateRecent = ref([])
const templateUsageCounts = ref({})
const localImportedTemplates = ref([])
const pinnedImportedTemplateIds = ref([])
const recommendedTemplateIds = ref([])
const recommendedPackId = ref('')
const showMcpInjectionModal = ref(false)
const pendingMcpInjection = ref({ presets: [] })
const selectedMcpInjectionNodeId = ref('')
const injectionFocusNodeId = ref('')
const TEMPLATE_FAVORITES_STORAGE_KEY = 'moviedev.workflow-template-favorites'
const TEMPLATE_RECENT_STORAGE_KEY = 'moviedev.workflow-template-recent'
const TEMPLATE_USAGE_STORAGE_KEY = 'moviedev.workflow-template-usage-counts'
const LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY = 'moviedev.workflow-template-imports'
const PINNED_IMPORTED_TEMPLATES_STORAGE_KEY = 'moviedev.workflow-template-imports-pinned'
const LEGACY_TEMPLATE_FAVORITES_STORAGE_KEY = 'chatdev.workflow-template-favorites'
const LEGACY_TEMPLATE_RECENT_STORAGE_KEY = 'chatdev.workflow-template-recent'
const LEGACY_TEMPLATE_USAGE_STORAGE_KEY = 'chatdev.workflow-template-usage-counts'
const LEGACY_LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY = 'chatdev.workflow-template-imports'
const LEGACY_PINNED_IMPORTED_TEMPLATES_STORAGE_KEY = 'chatdev.workflow-template-imports-pinned'
const MAX_TEMPLATE_RECENT = 6

const templateCategories = Object.freeze([
  { id: 'all', labelKey: 'workflowView.templateCategories.all' },
  { id: 'favorites', labelKey: 'workflowView.templateCategories.favorites' },
  { id: 'recent', labelKey: 'workflowView.templateCategories.recent' },
  { id: 'imported', labelKey: 'workflowView.templateCategories.imported' },
  { id: 'core', labelKey: 'workflowView.templateCategories.core' },
  { id: 'research', labelKey: 'workflowView.templateCategories.research' },
  { id: 'writing', labelKey: 'workflowView.templateCategories.writing' },
  { id: 'decision', labelKey: 'workflowView.templateCategories.decision' },
  { id: 'human', labelKey: 'workflowView.templateCategories.human' },
  { id: 'skills', labelKey: 'workflowView.templateCategories.skills' },
  { id: 'mcp', labelKey: 'workflowView.templateCategories.mcp' },
])

const normalizedTemplateSearch = computed(() => String(templateSearchQuery.value || '').trim().toLowerCase())
const allTemplateItems = computed(() => [...workflowTemplates, ...localImportedTemplates.value])
const isRecommendedTemplate = (templateId) => recommendedTemplateIds.value.includes(templateId)
const availableAgentNodesForInjection = computed(() => (
  Array.isArray(yamlContent.value?.graph?.nodes)
    ? yamlContent.value.graph.nodes.filter((node) => node?.type === 'agent' && node?.id)
    : []
))
const pendingMcpInjectionPresets = computed(() => (
  Array.isArray(pendingMcpInjection.value?.presets)
    ? pendingMcpInjection.value.presets
    : []
))
const pendingMcpInjectionLabel = computed(() => {
  const presets = pendingMcpInjectionPresets.value
  if (!presets.length) {
    return ''
  }
  if (presets.length === 1) {
    return presets[0]?.title || presets[0]?.id || ''
  }
  return t('workflowView.mcpInjectionPresetCount', { count: presets.length })
})

const filteredWorkflowTemplates = computed(() => {
  const search = normalizedTemplateSearch.value
  return allTemplateItems.value
    .filter((templateItem) => {
      if (selectedTemplateCategory.value === 'favorites' && !isTemplateFavorite(templateItem.id)) {
        return false
      }
      if (selectedTemplateCategory.value === 'recent' && !isTemplateRecent(templateItem.id)) {
        return false
      }
      if (selectedTemplateCategory.value === 'imported' && templateItem.source !== 'local_import') {
        return false
      }
      if (
        selectedTemplateCategory.value !== 'all'
        && selectedTemplateCategory.value !== 'favorites'
        && selectedTemplateCategory.value !== 'recent'
        && selectedTemplateCategory.value !== 'imported'
      ) {
        const targetKey = `workflowView.templateCategories.${selectedTemplateCategory.value}`
        if (templateItem.categoryKey !== targetKey) {
          return false
        }
      }
      if (!search) {
        return true
      }
      const searchable = [
        getTemplateTitle(templateItem),
        getTemplateDescription(templateItem),
        getTemplateCategoryLabel(templateItem),
        getTemplateTags(templateItem).join(' '),
      ]
        .join(' ')
        .toLowerCase()
      return searchable.includes(search)
    })
    .sort((left, right) => {
      const leftRecommended = isRecommendedTemplate(left.id) ? 1 : 0
      const rightRecommended = isRecommendedTemplate(right.id) ? 1 : 0
      const leftRecentRank = recentRank(left.id)
      const rightRecentRank = recentRank(right.id)
      const leftFavorite = isTemplateFavorite(left.id) ? 1 : 0
      const rightFavorite = isTemplateFavorite(right.id) ? 1 : 0
      const leftPinned = isPinnedImportedTemplate(left.id) ? 1 : 0
      const rightPinned = isPinnedImportedTemplate(right.id) ? 1 : 0
      const leftUsageCount = templateUsageCount(left.id)
      const rightUsageCount = templateUsageCount(right.id)
      if (leftRecommended !== rightRecommended) {
        return rightRecommended - leftRecommended
      }
      if (selectedTemplateCategory.value === 'recent' && leftRecentRank !== rightRecentRank) {
        return leftRecentRank - rightRecentRank
      }
      if (leftRecentRank !== rightRecentRank) {
        return leftRecentRank - rightRecentRank
      }
      if (leftPinned !== rightPinned) {
        return rightPinned - leftPinned
      }
      if (leftFavorite !== rightFavorite) {
        return rightFavorite - leftFavorite
      }
      if (leftUsageCount !== rightUsageCount) {
        return rightUsageCount - leftUsageCount
      }
      return left.id.localeCompare(right.id)
    })
})

const getTemplateTitle = (templateItem) => {
  if (templateItem?.titleKey) {
    return t(templateItem.titleKey)
  }
  return String(templateItem?.title || t('common.unnamed'))
}

const getTemplateDescription = (templateItem) => {
  if (templateItem?.descriptionKey) {
    return t(templateItem.descriptionKey)
  }
  return String(templateItem?.description || '')
}

const getTemplateCategoryLabel = (templateItem) => {
  if (templateItem?.categoryKey) {
    return t(templateItem.categoryKey)
  }
  return ''
}

const getTemplateTags = (templateItem) => (
  Array.isArray(templateItem?.tags)
    ? templateItem.tags.map((tag) => String(tag || '').trim()).filter(Boolean)
    : []
)

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
  const source = yamlContent.value
  if (!source?.graph) {
    return
  }
  const sourceGraph = source.graph
  const nodesArr = Array.isArray(sourceGraph.nodes) ? sourceGraph.nodes : []
  const edgesArr = Array.isArray(sourceGraph.edges) ? sourceGraph.edges : []

  // Remove the node and its related edges
  const nextNodes = nodesArr.filter(node => node?.id !== nodeId)
  const nextEdges = edgesArr.filter(edge => edge?.from !== nodeId && edge?.to !== nodeId)
  
  // Remove node ID from graph.start/end
  const nextStart = Array.isArray(sourceGraph.start)
    ? sourceGraph.start.filter(id => id !== nodeId)
    : sourceGraph.start
  const nextEnd = Array.isArray(sourceGraph.end)
    ? sourceGraph.end.filter(id => id !== nodeId)
    : sourceGraph.end

  const nextSnapshot = {
    ...source,
    graph: {
      ...sourceGraph,
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
  const source = yamlContent.value
  if (!source?.graph || !Array.isArray(source.graph.edges)) {
    return
  }
  const sourceGraph = source.graph

  let removed = false
  const nextEdges = sourceGraph.edges.filter(edge => {
    if (!removed && edge?.from === fromId && edge?.to === toId) {
      removed = true
      return false
    }
    return true
  })

  // Delete from .start if edge is from Start Node
  let nextStart = sourceGraph.start
  if (fromId === START_NODE_ID) {
    nextStart = Array.isArray(sourceGraph.start)
      ? sourceGraph.start.filter(id => id !== toId)
      : sourceGraph.start

    // Empty start node array is not allowed
    const startArray = Array.isArray(nextStart) ? nextStart : []
    if (startArray.length === 0) {
      alert(t('workflowView.startConnectionRequired'))
      return
    }
  }

  const nextSnapshot = {
    ...source,
    graph: {
      ...sourceGraph,
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
  const confirmed = window.confirm(t('workflowView.confirmDeleteNode'))
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
  const confirmed = window.confirm(t('workflowView.confirmDeleteEdge'))
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
  injectionFocusNodeId.value = ''
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
  loadTemplateFavorites()
  loadTemplateRecent()
  loadTemplateUsageCounts()
  loadLocalImportedTemplates()
  loadPinnedImportedTemplateIds()
  await initializeWorkflow(props.workflowName)
  syncRecommendedTemplatesFromRoute()
  syncPendingMcpInjectionFromRoute()
  if (String(route.query.openTemplates || '') === '1') {
    openTemplateModal()
  }
  if (String(route.query.injectMcpPreset || '')) {
    openMcpInjectionModalIfNeeded()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('click', onGlobalClick)
})

watch(
  () => route.query,
  (query) => {
    syncRecommendedTemplatesFromRoute()
    syncPendingMcpInjectionFromRoute()
    if (String(query.openTemplates || '') === '1') {
      openTemplateModal()
    }
    if (String(query.injectMcpPreset || '')) {
      openMcpInjectionModalIfNeeded()
    }
  },
  { deep: true }
)

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
    const defaultCenterPosition = getCentralPosition()
    const getDefaultCenterPosition = () => ({
      x: defaultCenterPosition.x,
      y: defaultCenterPosition.y
    })

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

        let queueIndex = 0
        while (queueIndex < q.length) {
          const id = q[queueIndex++]
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

          const pos = positions.get(id) || getDefaultCenterPosition()
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
          position: getDefaultCenterPosition(),
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
          const xs = yamlNodesInGraph.map(n => (n?.position && typeof n.position.x === 'number') ? n.position.x : defaultCenterPosition.x)
          const minX = Math.min(...xs)
          // Find nodes in that left column
          const tol = 1
          const leftColumn = yamlNodesInGraph.filter(n => Math.abs((n?.position?.x || 0) - minX) <= tol)
          const ys = leftColumn.map(n => (n?.position && typeof n.position.y === 'number') ? n.position.y : defaultCenterPosition.y)
          const avgY = ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : defaultCenterPosition.y
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
            position: getDefaultCenterPosition(),
            data: { id: START_NODE_ID, label: 'Start' }
          }
        }
      } catch (err) {
        console.warn('Failed to compute start node position, falling back to center:', err)
        startNode = {
          id: START_NODE_ID,
          type: 'start-node',
          label: 'Start',
          position: getDefaultCenterPosition(),
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
    const nextYamlEdgeIdSet = new Set(nextYamlEdges.map(edge => edge.id))
    edges.value = [
      // keep any existing edges that are not YAML edges (e.g., visual-only) when preserving layout
      // but always exclude previous Start edges so they are replaced by the newly computed ones
      ...(preserveExistingLayout ? currentEdges.filter(e => {
        const k = `${e.source}-${e.target}`
        // drop if it's a YAML-defined edge or a previous Start edge
        const isYamlEdge = nextYamlEdgeIdSet.has(k)
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
// Build YAML without specific node (shallow clone path to avoid full deep-clone on editor open)
const buildYamlWithoutNode = (nodeId) => {
  const source = yamlContent.value
  if (!source?.graph?.nodes || !Array.isArray(source.graph.nodes)) {
    return source
  }
  return {
    ...source,
    graph: {
      ...source.graph,
      nodes: source.graph.nodes.filter(node => node?.id !== nodeId)
    }
  }
}

const buildYamlWithoutEdge = (fromId, toId) => {
  const source = yamlContent.value
  if (!source?.graph?.edges || !Array.isArray(source.graph.edges)) {
    return source
  }
  let removed = false
  const filteredEdges = source.graph.edges.filter(edge => {
    if (!removed && edge?.from === fromId && edge?.to === toId) {
      removed = true
      return false
    }
    return true
  })
  return {
    ...source,
    graph: {
      ...source.graph,
      edges: filteredEdges
    }
  }
}

const buildYamlWithoutVars = () => {
  const source = yamlContent.value
  if (!source || typeof source !== 'object') {
    return source
  }
  if (!Object.prototype.hasOwnProperty.call(source, 'vars')) {
    return source
  }
  const sanitized = { ...source }
  delete sanitized.vars
  return sanitized
}

const buildYamlWithoutMemory = () => {
  const source = yamlContent.value
  if (!source?.graph) {
    return source
  }
  if (Object.prototype.hasOwnProperty.call(source.graph, 'memory')) {
    const newGraph = { ...source.graph }
    delete newGraph.memory
    return {
      ...source,
      graph: newGraph
    }
  }
  return source
}

const buildYamlWithoutTriggers = () => {
  const source = yamlContent.value
  if (!source?.graph) {
    return source
  }
  if (Object.prototype.hasOwnProperty.call(source.graph, 'triggers')) {
    const newGraph = { ...source.graph }
    delete newGraph.triggers
    return {
      ...source,
      graph: newGraph
    }
  }
  return source
}

const buildYamlWithoutGraph = () => {
  const source = yamlContent.value
  if (!source || typeof source !== 'object') {
    return source
  }
  if (!Object.prototype.hasOwnProperty.call(source, 'graph')) {
    return source
  }
  const sanitized = { ...source }
  delete sanitized.graph
  return sanitized
}

const autoAddStartEdge = async (nextNodeId) => {
  const workflowNodes = (yamlContent.value?.graph?.nodes || []).filter(node => node?.id !== START_NODE_ID)
  if (workflowNodes.length === 1 && workflowNodes[0]?.id === nextNodeId) {
    const source = yamlContent.value
    const sourceGraph = source?.graph && typeof source.graph === 'object' ? source.graph : {}
    const currentStart = Array.isArray(sourceGraph.start) ? sourceGraph.start : []
    if (!currentStart.includes(nextNodeId)) {
      const nextSnapshot = {
        ...source,
        graph: {
          ...sourceGraph,
          start: [...currentStart, nextNodeId]
        }
      }
      const ok = await persistYamlSnapshot(nextSnapshot)
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
  formGeneratorInitialYaml.value = yamlSource || null

  if (Object.prototype.hasOwnProperty.call(options, 'initialFormData')) {
    formGeneratorInitialFormData.value = options.initialFormData || null
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

const openTemplateModal = () => {
  selectedTemplateCategory.value = 'all'
  templateSearchQuery.value = ''
  clearTemplateImportPreview()
  showTemplateModal.value = true
}

const syncRecommendedTemplatesFromRoute = () => {
  const rawTemplates = String(route.query.recommendedTemplates || '')
  recommendedTemplateIds.value = rawTemplates
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  recommendedPackId.value = String(route.query.recommendedPack || '').trim()
}

const clearTemplateRecommendationQuery = async () => {
  const nextQuery = { ...route.query }
  delete nextQuery.openTemplates
  delete nextQuery.recommendedPack
  delete nextQuery.recommendedTemplates
  await router.replace({ query: nextQuery })
}

const syncPendingMcpInjectionFromRoute = () => {
  const payload = String(route.query.injectMcpPayload || '').trim()
  if (payload) {
    try {
      const parsed = JSON.parse(decodeURIComponent(payload))
      const presets = Array.isArray(parsed)
        ? parsed.map((item) => ({
            id: String(item?.id || '').trim(),
            title: String(item?.title || item?.id || '').trim(),
            mode: String(item?.mode || 'mcp_remote').trim(),
            prefix: String(item?.prefix || '').trim(),
            server: String(item?.server || '').trim(),
          })).filter((item) => item.id && item.server)
        : []
      pendingMcpInjection.value = { presets }
      return
    } catch (_error) {
      // Fall back to legacy single-preset query parsing below.
    }
  }

  const presetId = String(route.query.injectMcpPreset || '').trim()
  if (!presetId) {
    pendingMcpInjection.value = { presets: [] }
    return
  }
  pendingMcpInjection.value = {
    presets: [
      {
        id: presetId,
        title: String(route.query.injectMcpTitle || presetId).trim(),
        mode: String(route.query.injectMcpMode || 'mcp_remote').trim(),
        prefix: String(route.query.injectMcpPrefix || '').trim(),
        server: String(route.query.injectMcpServer || '').trim(),
      }
    ],
  }
}

const clearMcpInjectionQuery = async () => {
  const nextQuery = { ...route.query }
  delete nextQuery.injectMcpPreset
  delete nextQuery.injectMcpTitle
  delete nextQuery.injectMcpMode
  delete nextQuery.injectMcpPrefix
  delete nextQuery.injectMcpServer
  delete nextQuery.injectMcpPayload
  await router.replace({ query: nextQuery })
}

const openMcpInjectionModalIfNeeded = () => {
  if (!pendingMcpInjectionPresets.value.length) {
    return
  }
  if (!availableAgentNodesForInjection.value.length) {
    alert(t('workflowView.mcpInjectionNoAgentNodes'))
    clearMcpInjectionQuery()
    return
  }
  selectedMcpInjectionNodeId.value = availableAgentNodesForInjection.value[0]?.id || ''
  showMcpInjectionModal.value = true
}

const closeTemplateModal = async () => {
  clearTemplateImportPreview()
  showTemplateModal.value = false
  if (
    String(route.query.openTemplates || '') ||
    String(route.query.recommendedPack || '') ||
    String(route.query.recommendedTemplates || '')
  ) {
    await clearTemplateRecommendationQuery()
  }
}

const closeMcpInjectionModal = async () => {
  showMcpInjectionModal.value = false
  selectedMcpInjectionNodeId.value = ''
  await clearMcpInjectionQuery()
}

const clearInjectionFocus = () => {
  injectionFocusNodeId.value = ''
}

const openInjectedNodeEditor = () => {
  if (!injectionFocusNodeId.value) {
    return
  }
  openNodeEditor(injectionFocusNodeId.value)
}

const clearTemplateImportPreview = () => {
  pendingImportedTemplate.value = null
}

const exportCurrentWorkflowTemplate = () => {
  if (!yamlContent.value?.graph) {
    alert(t('workflowView.templateExportFailed'))
    return
  }

  const exportPayload = {
    version: 1,
    exported_at: new Date().toISOString(),
    workflow_name: workflowName.value,
    source: 'moviedev-template-export',
    tags: ['moviedev', 'agent-team', 'workflow-template'],
    snapshot: cloneDeep(yamlContent.value),
  }

  try {
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    const safeName = String(workflowName.value || 'workflow_template')
      .replace(/\.(yaml|yml)$/i, '')
      .replace(/[^A-Za-z0-9_-]+/g, '_')
    link.href = url
    link.download = `${safeName || 'workflow_template'}.template.json`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (_error) {
    alert(t('workflowView.templateExportFailed'))
  }
}

const triggerTemplateImport = () => {
  templateImportInputRef.value?.click?.()
}

const normalizeImportedTemplateSnapshot = (raw) => {
  if (!raw || typeof raw !== 'object') {
    return null
  }

  const candidate = raw?.snapshot && typeof raw.snapshot === 'object'
    ? raw.snapshot
    : raw

  if (!candidate?.graph || typeof candidate.graph !== 'object') {
    return null
  }

  const nodes = Array.isArray(candidate.graph.nodes) ? candidate.graph.nodes : []
  const start = Array.isArray(candidate.graph.start) ? candidate.graph.start : []
  if (!nodes.length || !start.length) {
    return null
  }

  return cloneDeep(candidate)
}

const buildImportedTemplatePreview = (fileName, snapshot) => {
  const nodes = Array.isArray(snapshot?.graph?.nodes) ? snapshot.graph.nodes : []
  const edges = Array.isArray(snapshot?.graph?.edges) ? snapshot.graph.edges : []
  const start = Array.isArray(snapshot?.graph?.start) ? snapshot.graph.start : []
  const tags = Array.isArray(snapshot?.tags)
    ? snapshot.tags.map((item) => String(item || '').trim()).filter(Boolean)
    : []
  const isValid = nodes.length > 0 && start.length > 0
  const edgeSummaries = edges.slice(0, 6).map((edge, index) => ({
    id: `${String(edge?.from || 'unknown')}-${String(edge?.to || 'unknown')}-${index}`,
    from: String(edge?.from || t('common.unnamed')),
    to: String(edge?.to || t('common.unnamed')),
  }))
  const nodeSummaries = nodes.slice(0, 6).map((node) => {
    const summary = String(
      node?.config?.role
      || node?.config?.description
      || node?.type
      || ''
    )
      .split('\n')[0]
      .trim()

    return {
      id: String(node?.id || t('common.unnamed')),
      type: String(node?.type || 'node'),
      summary,
    }
  })

  return {
    fileName: String(fileName || t('common.unnamed')),
    workflowName: String(snapshot?.name || snapshot?.workflow_name || workflowName.value || t('common.unnamed')),
    nodeCount: nodes.length,
    edgeCount: edges.length,
    startCount: start.length,
    tags,
    startNodes: start.map((item) => String(item || '').trim()).filter(Boolean),
    edgeSummaries,
    remainingEdgeCount: Math.max(0, edges.length - edgeSummaries.length),
    nodeSummaries,
    remainingNodeCount: Math.max(0, nodes.length - nodeSummaries.length),
    isValid,
    snapshot,
    validationMessage: isValid
      ? t('workflowView.templateImportValidationPassed')
      : t('workflowView.templateImportValidationFailed'),
  }
}

const handleTemplateImport = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  try {
    const text = await file.text()
    const parsed = JSON.parse(text)
    const importedSnapshot = normalizeImportedTemplateSnapshot(parsed)

    if (!importedSnapshot) {
      pendingImportedTemplate.value = {
        fileName: String(file?.name || t('common.unnamed')),
        workflowName: t('common.unknownError'),
        nodeCount: 0,
        edgeCount: 0,
        startCount: 0,
        tags: [],
        startNodes: [],
        edgeSummaries: [],
        remainingEdgeCount: 0,
        nodeSummaries: [],
        remainingNodeCount: 0,
        isValid: false,
        snapshot: null,
        validationMessage: t('workflowView.templateImportValidationFailed'),
      }
      alert(t('workflowView.templateImportFailed'))
      return
    }
    pendingImportedTemplate.value = buildImportedTemplatePreview(file?.name, importedSnapshot)
  } catch (_error) {
    pendingImportedTemplate.value = {
      fileName: String(file?.name || t('common.unnamed')),
      workflowName: t('common.unknownError'),
      nodeCount: 0,
      edgeCount: 0,
      startCount: 0,
      tags: [],
      startNodes: [],
      edgeSummaries: [],
      remainingEdgeCount: 0,
      nodeSummaries: [],
      remainingNodeCount: 0,
      isValid: false,
      snapshot: null,
      validationMessage: t('workflowView.templateImportValidationFailed'),
    }
    alert(t('workflowView.templateImportFailed'))
  } finally {
    if (event?.target) {
      event.target.value = ''
    }
  }
}

const applyImportedTemplate = async () => {
  const preview = pendingImportedTemplate.value
  const importedSnapshot = pendingImportedTemplate.value?.snapshot
  if (!pendingImportedTemplate.value?.isValid || !importedSnapshot) {
    alert(t('workflowView.templateImportFailed'))
    return
  }

  const existingNodes = Array.isArray(yamlContent.value?.graph?.nodes) ? yamlContent.value.graph.nodes : []
  if (existingNodes.length > 0) {
    const confirmed = window.confirm(t('workflowView.templateReplaceConfirm'))
    if (!confirmed) {
      return
    }
  }

  const ok = await persistYamlSnapshot(importedSnapshot)
  if (!ok) {
    alert(t('workflowView.templateImportFailed'))
    return
  }

  saveImportedTemplateToLibrary(preview)
  clearTemplateImportPreview()
  await loadYamlFile()
  await generateNodesAndEdges({ fit: true })
  closeTemplateModal()
  alert(t('workflowView.templateImported'))
}

const loadTemplateFavorites = () => {
  try {
    const raw = window.localStorage.getItem(TEMPLATE_FAVORITES_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_TEMPLATE_FAVORITES_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    templateFavorites.value = Array.isArray(parsed)
      ? parsed.map((item) => String(item || '').trim()).filter(Boolean)
      : []
    if (!window.localStorage.getItem(TEMPLATE_FAVORITES_STORAGE_KEY) && raw) {
      persistTemplateFavorites()
    }
  } catch (_error) {
    templateFavorites.value = []
  }
}

const persistTemplateFavorites = () => {
  try {
    window.localStorage.setItem(
      TEMPLATE_FAVORITES_STORAGE_KEY,
      JSON.stringify(templateFavorites.value),
    )
  } catch (_error) {
    // Ignore storage failures and keep the in-memory state.
  }
}

const isTemplateFavorite = (templateId) => templateFavorites.value.includes(String(templateId || '').trim())
const isTemplateRecent = (templateId) => templateRecent.value.includes(String(templateId || '').trim())
const templateUsageCount = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  return Number(templateUsageCounts.value?.[normalizedId] || 0)
}
const recentRank = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  const index = templateRecent.value.indexOf(normalizedId)
  return index >= 0 ? index : Number.MAX_SAFE_INTEGER
}

const toggleTemplateFavorite = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  if (isTemplateFavorite(normalizedId)) {
    templateFavorites.value = templateFavorites.value.filter((item) => item !== normalizedId)
  } else {
    templateFavorites.value = [...templateFavorites.value, normalizedId]
  }
  persistTemplateFavorites()
}

const loadTemplateRecent = () => {
  try {
    const raw = window.localStorage.getItem(TEMPLATE_RECENT_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_TEMPLATE_RECENT_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    templateRecent.value = Array.isArray(parsed)
      ? parsed.map((item) => String(item || '').trim()).filter(Boolean).slice(0, MAX_TEMPLATE_RECENT)
      : []
    if (!window.localStorage.getItem(TEMPLATE_RECENT_STORAGE_KEY) && raw) {
      persistTemplateRecent()
    }
  } catch (_error) {
    templateRecent.value = []
  }
}

const persistTemplateRecent = () => {
  try {
    window.localStorage.setItem(
      TEMPLATE_RECENT_STORAGE_KEY,
      JSON.stringify(templateRecent.value),
    )
  } catch (_error) {
    // Ignore storage failures and keep the in-memory state.
  }
}

const markTemplateRecent = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  templateRecent.value = [
    normalizedId,
    ...templateRecent.value.filter((item) => item !== normalizedId),
  ].slice(0, MAX_TEMPLATE_RECENT)
  persistTemplateRecent()
}

const loadTemplateUsageCounts = () => {
  try {
    const raw = window.localStorage.getItem(TEMPLATE_USAGE_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_TEMPLATE_USAGE_STORAGE_KEY)
    const parsed = JSON.parse(raw || '{}')
    templateUsageCounts.value = (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : {}
    if (!window.localStorage.getItem(TEMPLATE_USAGE_STORAGE_KEY) && raw) {
      persistTemplateUsageCounts()
    }
  } catch (_error) {
    templateUsageCounts.value = {}
  }
}

const persistTemplateUsageCounts = () => {
  try {
    window.localStorage.setItem(
      TEMPLATE_USAGE_STORAGE_KEY,
      JSON.stringify(templateUsageCounts.value),
    )
  } catch (_error) {
    // Ignore storage failures and keep the in-memory state.
  }
}

const incrementTemplateUsage = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  templateUsageCounts.value = {
    ...templateUsageCounts.value,
    [normalizedId]: Number(templateUsageCounts.value?.[normalizedId] || 0) + 1,
  }
  persistTemplateUsageCounts()
}

const loadLocalImportedTemplates = () => {
  try {
    const raw = window.localStorage.getItem(LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    localImportedTemplates.value = Array.isArray(parsed)
      ? parsed
          .filter((item) => item && typeof item === 'object')
          .map((item) => ({
            id: String(item.id || ''),
            source: 'local_import',
            categoryKey: 'workflowView.templateCategories.imported',
            title: String(item.title || t('common.unnamed')),
            description: String(item.description || ''),
            tags: Array.isArray(item.tags)
              ? item.tags.map((tag) => String(tag || '').trim()).filter(Boolean)
              : [],
            snapshot: cloneDeep(item.snapshot || {}),
          }))
          .filter((item) => item.id && item.snapshot?.graph)
      : []
    if (!window.localStorage.getItem(LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY) && raw) {
      persistLocalImportedTemplates()
    }
  } catch (_error) {
    localImportedTemplates.value = []
  }
}

const persistLocalImportedTemplates = () => {
  try {
    window.localStorage.setItem(
      LOCAL_IMPORTED_TEMPLATES_STORAGE_KEY,
      JSON.stringify(localImportedTemplates.value.map((item) => ({
        id: item.id,
        title: item.title,
        description: item.description,
        tags: item.tags || [],
        snapshot: item.snapshot,
      }))),
    )
  } catch (_error) {
    // Ignore storage failures and keep the in-memory state.
  }
}

const isLocalImportedTemplate = (templateItem) => templateItem?.source === 'local_import'
const isPinnedImportedTemplate = (templateId) => pinnedImportedTemplateIds.value.includes(String(templateId || '').trim())

const loadPinnedImportedTemplateIds = () => {
  try {
    const raw = window.localStorage.getItem(PINNED_IMPORTED_TEMPLATES_STORAGE_KEY)
      ?? window.localStorage.getItem(LEGACY_PINNED_IMPORTED_TEMPLATES_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    pinnedImportedTemplateIds.value = Array.isArray(parsed)
      ? parsed.map((item) => String(item || '').trim()).filter(Boolean)
      : []
    if (!window.localStorage.getItem(PINNED_IMPORTED_TEMPLATES_STORAGE_KEY) && raw) {
      persistPinnedImportedTemplateIds()
    }
  } catch (_error) {
    pinnedImportedTemplateIds.value = []
  }
}

const persistPinnedImportedTemplateIds = () => {
  try {
    window.localStorage.setItem(
      PINNED_IMPORTED_TEMPLATES_STORAGE_KEY,
      JSON.stringify(pinnedImportedTemplateIds.value),
    )
  } catch (_error) {
    // Ignore storage failures and keep the in-memory state.
  }
}

const saveImportedTemplateToLibrary = (preview) => {
  const snapshot = cloneDeep(preview?.snapshot || {})
  if (!snapshot?.graph) {
    return
  }
  const normalizedTitle = String(preview?.workflowName || t('common.unnamed')).trim()
  const normalizedId = `imported_${normalizedTitle.replace(/[^A-Za-z0-9_]+/g, '_') || Date.now()}`
  const description = `${preview?.nodeCount || 0} nodes · ${preview?.edgeCount || 0} edges`
  const nextItem = {
    id: normalizedId,
    source: 'local_import',
    categoryKey: 'workflowView.templateCategories.imported',
    title: normalizedTitle,
    description,
    tags: Array.isArray(preview?.tags) ? preview.tags : [],
    snapshot,
  }
  localImportedTemplates.value = [
    nextItem,
    ...localImportedTemplates.value.filter((item) => item.id !== normalizedId),
  ].slice(0, 20)
  persistLocalImportedTemplates()
}

const togglePinImportedTemplate = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  if (isPinnedImportedTemplate(normalizedId)) {
    pinnedImportedTemplateIds.value = pinnedImportedTemplateIds.value.filter((item) => item !== normalizedId)
  } else {
    pinnedImportedTemplateIds.value = [normalizedId, ...pinnedImportedTemplateIds.value.filter((item) => item !== normalizedId)]
  }
  persistPinnedImportedTemplateIds()
}

const renameImportedTemplate = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  const current = localImportedTemplates.value.find((item) => item.id === normalizedId)
  if (!current) {
    return
  }
  const nextTitle = window.prompt(t('workflowView.templateRenamePrompt'), current.title)
  if (nextTitle == null) {
    return
  }
  const normalizedTitle = String(nextTitle || '').trim()
  if (!normalizedTitle) {
    return
  }
  localImportedTemplates.value = localImportedTemplates.value.map((item) => (
    item.id === normalizedId
      ? { ...item, title: normalizedTitle }
      : item
  ))
  persistLocalImportedTemplates()
}

const deleteImportedTemplate = (templateId) => {
  const normalizedId = String(templateId || '').trim()
  if (!normalizedId) {
    return
  }
  const current = localImportedTemplates.value.find((item) => item.id === normalizedId)
  if (!current) {
    return
  }
  const confirmed = window.confirm(t('workflowView.templateDeleteConfirm', { name: current.title }))
  if (!confirmed) {
    return
  }
  localImportedTemplates.value = localImportedTemplates.value.filter((item) => item.id !== normalizedId)
  templateFavorites.value = templateFavorites.value.filter((item) => item !== normalizedId)
  templateRecent.value = templateRecent.value.filter((item) => item !== normalizedId)
  const nextUsageCounts = { ...templateUsageCounts.value }
  delete nextUsageCounts[normalizedId]
  templateUsageCounts.value = nextUsageCounts
  pinnedImportedTemplateIds.value = pinnedImportedTemplateIds.value.filter((item) => item !== normalizedId)
  persistLocalImportedTemplates()
  persistTemplateFavorites()
  persistTemplateRecent()
  persistTemplateUsageCounts()
  persistPinnedImportedTemplateIds()
}

const applyTemplate = async (templateId) => {
  const existingNodes = Array.isArray(yamlContent.value?.graph?.nodes)
    ? yamlContent.value.graph.nodes
    : []

  if (existingNodes.length > 0) {
    const confirmed = window.confirm(t('workflowView.templateReplaceConfirm'))
    if (!confirmed) {
      return
    }
  }

  const localTemplate = localImportedTemplates.value.find((item) => item.id === templateId)
  const nextSnapshot = localTemplate
    ? cloneDeep(localTemplate.snapshot)
    : buildWorkflowTemplate(templateId, {
        workflowName: workflowName.value,
        currentSnapshot: yamlContent.value,
      })

  if (!nextSnapshot) {
    alert(t('workflowView.templateApplyFailed'))
    return
  }

  const ok = await persistYamlSnapshot(nextSnapshot)
  if (!ok) {
    alert(t('workflowView.templateApplyFailed'))
    return
  }

  await loadYamlFile()
  await generateNodesAndEdges({ fit: true })
  markTemplateRecent(templateId)
  incrementTemplateUsage(templateId)
  closeTemplateModal()
  alert(t('workflowView.templateApplied'))
}

const applyMcpInjection = async () => {
  const targetNodeId = String(selectedMcpInjectionNodeId.value || '').trim()
  const presets = pendingMcpInjectionPresets.value
  const source = yamlContent.value

  if (!targetNodeId || !presets.length || !source?.graph || !Array.isArray(source.graph.nodes)) {
    return
  }

  const nextSnapshot = cloneDeep(source)
  const targetNode = nextSnapshot.graph.nodes.find((node) => node?.id === targetNodeId)
  if (!targetNode) {
    return
  }

  if (!targetNode.config || typeof targetNode.config !== 'object') {
    targetNode.config = {}
  }

  const tooling = Array.isArray(targetNode.config.tooling) ? targetNode.config.tooling : []
  const newEntries = presets.filter((preset) => !tooling.some((item) => (
    item?.type === preset.mode
    && String(item?.prefix || '').trim() === preset.prefix
    && String(item?.config?.server || '').trim() === preset.server
  )))

  if (!newEntries.length) {
    alert(t('workflowView.mcpInjectionAlreadyExists'))
    await closeMcpInjectionModal()
    return
  }

  newEntries.forEach((preset) => {
    tooling.push({
      type: preset.mode || 'mcp_remote',
      prefix: preset.prefix || '',
      config: {
        server: preset.server || '',
        timeout: 30,
        cache_ttl: 0,
      },
    })
  })
  targetNode.config.tooling = tooling

  const ok = await persistYamlSnapshot(nextSnapshot)
  if (!ok) {
    alert(t('workflowView.mcpInjectionFailed'))
    return
  }

  await loadYamlFile()
  await generateNodesAndEdges({ fit: false })
  injectionFocusNodeId.value = targetNodeId
  await closeMcpInjectionModal()
  alert(t('workflowView.mcpInjectionApplied', {
    preset: newEntries.length === 1
      ? (newEntries[0]?.title || newEntries[0]?.id || '')
      : t('workflowView.mcpInjectionPresetCount', { count: newEntries.length }),
    node: targetNodeId
  }))
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

const openManageTriggersModal = () => {
  const currentTriggers = yamlContent.value?.graph?.triggers || null
  const sanitizedYaml = buildYamlWithoutTriggers()
  openDynamicFormGenerator('graph', {
    recursive: false,
    initialYaml: sanitizedYaml,
    initialFormData: currentTriggers ? { triggers: currentTriggers } : null,
    mode: currentTriggers ? 'edit' : 'create',
    fieldFilter: ['triggers']
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
    const source = yamlContent.value
    if (!source?.graph) {
      setTimeout(() => {
        isCreatingConnection.value = false
      }, 10)
      return
    }
    const sourceGraph = source.graph

    // Ensure graph.start exists as an array
    const currentStart = Array.isArray(sourceGraph.start) ? sourceGraph.start : []

    // Add target node to start array if not already present
    if (!currentStart.includes(connection.target)) {
      const nextSnapshot = {
        ...source,
        graph: {
          ...sourceGraph,
          start: [...currentStart, connection.target]
        }
      }

      // Persist the updated YAML
      const ok = await persistYamlSnapshot(nextSnapshot)
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
    alert(result.error?.message || t('workflowView.renameFailed'))
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
    alert(result.message || result.error?.message || t('workflowView.copyFailed'))
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

.template-modal {
  max-width: 760px;
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

.template-intro {
  margin: 0 0 18px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  line-height: 1.5;
}

.template-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-toolbar-button {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #f2f2f2;
  font-size: 12px;
  cursor: pointer;
}

.template-toolbar-button:hover {
  border-color: rgba(153, 234, 249, 0.35);
  background: rgba(153, 234, 249, 0.08);
}

.template-import-input {
  display: none;
}

.template-import-preview {
  margin-top: 16px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-import-preview-title {
  color: #f2f2f2;
  font-size: 14px;
  font-weight: 600;
}

.template-import-preview-meta {
  color: rgba(255, 255, 255, 0.68);
  font-size: 12px;
}

.template-import-node-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 4px;
}

.template-import-edge-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.template-import-edge-endpoint {
  color: #f2f2f2;
  font-weight: 600;
}

.template-import-edge-arrow {
  color: #99eaf9;
  font-size: 11px;
}

.template-import-node-list-title {
  color: #f2f2f2;
  font-size: 12px;
  font-weight: 600;
}

.template-import-node-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.template-import-node-main {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.template-import-node-id {
  color: #f2f2f2;
  font-size: 12px;
  font-weight: 600;
}

.template-import-node-type {
  color: #99eaf9;
  font-size: 11px;
  text-transform: uppercase;
}

.template-import-node-summary {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.66);
  font-size: 12px;
  line-height: 1.45;
}

.template-import-preview-status {
  font-size: 12px;
  font-weight: 600;
}

.template-import-preview-status.is-valid {
  color: #aaffcd;
}

.template-import-preview-status.is-invalid {
  color: #ffd580;
}

.template-import-preview-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.template-search-input {
  width: 100%;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #f2f2f2;
  font-size: 13px;
  box-sizing: border-box;
}

.template-search-input:focus {
  outline: none;
  border-color: rgba(153, 234, 249, 0.4);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}

.template-category-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.template-category-chip {
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.72);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.template-category-chip.is-active,
.template-category-chip:hover {
  border-color: rgba(153, 234, 249, 0.45);
  color: #f2f2f2;
  background: rgba(153, 234, 249, 0.12);
}

.template-card {
  text-align: left;
  padding: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  color: #f2f2f2;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
}

.template-card:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(170, 255, 205, 0.45);
}

.template-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.template-card-meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.template-card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
}

.template-card-meta {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.template-card-meta.is-favorite {
  color: #ffd580;
  background: rgba(255, 213, 128, 0.12);
}

.template-card-meta.is-recommended {
  color: #6fe2c7;
  background: rgba(111, 226, 199, 0.14);
}

.template-card-meta.is-recent {
  color: #a0c4ff;
  background: rgba(160, 196, 255, 0.12);
}

.template-card-meta.is-usage {
  color: #aaffcd;
  background: rgba(170, 255, 205, 0.12);
}

.injection-focus-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(111, 226, 199, 0.18);
  background: rgba(111, 226, 199, 0.08);
}

.injection-focus-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #eafbf6;
}

.injection-focus-copy strong {
  font-size: 14px;
}

.injection-focus-copy span {
  font-size: 13px;
  color: rgba(234, 251, 246, 0.78);
}

.injection-focus-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.template-favorite-button {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.72);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.template-favorite-button.is-active {
  color: #ffd580;
  border-color: rgba(255, 213, 128, 0.35);
  background: rgba(255, 213, 128, 0.08);
}

.template-card-category {
  color: #99eaf9;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
}

.template-card-description {
  color: rgba(255, 255, 255, 0.68);
  font-size: 13px;
  line-height: 1.5;
  min-height: 58px;
}

.template-tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.template-tag-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(153, 234, 249, 0.08);
  color: #99eaf9;
  font-size: 10px;
  letter-spacing: 0.02em;
}

.template-card-library-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.template-library-button {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  cursor: pointer;
}

.template-library-button.is-danger {
  color: #ffd580;
  border-color: rgba(255, 213, 128, 0.22);
  background: rgba(255, 213, 128, 0.08);
}

.template-card-action {
  margin-top: 14px;
  color: #aaffcd;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.template-empty-state {
  margin-top: 10px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
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

.workflow-view {
  min-height: 100%;
  padding: 0;
  background:
    radial-gradient(circle at top left, rgba(35, 156, 145, 0.1), transparent 24%),
    radial-gradient(circle at 88% 10%, rgba(236, 197, 122, 0.14), transparent 28%),
    linear-gradient(180deg, rgba(248, 245, 239, 0.88) 0%, rgba(239, 233, 222, 0.82) 100%);
  color: #17353c;
  border-radius: 28px;
  overflow: hidden;
}

.workflow-view--embedded {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  overflow: hidden;
}

.workflow-bg {
  top: -120px;
  left: 10%;
  right: 10%;
  height: 300px;
  background: linear-gradient(90deg, rgba(52, 166, 153, 0.16), rgba(236, 197, 122, 0.14), rgba(85, 148, 185, 0.12));
  filter: blur(95px);
  opacity: 1;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  min-height: 112px;
  padding: 26px 28px 20px;
  border-bottom: 1px solid rgba(21, 58, 64, 0.06);
  background: linear-gradient(135deg, rgba(20, 84, 90, 0.95) 0%, rgba(32, 106, 110, 0.92) 58%, rgba(240, 204, 134, 0.88) 140%);
}

.header--embedded {
  min-height: auto;
  padding: 0 0 10px;
  border-bottom: none;
  background: transparent;
}

.header-copy {
  max-width: 760px;
}

.header-eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(243, 249, 246, 0.66);
}

.workflow-name {
  margin: 10px 0 0;
  font-size: clamp(28px, 3.8vw, 42px);
  line-height: 1.06;
  color: #f8fcfa;
  letter-spacing: -0.03em;
}

.header-subtitle {
  margin: 12px 0 0;
  max-width: 620px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(243, 249, 246, 0.84);
}

.header-chip {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(250, 251, 248, 0.14);
  color: #fff7dc;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.injection-focus-banner {
  margin: 18px 22px 0;
  border: 1px solid rgba(31, 103, 109, 0.12);
  background: rgba(235, 246, 242, 0.9);
  box-shadow: 0 16px 34px rgba(22, 55, 62, 0.06);
}

.injection-focus-copy {
  color: #17353c;
}

.injection-focus-copy span {
  color: #5f7276;
}

.tabs {
  order: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px 0;
}

.tab-buttons {
  padding: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(21, 58, 64, 0.08);
  display: inline-flex;
  flex-wrap: wrap;
}

.tab {
  min-height: 42px;
  border-radius: 999px;
  padding: 0 18px;
  color: #5c7074;
}

.tab.active {
  background: #1f676d;
  color: #ffffff;
}

.editor-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(21, 58, 64, 0.08);
  box-shadow: 0 12px 28px rgba(29, 54, 61, 0.06);
}

.glass-button,
.menu-trigger,
.template-toolbar-button,
.cancel-button,
.form-input,
.template-search-input,
.template-category-chip,
.template-library-button {
  background: rgba(255, 255, 255, 0.92) !important;
  color: #17353c !important;
  border: 1px solid rgba(21, 58, 64, 0.1) !important;
  border-radius: 14px !important;
}

.glass-button:hover,
.menu-trigger:hover,
.template-toolbar-button:hover,
.template-category-chip:hover,
.template-category-chip.is-active {
  border-color: rgba(28, 104, 113, 0.2) !important;
  background: rgba(237, 246, 242, 0.96) !important;
}

.launch-button-primary,
.submit-button {
  background: linear-gradient(135deg, #19555c, #23707b, #e2b459) !important;
  color: #ffffff !important;
  border: none !important;
}

.glass-button,
.launch-button-primary,
.menu-trigger {
  min-height: 42px;
}

.content {
  order: 3;
  flex: 1;
  min-height: 0;
  padding: 18px 22px 22px;
}

.workflow-view--embedded .tabs {
  padding: 0 0 14px;
}

.workflow-view--embedded .content {
  padding: 0;
  flex: 1;
  min-height: 0;
}

.workflow-view--embedded .injection-focus-banner {
  margin: 0 0 14px;
}

.vueflow-container,
.yaml-editor {
  border-radius: 24px;
  background: rgba(255, 250, 243, 0.82);
  border: 1px solid rgba(21, 58, 64, 0.08);
  box-shadow: 0 24px 60px rgba(33, 55, 63, 0.08);
}

.yaml-error {
  background: rgba(181, 96, 73, 0.12);
  color: #8f4c40;
  border: 1px solid rgba(143, 76, 64, 0.12);
}

.yaml-textarea,
.form-input,
.template-search-input {
  background: rgba(255, 255, 255, 0.94);
  color: #17353c;
  border: 1px solid rgba(21, 58, 64, 0.1);
}

.yaml-textarea {
  background: rgba(255, 255, 255, 0.98) !important;
  color: #17353c !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Courier New', monospace;
  line-height: 1.7;
}

.context-menu,
.menu-dropdown,
.modal-content,
.template-card {
  background: #fffdf8 !important;
  border: 1px solid rgba(21, 58, 64, 0.08) !important;
  color: #17353c !important;
  box-shadow: 0 24px 50px rgba(24, 50, 57, 0.12);
}

.menu-item,
.modal-title,
.form-label,
.template-card-title,
.template-import-node-id,
.template-import-node-type {
  color: #17353c !important;
}

.modal-header,
.modal-body,
.modal-footer {
  background: #fffdf8 !important;
  color: #17353c !important;
  border-color: rgba(21, 58, 64, 0.08) !important;
}

.modal-header {
  height: auto !important;
  min-height: 68px;
  padding: 18px 22px !important;
  align-items: center !important;
}

.modal-body {
  padding: 20px 22px !important;
}

.modal-footer {
  padding: 16px 22px 20px;
}

.template-intro,
.yaml-error,
.template-import-preview-meta,
.template-import-node-summary,
.template-card-description,
.template-card-category,
.template-empty-state,
.menu-item,
.context-menu-item {
  color: #607477 !important;
}

.context-menu,
.menu-dropdown {
  background: rgba(255, 253, 248, 0.98) !important;
}

.context-menu-item:hover,
.menu-item:hover {
  background: rgba(237, 246, 242, 0.96) !important;
  color: #17353c !important;
}

.template-search-input::placeholder,
.form-input::placeholder {
  color: #7b8d90 !important;
}

.workflow-view--embedded .vueflow-container,
.workflow-view--embedded .yaml-editor {
  height: 100%;
  min-height: 0;
}

.template-card-description,
.template-empty-state,
.template-intro,
.template-card-category,
.template-import-preview-meta,
.template-import-node-summary {
  color: #617477 !important;
}

.template-card-action,
.template-tag-chip,
.template-card-meta.is-recent,
.template-card-meta.is-usage {
  color: #1c6871 !important;
}

.template-card-meta.is-favorite,
.template-favorite-button.is-active,
.template-library-button.is-danger {
  color: #9c6b12 !important;
}

.template-card.is-recommended {
  border-color: rgba(31, 103, 109, 0.22) !important;
  box-shadow: 0 18px 40px rgba(31, 103, 109, 0.08);
}

.template-card-meta.is-recommended {
  color: #1f676d !important;
  background: rgba(31, 103, 109, 0.08);
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

@media (max-width: 1100px) {
  .header,
  .tabs {
    flex-direction: column;
    align-items: stretch;
  }

  .header-chip {
    align-self: flex-start;
  }

  .editor-actions {
    width: 100%;
  }
}

.workflow-view,
.workflow-view--embedded {
  --mv-surface: #fffdf8;
  --mv-surface-soft: rgba(255, 250, 243, 0.96);
  --mv-surface-muted: rgba(245, 239, 229, 0.9);
  --mv-border: rgba(21, 58, 64, 0.1);
  --mv-text: #17353c;
  --mv-text-soft: #607477;
  --mv-accent: #1f676d;
}

.workflow-view .yaml-editor,
.workflow-view .vueflow-container,
.workflow-view .context-menu,
.workflow-view .menu-dropdown,
.workflow-view .modal-content,
.workflow-view .template-card,
.workflow-view .template-import-preview,
.workflow-view .template-import-node-item,
.workflow-view .template-import-edge-item,
.workflow-view .template-category-chip,
.workflow-view .template-toolbar-button,
.workflow-view .glass-button,
.workflow-view .menu-trigger,
.workflow-view .cancel-button,
.workflow-view .form-input,
.workflow-view .template-search-input {
  color: var(--mv-text) !important;
  border-color: var(--mv-border) !important;
}

.workflow-view .yaml-editor,
.workflow-view .vueflow-container,
.workflow-view .context-menu,
.workflow-view .menu-dropdown,
.workflow-view .modal-content,
.workflow-view .template-card,
.workflow-view .template-import-preview,
.workflow-view .template-import-node-item,
.workflow-view .template-import-edge-item {
  background: var(--mv-surface) !important;
}

.workflow-view .modal-header,
.workflow-view .modal-body,
.workflow-view .modal-footer,
.workflow-view .template-intro,
.workflow-view .template-import-preview-meta,
.workflow-view .template-import-node-summary,
.workflow-view .template-card-description,
.workflow-view .template-card-category,
.workflow-view .template-empty-state,
.workflow-view .menu-item,
.workflow-view .context-menu-item,
.workflow-view .yaml-error,
.workflow-view .header-subtitle {
  color: var(--mv-text-soft) !important;
}

.workflow-view .modal-title,
.workflow-view .form-label,
.workflow-view .template-card-title,
.workflow-view .template-import-node-id,
.workflow-view .template-import-node-type,
.workflow-view .workflow-name,
.workflow-view .header-chip,
.workflow-view .tab,
.workflow-view .menu-item:hover,
.workflow-view .context-menu-item:hover {
  color: var(--mv-text) !important;
}

.workflow-view .yaml-textarea,
.workflow-view textarea,
.workflow-view input,
.workflow-view select {
  background: #ffffff !important;
  color: var(--mv-text) !important;
  border: 1px solid var(--mv-border) !important;
  -webkit-text-fill-color: var(--mv-text) !important;
}

.workflow-view .yaml-textarea::placeholder,
.workflow-view input::placeholder,
.workflow-view textarea::placeholder {
  color: #7b8d90 !important;
  -webkit-text-fill-color: #7b8d90 !important;
}

.workflow-view select option {
  background: var(--mv-surface) !important;
  color: var(--mv-text) !important;
}

.workflow-view .yaml-editor,
.workflow-view .yaml-textarea {
  background: var(--mv-surface-soft) !important;
}

.workflow-view .context-menu-item:hover,
.workflow-view .menu-item:hover,
.workflow-view .template-category-chip:hover,
.workflow-view .template-category-chip.is-active,
.workflow-view .glass-button:hover,
.workflow-view .template-toolbar-button:hover,
.workflow-view .menu-trigger:hover {
  background: rgba(237, 246, 242, 0.96) !important;
  color: var(--mv-text) !important;
}

.workflow-view .modal-header,
.workflow-view .modal-body,
.workflow-view .modal-footer {
  background: var(--mv-surface) !important;
}

.workflow-view .close-button {
  background: rgba(255, 255, 255, 0.92) !important;
  color: var(--mv-text-soft) !important;
  border: 1px solid var(--mv-border) !important;
}

.workflow-view .close-button:hover {
  color: var(--mv-text) !important;
  background: #ffffff !important;
}

.workflow-view .template-card-action,
.workflow-view .template-tag-chip,
.workflow-view .template-card-meta,
.workflow-view .group-name {
  color: var(--mv-accent) !important;
}

.workflow-view .tab.active,
.workflow-view .launch-button-primary,
.workflow-view .submit-button {
  color: #ffffff !important;
}

.workflow-view {
  color: var(--mv-ink) !important;
}

.workflow-view .tabs,
.workflow-view .editor-actions {
  background: rgba(255, 250, 242, 0.72) !important;
  border: 1px solid var(--mv-line) !important;
  box-shadow: none !important;
}

.workflow-view .tab {
  color: var(--mv-ink-soft) !important;
  background: transparent !important;
}

.workflow-view .tab.active {
  background: var(--mv-primary) !important;
  color: #fffaf2 !important;
}

.workflow-view .glass-button,
.workflow-view .menu-trigger,
.workflow-view .template-toolbar-button,
.workflow-view .cancel-button {
  background: #fffaf2 !important;
  color: var(--mv-ink) !important;
  border: 1px solid var(--mv-line) !important;
  box-shadow: none !important;
}

.workflow-view .glass-button::before {
  display: none !important;
}

.workflow-view .glass-button:hover,
.workflow-view .menu-trigger:hover,
.workflow-view .template-toolbar-button:hover,
.workflow-view .cancel-button:hover {
  transform: translateY(-1px);
  background: var(--mv-panel-green) !important;
  border-color: rgba(30, 100, 107, 0.22) !important;
}

.workflow-view .launch-button-primary,
.workflow-view .submit-button {
  background: var(--mv-primary) !important;
  color: #fffaf2 !important;
  box-shadow: 0 12px 24px rgba(30, 100, 107, 0.18) !important;
}

.workflow-view .launch-button-primary:hover,
.workflow-view .submit-button:hover:not(:disabled) {
  background: var(--mv-primary-strong) !important;
}

.workflow-view .header--embedded {
  padding: 0 0 14px !important;
  border-bottom: 1px solid var(--mv-line) !important;
  background: transparent !important;
}

.workflow-view--embedded .workflow-name {
  display: inline-flex;
  align-items: center;
  min-height: 42px;
  margin: 0 !important;
  padding: 0 4px;
  font-family: var(--mv-heading-font);
  font-size: 30px !important;
  line-height: 1.1 !important;
  color: var(--mv-ink) !important;
  -webkit-text-fill-color: var(--mv-ink) !important;
}

.workflow-view .tab-buttons {
  gap: 6px !important;
  padding: 5px !important;
  border-radius: 16px !important;
  background: #f5eadc !important;
  border: 1px solid var(--mv-line) !important;
}

.workflow-view .tab {
  min-height: 38px !important;
  height: auto !important;
  padding: 0 16px !important;
  border: 1px solid transparent !important;
  border-radius: 12px !important;
  background: transparent !important;
  color: #4e6266 !important;
  -webkit-text-fill-color: #4e6266 !important;
  background-clip: border-box !important;
  -webkit-background-clip: border-box !important;
  font-weight: 700 !important;
}

.workflow-view .tab:hover {
  background: rgba(255, 250, 242, 0.74) !important;
  color: var(--mv-ink) !important;
  -webkit-text-fill-color: var(--mv-ink) !important;
}

.workflow-view .tab.active {
  background: #fffdf8 !important;
  color: var(--mv-ink) !important;
  -webkit-text-fill-color: var(--mv-ink) !important;
  border-color: rgba(30, 100, 107, 0.32) !important;
  box-shadow: inset 0 0 0 1px rgba(30, 100, 107, 0.12), 0 6px 14px rgba(39, 49, 45, 0.08) !important;
}

.workflow-view .editor-actions {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  box-shadow: none !important;
}

.workflow-view .glass-button,
.workflow-view .launch-button-primary,
.workflow-view .menu-trigger {
  min-height: 38px !important;
  border-radius: 12px !important;
}

.workflow-view .launch-button-primary {
  background: #183f45 !important;
  color: #fffaf2 !important;
  -webkit-text-fill-color: #fffaf2 !important;
}

.workflow-view .glass-button {
  background: #fffdf8 !important;
  color: var(--mv-ink) !important;
  -webkit-text-fill-color: var(--mv-ink) !important;
}

.workflow-view .yaml-editor {
  background: #fffdf8 !important;
}

.workflow-view .yaml-textarea {
  background: #fffdf8 !important;
  color: #172f34 !important;
  -webkit-text-fill-color: #172f34 !important;
}

.workflow-view--embedded {
  border: 0 !important;
}

.workflow-view .header--embedded {
  border-bottom: 0 !important;
  padding-bottom: 10px !important;
}

.workflow-view .tabs {
  border: 0 !important;
  background: transparent !important;
  padding-bottom: 12px !important;
}

.workflow-view .tab-buttons {
  border: 0 !important;
  background: #efe4d4 !important;
  box-shadow: inset 0 0 0 1px rgba(24, 42, 46, 0.08) !important;
}

.workflow-view .tab {
  border: 0 !important;
  box-shadow: none !important;
}

.workflow-view .tab.active {
  border: 0 !important;
  box-shadow: 0 5px 14px rgba(39, 49, 45, 0.1) !important;
}

.workflow-view .vueflow-container,
.workflow-view .yaml-editor {
  border: 0 !important;
  box-shadow: inset 0 0 0 1px rgba(24, 42, 46, 0.08) !important;
}

.workflow-view .yaml-textarea {
  border: 0 !important;
  box-shadow: none !important;
}

.workflow-view .glass-button,
.workflow-view .launch-button-primary,
.workflow-view .menu-trigger {
  border: 0 !important;
  box-shadow: inset 0 0 0 1px rgba(24, 42, 46, 0.11) !important;
}

.workflow-view .launch-button-primary {
  box-shadow: none !important;
}
</style>
