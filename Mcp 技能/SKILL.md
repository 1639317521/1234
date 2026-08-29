---
name: "canvas-mcp"
description: "Controls Infinite Canvas nodes through the MCP protocol. Supports smart canvas operations: list/open canvases, batch create smart-image nodes (with auto-connect), batch update node settings, query single/multi selection, update prompt text, arrange nodes, and update node positions. Frontend updates in-place without full reload. Match by user intent even when no exact tool name is mentioned."
---

# 无限画布 MCP 技能

## 技能用途

通过 MCP 协议让外部 AI 客户端（Trae / Claude Desktop / Cursor / 任意 MCP 客户端）控制无限画布（**智能画布**）的节点操作：

- 查询画布列表、打开画布查看节点详情
- **批量创建智能节点**：从表格数据批量创建 `smart-image` 节点，可选自动连线到上游节点
- **批量修改节点设置**：对框选或指定的多个节点统一修改比例、分辨率、标题、提示词等字段
- 查询当前选中的单个或多个节点
- 更新节点提示词文本
- 创建基础提示词节点（`prompt` 节点）

调用链路：

`外部 AI → MCP 服务(mcp_server.py) → HTTP 调用主服务(main.py, 默认 :3000) → 数据持久化与 WebSocket 广播 → 前端实时更新`

## 真实能力边界（重要）

本技能只覆盖**已通过 MCP 暴露**的能力。以下事实务必遵守，不得伪造：

- MCP 服务当前提供 **10 个工具**（见「当前已实现的 MCP 工具」），聚焦智能画布操作。
- `batch_create_nodes` 仅支持智能画布（`kind == "smart"`），**不能**在普通画布上创建 `smart-image` 节点，也不能创建 `prompt` 节点之外的普通节点。
- `batch_update_nodes` 使用 `deep_merge` 策略，只覆盖传入的字段，不修改未指定的字段。支持嵌套字段（如 `runSettings.ratio` 通过 `{"runSettings": {"ratio": "wide"}}` 设置）。
- `get_selected_nodes` 依赖前端上报的多个选中节点 ID；若前端未上报或框选为空，返回空列表。
- 画布前端已实现 Ctrl 增量框选、右键打组、批量运行，但**打组和批量运行**目前没有对应 MCP 工具。AI 不得声称已通过 MCP 完成打组或批量运行。

## 触发条件

遇到以下需求时使用本技能：

- 用户以自然语言提到无限画布相关操作时，即使没有明确说出 MCP 工具名称，也按语义自动触发
- 当前任务明确针对无限画布项目、画布节点或 `canvas-mcp` 时，优先使用本技能
- 外部 AI、Claude、Cursor 或其他 MCP 客户端需要连接无限画布
- 查询画布列表或打开指定画布
- **批量创建智能画布节点**（如「把这些提示词传到画布」「根据表格创建节点」）
- **批量修改节点设置**（如「把选中节点改成 16:9」「批量改比例」）
- **批量设置节点位置**（如「按左中右排列」「整理布局」）
- 读取用户当前选中的**单个或多个**节点
- 更新选中节点的提示词文本
- 无限画布 MCP 能力新增、修改或删除，需要同步更新技能说明

## 当前已实现的 MCP 工具

调用前应先读取 MCP 服务实际返回的工具描述与参数结构，不得凭经验伪造参数。以下信息基于 `mcp_server.py` 实际代码：

### 基础工具

- `list_canvases()` → 返回 `[{id, title, kind}]`，用于定位 `canvas_id`。
- `open_canvas(canvas_id: str)` → 返回画布概览：
  `{canvas_id, title, node_count, nodes:[{id, type, x, y, text(前60字)}]}`。
- `create_prompt_node(canvas_id: str, text: str, x: float = 0.0, y: float = 0.0)` →
  在指定画布新建一个基础提示词节点。返回 `{ok:true, node:{id:"prompt_"+uuid, type:"prompt", x, y, text}}`。
  - `x`、`y` 同时缺省为 `0` 时，节点落在前端最近上报的视口中心（来自 `mcp-selection`）；
    传入显式坐标可覆盖落点。
  - 新建后主服务会写盘并通过 WebSocket 广播到已打开画布。
