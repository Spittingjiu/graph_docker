# graph_docker

轻量、可靠的 Microsoft Graph API 保活与开发活跃度维护工具（自维护版）。

> **项目说明与来源归属**
>
> 本项目由 `Spittingjiu/ms_graph_docker` 全面重构迁移而来，原始项目来源：
> - 原仓库（fork 来源）：`https://github.com/comdotwww/ms_graph_docker`
> - 迁移来源（本账号 fork）：`https://github.com/Spittingjiu/ms_graph_docker`
>
> 本仓库针对原版的无序无限重启、Telegram 刷屏、Token 单文件挂载丢失、高频重复鉴权等痛点进行了核心重构与独立维护。

---

## 核心特性与优化升级

- **智能常驻调度（Daemon 模式）**：内置智能间隔循环（默认 6 小时 ± 30 分钟随机浮动），进程常驻休眠，彻底消除 Docker `restart: unless-stopped` 导致的每 2 分钟极速死循环重启。
- **Token 内存缓存机制**：微软 `access_token` 在 60 分钟有效期内直接复用，避免每次 API 调用都发起多余的 OAuth 刷新请求（减少 90% 鉴权流量）。
- **聚合消息与富文本通知**：Telegram 通知全面采用 HTTP POST + JSON 结构，支持富文本汇总排版；单次巡检仅在完成时发送一封汇总报告（轮数、成功数、失败数、耗时、下次执行时间），告别刷屏与字符截断。
- **调用序列随机化与 429 规避**：每次循环对 API 端点进行真随机乱序请求，模拟真实人类开发活动；深度支持 HTTP 429 限流检测并按 `Retry-After` 头优雅退避。
- **持久化目录挂载防丢失**：规范使用 `./data` 目录持久化 `token.txt`，彻底解决 Docker 单文件挂载因 Inode 漂移导致的宿主机与容器脱节问题。
- **一键运维与测试**：内置 `graphctl test` 快速测试单轮巡检，`graphctl status` 查看容器、Token 及日志状态。

---

## 快速安装与使用（推荐）

在 Linux VPS 终端直接执行一键脚本：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Spittingjiu/graph_docker/master/install.sh)"
```

安装完成后，可随时在终端输入快捷命令：

```bash
gb
```

即可打开交互式运维菜单（会自动检测并提示版本更新）。

---

## 常用命令一览

除了交互式菜单，也可以直接通过 `gb` 或 `./graphctl` 执行快捷指令：

```bash
gb test           # 单次批处理测试（即时运行一轮并输出完整日志，不进入长休眠）
gb status         # 查看当前容器运行状态、Token 状态与最近日志
gb up             # 启动后台守护容器（自动完成增量构建）
gb down           # 停止并移除容器
gb logs [行数]     # 实时查看容器运行日志（默认 100 行，如: gb logs 200）
gb auth           # 运行交互式首次授权向导（获取 refresh_token）
gb init           # 全自动化创建 Azure AD 应用并初始化 .env（需 GRAPH_BOOTSTRAP_TOKEN）
gb check          # 执行环境配置与端点网络连通性自检
gb clean          # 一键完全清理本地数据与容器（可选删除云端应用）
```

---

## 配置说明（.env）

通过复制 `.env.example` 为 `.env` 进行自定义配置：

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `RUN_MODE` | `loop` | 运行模式：`loop` 为内置常驻调度，`once` 为执行一次后退出（适合外部 crontab） |
| `RUN_INTERVAL_HOURS` | `6` | 常驻模式下每轮执行间隔（小时） |
| `JITTER_MINUTES` | `30` | 随机时间浮动（分钟），即在基准间隔上浮动模拟真实活动 |
| `TG_NOTIFY_MODE` | `summary` | Telegram 通知模式：`summary`（每轮汇总报表）、`error`（仅报错发送）、`all`（每接口均发） |
| `TG_BOT_TOKEN` | 留空 | Telegram 机器人 Token（与 `TG_SEND_ID` 搭配使用） |
| `TG_SEND_ID` | 留空 | Telegram 接收者 User ID / Chat ID |
| `CLIENT_ID` | 必填 | Azure AD 应用程序 (客户端) ID |
| `CLIENT_SECRET` | 必填 | Azure AD 客户端密码 (Secret) |
| `GRAPH_API_PROFILE` | `full` | API 策略模式：`full`（全量接口）或 `lite`（仅 User.Read 极简模式） |

---

## 目录结构

```text
graph_docker/
├── graphctl           # 底层命令行运维工具
├── install.sh         # 一键菜单入口（已映射全局 gb 别名）
├── setup_all_in_one.sh# 全自动初始化脚本
├── main.py            # 主程序（包含调度守护、API 乱序调用、汇总统计）
├── update.py          # Token 交换、刷新与安全持久化
├── SendMsg.py         # Telegram POST 富文本聚合通知模块
├── auth_cli.py        # 终端交互式 OAuth 授权向导
├── tenant_init.py     # Microsoft Graph 自动化创建应用与凭据
├── Dockerfile         # 采用分层缓存优化的轻量 Alpine 镜像
├── docker-compose.yml # 容器编排定义与挂载规则
└── data/              # 持久化数据目录（存储 token.txt）
```

---

## 安全与隐私提醒

- 请妥善保管 `.env` 与 `data/token.txt`，切勿将包含真实 Secret 或 Token 的文件上传至公共 Git 仓库。
- 若登录过程中遇到 `AADSTS50076`，说明租户开启了多因素认证（MFA），在浏览器按照微软指引完成验证即可。
