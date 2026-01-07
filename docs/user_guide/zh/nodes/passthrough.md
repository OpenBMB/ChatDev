# Passthrough 节点

Passthrough 节点是最简单的节点类型，它不执行任何操作，仅将接收到的消息传递给下游节点。默认情况下只传递**最后一条消息**。它主要用于图结构的"理线"优化和上下文控制。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `only_last_message` | bool | 否 | `true` | 是否只传递最后一条消息。设为 `false` 时传递所有消息。 |

### 基本配置

```yaml
config: {}  # 使用默认配置，只传递最后一条消息
```

### 传递所有消息

```yaml
config:
  only_last_message: false  # 传递所有接收到的消息
```

## 核心概念

### 透传行为

- 接收上游传入的所有消息
- **默认只传递最后一条消息**（`only_last_message: true`）
- 设置 `only_last_message: false` 时传递所有消息
- 不做任何内容处理或转换

### 图结构优化

Passthrough 节点的核心价值不在于数据处理，而在于**图结构的优化**（"理线"）：
- 使复杂的边连接更加清晰
- 集中管理出边配置（如 `keep_message`）
- 作为逻辑分界点，提高工作流可读性

## 关键用途

### 1. 作为起始节点保留初始上下文

将 Passthrough 作为工作流的入口节点，配合边的 `keep_message: true` 配置，可以确保用户的初始任务始终保留在上下文中，不会被后续节点的输出覆盖：

```yaml
nodes:
  - id: Task Keeper
    type: passthrough
    config: {}

  - id: Worker A
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Worker B
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  # 从入口分发任务，保留原始消息
  - from: Task Keeper
    to: Worker A
    keep_message: true  # 保留初始任务上下文

  - from: Task Keeper
    to: Worker B
    keep_message: true

start: [Task Keeper]
```

**效果**：Worker A 和 Worker B 都能看到用户的原始输入，而不仅仅是上一个节点的输出。

### 2. 过滤循环中的冗余输出

在包含循环的工作流中，循环内的节点可能产生大量中间输出。如果将所有输出都传递给后续节点，会导致上下文膨胀。使用 Passthrough 节点可以**只传递循环的最终结果**：

```yaml
nodes:
  - id: Iterative Improver
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: 根据反馈不断改进输出

  - id: Evaluator
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: |
        评估输出质量，回复 GOOD 或提供改进建议

  - id: Result Filter
    type: passthrough
    config: {}

  - id: Final Processor
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: 对最终结果进行后处理

edges:
  - from: Iterative Improver
    to: Evaluator
  
  # 循环：评估不通过时回到改进节点
  - from: Evaluator
    to: Iterative Improver
    condition:
      type: keyword
      config:
        none: [GOOD]
  
  # 循环结束：通过 Passthrough 过滤，只传递最后一条
  - from: Evaluator
    to: Result Filter
    condition:
      type: keyword
      config:
        any: [GOOD]
  
  - from: Result Filter
    to: Final Processor

start: [Iterative Improver]
end: [Final Processor]
```

**效果**：无论循环迭代多少次，`Final Processor` 只会收到 `Evaluator` 的最后一条输出（表示质量通过的那条），而不是所有中间结果。

## 其他用途

- **占位符**：在设计阶段预留节点位置
- **条件分支**：配合条件边实现路由逻辑
- **调试观察点**：在流程中插入便于观察的节点

## 示例

### 基础用法

```yaml
nodes:
  - id: Router
    type: passthrough
    config: {}
```

### 条件路由

```yaml
nodes:
  - id: Classifier
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: |
        分类输入内容，回复 TECHNICAL 或 BUSINESS

  - id: Router
    type: passthrough
    config: {}

  - id: Tech Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Biz Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  - from: Classifier
    to: Router
  - from: Router
    to: Tech Handler
    condition:
      type: keyword
      config:
        any: [TECHNICAL]
  - from: Router
    to: Biz Handler
    condition:
      type: keyword
      config:
        any: [BUSINESS]
```

## 最佳实践

- 使用有意义的节点 ID 描述其拓扑作用（如 `Task Keeper`、`Result Filter`）
- 作为入口节点时，出边配置 `keep_message: true` 保留上下文
- 在循环后使用，可以过滤掉冗余的中间输出
