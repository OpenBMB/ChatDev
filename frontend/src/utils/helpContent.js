export const helpContent = {
  // Start Node Help
  startNode: {
    title: "help.startNode.title",
    description: "help.startNode.description",
    examples: [
      "help.startNode.examples.0",
      "help.startNode.examples.1"
    ],
    learnMoreUrl: "/tutorial#2-create-nodes"
  },

  // Workflow Node Types
  workflowNode: {
    agent: {
      title: "help.workflowNode.agent.title",
      description: "help.workflowNode.agent.description",
      examples: [
        "help.workflowNode.agent.examples.0",
        "help.workflowNode.agent.examples.1",
        "help.workflowNode.agent.examples.2"
      ],
      learnMoreUrl: "/tutorial#agent-node"
    },
    human: {
      title: "help.workflowNode.human.title",
      description: "help.workflowNode.human.description",
      examples: [
        "help.workflowNode.human.examples.0",
        "help.workflowNode.human.examples.1",
        "help.workflowNode.human.examples.2"
      ],
      learnMoreUrl: "/tutorial#human-node"
    },
    python: {
      title: "help.workflowNode.python.title",
      description: "help.workflowNode.python.description",
      examples: [
        "help.workflowNode.python.examples.0",
        "help.workflowNode.python.examples.1",
        "help.workflowNode.python.examples.2"
      ],
      learnMoreUrl: "/tutorial#python-node"
    },
    passthrough: {
      title: "help.workflowNode.passthrough.title",
      description: "help.workflowNode.passthrough.description",
      examples: [
        "help.workflowNode.passthrough.examples.0",
        "help.workflowNode.passthrough.examples.1",
        "help.workflowNode.passthrough.examples.2"
      ],
      learnMoreUrl: "/tutorial#passthrough-node"
    },
    literal: {
      title: "help.workflowNode.literal.title",
      description: "help.workflowNode.literal.description",
      examples: [
        "help.workflowNode.literal.examples.0",
        "help.workflowNode.literal.examples.1",
        "help.workflowNode.literal.examples.2"
      ],
      learnMoreUrl: "/tutorial#literal-node"
    },
    loop_counter: {
      title: "help.workflowNode.loop_counter.title",
      description: "help.workflowNode.loop_counter.description",
      examples: [
        "help.workflowNode.loop_counter.examples.0",
        "help.workflowNode.loop_counter.examples.1",
        "help.workflowNode.loop_counter.examples.2"
      ],
      learnMoreUrl: "/tutorial#loop-counter-node"
    },
    subgraph: {
      title: "help.workflowNode.subgraph.title",
      description: "help.workflowNode.subgraph.description",
      examples: [
        "help.workflowNode.subgraph.examples.0",
        "help.workflowNode.subgraph.examples.1",
        "help.workflowNode.subgraph.examples.2"
      ],
      learnMoreUrl: "/tutorial#subgraph-node"
    },
    unknown: {
      title: "help.workflowNode.unknown.title",
      description: "help.workflowNode.unknown.description",
      learnMoreUrl: "/tutorial#2-create-nodes"
    }
  },

  // Workflow Edge Help
  edge: {
    basic: {
      title: "help.edge.basic.title",
      description: "help.edge.basic.description",
      examples: [
        "help.edge.basic.examples.0",
        "help.edge.basic.examples.1"
      ],
      learnMoreUrl: "/tutorial#what-is-an-edge"
    },
    trigger: {
      enabled: {
        description: "help.edge.trigger.enabled.description",
      },
      disabled: {
        description: "help.edge.trigger.disabled.description",
      }
    },
    condition: {
      hasCondition: {
        description: "help.edge.condition.hasCondition.description",
        learnMoreUrl: "/tutorial#edge-condition"
      }
    }
  },

  // Context Menu Actions
  contextMenu: {
    createNode: {
      description: "help.contextMenu.createNode.description",
    },
    copyNode: {
      description: "help.contextMenu.copyNode.description",
    },
    deleteNode: {
      description: "help.contextMenu.deleteNode.description",
    },
    deleteEdge: {
      description: "help.contextMenu.deleteEdge.description",
    },
    createNodeButton: {
      description: "help.contextMenu.createNodeButton.description",
    },
    configureGraph: {
      description: "help.contextMenu.configureGraph.description",
    },
    launch: {
      description: "help.contextMenu.launch.description",
    },
    createEdge: {
      description: "help.contextMenu.createEdge.description",
    },
    manageVariables: {
      description: "help.contextMenu.manageVariables.description",
    },
    manageMemories: {
      description: "help.contextMenu.manageMemories.description",
    },
    renameWorkflow: {
      description: "help.contextMenu.renameWorkflow.description",
    },
    copyWorkflow: {
      description: "help.contextMenu.copyWorkflow.description",
    }
  }
}

/**
 * Get help content by key path
 * @param {string} key - Dot-separated path to content (e.g., 'workflowNode.agent')
 * @returns {Object|null} Help content object or null if not found
 */
export function getHelpContent(key) {
  const keys = key.split('.')
  let content = helpContent

  for (const k of keys) {
    if (content && typeof content === 'object' && k in content) {
      content = content[k]
    } else {
      // Return null for missing content instead of fallback
      return null
    }
  }

  // Ensure we return an object with at least a description
  if (typeof content === 'string') {
    return { description: content }
  }

  return content || null
}

/**
 * Get node-specific help content based on node type
 * @param {string} nodeType - The type of node (agent, human, python, etc.)
 * @returns {Object|null} Help content for that node type, or null for unknown types
 */
export function getNodeHelp(nodeType) {
  if (!nodeType) {
    return null
  }
  
  const type = nodeType.toLowerCase()
  const content = getHelpContent(`workflowNode.${type}`)
  
  // Return null for unknown types (when content lookup fails)
  // This prevents showing tooltips for custom/user-defined node types
  return content
}

/**
 * Get edge help content based on edge properties
 * @param {Object} edgeData - The edge data object
 * @returns {Object} Combined help content for the edge
 */
export function getEdgeHelp(edgeData) {
  const base = { ...helpContent.edge.basic }
  base.descriptions = [base.description] // Change to array to support multiple parts

  // Add trigger information
  const trigger = edgeData?.trigger !== undefined ? edgeData.trigger : true
  if (!trigger) {
    base.descriptions.push(helpContent.edge.trigger.disabled.description)
  }

  // Add condition information
  if (edgeData?.condition) {
    base.descriptions.push(helpContent.edge.condition.hasCondition.description)
    if (!base.learnMoreUrl) {
      base.learnMoreUrl = helpContent.edge.condition.hasCondition.learnMoreUrl
    }
  }

  return base
}

export default {
  helpContent,
  getHelpContent,
  getNodeHelp,
  getEdgeHelp
}