- `get_selected_node(canvas_id: str)` → 返回前端最近上报的**单个**选中节点详情：
  `{canvas_id, selected_node: node | null, center:{x,y}, hint?}`。
  - `selected_node` 为 `null` 时表示画布上没有上报选中节点，应提示用户先在界面点选。
- `update_prompt_node(canvas_id: str, node_id: str, text: str)` →
  将该节点的 `text` 字段整体替换为新文本，保存并广播。返回 `{ok:true, node}` 或错误文本。
  - 仅修改 `text`；不会改动位置、标题（`displayTitle`）、分组或提示词其他字段。

### 新增工具（智能画布专用）

- `get_selected_nodes(canvas_id: str)` → 返回前端最近上报的**多个**选中节点详情：
  `{canvas_id, selected_nodes: [node, ...], center:{x,y}, hint?}`。
  - `selected_nodes` 为空数组时表示画布上没有上报多选节点，应提示用户先在画布界面框选多个节点。
  - 用于「批量修改框选的节点」场景，先调此工具获取选中节点，再调 `batch_update_nodes` 修改。

- `batch_update_nodes(canvas_id: str, node_ids: list, updates: dict)` →
  批量修改指定节点的字段/设置。使用 `deep_merge` 策略，只覆盖传入的字段。
  - 返回 `{ok:true, updated_count: N, nodes: [...]}`。
  - 用法示例：
    - 改比例：`node_ids=[...], updates={"runSettings": {"ratio": "wide", "resolution": "4k"}}`
    - 改标题：`node_ids=[...], updates={"displayTitle": "新标题"}`
    - 改提示词：`node_ids=[...], updates={"promptDraftText": "新提示词"}`
    - 支持嵌套字段，如 `updates` 为 `{"runSettings": {"ratio": "wide"}}` 时只改比例，不改其他设置。
  - 所有节点应用相同的 `updates`；如需每个节点不同值，需多次调用。
  - 若 `node_ids` 中存在不存在的 ID，仅处理存在的节点，返回其中 `updated_count` 实际数量。

- `batch_create_nodes(canvas_id: str, nodes: list, auto_connect: bool = False)` →
  批量创建智能画布节点（`smart-image`），可选自动连线到上游节点。
  - `nodes` 是数组，每个元素包含：
    - `text`（必填）：提示词正文
    - `title`（可选）：节点标题，不传时自动从提示词提取
    - `upstream`（可选）：上游节点名称，用于 `auto_connect` 时指定连线目标
  - `auto_connect=True` 时自动匹配上游节点并建立 `flow` 连线。
  - 返回 `{ok, created: [{id, title, type}], connections: [{from, to}], total_nodes, unmatched_upstream?, hint?}`。
  - 节点位置自动避让现有节点，不会重叠。
  - 匹配规则详见「名称匹配规则」章节。

- `arrange_nodes(canvas_id: str, node_ids: list)` →
  整理指定的节点为整齐网格布局，消除它们之间的重叠，**不触动其他节点**。
  - 适合 `batch_create_nodes` 创建后调用，传入返回的 `created[].id` 列表，让新节点排齐。
  - 其他已有节点保持原位不动。
  - 返回 `{ok:true, arranged_count: N}`。

- `update_node_positions(canvas_id: str, nodes: list)` →
  批量更新节点位置/字段。每个节点指定 `id` 和要修改的字段。
  - `nodes` 格式：`[{id: "节点ID", x: 100, y: 200}, ...]`
  - 支持任意字段，如 `{id: "...", displayTitle: "新标题", "runSettings": {"ratio": "wide"}}`
  - 适合按左中右工作流布局排列节点时使用。
  - 前端原地更新，**不触发全量重载**，不改变视口，**不中断生成计时器**。

## 轻量广播机制（mcp_nodes_updated）

MCP 的批量操作（`batch_update_nodes`、`batch_create_nodes`、`arrange_nodes`、`update_node_positions`）使用 `mcp_nodes_updated` 消息类型广播节点变更，区别于普通保存的 `canvas_updated` 全量重载：

| | `canvas_updated`（普通保存） | `mcp_nodes_updated`（MCP 操作） |
|---|---|---|
| 前端行为 | 全量重载画布 | **原地更新**指定节点的 x/y/字段 |
| 视口 | 重置 | 保持不动 |
| 选中状态 | 丢失 | 保持不动 |
| 生成计时器 | 中断 | 继续运行 |
| 其他节点 | 全部重新渲染 | 完全不动 |

