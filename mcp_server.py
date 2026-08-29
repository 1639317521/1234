# -*- coding: utf-8 -*-
"""
无限画布 · MCP 服务器
======================
让外部 AI（Claude Desktop / Cursor / 任意 MCP 客户端）通过官方 mcp 协议控制画布节点。

运行方式:
    python mcp_server.py

连接地址:
    SSE  http://127.0.0.1:8765/sse

它通过 HTTP 调用本机 main.py（默认 http://127.0.0.1:3000）读写画布；
main.py 会把新节点写盘并广播到已打开画布的 WebSocket，前端自动渲染。

环境变量:
    WUCANVAS_MCP_BASE_URL   指向 main.py 的地址，默认 http://127.0.0.1:3000
    WUCANVAS_MCP_PORT       MCP 服务端口，默认 8765
    MCP_API_TOKEN           与 main.py 的 MCP_API_TOKEN 保持一致，默认 wucanvas-mcp-default-token
"""
import os
import json
import httpx
from mcp.server.mcpserver import MCPServer

_MAIN_DEFAULT_PORT = os.environ.get("WUCANVAS_PORT", "3000")
BASE_URL = os.environ.get("WUCANVAS_MCP_BASE_URL", f"http://127.0.0.1:{_MAIN_DEFAULT_PORT}").rstrip("/")
MCP_API_TOKEN = os.environ.get("MCP_API_TOKEN", "wucanvas-mcp-default-token")
PORT = int(os.environ.get("WUCANVAS_MCP_PORT", "8765"))

mcp = MCPServer(
    name="wucanvas-mcp",
    title="无限画布 · MCP",
    version="0.1.0",
    instructions=(
        "无限画布 MCP 服务 —— 智能画布专用。先调 list_canvases 找到 canvas_id；"
        "查看节点用 open_canvas；新建智能节点用 batch_create_nodes（节点自动避让不重叠，支持表格批量创建+自动连线）；"
        "若用户说\"改当前选中那个节点\"，先调 get_selected_node 获取用户当前选中的节点，"
        "再用 update_prompt_node 修改该节点的提示词文本。"
        "若用户说\"批量修改框选的节点\"，先调 get_selected_nodes 获取多选节点，"
        "再用 batch_update_nodes 批量修改设置（如改比例、改标题、改提示词等）。"
        "创建后若新节点位置不整齐，用 arrange_nodes 传入刚创建的节点 ID 列表，只整理这批节点，不碰其他节点。"
        "若用户说\"排布节点\"\"按左中右排列\"\"调整布局\"，用 update_node_positions 传入所有节点的 id/x/y 批量设置位置。"
        "改动自动推送前端，不触发全量重载，不中断生成。"
    ),
)


