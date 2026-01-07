# Python 节点

Python 节点用于在工作流中执行 Python 脚本或内联代码，实现自定义数据处理、API 调用、文件操作等逻辑。脚本在共享的 `code_workspace/` 目录中执行，可访问工作流上下文数据。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `interpreter` | string | 否 | 当前 Python | Python 解释器路径 |
| `args` | list[str] | 否 | `[]` | 追加到解释器后的启动参数 |
| `env` | dict[str, str] | 否 | `{}` | 额外环境变量，会覆盖系统默认值 |
| `timeout_seconds` | int | 否 | `60` | 脚本执行超时时间（秒） |
| `encoding` | string | 否 | `utf-8` | 解析 stdout/stderr 的编码 |

## 核心概念

### 代码工作区

Python 脚本在 `code_workspace/` 目录下执行：
- 脚本可以读写该目录中的文件
- 多个 Python 节点共享同一工作区
- 工作区在单次工作流执行期间持久化

### 输入输出

- **输入**：上游节点的输出作为环境变量或标准输入传递
- **输出**：脚本的 stdout 输出将作为 Message 传递给下游节点

## 何时使用

- **数据处理**：解析 JSON/XML、数据转换、格式化
- **API 调用**：调用第三方服务、获取外部数据
- **文件操作**：读写文件、生成报告
- **复杂计算**：数学运算、算法实现
- **胶水逻辑**：连接不同节点的自定义逻辑

## 示例

### 基础配置

```yaml
nodes:
  - id: Data Processor
    type: python
    config:
      timeout_seconds: 120
      env:
        key: value
```

### 指定解释器和参数

```yaml
nodes:
  - id: Script Runner
    type: python
    config:
      interpreter: /usr/bin/python3.11
      timeout_seconds: 300
      encoding: utf-8
```

### 典型工作流示例

```yaml
nodes:
  - id: LLM Generator
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      role: 你需要根据用户的输入，生成可执行的 Python 代码。代码应当包裹在 ```python ``` 之间。

  - id: Result Parser
    type: python
    config:
      timeout_seconds: 30

edges:
  - from: LLM Generator
    to: Result Parser
```

## 注意事项

- 确保脚本文件放置在 `code_workspace/` 目录下
- 长时间运行的脚本应适当增加 `timeout_seconds`
- 使用 `env` 传递额外的环境变量，可在脚本中通过 `os.getenv` 访问
