# Literal 节点

Literal 节点用于输出固定的文本内容。当节点被触发时，它会忽略所有输入，直接输出预定义的消息。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | text | 是 | - | 输出的固定文本内容，不能为空 |
| `role` | string | 否 | `user` | 消息角色：`user` 或 `assistant` |

## 核心概念

### 固定输出

Literal 节点的特点：
- **忽略输入**：不管上游传入什么内容，都不影响输出
- **固定内容**：每次执行都输出相同的 `content`
- **角色标记**：输出消息带有指定的角色标识

### 消息角色

- `user`：表示这是用户发出的消息
- `assistant`：表示这是助手（AI）发出的消息

角色设置会影响下游节点对消息的处理方式。

## 何时使用

- **固定提示注入**：向流程中注入固定的指令或上下文
- **测试调试**：使用固定输入测试下游节点
- **默认响应**：在特定条件下返回固定消息
- **流程初始化**：作为工作流的起点提供初始内容

## 示例

### 基础用法

```yaml
nodes:
  - id: Welcome Message
    type: literal
    config:
      content: |
        欢迎使用智能助手！请描述您的需求。
      role: assistant
```

### 注入固定上下文

```yaml
nodes:
  - id: Context Injector
    type: literal
    config:
      content: |
        请注意以下规则：
        1. 回答必须简洁明了
        2. 使用中文回复
        3. 如有不确定，请说明
      role: user

  - id: Assistant
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  - from: Context Injector
    to: Assistant
```

### 条件分支中的固定响应

```yaml
nodes:
  - id: Classifier
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: 判断用户意图，回复 KNOWN 或 UNKNOWN

  - id: Known Response
    type: literal
    config:
      content: 我能帮助您完成这个任务。
      role: assistant

  - id: Unknown Response
    type: literal
    config:
      content: 抱歉，我无法理解您的请求，请换一种方式描述。
      role: assistant

edges:
  - from: Classifier
    to: Known Response
    condition:
      type: keyword
      config:
        any: [KNOWN]
  - from: Classifier
    to: Unknown Response
    condition:
      type: keyword
      config:
        any: [UNKNOWN]
```

### 测试用途

```yaml
nodes:
  - id: Test Input
    type: literal
    config:
      content: |
        这是一段测试文本，用于验证下游处理逻辑。
        包含多行内容。
      role: user

  - id: Processor
    type: python
    config:
      timeout_seconds: 30

edges:
  - from: Test Input
    to: Processor

start: [Test Input]
```

## 注意事项

- `content` 字段不能为空字符串
- 使用 YAML 多行字符串语法 `|` 便于编写长文本
- 选择正确的 `role` 以确保下游节点正确处理消息
