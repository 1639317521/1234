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

## 版本管理
- 项目版本以根目录 `VERSION` 第一行为唯一依据，格式使用递增语义版本号 `主版本.次版本.修订号`
- 普通修复和性能优化递增修订号，新功能递增次版本号，不兼容改动递增主版本号
- 禁止使用日期或时间作为版本号；更新时间写入 `static/update-notes.json` 的 `updated_at`，仅作为小字附注
- 每次项目改动前必须使用 `tools/rollback.py save` 建立备份点，修改后同步更新 `VERSION`、更新说明和《本地改动记录.md》
- 回档时使用备份点恢复对应项目文件，确保代码、版本号和更新记录一并回退
