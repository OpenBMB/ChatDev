# Human 节点

Human 节点用于在工作流执行过程中引入人工交互，允许用户在 Web UI 中查看当前状态并提供输入。这种节点会阻塞工作流执行，直到用户提交响应。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `description` | text | 否 | - | 显示给用户的任务描述，说明需要人工完成的操作 |

## 核心概念

### 阻塞等待机制

当工作流执行到 Human 节点时：
1. 工作流暂停，等待人工输入
2. Web UI 显示当前上下文和任务描述
3. 用户在界面中输入响应
4. 工作流继续执行，将用户输入传递给下游节点

### 与 Web UI 交互

- Human 节点在 Launch 界面以对话形式呈现
- 用户可以查看之前的执行历史
- 支持附件上传（如文件、图片）

## 何时使用

- **审核确认**：让人工审核 LLM 输出后继续
- **修改意见**：收集用户对生成内容的修改建议
- **关键决策**：需要人工判断才能继续的分支
- **数据补充**：需要用户提供额外信息
- **质量把关**：在关键节点引入人工质检

## 示例

### 基础配置

```yaml
nodes:
  - id: Human Reviewer
    type: human
    config:
      description: 请审阅上述内容，如满意请输入 ACCEPT，否则输入修改意见。
```

### 人机协作循环

```yaml
nodes:
  - id: Article Writer
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      role: 你是一位专业作家，根据用户要求撰写文章。

  - id: Human Reviewer
    type: human
    config:
      description: |
        请审阅文章：
        - 满意结果请输入 ACCEPT 结束流程
        - 否则输入修改意见继续迭代

edges:
  - from: Article Writer
    to: Human Reviewer
  - from: Human Reviewer
    to: Article Writer
    condition:
      type: keyword
      config:
        none: [ACCEPT]
        case_sensitive: false
```

### 多阶段审核

```yaml
nodes:
  - id: Draft Generator
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Content Review
    type: human
    config:
      description: 请审核内容准确性，输入 APPROVED 或修改意见。

  - id: Final Reviewer
    type: human
    config:
      description: 最终确认，输入 PUBLISH 发布或 REJECT 驳回。

edges:
  - from: Draft Generator
    to: Content Review
  - from: Content Review
    to: Final Reviewer
    condition:
      type: keyword
      config:
        any: [APPROVED]
```

## 最佳实践

- 在 `description` 中清晰说明期望的操作和关键词
- 使用条件边配合关键词实现流程控制
- 考虑添加超时机制避免工作流无限等待
