# Thinking 模块指南

Thinking 模块为 Agent 节点提供思考增强能力，使模型能够在生成结果前或后进行额外的推理过程。本文档介绍 Thinking 模块的架构、内置模式及配置方法。

## 1. 体系结构

1. **ThinkingConfig**：在 YAML `nodes[].config.thinking` 中声明，包含 `type` 和 `config` 两个字段。
2. **ThinkingManagerBase**：抽象基类，定义 `_before_gen_think` 和 `_after_gen_think` 两个时机的思考逻辑。
3. **注册中心**：通过 `register_thinking_mode()` 注册新的思考模式，Schema API 会自动展示可用选项。

## 2. 配置示例

```yaml
nodes:
  - id: Thoughtful Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      thinking:
        type: reflection
        config:
          reflection_prompt: |
            请仔细审视你的回答，考虑以下方面：
            1. 逻辑是否严密
            2. 有无事实错误
            3. 表达是否清晰
            然后给出改进后的回答。
```

## 3. 内置思考模式

| 类型 | 描述 | 触发时机 | 配置字段 |
|------|------|----------|----------|
| `reflection` | 模型生成后进行自我反思并优化输出 | 生成后 (`after_gen`) | `reflection_prompt` |

### 3.1 Reflection 模式

Self-Reflection 模式让模型在初次生成后对自己的输出进行反思和改进。实现流程：

1. Agent 节点正常调用模型生成初始回答
2. ThinkingManager 将对话历史（系统角色、用户输入、模型输出）拼接为反思上下文
3. 结合 `reflection_prompt` 再次调用模型生成反思结果
4. 反思结果替换原始输出作为节点最终输出

#### 配置项

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reflection_prompt` | string | 是 | 引导模型反思的提示词，可指定反思维度和期望改进方向 |

#### 适用场景

- **写作润色**：让模型自我审阅并修正语法、逻辑问题
- **代码审查**：生成代码后自动进行安全和质量检查
- **复杂推理**：对多步骤推理结果进行验证和修正

## 4. 执行时机

ThinkingManager 支持两种执行时机：

| 时机 | 属性 | 说明 |
|------|------|------|
| 生成前 (`before_gen`) | `before_gen_think_enabled` | 在模型调用前执行思考，可预处理输入 |
| 生成后 (`after_gen`) | `after_gen_think_enabled` | 在模型输出后执行思考，可后处理或优化输出 |

内置的 `reflection` 模式仅启用生成后思考。扩展开发者可根据需求实现生成前思考。

## 5. 与 Memory 的交互

Thinking 模块可访问 Memory 上下文：

- `ThinkingPayload.text`：当前阶段的文本内容
- `ThinkingPayload.blocks`：多模态内容块（图片、附件等）
- `ThinkingPayload.metadata`：附加元数据

Memory 检索结果会通过 `memory` 参数传入思考函数，允许反思时参考历史记忆。

## 6. 扩展自定义思考模式

1. **创建配置类**：继承 `BaseConfig`，定义所需配置字段
2. **实现 ThinkingManager**：继承 `ThinkingManagerBase`，实现 `_before_gen_think` 或 `_after_gen_think`
3. **注册模式**：
   ```python
   from runtime.node.agent.thinking.registry import register_thinking_mode
   
   register_thinking_mode(
       "my_thinking",
       config_cls=MyThinkingConfig,
       manager_cls=MyThinkingManager,
       summary="自定义思考模式描述",
   )
   ```
4. **导出模板**：运行 `python -m tools.export_design_template` 更新前端选项

## 7. 最佳实践

- **控制反思轮次**：当前反思为单轮，若需多轮可在 `reflection_prompt` 中明确迭代要求
- **简洁提示词**：过长的 `reflection_prompt` 会增加 token 消耗，建议聚焦关键改进点
- **配合 Memory**：将重要反思结果存入 Memory，供后续节点参考
- **监控成本**：反思会额外调用模型，注意 token 用量

## 8. 相关文档

- [Agent 节点配置](../nodes/agent.md)
- [Memory 模块](memory.md)
- [工作流编排指南](../workflow_authoring.md)
