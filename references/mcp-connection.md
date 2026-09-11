# 生财 MCP 连接流程

官方说明页：<https://scys.com/onepage/mcpHelp>；接入页：<https://scys.com/mcp>。

## 目标与前提

- 服务名：`scys-mcp`
- 生产地址：`https://mcp.scys.com/shengcai-web/mcp`
- 协议：MCP Stateless Streamable HTTP
- 授权服务器：`https://mcp.scys.com/mcp-oauth`
- 已**全量开放**：OAuth 登录授权即可接入，不再以内测白名单为主要限制
- 授权后 **59 个工具**（实测），可做范围随账号权限
- 两种凭据方式：
  - **OAuth**（首选）：每台设备各自授权，机器可轮换，适合支持 OAuth 的宿主
  - **手动密钥**（官方 API 名 `manual-key`）：给不支持 OAuth 的宿主兜底，长效

## 授权操作规范

**用户已明确确认的工作方式：需要授权时，直接把授权链接给用户，用户只在浏览器点确认。**

- 生成授权链接后同时启动本机 loopback 监听接收回调，用户不需要复制 authorization code、回调地址、JSON、命令或第二段提示词。
- 只有无本地浏览器的服务器宿主例外，见「C. 无浏览器宿主」。
- 授权请求**必须携带 `resource` 参数**（RFC 8707 资源指示器），值为 `https://mcp.scys.com/shengcai-web/mcp`。**缺少该参数会直接返回 HTTP 400 `invalid_request`**，且发生在生成重定向之前 —— 浏览器里看不到任何可授权的页面。
- token 交换同样建议带上 `resource`。
- 全程不回显、不记录、不写入任务产物：access_token、refresh_token、authorization code、code_verifier、手动密钥、Cookie、callback URL。

可用的端点（来自授权服务器元数据，实测）：

| 端点 | 值 |
| --- | --- |
| 保护资源元数据 | `https://mcp.scys.com/.well-known/oauth-protected-resource` |
| 授权服务器元数据 | `https://mcp.scys.com/mcp-oauth/.well-known/oauth-authorization-server` |
| 授权 | `https://mcp.scys.com/mcp-oauth/authorize` |
| 换取 token | `https://mcp.scys.com/mcp-oauth/token` |
| 动态客户端注册 | `https://mcp.scys.com/mcp-oauth/register` |
| 撤销 | `https://mcp.scys.com/mcp-oauth/revoke` |

关键能力：`registration_endpoint` 支持**动态客户端注册**（无需预置 client_id）；`token_endpoint_auth_methods_supported` 为 `["none"]`（公开客户端，无需 client_secret）；`code_challenge_methods_supported` 为 `["S256"]`；`grant_types_supported` 含 `authorization_code` 与 `refresh_token`。

未授权访问 MCP 端点会返回 `401` 并带 `WWW-Authenticate: Bearer resource_metadata="…", scope="mcp"`，可据此定位授权服务器。

## 凭据与续期

- **`refresh_token` 是轮换式的**：每次刷新都会返回一个新的，旧的同时作废。刷新成功后**必须回写**新的 refresh_token，否则下一次刷新失败。
- **不要并发刷新**：两个进程同时刷会互相作废。由单一进程或单一计划任务负责。
- access_token 有效期 **3600 秒（1 小时）**。
- 手动密钥的接口在会员侧：`/shengcai-web/client/mcp/manual-keys`、`/manual-key/create`、`/manual-key/revoke`。界面文案不含「密钥」字样，按字面找不到时按这些接口名推断所在页面。

## 按宿主选择接入方式

| 宿主情形 | 接入方式 |
| --- | --- |
| 支持 OAuth 的本地宿主（Codex、Claude 桌面等） | A. 宿主自带 OAuth |
| dsh（MCP 插件只支持静态 header，无 OAuth） | B. 本机完成 PKCE + 定时刷新回写配置 |
| 服务器 agent、本地无浏览器 | C. 授权链接带回 |

### A. Codex 等支持 OAuth 的宿主

1. 确认宿主确实为该客户端，并识别原生 Windows、WSL、macOS 或 Linux。配置、CLI 与 OAuth 必须位于同一环境；禁止跨 Windows 用户目录和 WSL Home 写入。
2. 定位该宿主实际使用的可执行文件绝对路径，之后始终使用该路径。执行 shell 前关闭 xtrace。
3. 将服务名与地址视为纯数据，使用结构化进程参数数组，不拼接 shell 命令，不依赖引号、续行或变量展开。
4. 先运行 `[exe, "mcp", "get", "scys-mcp"]`；仅当连接不存在时运行 `[exe, "mcp", "add", "scys-mcp", "--url", "https://mcp.scys.com/shengcai-web/mcp", "--auth", "oauth"]`。已有连接地址与 auth 正确时保留原配置。
5. 宿主没有 CLI 但有官方 MCP 设置界面或 API 时，在同一配置域完成等价操作；不得编造命令。
6. 登录前确认是否已有等待中的授权流程；明确未认证且无活动流程时才登录，**本次最多一次 OAuth**。
7. 打开本机浏览器并等待用户确认授权，由宿主自动接收 loopback 回调。
8. 成功后提醒用户重启当前会话一次；重启后用一次无副作用的只读工具验证。旧会话探测失败不得再次打开浏览器。

### B. dsh —— 实测可行方案

dsh 的 MCP 插件（`@deepseek-ai/dsh-mcp-client` 与 `@yilinxiao/dsh-mcp-lazy`）**都只支持静态 `headers`，全包没有 OAuth 代码**，无法自动刷新。因此走「本机完成 PKCE + 定时刷新回写配置」：