该机制解决了「以前端为主」的冲突——前端 `mergeSmartNode` 函数会忽略服务端的位置变更（防止覆盖用户拖动结果），而 `mcp_nodes_updated` 直接通过 `Object.assign` 更新本地数据并修改 DOM 的 `left/top`，绕过合并逻辑。

## 名称匹配规则（用于 auto_connect）

当 `batch_create_nodes` 的 `auto_connect=True` 时，自动连线遵循以下匹配规则：

### 匹配优先级

1. **`upstream` 字段精确匹配**：如果节点数据中明确指定了 `upstream`（上游节点名称），优先按此名称精确匹配现有节点的 `displayTitle` 或 `title`（不区分大小写）。
2. **文本内容自动匹配**：如果未指定 `upstream`，从节点的提示词文本中搜索现有节点名称。匹配条件是：现有节点的 `displayTitle` 或 `title` 作为子串出现在提示词文本中（不区分大小写）。

### 匹配规则

- 按 `displayTitle` 优先，`title` 后备。
- 不区分大小写。
- 匹配多个同名节点时，取第一个匹配到的节点（按数组顺序）。
- 只匹配已有节点，不会自动创建新节点。
- 匹配不到的节点名会记录在返回结果的 `unmatched_upstream` 列表中，并附带提示。

### 示例

画布上有节点「主角」「城堡」「宝剑」，创建新节点时：

```
batch_create_nodes(canvas_id, nodes=[
  {text: "一个英俊的年轻人站在城堡前", title: "主角出场"},
  {text: "古老的城堡外观", title: "城堡外景", upstream: "城堡"}
], auto_connect=True)
```

结果：
- 「主角出场」节点的文本包含「城堡」，自动连线到「城堡」节点
- 「城堡外景」节点通过 `upstream` 字段精确匹配到「城堡」节点，自动连线

## 部署与鉴权

- 启动：`python mcp_server.py`，SSE 地址 `http://127.0.0.1:8765/sse`。
- 主服务 `main.py` 默认 `http://127.0.0.1:3000`，需先启动。
- 写操作（`create_prompt_node` / `update_prompt_node` / `batch_update_nodes` / `batch_create_nodes`）需携带与主服务一致的令牌：
  - 环境变量 `MCP_API_TOKEN`（默认 `wucanvas-mcp-default-token`）。
  - 主服务侧同名环境变量 `MCP_API_TOKEN` 必须一致，否则返回 401。
- 其他环境变量：`WUCANVAS_MCP_BASE_URL`（指向主服务）、`WUCANVAS_MCP_PORT`（MCP 端口，默认 8765）。

## 画布前端已实现、但 MCP 尚未暴露的能力（供理解产品边界）

以下交互在画布前端可用，但**没有对应 MCP 工具**，AI 不应通过 MCP 调用或声称已完成：

- 多选节点右键菜单 →「打组」：复用前端 `groupSelectedImages()` / `groupSelectedNodes()`。
- 多选节点右键菜单 →「批量运行」：复用前端运行队列，按选择顺序串行运行可运行节点，跳过不可运行或正在运行的节点。

MCP 当前可以读取多选集合（`get_selected_nodes`）和批量修改（`batch_update_nodes`），但无法执行打组或批量运行。

## 规划中（MCP 暂不支持，严禁当作现有能力调用）

以下均为**尚未在 MCP 暴露**的能力，仅作为产品演进方向记录：

### 1. 视频节点智能连线

规划中的能力：解析自然语言，匹配已有素材节点，创建 `runSettings.apiKind:"video"` 的节点并自动建立 `flow` 连线。当前 MCP 的 `batch_create_nodes` 可以创建 `smart-image` 节点和连线，但尚未专门针对视频节点优化。

### 2. 未来 MCP 多选工具建议

当后端正式提供多选能力时，建议新增或扩展：

- `group_selected_nodes`：将当前选中节点创建为一个分组
- `batch_run_selected_nodes`：批量运行当前选中的可运行节点
- `get_batch_run_status`：查询批量运行状态和每个节点的结果

