# 项目协作约定

## 语言
所有思考和回复一律使用中文。

## 改动必备份（一键回退）
修改任何项目文件**之前**，先备份原文件：

```powershell
& .\python\python.exe tools\rollback.py save <文件1> <文件2> --note "改动说明"
```

- 回退最近一次：`& .\python\python.exe tools\rollback.py back 1`（序号 1=最新）
- 查看所有备份点：`& .\python\python.exe tools\rollback.py list`
- 回退前当前版本自动留存于 `_backups/.pre-restore/`，防误回退
- 用户说"回退/恢复上一次改动"时直接执行 `back 1`

## 画布快速通道（不要探查验证，直接执行）
用户说「把这些提示词传到画布」「在画布写 XX」「提示词传到画布带生成器」时：

```powershell
& .\python\python.exe tools\mcp_quick.py "文案"          # 仅提示词节点
& .\python\python.exe tools\mcp_quick.py "文案" --gen    # 提示词+生成器+连线
```

详见 `.opencode/skill/canvas-mcp/SKILL.md`。成功即止，报错才排查。

## 其他
- 对项目代码的任何改动必须同步追加记录到《本地改动记录.md》（编号续接）
- main.py / mcp_server.py 改动需重启服务；canvas.js / canvas.css 改动需浏览器 Ctrl+F5