1. 注册公开客户端并完成 PKCE（授权请求带 `resource`），把 token 存到宿主目录，例如 `$DSH_HOME/.scys-mcp-oauth.json`。
2. 在 `$DSH_HOME/cordis.patch.yml` 追加插件行。**优先用 `@yilinxiao/dsh-mcp-lazy`**：它按需披露工具 schema，59 个工具不会常驻上下文。

```yaml
- insert:
    - id: mcp-scys
      name: '@yilinxiao/dsh-mcp-lazy'
      config:
        transport: streamable-http
        serverName: scys-mcp
        url: https://mcp.scys.com/shengcai-web/mcp
        headers:
          Authorization: Bearer <access_token>
        routingHints: ["生财", "生财有术", "风向标", "精华帖", "深海圈", "航海", "圈友"]
        warmIdleMs: 300000
```

3. 写一个续期脚本，读取 refresh_token 换新 token，**同时回写 token 文件与上面那一行 Authorization**。patch 层是热重载的，改写即触发断开重连，**不需要重启 dsh**。
4. 用单一计划任务（例如每 45 分钟）调用该脚本。工具名形如 `mcp__scys-mcp__<工具名>`。
5. 验证：宿主里用一次无副作用的只读工具，例如 `getMyPoints`。

patch 层语义：`insert` 新增条目；条目替换会替换目标的整个 `config`（要重述保留字段）；`!!js` 在启动时插值；profile 级先应用、home 级后应用且优先级更高。空文件或只含注释会导致启动失败，禁用该层请写 `[]`。

**替代方案**：若宿主完全不接受本机脚本或计划任务，改用官方手动密钥填进 `headers`，一次配置长期有效。

### C. 无浏览器宿主

官方流程就是复制链接：服务器上的 agent 生成授权链接 → 用户在本地电脑打开确认 → 浏览器跳到 `localhost` 开头、本地打不开的地址 → 把该链接原样复制贴回会话，由 agent 完成接入。这是唯一允许用户复制回调地址的场景；仍不得把它写入任务产物或长期日志。

## 调用额度与数据时效

- 按账号套餐分级限流，默认套餐约**每分钟 20 次**（信任／内部套餐更高）。批量任务自行加 sleep 间隔，不要开多个并行子 agent 撞额度。
- `contentSearch` 不支持精简模式、返回完整正文，`pageSize` 压到个位数；`searchTopic` 支持精简模式，适合大范围扫描。
- 站内内容**不是实时同步**：「全部帖子」可能停在前一天，属正常现象，不是限流。遇到数据不全时如实说明时间窗，不要反复重试刷取。
- 默认只读更安全。点赞、投锚、收藏是真实写操作；不需要时明确按只读执行。

## 能力概览

- **内容搜索与阅读**：帖子、精华、中标、主题、风向标、广场、详情与评论。
- **用户公开资料与个人数据**：用户检索、公开主页、关注与粉丝、公开评论动态、本人足迹、龙珠／碎片／术值、权益、TokenRank 用量与榜单。
- **航海**：项目、手册、高手领航、问答、作业、本人报名、地图进度与任务产出。自助授权**不含**「全员提交台账」这类内部运营权限，但可查页面本来对当前用户可见的全部作业（含真实提交者昵称）。
- **深海圈**：本人已加入圈内公开内容、评论、课程、章节目录、正文与学习进度。
- **聚会与项目库**：公开聚会、组局官、项目案例、工具、详情与条件筛选。
- **内容形态**：站内内容，含所带飞书文档全文。
- **社区互动**：以当前绑定账号点赞、取消点赞、收藏、取消收藏、投锚。投锚有每日上限并消耗锚点。当前不包含新建、上传或发布帖子。
- **AI 顾问**：AI 亦仁与 AI 刘小排会诊；这两个工具走默认 scope，授权时自动开通。

## 工具名索引（实测 59 个）

工具名随版本变化，始终以当前 `mcp__<serverName>__*` 目录为准。以下为实测清单，用于发现而非硬编码依赖。

| 用途 | 工具 |
| --- | --- |
| 内容检索 | `contentSearch` `searchTopic` `topicDetail` `pageTopicComment` `listMenu` |
| 用户 | `userSearch` `getProfileInfo` `getUserComments` `getUserRelationList` |
| 项目库与工具 | `projectLibSearch` `projectLibList` `projectLibDetail` `searchProjectCases` `listProjectCaseFilters` `searchProjectTools` `getProjectToolDetail` |
| 航海 | `activityList` `activitySearch` `activityManualToc` `activityManualDetail` `activityManualSearch` `activityPilotSearch` `listMyActivities` `getMyActivityProgress` `searchMyActivityOutputs` `searchVisibleActivitySubmissions` `searchVisibleActivityQa` `pageActivityCourseComments` |
| 深海圈 | `listMyDeepseaCommunities` `searchDeepseaPublicContent` `getDeepseaContentDetail` `pageDeepseaContentComments` `searchDeepseaCourses` `getDeepseaCourseDetail` `searchDeepseaCourseChapters` `getDeepseaCourseChapterContent` `pageDeepseaCourseComments` |
| 聚会 | `searchParties` `getPartyDetail` |
| 个人数据 | `getMyBenefits` `getMyPoints` `listMyTopicFootprints` |
| AI 顾问 | `startAiYiRenChat` `queryAiYiRenChat` `qaHistoryList` `startLiuXiaoPaiChat` `queryLiuXiaoPaiChat` `liuXiaoPaiHistoryList` |
| 互动（写操作） | `topicLike` `topicUnlike` `addFavorite` `deleteFavorite` `addCoinToTopic` |
| 命名空间工具 | `co-creation__listMyFeedbacks` `co-creation__getMyFeedback` `tokenrank__queryMyTokenrank` `tokenrank__queryPublicTokenrank` `tokenrank__setFollowStatus` `ai__listAiFeedItems` |
