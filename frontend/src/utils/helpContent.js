export const helpContent = {
  startNode: {
    title: "开始节点",
    description: "这是工作流的入口。所有连接到开始节点的下游节点，会在流程启动时并行进入可执行状态。",
    examples: [
      "把多个节点连到开始节点上，就能并行起跑",
      "第一批执行节点会收到你的初始输入"
    ],
    learnMoreUrl: "/tutorial#2-create-nodes"
  },

  workflowNode: {
    agent: {
      title: "Agent 节点",
      description: "用于放置一个可推理、可生成、可调工具的 AI Agent。它会接收消息，并按自身配置产出结果。",
      examples: [
        "写作、编码、分析等内容生成",
        "分流判断和路径决策",
        "搜索、文件处理、API 调用等工具使用"
      ],
      learnMoreUrl: "/tutorial#agent-node"
    },
    human: {
      title: "人工节点",
      description: "在这里暂停工作流并等待人工输入，适合做审核、补充说明、纠偏和关键决策。",
      examples: [
        "审核并批准生成结果",
        "补充额外要求或修正方向",
        "在多条路径之间做选择"
      ],
      learnMoreUrl: "/tutorial#human-node"
    },
    python: {
      title: "Python 节点",
      description: "在本地环境中执行 Python 代码。代码会运行在当前工作区，并可读取已上传文件。",
      examples: [
        "数据处理与分析",
        "执行生成出的代码",
        "文件读写与转换"
      ],
      learnMoreUrl: "/tutorial#python-node"
    },
    passthrough: {
      title: "透传节点",
      description: "不修改消息内容，直接把输入传给下一个节点，适合做流程整理、上下文保留或循环链路中的结果筛选。",
      examples: [
        "在循环中保留初始上下文",
        "过滤多余输出",
        "整理工作流结构"
      ],
      learnMoreUrl: "/tutorial#passthrough-node"
    },
    literal: {
      title: "字面量节点",
      description: "忽略上游输入，直接输出一段固定文本。适合在流程的特定位置插入规则、说明或上下文。",
      examples: [
        "在某个节点前插入固定指令",
        "注入额外约束或背景",
        "提供测试数据"
      ],
      learnMoreUrl: "/tutorial#literal-node"
    },
    loop_counter: {
      title: "循环计数节点",
      description: "限制循环次数。只有达到最大次数时才会产出结果，用来防止流程无限循环。",
      examples: [
        "防止流程失控循环",
        "设置最大修订轮次",
        "控制迭代过程"
      ],
      learnMoreUrl: "/tutorial#loop-counter-node"
    },
    subgraph: {
      title: "子图节点",
      description: "把另一个工作流嵌入为可复用模块，适合做模块化设计和复杂流程复合编排。",
      examples: [
        "在多个工作流里复用通用模式",
        "把复杂流程拆成可管理的片段",
        "跨团队共享流程能力"
      ],
      learnMoreUrl: "/tutorial#subgraph-node"
    },
    unknown: {
      title: "工作流节点",
      description: "这是工作流中的一个节点。点击后可以查看并编辑它的配置。",
      learnMoreUrl: "/tutorial#2-create-nodes"
    }
  },

  edge: {
    basic: {
      title: "连线",
      description: "用于连接两个节点，决定信息流向和执行顺序。上游节点的输出会成为下游节点的输入。",
      examples: [
        "数据会从源节点流向目标节点",
        "目标节点会在源节点完成后触发"
      ],
      learnMoreUrl: "/tutorial#what-is-an-edge"
    },
    trigger: {
      enabled: {
        description: "这条连线会触发下游节点执行。",
      },
      disabled: {
        description: "这条连线会传递数据，但不会触发执行。下游节点只有被其他连线触发时才会运行。",
      }
    },
    condition: {
      hasCondition: {
        description: "这条连线带有条件，只有条件计算为真时才会生效。",
        learnMoreUrl: "/tutorial#edge-condition"
      }
    }
  },

  contextMenu: {
    createNode: {
      description: "在当前工作流中新增一个节点。你可以从 Agent、人工、Python 等类型里选择。",
    },
    copyNode: {
      description: "复制当前节点及其配置。副本会保留内容，但需要你填写新的节点 ID。",
    },
    deleteNode: {
      description: "从工作流中删除当前节点及其所有相关连线。",
    },
    deleteEdge: {
      description: "删除这条节点之间的连接关系。",
    },
    createNodeButton: {
      description: "打开新建节点表单。你也可以在画布上右键，在指定位置直接创建节点。",
    },
    configureGraph: {
      description: "配置工作流级别设置，比如名称、描述和全局变量。",
    },
    launch: {
      description: "带着任务提示运行当前工作流，并在运行台里查看执行结果。",
    },
    createEdge: {
      description: "创建节点之间的连线。你也可以直接拖拽节点句柄来可视化建边。",
    },
    manageVariables: {
      description: "定义全局变量，例如 API Key，所有节点都可以通过 ${VARIABLE_NAME} 方式访问。",
    },
    manageMemories: {
      description: "配置记忆模块，用于跨多次运行存储和检索长期信息。",
    },
    renameWorkflow: {
      description: "修改当前工作流文件名称。",
    },
    copyWorkflow: {
      description: "以新名字复制出一份完整的工作流副本。",
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

  if (!content || typeof content !== 'object') {
    return content || null
  }

  const normalized = { ...content }
  if (typeof normalized.learnMoreUrl === 'string' && normalized.learnMoreUrl.startsWith('/tutorial')) {
    delete normalized.learnMoreUrl
  }

  return normalized
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

  if (typeof base.learnMoreUrl === 'string' && base.learnMoreUrl.startsWith('/tutorial')) {
    delete base.learnMoreUrl
  }

  return base
}

export default {
  helpContent,
  getHelpContent,
  getNodeHelp,
  getEdgeHelp
}
