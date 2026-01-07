# 配置 Schema API 契约

本参考说明 `/api/config/schema` 与 `/api/config/schema/validate` 如何暴露 DevAll 的动态配置元数据，便于前端表单、IDE/CLI 通过 breadcrumbs（路径面包屑）按需获取局部 Schema。

## 1. 接口
| 方法 | 作用 |
| --- | --- |
| `POST /api/config/schema` | 根据 breadcrumbs 返回对应配置节点的字段定义。 |
| `POST /api/config/schema/validate` | 校验一份 YAML/JSON 文档，并可回传局部 Schema。 |

### 1.1 请求体（公共字段）
```json
{
  "breadcrumbs": [
    {"node": "DesignConfig", "field": "graph"},
    {"node": "GraphConfig", "field": "nodes"},
    {"node": "NodeConfig", "value": "model"}
  ]
}
```
- `node`（必填）：当前所处的类名（如 `DesignConfig`、`GraphConfig`、`NodeConfig`）。
- `field`（可选）：要下钻的子字段名；缺省表示仅断言仍在该 `node`。
- `value`（可选）：当子类由判别字段决定时填写（如节点 `type`）。值与 YAML 中保持一致。
- `index`（可选 int）：预留用于列表遍历，当前以 `field`/`value` 为主。

### 1.2 `/schema` 响应示例
```json
{
  "schemaVersion": "0.1.0",
  "node": "NodeConfig",
  "fields": [
    {"name": "id", "typeHint": "str", "required": true, "description": "Unique node identifier"},
    {"name": "type", "typeHint": "str", "required": true,
     "enum": ["model","python","agent"],
     "enumOptions": [{"value":"model","label":"LLM Node","description":"Runs provider-backed models"}]
    }
  ],
  "constraints": [...],
  "breadcrumbs": [...],
  "cacheKey": "f90d..."
}
```
- `fields`：序列化的 `ConfigFieldSpec`；若有子配置，会包含 `childRoutes`。
- `constraints`：由 `collect_schema()` 生成的互斥/组合约束。
- `cacheKey`：基于 `{node, breadcrumbs}` 的 SHA-1，可用于客户端缓存。

### 1.3 `/schema/validate` 额外字段
请求体在 breadcrumbs 旁加入 `document`：
```json
{
  "breadcrumbs": [{"node": "DesignConfig"}],
  "document": "name: demo\nversion: 0.4.0\nworkflow:\n  nodes: []\n  edges: []\n"
}
```
响应：
- 通过：`{ "valid": true, "schema": { ... } }`
- 配置错误：
  ```json
  {
    "valid": false,
    "error": "field 'nodes' must not be empty",
    "path": ["workflow","nodes"],
    "schema": { ... }
  }
  ```
- YAML 解析失败：HTTP 400，payload `{ "message": "invalid_yaml", "error": "..." }`

## 2. Breadcrumb 使用提示
- 起点：`{ "node": "DesignConfig" }`。
- 每一步的 `node` 必须与当前位置的类匹配，否则返回 422。
- 用 `field` 进入子配置（graph → nodes → config 等）。
- 判别式子类（如节点 `type`、tooling `type`）需填写 `value`。
- 不可导航的字段会返回 `field '<name>' on <node> is not navigable`。

## 3. CLI 辅助
```bash
python run.py --inspect-schema --schema-breadcrumbs '[{"node":"DesignConfig","field":"graph"}]'
```
输出与 `/schema` 相同，便于在导出模板前调试 `FIELD_SPECS` 或注册表。

## 4. 前端调用范式
1. 以 `[{node:'DesignConfig', field:'graph'}]` 拉取基础表单。
2. 用户展开子配置（节点、tooling 等）时，附加相应 breadcrumbs 再取一次 Schema。
3. 用 `cacheKey + breadcrumbs` 做客户端缓存。
4. 保存前调用 `/schema/validate`，将 `error` + `path` 显示在表单中。

## 5. 错误参考
| HTTP | 场景 | Payload |
| --- | --- | --- |
| 400 | YAML 解析失败 | `{ "message": "invalid_yaml", "error": "..." }` |
| 422 | Breadcrumb 解析失败 | `{ "message": "breadcrumb node 'X'..." }` |
| 200 + `valid=false` | 后端 `ConfigError` | `{ "error": "...", "path": ["workflow", ...] }` |
| 200 + `valid=true` | 文档有效 | 返回所请求的 Schema，便于表单渲染。 |

搭配 `FIELD_SPECS` 使用，可在前端/IDE 构建无需硬编码的配置体验。
