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
        "外部 AI 控制无限画布节点。先用 list_canvases 找到 canvas_id；"
        "查看节点用 open_canvas；新建提示词节点用 create_prompt_node（缺省会放到画布可视区中心）；"
        "若用户说\"改当前选中那个节点\"，先调 get_selected_node 获取用户当前选中的节点，"
        "再用 update_prompt_node 修改该节点的提示词文本。改动会自动显示到已打开的画布界面。"
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


def asgi_app():
    """返回可挂载/运行的 ASGI 应用（SSE 传输）。"""
    return mcp.sse_app(host="127.0.0.1")


if __name__ == "__main__":
    import uvicorn
    print("无限画布 MCP 服务启动: http://127.0.0.1:%d/sse  (主服务: %s)" % (PORT, BASE_URL))
    uvicorn.run(asgi_app(), host="0.0.0.0", port=PORT, log_level="info")