这些工具目前属于规划建议。在工具尚未真实存在前，外部 AI 不得声称已通过这些工具完成操作，也不得伪造调用结果。

## 选中节点的读取与更新

读取和更新节点时遵循以下顺序：

1. 用 `get_selected_node` 查询当前选中的单个节点（可能为 null），或用 `get_selected_nodes` 查询多个选中节点。
2. 校验画布 ID、节点 ID 和节点类型。
3. 读取节点当前数据，避免覆盖无关字段。
4. 只修改用户明确要求修改的字段。
5. 保存后重新读取节点进行校验。
6. 确认节点 ID、类型、位置及其他未要求修改的属性保持不变。
7. 确认已打开的画布通过 WebSocket 得到实时更新。

选中状态属于短时状态，且 MCP 只持有单节点。读取后应尽快执行更新，避免用户已切换选择对象。

## 名称匹配规则（工具使用指引）

使用 `batch_create_nodes` 的 `auto_connect=True` 时：

1. 先调 `open_canvas` 获取画布上所有现有节点及其 `displayTitle` / `title`。
2. 构建节点名称列表，用于判断哪些节点名会被匹配到。
3. 如果用户提供的表格中有「上游节点」列，映射到 `upstream` 字段。
4. 如果用户没有指定上游，但文本中提到了现有节点名，`auto_connect` 会自动匹配。
5. 调用后检查返回结果中的 `unmatched_upstream` 和 `connections`，向用户报告哪些匹配成功、哪些未匹配到。

## 验证清单

每次新增或修改 MCP 能力后，至少验证：

- MCP 服务能够正常启动并连接主服务
- MCP 客户端能够获取最新工具列表（当前 10 个：`list_canvases` / `open_canvas` / `create_prompt_node` / `get_selected_node` / `update_prompt_node` / `get_selected_nodes` / `batch_update_nodes` / `batch_create_nodes` / `arrange_nodes` / `update_node_positions`）
- 工具名称、参数和返回结构与实际实现一致
- 创建或修改节点后已正确落盘
- 当前打开的画布能够实时更新
- `batch_create_nodes` 在智能画布上创建节点成功，在普通画布上返回 400 错误
- `batch_create_nodes` 的 `auto_connect=True` 能正确匹配并创建连线
- `batch_update_nodes` 的 `deep_merge` 只修改传入字段，不触动其他字段
- `get_selected_nodes` 在无人框选时返回空数组及友好提示
- 写操作令牌与主服务一致，令牌错误时返回 401
- 节点失败、服务断开和保存失败都有清晰反馈
- 中文标题和提示词不存在乱码或替换字符

## 技能维护与同步规则

本目录是无限画布 MCP 技能的维护源目录：

`无限画布/Mcp 技能/`

以后新增、修改或删除无限画布 MCP 功能时，必须首先更新本目录中的 `SKILL.md`。不要只修改某个 AI 客户端自己的技能副本。

推荐同步流程：

1. 在 `无限画布/Mcp 技能/SKILL.md` 更新技能内容。
2. 校验 frontmatter、工具名称、参数、返回值、使用规则和验证清单。
3. 将该版本同步复制到 `.trae/skills/canvas-mcp/SKILL.md` 或其他 AI 客户端对应的技能目录。
4. 重新加载目标 AI 客户端的技能。
5. 执行一次 MCP 工具发现和端到端验证。
6. 确认客户端副本与本目录版本一致。

当维护源目录与客户端副本内容不一致时，以 `无限画布/Mcp 技能/SKILL.md` 为准。其他 AI 在更新技能前，也应先读取本目录中的最新版，完成修改后再同步到各客户端，避免多个副本分别演进而产生不一致。

## 安全与稳定性要求

- 不在技能中写入令牌、密码、Cookie、私有地址或个人数据。
- 写操作前必须确认目标画布和节点。
- 空选择 / 空集合不得执行写操作。
- 避免对同一画布发起过多并发写入。
- 保存失败时不得向用户宣称操作成功。
- 工具调用结束后必须重新读取数据进行验证。
- 未实现的 MCP 工具只能作为规划说明，不得当作现有能力调用。
- 禁止把访问令牌、用户隐私数据或一次性任务结果写入技能文件。