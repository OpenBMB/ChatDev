# Subgraph 节点

Subgraph 节点允许将另一个工作流图嵌入到当前工作流中，实现流程复用和模块化设计。子图可以来自外部 YAML 文件，也可以直接在配置中内联定义。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `type` | string | 是 | - | 子图来源类型：`file` 或 `config` |
| `config` | object | 是 | - | 根据 `type` 不同，包含不同的配置 |

### file 类型配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 子图文件路径（相对于 `yaml_instance/` 或绝对路径） |

### config 类型配置

内联定义完整的子图结构，包含与顶层 `graph` 相同的字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 子图标识符 |
| `description` | string | 否 | 子图描述 |
| `log_level` | string | 否 | 日志级别（DEBUG/INFO） |
| `nodes` | list | 是 | 节点列表 |
| `edges` | list | 否 | 边列表 |
| `start` | list | 否 | 入口节点列表 |
| `end` | list | 否 | 出口节点列表 |
| `memory` | list | 否 | 子图专用的 Memory 定义 |

## 核心概念

### 模块化复用

将常用的流程片段抽取为独立的 YAML 文件，多个工作流可以复用同一子图：
- 例如：将"文章润色"流程封装为子图
- 不同的主工作流都可以调用该子图

### 变量继承

子图会继承父图的 `vars` 变量定义，支持跨层级变量传递。

### 执行隔离

子图作为独立单元执行，拥有自己的：
- 节点命名空间
- 日志级别配置
- Memory 定义（可选）

## 何时使用

- **流程复用**：多个工作流共享相同的子流程
- **模块化设计**：将复杂流程拆分为可管理的小单元
- **团队协作**：不同团队维护不同的子图模块

## 示例

### 引用外部文件

```yaml
nodes:
  - id: Review Process
    type: subgraph
    config:
      type: file
      config:
        path: common/review_flow.yaml
```

### 内联定义子图

```yaml
nodes:
  - id: Translation Unit
    type: subgraph
    config:
      type: config
      config:
        id: translation_subgraph
        description: 多语言翻译子流程
        nodes:
          - id: Translator
            type: agent
            config:
              provider: openai
              name: gpt-4o
              role: 你是一位专业翻译，将内容翻译为目标语言。
          - id: Proofreader
            type: agent
            config:
              provider: openai
              name: gpt-4o
              role: 你是一位校对专家，检查并润色翻译内容。
        edges:
          - from: Translator
            to: Proofreader
        start: [Translator]
        end: [Proofreader]
```

### 组合多个子图

```yaml
nodes:
  - id: Input Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Analysis Module
    type: subgraph
    config:
      type: file
      config:
        path: modules/analysis.yaml

  - id: Report Module
    type: subgraph
    config:
      type: file
      config:
        path: modules/report_gen.yaml

edges:
  - from: Input Handler
    to: Analysis Module
  - from: Analysis Module
    to: Report Module
```

## 注意事项

- 子图文件路径支持相对路径（基于 `yaml_instance/`）和绝对路径
- 避免循环嵌套（A 引用 B，B 再引用 A）
- 子图的 `start` 和 `end` 节点决定了数据如何流入流出，这决定了子图如何处理父图传入的消息，以及以哪个节点的最终输出作为返回给父图的消息。
