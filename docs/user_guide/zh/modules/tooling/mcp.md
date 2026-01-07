# MCP Tooling 指南

MCP 工具被明确拆分为 **Remote (HTTP)** 与 **Local (stdio)** 两种模式，对应 `tooling.type: mcp_remote` 与 `tooling.type: mcp_local`。旧的 `type: mcp` schema 已下线，请在 YAML 与文档中全部迁移。

## 1. 配置模式概览
| 模式 | Tooling type | 适用场景 | 关键字段 |
| --- | --- | --- | --- |
| Remote | `mcp_remote` | 已部署的 HTTP(S) MCP 服务器（如 FastMCP、Claude Desktop Connector、自建代理） | `server`、`headers`、`timeout` |
| Local | `mcp_local` | 通过 stdio 握手的本地可执行脚本（Blender MCP、CLI 工具等） | `command`、`args`、`cwd`、`env` 等进程字段 |

## 2. `McpRemoteConfig` 字段
| 字段 | 说明 |
| --- | --- |
| `server` | 必填，MCP HTTP(S) 端点，例如 `https://api.example.com/mcp`。 |
| `headers` | 可选，附加 HTTP 头（如 `Authorization`）。 |
| `timeout` | 可选，单次工具调用超时时间（秒）。 |

**YAML 示例：**
```yaml
nodes:
  - id: remote_mcp
    type: agent
    config:
      tooling:
        type: mcp_remote
        config:
          server: https://mcp.mycompany.com/mcp
          headers:
            Authorization: Bearer ${MY_MCP_TOKEN}
          timeout: 15
```
DevAll 会在列举/调用工具时连接该 URL，并携带 `headers`。若服务器不可达，将直接抛出错误，不再尝试本地回退。

## 3. `McpLocalConfig` 字段
`mcp_local` 直接在 `config` 下声明进程参数：
- `command` / `args`：可执行文件与参数（如 `uvx blender-mcp`）。
- `cwd`：可选工作目录。
- `env` / `inherit_env`：定制子进程环境；默认继承父进程后再覆盖。
- `startup_timeout`：等待 `wait_for_log` 命中的最长秒数。
- `wait_for_log`：stdout 正则，用于判定“就绪”。

**YAML 示例：**
```yaml
nodes:
  - id: local_mcp
    type: agent
    config:
      tooling:
        type: mcp_local
        config:
          command: uvx
          args:
            - blender-mcp
          cwd: ${REPO_ROOT}
          wait_for_log: "MCP ready"
          startup_timeout: 8
```
运行期间 DevAll 会保持该进程常驻，并通过 stdio 传输 MCP 数据帧。

## 4. FastMCP 示例服务器
`mcp_example/mcp_server.py`：
```python
from fastmcp import FastMCP
import random

mcp = FastMCP("Company Simple MCP Server", debug=True)

@mcp.tool
def rand_num(a: int, b: int) -> int:
    return random.randint(a, b)

if __name__ == "__main__":
    mcp.run()
```
启动：
```bash
uv run fastmcp run mcp_example/mcp_server.py --transport streamable-http --port 8010
```
- 若以 Remote 模式使用，只需将 `server` 指向 `http://127.0.0.1:8010/mcp`。
- 若以 Local 模式使用，可将 `command` 设置为 `uv run fastmcp run ...` 并保持 `transport=stdio`。

## 5. 安全与运维
- **网络暴露**：Remote 模式建议置于 HTTPS 反向代理之后，并结合 API Key/ACL；Local 模式进程仍可访问宿主机文件，请限制其权限。
- **资源回收**：Local 模式由 DevAll 负责终止子进程，确保脚本可以正确处理 SIGTERM/SIGKILL。
- **日志定位**：为 `wait_for_log` 输出清晰的“ready”日志，便于在超时时排查。
- **鉴权**：Remote 模式通过 `headers` 传递 Token；Local 模式可在 `env` 中注入密钥，注意不要写入仓库。
- **多会话**：MCP 服务若不支持多客户端，可在模型或工具层设置 `max_concurrency=1` 并在 YAML 中复用同一配置。

## 6. 调试步骤
1. Remote：使用 curl 或 `fastmcp client` 测试 HTTP 端点；Local：先单独运行并确认 stdout 中有 `wait_for_log` 匹配的文本。
2. 启动 DevAll（可加 `--reload`），观察后端日志是否打印工具清单。
3. 若调用失败，查看 Web UI 中的工具请求/响应，或在 `logs/` 中搜索对应 session 的结构化日志。