@mcp.tool()
async def list_canvases() -> str:
    """列出所有画布（id / title / kind），供后续操作定位 canvas_id。"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/canvases")
        r.raise_for_status()
        data = r.json().get("canvases", [])
    records = [{"id": c.get("id"), "title": c.get("title"), "kind": c.get("kind")} for c in data]
    return json.dumps(records, ensure_ascii=False, indent=2)


@mcp.tool()
async def open_canvas(canvas_id: str) -> str:
    """打开指定画布，返回其节点概览（每个节点的 id / type / x / y / 简短文本）。"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/canvases/{canvas_id}")
        if r.status_code == 404:
            return f"画布不存在或已删除: {canvas_id}"
        r.raise_for_status()
        canvas = r.json().get("canvas", {})
    nodes = canvas.get("nodes", [])
    summary = [{
        "id": n.get("id"),
        "type": n.get("type"),
        "x": n.get("x"),
        "y": n.get("y"),
        "text": (n.get("text") or "")[:60],
    } for n in nodes]
    return json.dumps({
        "canvas_id": canvas.get("id"),
        "title": canvas.get("title"),
        "node_count": len(summary),
        "nodes": summary,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def create_prompt_node(canvas_id: str, text: str, x: float = 0.0, y: float = 0.0) -> str:
    """在指定画布上新建一个提示词节点，即时显示到已打开的画布界面。"""
    payload = {
        "canvas_id": canvas_id,
        "text": text,
        "x": x,
        "y": y,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/prompt-node", json=payload)
    if r.status_code != 200:
        return f"创建失败({r.status_code}): {r.text}"
    node = r.json().get("node")
    return json.dumps({"ok": True, "node": node}, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_selected_node(canvas_id: str) -> str:
    """返回画布上当前被选中的节点详情；用户说\"改选中节点\"时用来定位。"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/canvases/{canvas_id}/mcp-selection")
    if r.status_code == 404:
        return f"画布不存在或已删除: {canvas_id}"
    r.raise_for_status()
    data = r.json()
    node = data.get("node")
    if not node:
        return json.dumps({
            "canvas_id": canvas_id,
            "selected_node": None,
            "center": {"x": data.get("x"), "y": data.get("y")},
            "hint": "画布上当前没有选中的节点，请先在画布界面点选一个节点，再重试。",
        }, ensure_ascii=False, indent=2)
    return json.dumps({"canvas_id": canvas_id, "selected_node": node}, ensure_ascii=False, indent=2)


@mcp.tool()
async def update_prompt_node(canvas_id: str, node_id: str, text: str) -> str:
    """修改画布上指定节点的提示词文本（node_id 由 get_selected_node 或 open_canvas 获得）。"""
    payload = {
        "canvas_id": canvas_id,
        "node_id": node_id,
        "text": text,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/prompt-node/update", json=payload)
    if r.status_code == 200:
        return json.dumps({"ok": True, "node": r.json().get("node")}, ensure_ascii=False, indent=2)
    if r.status_code == 404:
        return f"节点不存在({r.status_code}): {r.text}"
    return f"修改失败({r.status_code}): {r.text}"


@mcp.tool()
async def get_selected_nodes(canvas_id: str) -> str:
    """返回画布上当前被选中的多个节点详情；用户说\"批量修改框选的节点\"时用来定位。"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/canvases/{canvas_id}/mcp-multi-selection")
    if r.status_code == 404:
        return f"画布不存在或已删除: {canvas_id}"
    r.raise_for_status()
    data = r.json()
    nodes = data.get("nodes") or []
    if not nodes:
        return json.dumps({
            "canvas_id": canvas_id,
            "selected_nodes": [],
            "center": {"x": data.get("x"), "y": data.get("y")},
            "hint": "画布上当前没有选中的节点，请先在画布界面框选多个节点，再重试。",
        }, ensure_ascii=False, indent=2)
    return json.dumps({"canvas_id": canvas_id, "selected_nodes": nodes}, ensure_ascii=False, indent=2)


@mcp.tool()
async def batch_update_nodes(canvas_id: str, node_ids: list, updates: dict) -> str:
    """批量修改节点的字段/设置。例如把多个节点统一改成 16:9。
    用法示例：
    - 改比例:   node_ids=[...], updates={"runSettings": {"ratio": "wide", "resolution": "4k"}}
    - 改标题:   node_ids=[...], updates={"displayTitle": "新标题"}
    - 改提示词: node_ids=[...], updates={"promptDraftText": "新提示词"}
    """
    payload = {
        "canvas_id": canvas_id,
        "node_ids": node_ids,
        "updates": updates,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/nodes/batch-update", json=payload)
    if r.status_code == 200:
        return json.dumps({"ok": True, "updated_count": r.json().get("updated_count"), "nodes": r.json().get("nodes")}, ensure_ascii=False, indent=2)
    if r.status_code == 404:
        return f"未找到匹配的节点({r.status_code}): {r.text}"
    return f"批量更新失败({r.status_code}): {r.text}"


@mcp.tool()
async def batch_create_nodes(canvas_id: str, nodes: list, auto_connect: bool = False) -> str:
    """批量创建智能画布节点（smart-image）。支持从表格数据批量创建，可选自动连线到上游节点。
    每个节点包含 text（提示词正文）和可选的 title（节点标题）、upstream（上游节点名称，用于自动连线）。
    auto_connect=True 时自动匹配上游节点并建立 flow 连线。
    匹配规则：upstream 字段 > 文本中匹配 displayTitle/title。
    节点位置自动避让现有节点，不会重叠。
    """
    payload = {
        "canvas_id": canvas_id,
        "nodes": nodes,
        "auto_connect": auto_connect,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/nodes/batch-create", json=payload)
    if r.status_code == 200:
        return json.dumps(r.json(), ensure_ascii=False, indent=2)
    return f"批量创建失败({r.status_code}): {r.text}"


@mcp.tool()
async def arrange_nodes(canvas_id: str, node_ids: list) -> str:
    """整理指定的节点为整齐网格布局，消除它们之间的重叠，不触动其他节点。
    适合 batch_create_nodes 创建后调用，传入返回的 created[].id 列表，让新节点排齐。
    其他已有节点保持原位不动。
    """
    payload = {
        "canvas_id": canvas_id,
        "node_ids": node_ids,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/nodes/arrange-specified", json=payload)
    if r.status_code == 200:
        return json.dumps(r.json(), ensure_ascii=False, indent=2)
    return f"整理失败({r.status_code}): {r.text}"


@mcp.tool()
async def update_node_positions(canvas_id: str, nodes: list) -> str:
    """批量更新节点位置/字段。每个节点指定 id 和要修改的字段（如 x, y, displayTitle 等）。
    nodes 格式: [{id: "节点ID", x: 100, y: 200}, ...]
    支持任意字段，如 {id: "...", displayTitle: "新标题", "runSettings": {"ratio": "wide"}}
    前端原地更新，不触发全量重载，不改变视口，不中断计时器。
    """
    payload = {
        "canvas_id": canvas_id,
        "nodes": nodes,
        "token": MCP_API_TOKEN,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/api/mcp/nodes/update-positions", json=payload)
    if r.status_code == 200:
        return json.dumps(r.json(), ensure_ascii=False, indent=2)
    return f"更新位置失败({r.status_code}): {r.text}"


def asgi_app():
    """返回可挂载/运行的 ASGI 应用（SSE 传输）。"""
    return mcp.sse_app(host="127.0.0.1")


if __name__ == "__main__":
    import uvicorn
    print("无限画布 MCP 服务启动: http://127.0.0.1:%d/sse  (主服务: %s)" % (PORT, BASE_URL))
    uvicorn.run(asgi_app(), host="0.0.0.0", port=PORT, log_level="info")