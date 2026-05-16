# ChatDev Workflow Graph 执行流程详解

本文档详细说明从 `workflow/graph.py` 开始的完整调用流程。

## 1. 整体架构概述

```
GraphExecutor (graph.py)
    ├── RuntimeBuilder.build() → RuntimeContext
    ├── GraphManager.build_graph()
    │       ├── _instantiate_nodes()
    │       ├── _initiate_edges()
    │       ├── _determine_start_nodes()
    │       ├── _warn_on_untriggerable_nodes()
    │       └── _build_topology_and_metadata()
    │
    ├── 执行策略选择 (基于图类型)
    │       ├── DAG → DagExecutionStrategy → DAGExecutor
    │       ├── Cycle → CycleExecutionStrategy → CycleExecutor
    │       └── MajorityVoting → MajorityVoteStrategy
    │
    └── _execute_node() → _process_result() → NodeExecutor.execute()
```

## 2. 入口点详解

### 2.1 便捷入口: `GraphExecutor.execute_graph()`

**文件**: [graph.py](file:///d:/Project/Git/ChatDev/workflow/graph.py#L111-L116)

```python
@classmethod
def execute_graph(
    cls,
    graph: GraphContext,
    task_prompt: Any,
    *,
    cancel_event: Optional[threading.Event] = None,
) -> "GraphExecutor":
    """Convenience method to execute a graph with a task prompt."""
    executor = cls(graph, cancel_event=cancel_event)
    executor._execute(task_prompt)
    return executor
```

这是最常用的入口方法，接收一个 `GraphContext` 和任务提示。

### 2.2 主要执行方法: `GraphExecutor.run()`

**文件**: [graph.py](file:///d:/Project/Git/ChatDev/workflow/graph.py#L217-L306)

```python
def run(self, task_prompt: Any) -> Dict[str, Any]:
    """Execute the graph based on topological layers structure or cycle-aware execution."""
    # 1. 构建图结构
    graph_manager = GraphManager(self.graph)
    graph_manager.build_graph()
    
    # 2. 准备边条件
    self._prepare_edge_conditions()
    
    # 3. 初始化 Memory 和 Thinking
    self._build_memories_and_thinking()
    
    # 4. 初始化周期管理器 (如果有循环)
    if self.graph.has_cycles:
        self.cycle_manager = graph_manager.get_cycle_manager()
    
    # 5. 标准化任务输入
    self.initial_task_messages = [msg.clone() for msg in self._normalize_task_input(task_prompt)]
    
    # 6. 初始化开始节点
    start_node_ids = set(self.graph.start_nodes)
    for node_id, node in self.graph.nodes.items():
        node.reset_triggers()
        if node_id in start_node_ids:
            node.start_triggered = True
            node.clear_input()
            for message in self.initial_task_messages:
                node.append_input(message.clone())
    
    # 7. 根据图类型选择执行策略
    if self.graph.is_majority_voting:
        strategy = MajorityVoteStrategy(...)
        self.majority_result = strategy.run()
    elif self.graph.has_cycles:
        strategy = CycleExecutionStrategy(...)
        strategy.run()
    else:
        strategy = DagExecutionStrategy(...)
        strategy.run()
    
    # 8. 收集输出并保存 Memory
    self._collect_all_outputs()
    self._save_memories()
    
    # 9. 导出运行时产物
    archiver = ResultArchiver(self.graph, self.log_manager, self.token_tracker)
    archiver.export(final_result)
    
    return self.outputs
```

## 3. 运行时构建 (RuntimeBuilder)

**文件**: [runtime_builder.py](file:///d:/Project/Git/ChatDev/workflow/runtime/runtime_builder.py#L1-L58)

### 3.1 `RuntimeBuilder.build()`

```python
def build(self, logger=None, *, session_id=None) -> RuntimeContext:
    # 1. 创建 ToolManager
    tool_manager = ToolManager()
    
    # 2. 获取 FunctionManager (边条件函数目录)
    function_manager = get_function_manager(EDGE_FUNCTION_DIR)
    
    # 3. 创建 LogManager 和 TokenTracker
    logger = logger or WorkflowLogger(...)
    log_manager = LogManager(logger)
    token_tracker = TokenTracker(workflow_id=self.graph.name)
    
    # 4. 创建工作空间和附件存储
    code_workspace = (self.graph.directory / "code_workspace").resolve()
    attachment_store = AttachmentStore(attachments_dir)
    
    # 5. 构建全局状态
    global_state = {
        "graph_directory": self.graph.directory,
        "vars": self.graph.config.vars,
        "python_workspace_root": code_workspace,
        "attachment_store": attachment_store,
    }
    
    # 6. 返回 RuntimeContext
    return RuntimeContext(
        tool_manager=tool_manager,
        function_manager=function_manager,
        edge_processor_function_manager=processor_function_manager,
        logger=logger,
        log_manager=log_manager,
        token_tracker=token_tracker,
        attachment_store=attachment_store,
        code_workspace=code_workspace,
        global_state=global_state,
    )
```

## 4. 图构建 (GraphManager)

**文件**: [graph_manager.py](file:///d:/Project/Git/ChatDev/workflow/graph_manager.py#L1-L300)

### 4.1 `GraphManager.build_graph()` → `build_graph_structure()`

```python
def build_graph_structure(self) -> None:
    """Build the complete graph structure including nodes, edges, and layers."""
    self._instantiate_nodes()           # 从配置实例化节点
    self._initiate_edges()              # 初始化边 (构建层或循环执行顺序)
    self._determine_start_nodes()       # 确定开始节点
    self._warn_on_untriggerable_nodes() # 警告无法触发的节点
    self._build_topology_and_metadata() # 构建拓扑和元数据
```

### 4.2 节点实例化: `_instantiate_nodes()`

**文件**: [graph_manager.py:L40-L60**

```python
def _instantiate_nodes(self) -> None:
    for node_def in self.graph.config.get_node_definitions():
        node_id = node_def.id
        # 深拷贝节点定义
        node_instance = copy.deepcopy(node_def)
        node_instance.predecessors = []
        node_instance.successors = []
        node_instance._outgoing_edges = []
        node_instance.vars = dict(self.graph.vars)
        
        self.graph.nodes[node_id] = node_instance
        
        # 如果是子图节点，构建子图
        if node_instance.node_type == "subgraph":
            self._build_subgraph(node_id)
```

### 4.3 边初始化: `_initiate_edges()`

**文件**: [graph_manager.py:L70-L140]**

```python
def _initiate_edges(self) -> None:
    # 多数投票模式：无边，所有节点独立并行
    if self.graph.is_majority_voting:
        self.graph.layers = [all_node_ids]
        return
    
    # 遍历边配置，创建边链接
    for edge_config in self.graph.config.get_edge_definitions():
        src, dst = edge_config.source, edge_config.target
        
        # 构建边payload
        payload = {
            "trigger": edge_config.trigger,
            "condition": condition_value,
            "condition_config": condition_config,
            "carry_data": edge_config.carry_data,
            "keep_message": edge_config.keep_message,
            "process_config": process_config,
            "dynamic_config": dynamic_config,  # 动态配置
            ...
        }
        
        # 添加前驱和后继
        self.graph.nodes[src].add_successor(self.graph.nodes[dst], payload)
        self.graph.nodes[dst].add_predecessor(self.graph.nodes[src])
    
    # 检测循环
    cycles = self._detect_cycles()
    self.graph.has_cycles = len(cycles) > 0
    
    if self.graph.has_cycles:
        self.graph.layers = self._build_cycle_execution_order(cycles)
    else:
        self.graph.layers = self._build_dag_layers()
```

### 4.4 DAG 层构建: `_build_dag_layers()`

**文件**: [graph_manager.py:L160-L175]**

```python
def _build_dag_layers(self) -> List[List[str]]:
    layers_with_items = GraphTopologyBuilder.build_dag_layers(self.graph.nodes)
    
    # 转换为 [[node_id, ...], [node_id, ...], ...]
    layers = [
        [item["node_id"] for item in layer]
        for layer in layers_with_items
    ]
    
    return layers
```

## 5. 执行策略详解

### 5.1 DAG 执行: `DagExecutionStrategy`

**文件**: [execution_strategy.py](file:///d:/Project/Git/ChatDev/workflow/runtime/execution_strategy.py#L1-L35) + [dag_executor.py](file:///d:/Project/Git/ChatDev/workflow/executor/dag_executor.py#L1-L55)

```
DagExecutionStrategy.run()
    └── DAGExecutor.execute()
            └── for layer in layers:
                    └── _execute_layer(layer)
                            └── ParallelExecutor.execute_nodes_parallel(layer_nodes, execute_if_triggered)
                                    └── ThreadPoolExecutor (并行执行)
```

**DAGExecutor.execute():**

```python
def execute(self) -> None:
    for layer_idx, layer_nodes in enumerate(self.layers):
        self.log_manager.debug(f"Executing Layer {layer_idx} with nodes: {layer_nodes}")
        self._execute_layer(layer_nodes)

def _execute_layer(self, layer_nodes: List[str]) -> None:
    def execute_if_triggered(node_id: str) -> None:
        node = self.nodes[node_id]
        if node.is_triggered():
            self.execute_node_func(node)  # 调用 GraphExecutor._execute_node
        else:
            self.log_manager.debug(f"Node {node_id} skipped - not triggered")
    
    self.parallel_executor.execute_nodes_parallel(layer_nodes, execute_if_triggered)
```

### 5.2 循环执行: `CycleExecutionStrategy`

**文件**: [execution_strategy.py](file:///d:/Project/Git/ChatDev/workflow/runtime/execution_strategy.py#L37-L64) + [cycle_executor.py](file:///d:/Project/Git/ChatDev/workflow/executor/cycle_executor.py#L1-L300)

```
CycleExecutionStrategy.run()
    └── CycleExecutor.execute()
            └── for layer_items in cycle_execution_order:
                    └── _execute_super_layer(layer_items)
                            └── _execute_super_layer_parallel(layer_items)
                                    └── ParallelExecutor.execute_items_parallel(...)
                                            └── for item in layer_items:
                                                    └── _execute_super_item(item)
                                                            ├── type == "node" → _execute_single_node()
                                                            └── type == "cycle" → _execute_cycle()
```

**CycleExecutor._execute_cycle():**

```python
def _execute_cycle(self, cycle_info: Dict[str, Any]) -> None:
    cycle_id = cycle_info["cycle_id"]
    nodes = cycle_info["nodes"]
    
    # 验证循环入口唯一性
    initial_node_id = self._validate_cycle_entry(cycle_id, nodes)
    
    # 激活循环
    self.cycle_manager.activate_cycle(cycle_id)
    
    # 多轮迭代执行
    self._execute_cycle_with_iterations(
        cycle_id,
        nodes,
        initial_node_id,
        max_iterations=self.cycle_manager.cycles[cycle_id].get_max_iterations()
    )
    
    # 停用循环
    self.cycle_manager.deactivate_cycle(cycle_id)
```

### 5.3 多数投票执行: `MajorityVoteStrategy`

**文件**: [execution_strategy.py](file:///d:/Project/Git/ChatDev/workflow/runtime/execution_strategy.py#L66-L149)

```
MajorityVoteStrategy.run()
    ├── 初始化所有节点输入
    ├── ParallelExecutor.execute_nodes_parallel(node_ids, _execute)
    │       └── 所有节点并行执行
    └── _collect_majority_result()
            └── 统计输出，返回多数结果
```

## 6. 节点执行详解

### 6.1 单节点执行入口: `_execute_node()`

**文件**: [graph.py:L530-L630]

```python
def _execute_node(self, node: Node) -> None:
    self._raise_if_cancelled()
    
    with self.resource_manager.guard_node(node):
        # 1. 获取输入
        input_results = node.input
        node.reset_triggers()  # 清除触发状态
        
        # 2. 记录开始
        self.log_manager.record_node_start(node.id, ...)
        
        # 3. 检查动态配置
        dynamic_config = self._get_dynamic_config_for_node(node)
        
        # 4. 执行节点
        with self.log_manager.node_timer(node.id):
            if dynamic_config is not None:
                raw_outputs = self._execute_with_dynamic_config(node, input_results, dynamic_config)
            else:
                raw_outputs = self._process_result(node, input_results)
        
        # 5. 处理输出消息
        output_messages: List[Message] = []
        for raw_output in raw_outputs:
            msg = self._ensure_source_output(raw_output, node.id)
            node.append_output(msg)
            output_messages.append(msg)
        
        # 6. 上下文追踪恢复
        if output_messages and node.context_window != 0:
            context_restored = self._restore_context_trace(node, context_trace_payload)
        
        # 7. 清理输入上下文
        if node.context_window != -1:
            node.clear_input(preserve_kept=True, context_window=node.context_window)
        
        # 8. 通过边传递结果到后继节点
        for output_msg in output_messages:
            for edge_link in node.iter_outgoing_edges():
                self._process_edge_output(edge_link, output_msg, node)
```

### 6.2 节点处理核心: `_process_result()`

**文件**: [graph.py:L660-L680]

```python
def _process_result(self, node: Node, input_payload: List[Message]) -> List[Message]:
    """Process a single input result using strategy pattern executors."""
    if node.type not in self.node_executors:
        raise ValueError(f"Unsupported node type: {node.type}")
    
    executor = self.node_executors[node.type]
    
    # Workspace hook
    hook = self.runtime_context.workspace_hook
    if hook:
        hook.before_node(node, workspace)
    
    try:
        result = executor.execute(node, input_payload)
        return result
    finally:
        if hook:
            hook.after_node(node, workspace, success=success)
```

### 6.3 执行器工厂: `NodeExecutorFactory`

**文件**: [factory.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/factory.py#L1-L31)

```python
@staticmethod
def create_executors(context: ExecutionContext, subgraphs: dict = None) -> Dict[str, NodeExecutor]:
    executors: Dict[str, NodeExecutor] = {}
    for name, registration in iter_node_registrations().items():
        executors[name] = registration.build_executor(context, subgraphs=subgraphs)
    return executors
```

### 6.4 节点执行器类型

| 节点类型 | 执行器 | 文件 |
|---------|--------|------|
| agent | `AgentNodeExecutor` | [agent_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/agent_executor.py) |
| human | `HumanNodeExecutor` | [human_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/human_executor.py) |
| subgraph | `SubgraphNodeExecutor` | [subgraph_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/subgraph_executor.py) |
| python | `PythonNodeExecutor` | [python_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/python_executor.py) |
| passthrough | `PassthroughNodeExecutor` | [passthrough_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/passthrough_executor.py) |
| literal | `LiteralNodeExecutor` | [literal_executor.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/literal_executor.py) |

## 7. 边处理详解

### 7.1 边输出处理: `_process_edge_output()`

**文件**: [graph.py:L380-L420]

```python
def _process_edge_output(
        self,
        edge_link: EdgeLink,
        source_result: Message,
        from_node: Node
) -> None:
    """Perform edge instantiation behavior."""
    manager = edge_link.condition_manager
    
    try:
        manager.process(
            edge_link,
            source_result,
            from_node,
            self.log_manager,
        )
    except Exception as exc:
        error_msg = f"Edge manager failed for {from_node.id} -> {edge_link.target.id}: {exc}"
        self.log_manager.error(error_msg, ...)
        raise WorkflowExecutionError(error_msg) from exc
```

### 7.2 动态边执行: `DynamicEdgeExecutor`

**文件**: [dynamic_edge_executor.py](file:///d:/Project/Git/ChatDev/workflow/executor/dynamic_edge_executor.py#L1-L300)

当边配置了动态执行 (`dynamic_config`) 时使用。

```
DynamicEdgeExecutor.execute_from_inputs()
    ├── create_splitter_from_config() → 创建分割器
    ├── splitter.split(inputs) → 分割输入为执行单元
    │
    ├── is_map() → _execute_map()
    │       └── 并行执行多个单元，扁平化结果
    │
    └── is_tree() → _execute_tree()
            └── 分层执行，reduce 合并结果
```

## 8. Memory 和 Thinking 管理

### 8.1 构建 Memory 和 Thinking: `_build_memories_and_thinking()`

**文件**: [graph.py:L120-L135]

```python
def _build_memories_and_thinking(self) -> None:
    """Initialize all memory and thinking managers before execution."""
    self._build_global_memories()      # 构建全局 Memory
    self._build_thinking_managers()     # 构建 Thinking Manager
    self._build_agent_memories()        # 构建 Agent Memory Manager
    self._build_node_executors()        # 构建节点执行器
```

### 8.2 全局 Memory 构建: `_build_global_memories()`

**文件**: [graph.py:L137-L175]

```python
def _build_global_memories(self) -> None:
    memory_config = self.graph.config.get_memory_config()
    
    for store in memory_config:
        # 创建 Memory 实例
        memory_instance = MemoryFactory.create_memory(store)
        self.global_memories[store.name] = memory_instance
        memory_instance.load()  # 加载已有数据
```

### 8.3 Thinking Manager 构建: `_build_thinking_managers()`

**文件**: [graph.py:L177-L185]

```python
def _build_thinking_managers(self) -> None:
    for node_id, node in self.graph.nodes.items():
        agent_config = node.as_config(AgentConfig)
        if agent_config and agent_config.thinking:
            self.thinking_managers[node_id] = ThinkingManagerFactory.get_thinking_manager(
                agent_config.thinking
            )
```

## 9. 边条件准备: `_prepare_edge_conditions()`

**文件**: [graph.py:L308-L380]

```python
def _prepare_edge_conditions(self) -> None:
    """Compile registered edge condition types into callable evaluators."""
    context = ConditionFactoryContext(
        function_manager=self.function_manager,
        log_manager=self.log_manager
    )
    
    for node in self.graph.nodes.values():
        for edge_link in node.iter_outgoing_edges():
            condition_config = edge_link.condition_config
            
            # 构建条件管理器
            manager = build_edge_condition_manager(
                condition_config,
                context,
                self._get_execution_context()
            )
            edge_link.condition_manager = manager
            
            # 如果有 payload processor，也构建
            if edge_link.process_config:
                processor = build_edge_payload_processor(
                    edge_link.process_config,
                    processor_context
                )
                edge_link.payload_processor = processor
```

## 10. 并行执行器: `ParallelExecutor`

**文件**: [parallel_executor.py](file:///d:/Project/Git/ChatDev/workflow/executor/parallel_executor.py#L1-L141)

```python
def execute_nodes_parallel(self, node_ids, executor_func):
    self.execute_items_parallel(
        node_ids,
        executor_func,
        item_desc_func,
        has_blocking_func  # 可用于序列化特定节点
    )

def _execute_parallel_batch(self, items, executor_func, item_desc_func):
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as executor:
        futures = []
        for item in items:
            future = executor.submit(executor_func, item)
            futures.append((item, future))
        
        for item, future in futures:
            try:
                future.result()
            except Exception as e:
                self.log_manager.error(...)
                raise
```

## 11. 执行上下文: `ExecutionContext`

**文件**: [runtime/node/executor/base.py](file:///d:/Project/Git/ChatDev/runtime/node/executor/base.py)

```python
@dataclass
class ExecutionContext:
    tool_manager: ToolManager
    function_manager: FunctionManager
    log_manager: LogManager
    memory_managers: Dict[str, MemoryManager]
    thinking_managers: Dict[str, ThinkingManagerBase]
    token_tracker: TokenTracker
    global_state: Dict[str, Any]
    workspace_hook: Optional[Any]
    human_prompt_service: HumanPromptService
    cancel_event: threading.Event
```

## 12. 完整调用时序图

```
用户调用
  │
  ▼
GraphExecutor.execute_graph()
  │
  ├── GraphExecutor.__init__()
  │     └── RuntimeBuilder.build() → RuntimeContext
  │
  └── executor._execute(task_prompt)
        │
        └── executor.run(task_prompt)
              │
              ├── GraphManager(graph).build_graph()
              │     ├── _instantiate_nodes()
              │     │     └── (如果是 subgraph) → _build_subgraph() → 递归
              │     │
              │     ├── _initiate_edges()
              │     │     ├── _detect_cycles()
              │     │     ├── _build_dag_layers()  (无环)
              │     │     └── _build_cycle_execution_order()  (有环)
              │     │
              │     └── _build_topology_and_metadata()
              │
              ├── _prepare_edge_conditions()
              │     └── build_edge_condition_manager() → edge_link.condition_manager
              │
              ├── _build_memories_and_thinking()
              │     ├── _build_global_memories()
              │     ├── _build_thinking_managers()
              │     ├── _build_agent_memories()
              │     └── _build_node_executors()
              │
              ├── 选择执行策略:
              │     │
              │     ├── [DAG] DagExecutionStrategy.run()
              │     │     └── DAGExecutor.execute()
              │     │           └── for layer in layers:
              │     │                 └── _execute_layer(layer)
              │     │                       └── ParallelExecutor.execute_nodes_parallel()
              │     │                             └── ThreadPoolExecutor (并行)
              │     │                                   └── _execute_node(node)
              │     │
              │     ├── [Cycle] CycleExecutionStrategy.run()
              │     │     └── CycleExecutor.execute()
              │     │           └── for layer in cycle_execution_order:
              │     │                 └── _execute_super_layer_parallel()
              │     │                       └── ParallelExecutor.execute_items_parallel()
              │     │                             └── _execute_super_item(item)
              │     │                                   ├── type="node" → _execute_single_node()
              │     │                                   │     └── _execute_node(node)
              │     │                                   └── type="cycle" → _execute_cycle()
              │     │                                         └── while iteration < max:
              │     │                                               └── _execute_cycle_with_iterations()
              │     │                                                     └── (循环内多层执行)
              │     │
              │     └── [MajorityVote] MajorityVoteStrategy.run()
              │           └── ParallelExecutor.execute_nodes_parallel()
              │                 └── 所有节点并行执行
              │                 └── _collect_majority_result()
              │
              ├── _execute_node(node)
              │     │
              │     ├── resource_manager.guard_node(node)
              │     │
              │     ├── [有动态配置?] → _execute_with_dynamic_config()
              │     │                       └── DynamicEdgeExecutor.execute_from_inputs()
              │     │                             ├── is_map() → _execute_map()
              │     │                             │     └── 并行执行单元
              │     │                             └── is_tree() → _execute_tree()
              │     │                                   └── 分层reduce
              │     │
              │     ├── [无动态配置] → _process_result()
              │     │                 └── NodeExecutor.execute()
              │     │                       ├── AgentNodeExecutor
              │     │                       ├── HumanNodeExecutor
              │     │                       ├── PythonNodeExecutor
              │     │                       └── ...
              │     │
              │     └── for edge_link in node.iter_outgoing_edges():
              │           └── _process_edge_output(edge_link, output_msg, node)
              │                 └── edge_link.condition_manager.process()
              │                       └── (可能触发后继节点)
              │
              ├── _collect_all_outputs()
              │
              ├── _save_memories()
              │
              └── ResultArchiver.export()
                    └── 导出最终结果
```

## 13. 关键类说明

| 类名 | 文件 | 职责 |
|------|------|------|
| `GraphExecutor` | graph.py | 工作流图执行器，协调整个执行过程 |
| `RuntimeContext` | runtime_context.py | 运行时依赖容器 |
| `RuntimeBuilder` | runtime_builder.py | 构建 RuntimeContext |
| `GraphManager` | graph_manager.py | 管理图的构建和拓扑 |
| `GraphContext` | graph_context.py | 图的上下文/状态容器 |
| `DagExecutionStrategy` | execution_strategy.py | DAG 执行策略 |
| `CycleExecutionStrategy` | execution_strategy.py | 循环图执行策略 |
| `MajorityVoteStrategy` | execution_strategy.py | 多数投票执行策略 |
| `DAGExecutor` | dag_executor.py | DAG 逐层执行器 |
| `CycleExecutor` | cycle_executor.py | 循环图执行器 |
| `ParallelExecutor` | parallel_executor.py | 并行执行辅助类 |
| `DynamicEdgeExecutor` | dynamic_edge_executor.py | 动态边执行器 |
| `NodeExecutorFactory` | factory.py | 节点执行器工厂 |
| `AgentNodeExecutor` | agent_executor.py | Agent 节点执行器 |
| `HumanNodeExecutor` | human_executor.py | Human 节点执行器 |
| `SubgraphNodeExecutor` | subgraph_executor.py | 子图节点执行器 |
| `PythonNodeExecutor` | python_executor.py | Python 代码执行器 |
| `PassthroughNodeExecutor` | passthrough_executor.py | 直通节点执行器 |
| `LiteralNodeExecutor` | literal_executor.py | 字面量节点执行器 |
| `CycleManager` | cycle_manager.py | 循环周期管理器 |

## 14. 执行模式总结

### 14.1 DAG 模式 (无环图)
- 按拓扑层级顺序执行
- 每层内节点并行执行
- 节点通过边传递消息触发后继

### 14.2 Cycle 模式 (有环图)
- 使用"超级节点"抽象循环
- 支持嵌套循环检测
- 多轮迭代执行，检测退出条件

### 14.3 MajorityVote 模式 (多数投票)
- 无需边配置（所有节点独立）
- 所有节点并行执行，接收相同输入
- 统计输出，返回出现最多的结果