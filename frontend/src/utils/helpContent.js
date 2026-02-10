export const helpContent = {
  // Start Node Help
  startNode: {
    title: "Start Node",
    description: "The entry point for your workflow. All nodes connected to the Start node will run in parallel when the workflow launches.",
    examples: [
      "Connect multiple nodes to start them simultaneously",
      "The first nodes to execute receive your initial input"
    ],
    learnMoreUrl: "/tutorial#2-create-nodes"
  },

  // Workflow Node Types
  workflowNode: {
    agent: {
      title: "Agent Node",
      description: "An AI agent that can reason, generate content, and use tools. Agents receive messages and produce responses based on their configuration.",
      examples: [
        "Content generation (writing, coding, analysis)",
        "Decision making and routing",
        "Tool usage (search, file operations, API calls)"
      ],
      learnMoreUrl: "/tutorial#agent-node"
    },
    human: {
      title: "Human Node",
      description: "Pauses workflow execution and waits for human input. Use this to review content, make decisions, or provide feedback.",
      examples: [
        "Review and approve generated content",
        "Provide additional instructions or corrections",
        "Choose between workflow paths"
      ],
      learnMoreUrl: "/tutorial#human-node"
    },
    python: {
      title: "Python Node",
      description: "Executes Python code on your local environment. The code runs in the workspace directory and can access uploaded files.",
      examples: [
        "Data processing and analysis",
        "Running generated code",
        "File manipulation"
      ],
      learnMoreUrl: "/tutorial#python-node"
    },
    passthrough: {
      title: "Passthrough Node",
      description: "Passes messages to the next node without modification. Useful for workflow organization and filtering outputs in loops.",
      examples: [
        "Preserve initial context in loops",
        "Filter redundant outputs",
        "Organize workflow structure"
      ],
      learnMoreUrl: "/tutorial#passthrough-node"
    },
    literal: {
      title: "Literal Node",
      description: "Outputs fixed text, ignoring all input. Use this to inject instructions or context at specific points in the workflow.",
      examples: [
        "Add fixed instructions before a node",
        "Inject context or constraints",
        "Provide test data"
      ],
      learnMoreUrl: "/tutorial#literal-node"
    },
    loop_counter: {
      title: "Loop Counter Node",
      description: "Limits loop iterations. Only produces output when the maximum count is reached, helping control infinite loops.",
      examples: [
        "Prevent runaway loops",
        "Set maximum revision cycles",
        "Control iterative processes"
      ],
      learnMoreUrl: "/tutorial#loop-counter-node"
    },
    subgraph: {
      title: "Subgraph Node",
      description: "Embeds another workflow as a reusable module. Enables modular design and workflow composition.",
      examples: [
        "Reuse common patterns across workflows",
        "Break complex workflows into manageable pieces",
        "Share workflows between teams"
      ],
      learnMoreUrl: "/tutorial#subgraph-node"
    },
    unknown: {
      title: "Workflow Node",
      description: "A node in your workflow. Click to view and edit its configuration.",
      learnMoreUrl: "/tutorial#2-create-nodes"
    }
  },

  // Workflow Edge Help
  edge: {
    basic: {
      title: "Connection",
      description: "Connects two nodes to control information flow and execution order. The upstream node's output becomes the downstream node's input.",
      examples: [
        "Data flows from source to target",
        "Target executes after source completes"
      ],
      learnMoreUrl: "/tutorial#what-is-an-edge"
    },
    trigger: {
      enabled: {
        description: "This connection triggers the downstream node to execute.",
      },
      disabled: {
        description: "This connection passes data but does NOT trigger execution. The downstream node only runs if triggered by another edge.",
      }
    },
    condition: {
      hasCondition: {
        description: "This connection has a condition. It only activates when the condition evaluates to true.",
        learnMoreUrl: "/tutorial#edge-condition"
      }
    }
  },

  // Context Menu Actions
  contextMenu: {
    createNode: {
      description: "Create a new node in your workflow. Choose from Agent, Human, Python, and other node types.",
    },
    copyNode: {
      description: "Duplicate this node with all its settings. The copy will have a blank ID that you must fill in.",
    },
    deleteNode: {
      description: "Remove this node and all its connections from the workflow.",
    },
    deleteEdge: {
      description: "Remove this connection between nodes.",
    },
    createNodeButton: {
      description: "Open the node creation form. You can also right-click the canvas to create a node at a specific position.",
    },
    configureGraph: {
      description: "Configure workflow-level settings like name, description, and global variables.",
    },
    launch: {
      description: "Run your workflow with a task prompt. The workflow will execute and show you the results.",
    },
    createEdge: {
      description: "Create a connection between nodes. You can also drag from a node's handle to create connections visually.",
    },
    manageVariables: {
      description: "Define global variables (like API keys) that all nodes can access using ${VARIABLE_NAME} syntax.",
    },
    manageMemories: {
      description: "Configure memory modules for long-term information storage and retrieval across workflow runs.",
    },
    renameWorkflow: {
      description: "Change the name of this workflow file.",
    },
    copyWorkflow: {
      description: "Create a duplicate of this entire workflow with a new name.",
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

  // Add trigger information
  const trigger = edgeData?.trigger !== undefined ? edgeData.trigger : true
  if (!trigger) {
    base.description += " " + helpContent.edge.trigger.disabled.description
  }

  // Add condition information
  if (edgeData?.condition) {
    base.description += " " + helpContent.edge.condition.hasCondition.description
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
