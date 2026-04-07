const DEFAULT_MODEL_NAME = '${MODEL_NAME}'
const DEFAULT_BASE_URL = '${BASE_URL}'
const DEFAULT_API_KEY = '${API_KEY}'

const clone = (value) => {
  if (value == null) {
    return value
  }
  return JSON.parse(JSON.stringify(value))
}

const sanitizeWorkflowId = (workflowName) => {
  const raw = String(workflowName || 'agent_team_template')
    .replace(/\.(yaml|yml)$/i, '')
    .trim()
  const sanitized = raw.replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '')
  return sanitized || 'agent_team_template'
}

const buildAgentNode = (id, role, overrides = {}) => {
  const params = overrides.params || {}

  return {
    id,
    type: 'agent',
    config: {
      provider: 'openai',
      base_url: DEFAULT_BASE_URL,
      api_key: DEFAULT_API_KEY,
      name: DEFAULT_MODEL_NAME,
      role,
      params: {
        temperature: 0.2,
        max_tokens: 2200,
        ...params,
      },
      ...(overrides.config || {}),
    },
  }
}

const buildHumanNode = (id, description) => ({
  id,
  type: 'human',
  config: {
    description,
  },
})

const buildFunctionTooling = (toolNames, extraConfig = {}) => ([
  {
    type: 'function',
    config: {
      tools: toolNames.map((name) => ({ name })),
      timeout: null,
      ...extraConfig,
    },
    prefix: '',
  },
])

const buildMcpRemoteTooling = (server, prefix, extraConfig = {}) => ({
  type: 'mcp_remote',
  config: {
    server,
    timeout: 30,
    cache_ttl: 0,
    ...extraConfig,
  },
  prefix,
})

const buildSkillsConfig = (skillNames) => ({
  enabled: true,
  allow: skillNames.map((name) => ({ name })),
})

const buildEdge = (from, to, extra = {}) => ({
  from,
  to,
  ...extra,
})

