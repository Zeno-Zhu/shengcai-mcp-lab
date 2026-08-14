# 生财 MCP 连接流程（Codex）

官方说明页：<https://scys.com/onepage/mcpHelp>；服务入口：<https://scys.com/mcp>。

## 目标与前提

- 服务名：`scys-mcp`
- 生产地址：`https://mcp.scys.com/shengcai-web/mcp`
- Codex OAuth 客户端标识：`scys-codex`
- 协议：MCP Stateless Streamable HTTP
- 需要用户在浏览器完成一次生财授权；内测访问可能受白名单限制。

此流程仅用于当前 Codex 实际运行环境。它使用 OAuth 2.1 + PKCE，不使用、不要求用户提供静态 MCP Token。浏览器授权、回调接收与凭据持久化由 Codex 完成。下文的参数数组供 Codex 宿主或 Agent 调用，不能当作可直接粘贴到终端的命令。

## 执行规则

1. 先确认当前宿主确实为 Codex，并识别原生 Windows、WSL、macOS 或 Linux。配置、CLI 与 OAuth 必须位于同一环境；禁止跨 Windows 用户目录和 WSL Home 写入。
2. 定位当前宿主实际使用的 Codex 可执行文件绝对路径。之后始终使用该路径，不能因 PATH 改变而切换到另一份安装。执行 shell 前关闭 xtrace。
3. 将服务名和地址视为纯数据。使用可用宿主的结构化进程参数数组，不拼接 shell 命令；不依赖 PowerShell、CMD 或 Bash 的引号、续行或变量展开。
4. 先以参数数组运行：`[codexPath, "mcp", "get", "scys-mcp"]`。仅当连接不存在时，以参数数组运行：`[codexPath, "mcp", "add", "scys-mcp", "--url", "https://mcp.scys.com/shengcai-web/mcp", "--oauth-client-id", "scys-codex"]`。已有连接的地址和 OAuth client id 正确时保留原配置。
5. 若当前 Codex 宿主没有可用 CLI，但提供官方 MCP 设置界面或宿主 API，则在同一配置域完成等价操作；不得编造命令。
6. 在登录前检查认证状态和是否已有等待中的授权流程。只有明确未认证或凭据失效且没有活动流程时，才以参数数组运行：`[codexPath, "mcp", "login", "scys-mcp", "--scopes", "mcp"]`。配置或探测已触发 OAuth 时，只等待该流程；本次最多进行一次 OAuth。
7. 打开本机浏览器并等待用户确认授权。不得要求用户复制 authorization code、callback 地址、JSON、命令或第二段提示词。由当前 Codex 环境自动接收 loopback 回调。
8. OAuth 成功后，只确认登录进程正常退出且配置已持久化。旧会话中不得再做 MCP 状态探测、重复登录或调用 MCP 工具，避免再次触发浏览器授权。
9. 明确提醒用户重启当前 Codex 会话或客户端一次。重启后列出 `scys-mcp` 工具，并调用一个无副作用的只读生财工具验证。首次连接稍慢时等待，不重新登录。
10. 连接流程结束时只报告：Codex 运行环境与版本、修改的配置位置、一次 OAuth 是否成功、已明确需要重启当前会话。不得回显 access token、refresh token、authorization code、code verifier、client secret、Cookie 或 callback URI。

## MCP 能力概览

在授权与访问范围内，服务可用于：

- 内容搜索与阅读：帖子、精华、中标、主题、风向标、广场、详情与评论。
- 用户公开资料与个人数据：用户检索、公开主页、评论动态、本人足迹、积分和权益。
- 航海：项目、手册、高手领航、问答、作业、本人报名、地图进度和任务产出。
- 深海圈：本人已加入圈内公开内容、评论、课程、章节目录、正文与学习进度。
- 聚会与项目库：公开聚会、项目案例、详情和筛选。
- 社区互动：点赞、收藏和投锚等以当前绑定账号执行的动作；当前不包含新建、上传或发布帖子。
- AI 顾问：AI 亦仁与 AI 刘小排的针对性会诊。

始终根据当前工具定义与用户权限决定可做范围。读取优先；互动动作必须由用户对具体目标明确确认。
