# Loop Counter 节点

Loop Counter 节点是一种循环控制节点，用于限制工作流中环路的执行次数。它通过计数机制，在达到预设上限前抑制输出，达到上限后才释放消息触发出边，从而终止循环。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_iterations` | int | 是 | `10` | 最大循环次数，必须 ≥ 1 |
| `reset_on_emit` | bool | 否 | `true` | 达到上限后是否重置计数器 |
| `message` | text | 否 | - | 达到上限时发送给下游的消息内容 |

## 核心概念

### 工作原理

Loop Counter 节点维护一个内部计数器，其行为如下：

1. **每次被触发时**：计数器 +1
2. **计数器 < `max_iterations`**：**不产生任何输出**，出边不会被触发
3. **计数器 = `max_iterations`**：产生输出消息，触发出边

这种"抑制-释放"机制使得 Loop Counter 可以精确控制循环何时终止。

### 拓扑结构要求

Loop Counter 节点在图结构中有特殊的位置要求：

```
    ┌──────────────────────────────────────┐
    ▼                                      │
  Agent ──► Human ─────► Loop Counter ──┬──┘
    ▲         │                         │
    └─────────┘                         ▼
                                   End Node (环外)
```

> **重要**：由于 Loop Counter **未达上限时不产生任何输出**，因此：
> - **Human 必须同时连接到 Agent 和 Loop Counter**：这样"继续循环"的边由 Human → Agent 承担，而 Loop Counter 仅负责计数
> - **Loop Counter 必须连接到 Agent（环内）**：使其被识别为环内节点，避免提前终止环路
> - **Loop Counter 必须连接到 End Node（环外）**：当达到上限时触发环外节点，终止整个环的执行

### 计数器状态

- 计数器状态在整个工作流执行期间持久化
- 当 `reset_on_emit: true` 时，达到上限后计数器重置为 0
- 当 `reset_on_emit: false` 时，达到上限后继续累计，后续每次触发都会输出

## 何时使用

- **防止无限循环**：为人机交互循环设置安全上限
- **迭代控制**：限制 Agent 自我迭代改进的最大轮次
- **超时保护**：作为流程执行的"熔断器"

## 示例

### 基础用法

```yaml
nodes:
  - id: Iteration Guard
    type: loop_counter
    config:
      max_iterations: 5
      reset_on_emit: true
      message: 已达到最大迭代次数，流程终止。
```

### 人机交互循环保护

这是 Loop Counter 最典型的使用场景：

```yaml
graph:
  id: review_loop
  description: 带迭代上限的审稿循环
  
  nodes:
    - id: Writer
      type: agent
      config:
        provider: openai
        name: gpt-4o
        role: 根据用户反馈改进文章

    - id: Reviewer
      type: human
      config:
        description: |
          审阅文章，输入 ACCEPT 接受或提供修改意见。

    - id: Loop Guard
      type: loop_counter
      config:
        max_iterations: 3
        message: 已达到最大修改次数（3次），流程自动结束。

    - id: Final Output
      type: passthrough
      config: {}

  edges:
    # 主循环：Writer -> Reviewer
    - from: Writer
      to: Reviewer
    
    # 条件1：用户输入 ACCEPT -> 结束
    - from: Reviewer
      to: Final Output
      condition:
        type: keyword
        config:
          any: [ACCEPT]
    
    # 条件2：用户输入修改意见 -> 同时触发 Writer 继续循环 AND Loop Guard 计数
    - from: Reviewer
      to: Writer
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    - from: Reviewer
      to: Loop Guard
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    # Loop Guard 连接到 Writer（使其保持在环内）
    - from: Loop Guard
      to: Writer
    
    # Loop Guard 达到上限时：触发 Final Output 结束流程
    - from: Loop Guard
      to: Final Output

  start: [Writer]
  end: [Final Output]
```

**执行流程说明**：
1. 用户首次输入修改意见 → 同时触发 Writer（继续循环）和 Loop Guard（计数 1，无输出）
2. 用户再次输入修改意见 → 同时触发 Writer（继续循环）和 Loop Guard（计数 2，无输出）
3. 用户第三次输入修改意见 → Writer 继续执行，Loop Guard 计数 3 达到上限，输出消息触发 Final Output，终止环路
4. 或者在任意时刻用户输入 ACCEPT → 直接到 Final Output 结束

## 注意事项

- `max_iterations` 必须为正整数（≥ 1）
- Loop Counter **未达上限时不产生任何输出**，出边不会触发
- 确保 Loop Counter 同时连接环内节点和环外节点
- `message` 字段可选，默认消息为 `"Loop limit reached (N)"`