const TEMPLATE_DEFINITIONS = [
  {
    id: 'planner_executor_reviewer',
    categoryKey: 'workflowView.templateCategories.core',
    titleKey: 'workflowView.templates.plannerExecutorReviewer.title',
    descriptionKey: 'workflowView.templates.plannerExecutorReviewer.description',
    buildGraph: () => ({
      description: 'Human-governed planner, executor, reviewer workflow.',
      initial_instruction: 'Describe the goal, constraints, and desired output. The team will plan, execute, and review the result.',
      start: ['Planner'],
      nodes: [
        buildAgentNode(
          'Planner',
          [
            'You are the planning lead for a human-governed agent team.',
            'Turn the user request into a compact execution plan with milestones, risks, and acceptance criteria.',
            'Keep the plan actionable and easy for a human to edit later.',
            'When possible, clearly separate facts, assumptions, and unknowns.',
          ].join('\n')
        ),
        buildAgentNode(
          'Executor',
          [
            'You are the execution lead for a human-governed agent team.',
            'Use the latest plan and available context to produce the best concrete result you can.',
            'If requirements are ambiguous, state the ambiguity instead of hiding it.',
            'Prefer structured output with sections for result, risks, and next steps.',
          ].join('\n'),
          {
            params: {
              temperature: 0.15,
              max_tokens: 2600,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for a human-governed agent team.',
            'Inspect the executor result against the user goal, constraints, and acceptance criteria.',
            'If the result is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Briefly explain what passed and any residual risk.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Executor',
            'Review Note: Explain what failed and what should be redone.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Planner', 'Executor'),
        buildEdge('Planner', 'Reviewer'),
        buildEdge('Executor', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'research_synthesis_review',
    categoryKey: 'workflowView.templateCategories.research',
    titleKey: 'workflowView.templates.researchSynthesisReview.title',
    descriptionKey: 'workflowView.templates.researchSynthesisReview.description',
    buildGraph: () => ({
      description: 'Research, synthesis, and review workflow for evidence-heavy tasks.',
      initial_instruction: 'Provide a question or objective that needs research, synthesis, and a final quality review.',
      start: ['Researcher'],
      nodes: [
        buildAgentNode(
          'Researcher',
          [
            'You are the research lead for a human-governed agent team.',
            'Collect the most relevant facts, sources, and open questions from the input you receive.',
            'Keep your output evidence-first and explicitly mark uncertain claims.',
          ].join('\n'),
          {
            params: {
              temperature: 0.1,
              max_tokens: 2200,
            },
          }
        ),
        buildAgentNode(
          'Synthesizer',
          [
            'You are the synthesis lead for a human-governed agent team.',
            'Turn the research material into a clear answer, brief, or proposal.',
            'Preserve nuance, cite uncertainty, and keep the structure easy for a human reviewer to inspect.',
          ].join('\n'),
          {
            params: {
              temperature: 0.2,
              max_tokens: 2400,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for a human-governed research team.',
            'Judge whether the synthesis is well-supported and aligned with the user request.',
            'If the answer is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Say what is strong and what remains uncertain.',
            '',
            'If more work is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Researcher',
            'Review Note: State which missing evidence or unsupported claim must be fixed.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Researcher', 'Synthesizer'),
        buildEdge('Researcher', 'Reviewer'),
        buildEdge('Synthesizer', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'human_approval_loop',
    categoryKey: 'workflowView.templateCategories.human',
    titleKey: 'workflowView.templates.humanApprovalLoop.title',
    descriptionKey: 'workflowView.templates.humanApprovalLoop.description',
    buildGraph: () => ({
      description: 'Human approval loop with planning, approval, execution, and review.',
      initial_instruction: 'Describe the outcome you want. The planner will propose a path, a human can approve or revise it, then execution and review continue.',
      start: ['Planner'],
      nodes: [
        buildAgentNode(
          'Planner',
          [
            'You are the planner in a human-governed agent team.',
            'Produce a concise plan, call out risks, and explain what needs human approval before execution.',
            'Keep the plan short enough for a human to review quickly.',
          ].join('\n')
        ),
        buildHumanNode(
          'Human Approval',
          [
            'Review the proposed plan.',
            '- Enter APPROVE to move into execution.',
            '- Otherwise, enter feedback or constraints and the planner will revise the plan.',
          ].join('\n')
        ),
        buildAgentNode(
          'Executor',
          [
            'You are the executor in a human-governed agent team.',
            'Follow the approved plan and human constraints as closely as possible.',
            'Produce a concrete result and highlight any tradeoffs that remain.',
          ].join('\n'),
          {
            params: {
              temperature: 0.15,
              max_tokens: 2400,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for a human-governed execution loop.',
            'If the result is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Say what passed.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Planner',
            'Review Note: Explain which plan or execution issues must be fixed.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Planner', 'Human Approval'),
        buildEdge('Human Approval', 'Executor', {
          condition: {
            type: 'keyword',
            config: {
              any: ['APPROVE', 'APPROVED', 'ACCEPT'],
              case_sensitive: false,
            },
          },
        }),
        buildEdge('Human Approval', 'Planner', {
          condition: {
            type: 'keyword',
            config: {
              none: ['APPROVE', 'APPROVED', 'ACCEPT'],
              case_sensitive: false,
            },
          },
        }),
        buildEdge('Executor', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'planner_research_writer_reviewer',
    categoryKey: 'workflowView.templateCategories.writing',
    titleKey: 'workflowView.templates.plannerResearchWriterReviewer.title',
    descriptionKey: 'workflowView.templates.plannerResearchWriterReviewer.description',
    buildGraph: () => ({
      description: 'Planning, research, writing, and review workflow for structured deliverables.',
      initial_instruction: 'Describe the deliverable you want. The team will plan the work, research the missing facts, write the draft, and review the result.',
      start: ['Planner'],
      nodes: [
        buildAgentNode(
          'Planner',
          [
            'You are the planner for a human-governed delivery team.',
            'Break the request into a practical writing plan with deliverable shape, evidence needs, and acceptance criteria.',
            'Keep the plan short and directly actionable.',
          ].join('\n')
        ),
        buildAgentNode(
          'Researcher',
          [
            'You are the researcher for a human-governed delivery team.',
            'Collect the facts, examples, and unresolved questions needed for the draft.',
            'Be explicit about what is confirmed versus assumed.',
          ].join('\n'),
          {
            params: {
              temperature: 0.1,
              max_tokens: 2200,
            },
          }
        ),
        buildAgentNode(
          'Writer',
          [
            'You are the writer for a human-governed delivery team.',
            'Turn the plan and research into a clean, useful draft.',
            'Favor structure, clarity, and practical usefulness over filler.',
          ].join('\n'),
          {
            params: {
              temperature: 0.25,
              max_tokens: 2600,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for a human-governed delivery team.',
            'Check whether the draft is complete, accurate enough, and aligned with the requested outcome.',
            'If the result is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Briefly say what is ready.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Writer',
            'Review Note: Explain what content, structure, or evidence is missing.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Planner', 'Researcher'),
        buildEdge('Planner', 'Writer'),
        buildEdge('Researcher', 'Writer'),
        buildEdge('Researcher', 'Reviewer'),
        buildEdge('Writer', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'debate_and_judge',
    categoryKey: 'workflowView.templateCategories.decision',
    titleKey: 'workflowView.templates.debateAndJudge.title',
    descriptionKey: 'workflowView.templates.debateAndJudge.description',
    tags: ['decision', 'review', 'judge'],
    buildGraph: () => ({
      description: 'Two perspectives debate and a judge decides whether another round is needed.',
      initial_instruction: 'Provide a question, decision, or tradeoff. The team will generate two perspectives and let a judge decide the stronger position.',
      start: ['Planner'],
      nodes: [
        buildAgentNode(
          'Planner',
          [
            'You are the debate planner.',
            'Frame the user problem as a decision or tradeoff, then specify what each side should argue.',
            'Keep the framing balanced and concrete.',
          ].join('\n')
        ),
        buildAgentNode(
          'Perspective A',
          [
            'You are one side of a structured debate.',
            'Argue for the strongest case in favor of the first option or perspective.',
            'Be rigorous, practical, and concise.',
          ].join('\n'),
          {
            params: {
              temperature: 0.3,
              max_tokens: 1800,
            },
          }
        ),
        buildAgentNode(
          'Perspective B',
          [
            'You are the opposing side of a structured debate.',
            'Argue for the strongest case in favor of the second option or perspective.',
            'Challenge weak assumptions and surface tradeoffs clearly.',
          ].join('\n'),
          {
            params: {
              temperature: 0.3,
              max_tokens: 1800,
            },
          }
        ),
        buildAgentNode(
          'Judge',
          [
            'You are the final judge of a human-governed debate workflow.',
            'Compare both perspectives and produce the clearest recommendation you can.',
            'If one side clearly wins, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Explain which side is stronger and why.',
            '',
            'If both sides are still weak or incomplete, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Planner',
            'Review Note: Explain what framing or evidence needs another debate round.',
          ].join('\n'),
          {
            params: {
              temperature: 0.08,
              max_tokens: 1400,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Planner', 'Perspective A'),
        buildEdge('Planner', 'Perspective B'),
        buildEdge('Perspective A', 'Judge'),
        buildEdge('Perspective B', 'Judge'),
      ],
    }),
  },
  {
    id: 'browser_research_mcp_team',
    categoryKey: 'workflowView.templateCategories.mcp',
    titleKey: 'workflowView.templates.browserResearchMcpTeam.title',
    descriptionKey: 'workflowView.templates.browserResearchMcpTeam.description',
    tags: ['mcp', 'fetch', 'browser', 'research'],
    buildGraph: () => ({
      description: 'Research workflow with browser-style MCP presets and built-in web skills.',
      initial_instruction: 'Describe a topic, company, product, or question that needs browser-style web research and a reviewed summary.',
      start: ['Research Planner'],
      nodes: [
        buildAgentNode(
          'Research Planner',
          [
            'You are the planning lead for browser-assisted research.',
            'Break the task into search goals, target evidence, and a clean deliverable shape.',
            'Call out what the browser researcher must verify versus what can remain open.',
          ].join('\n')
        ),
        buildAgentNode(
          'Browser Researcher',
          [
            'You are the browser-first researcher.',
            'Use available MCP browser/fetch tools first when they are online; otherwise fall back to built-in web tools.',
            'Return a compact evidence brief with facts, source shortlist, and unresolved questions.',
          ].join('\n'),
          {
            config: {
              tooling: [
                ...buildFunctionTooling(['web_search', 'read_webpage_content']),
                buildMcpRemoteTooling('http://127.0.0.1:3001/mcp', 'fetch'),
                buildMcpRemoteTooling('http://127.0.0.1:3002/mcp', 'browser'),
              ],
              skills: buildSkillsConfig(['browser-researcher']),
            },
            params: {
              temperature: 0.1,
              max_tokens: 2400,
            },
          }
        ),
        buildAgentNode(
          'Research Writer',
          [
            'You are the writer for a browser-assisted research team.',
            'Turn the evidence brief into a clear answer or report draft without overstating certainty.',
          ].join('\n'),
          {
            config: {
              skills: buildSkillsConfig(['content-packager']),
            },
            params: {
              temperature: 0.2,
              max_tokens: 2400,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for browser-assisted research.',
            'If the result is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Say what is strong and what remains uncertain.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Browser Researcher',
            'Review Note: Explain which evidence or source coverage is still missing.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Research Planner', 'Browser Researcher'),
        buildEdge('Research Planner', 'Research Writer'),
        buildEdge('Browser Researcher', 'Research Writer'),
        buildEdge('Browser Researcher', 'Reviewer'),
        buildEdge('Research Writer', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'repo_analyst_mcp_team',
    categoryKey: 'workflowView.templateCategories.mcp',
    titleKey: 'workflowView.templates.repoAnalystMcpTeam.title',
    descriptionKey: 'workflowView.templates.repoAnalystMcpTeam.description',
    tags: ['mcp', 'filesystem', 'git', 'github', 'repo'],
    buildGraph: () => ({
      description: 'Repository analysis workflow with MCP presets for filesystem, git, and GitHub-style tooling.',
      initial_instruction: 'Describe the repository question, bug, or feature area you want the team to inspect.',
      start: ['Planner'],
      nodes: [
        buildAgentNode(
          'Planner',
          [
            'You are the planning lead for repository analysis.',
            'Clarify the goal, likely modules, and what evidence is needed before code changes are proposed.',
          ].join('\n')
        ),
        buildAgentNode(
          'Repo Analyst',
          [
            'You are the repository analyst.',
            'Use filesystem, git, and GitHub-style tools when available; otherwise inspect the repo with built-in file tools.',
            'Produce a precise architecture brief with edit targets and risk notes.',
          ].join('\n'),
          {
            config: {
              tooling: [
                ...buildFunctionTooling([
                  'describe_available_files',
                  'list_directory',
                  'read_file_segment',
                  'search_in_files',
                ]),
                buildMcpRemoteTooling('http://127.0.0.1:3101/mcp', 'filesystem'),
                buildMcpRemoteTooling('http://127.0.0.1:3102/mcp', 'git'),
                buildMcpRemoteTooling('http://127.0.0.1:3103/mcp', 'github'),
              ],
              skills: buildSkillsConfig(['repo-analyst']),
            },
            params: {
              temperature: 0.1,
              max_tokens: 2600,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for repository analysis.',
            'If the architecture brief is sufficient, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Say which files and risks are now clear.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Repo Analyst',
            'Review Note: Explain what code path, dependency, or evidence is still unclear.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Planner', 'Repo Analyst'),
        buildEdge('Planner', 'Reviewer'),
        buildEdge('Repo Analyst', 'Reviewer'),
      ],
    }),
  },
  {
    id: 'skill_powered_research_writer',
    categoryKey: 'workflowView.templateCategories.skills',
    titleKey: 'workflowView.templates.skillPoweredResearchWriter.title',
    descriptionKey: 'workflowView.templates.skillPoweredResearchWriter.description',
    tags: ['skills', 'research', 'report', 'content'],
    buildGraph: () => ({
      description: 'Skill-first team using built-in function tools for research, report orchestration, and final packaging.',
      initial_instruction: 'Describe the topic or deliverable. The team will research it, structure it into a report, then package the final answer.',
      start: ['Research Lead'],
      nodes: [
        buildAgentNode(
          'Research Lead',
          [
            'You are the research lead for a skill-first team.',
            'Use available skills and function tools to gather facts, open questions, and a clean report outline.',
          ].join('\n'),
          {
            config: {
              tooling: [
                ...buildFunctionTooling([
                  'web_search',
                  'read_webpage_content',
                  'report_outline',
                  'report_create_chapter',
                  'report_continue_chapter',
                  'report_rewrite_chapter',
                ]),
              ],
              skills: buildSkillsConfig(['browser-researcher', 'report-orchestrator']),
            },
            params: {
              temperature: 0.15,
              max_tokens: 2600,
            },
          }
        ),
        buildAgentNode(
          'Content Packager',
          [
            'You are the final packager for a skill-first content team.',
            'Turn the latest research/report material into a polished deliverable that is easy for a human to review.',
          ].join('\n'),
          {
            config: {
              skills: buildSkillsConfig(['content-packager']),
            },
            params: {
              temperature: 0.25,
              max_tokens: 2400,
            },
          }
        ),
        buildAgentNode(
          'Reviewer',
          [
            'You are the reviewer for a skill-powered research-and-writing workflow.',
            'If the deliverable is acceptable, respond exactly in this format:',
            'Review Decision: APPROVED',
            'Replay Target:',
            'Review Note: Say what is ready.',
            '',
            'If rework is needed, respond exactly in this format:',
            'Review Decision: REWORK',
            'Replay Target: Research Lead',
            'Review Note: Explain what evidence, report structure, or packaging still needs work.',
          ].join('\n'),
          {
            params: {
              temperature: 0.05,
              max_tokens: 1200,
            },
          }
        ),
      ],
      edges: [
        buildEdge('Research Lead', 'Content Packager'),
        buildEdge('Research Lead', 'Reviewer'),
        buildEdge('Content Packager', 'Reviewer'),
      ],
    }),
  },
]

export const workflowTemplates = TEMPLATE_DEFINITIONS

export const buildWorkflowTemplate = (templateId, context = {}) => {
  const template = TEMPLATE_DEFINITIONS.find((item) => item.id === templateId)
  if (!template) {
    return null
  }

  const source = context.currentSnapshot && typeof context.currentSnapshot === 'object'
    ? context.currentSnapshot
    : {}
  const sourceGraph = source.graph && typeof source.graph === 'object'
    ? source.graph
    : {}
  const graph = template.buildGraph(context)

  const nextGraph = {
    id: sourceGraph.id || sanitizeWorkflowId(context.workflowName),
    description: graph.description,
    log_level: sourceGraph.log_level || 'INFO',
    is_majority_voting: false,
    initial_instruction: graph.initial_instruction,
    organization: sourceGraph.organization || '',
    team_mode: sourceGraph.team_mode || 'human_governed',
    start: clone(graph.start) || [],
    nodes: clone(graph.nodes) || [],
    edges: clone(graph.edges) || [],
  }

  if (sourceGraph.memory) {
    nextGraph.memory = clone(sourceGraph.memory)
  }

  return {
    version: source.version || '0.4.0',
    vars: clone(source.vars || {}),
    graph: nextGraph,
  }
}
