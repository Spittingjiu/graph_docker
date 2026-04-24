# graph_docker

轻量的 Microsoft Graph 保活工具（自维护版）。

> 转载与二次维护说明
>
> 本仓库由 `Spittingjiu/ms_graph_docker` 迁移而来，原始项目来源：
> - 原仓库（fork 来源）：`https://github.com/comdotwww/ms_graph_docker`
> - 迁移来源（本账号 fork）：`https://github.com/Spittingjiu/ms_graph_docker`
>
> 从本仓库开始，后续功能迭代、修复与发布将由我们独立维护。

---

## 这版解决了什么

- 不再需要下载 `rclone`
- 新增首次授权向导（`./graphctl auth`）
- 新增一键初始化（`./bootstrap.sh`）
- 新增自检命令（`./graphctl check`）
- 默认 `lite` 模式，仅需最小权限（`User.Read + offline_access`）

---

## 快速开始（3 步）

### 1) 准备配置

```bash
cp .env.example .env
# 编辑 .env 填 CLIENT_ID / CLIENT_SECRET
```

### 2) 首次授权（替代 rclone）

```bash
./graphctl auth
```

执行后会打印授权链接：
- 浏览器打开并登录同意
- 复制回跳 URL 粘贴回终端
- 自动写入 `token.txt`

### 3) 启动

```bash
./bootstrap.sh
```

或：

```bash
./graphctl up
```

---

## 常用命令

```bash
./graphctl up        # 启动
./graphctl down      # 停止
./graphctl logs      # 看日志
./graphctl auth      # 重新授权
./graphctl check     # 网络/容器自检
```

---

## 必填参数说明（.env）

- `CLIENT_ID`：Entra 应用 ID
- `CLIENT_SECRET`：应用密钥

推荐保留默认：
- `TENANT_ID=common`
- `GRAPH_API_PROFILE=lite`
- `AUTH_SCOPES=offline_access openid profile User.Read`

可选：
- `TG_BOT_TOKEN` + `TG_SEND_ID`：开启 Telegram 通知
- `IS_API_URLS_EXTEND=true`：调用补充 API（需额外权限）

---

## 最小权限建议（自己用）

这版默认 `lite` 模式只调 `/me`，建议先只给：
- `User.Read`
- `offline_access`

后续若要开 `full` 或补充 API，再按需加权限，避免一开始就全量申请。

---

## 目录说明

- `main.py`：主调用流程
- `update.py`：token 刷新与授权交换
- `auth_cli.py`：首次授权向导
- `graphctl`：常用运维命令
- `bootstrap.sh`：一键初始化
- `.env.example`：配置模板

---

## 注意

- 首次授权后会生成/更新 `token.txt`（敏感文件，勿外泄）
- 若容器网络 DNS 不稳，建议保持 `network_mode: host`（本仓库默认已开启）
