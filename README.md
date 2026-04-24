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
- 新增一键全流程初始化（`./setup_all_in_one.sh`）
- 新增自检命令（`./graphctl check`）
- 默认 `full` 模式（保留原多接口保活策略）

---

## 一键初始化（推荐）

你只需要执行一次：

```bash
./setup_all_in_one.sh
```

脚本会自动完成：
1) 创建 Entra 应用并写入 `.env`
2) 首次授权向导（浏览器登录 + 粘贴回跳 URL）
3) 启动容器
4) 自检

---

## GRAPH_BOOTSTRAP_TOKEN 怎么获取

这个 token 用来调用 Microsoft Graph 管理 API（自动创应用/配权限），推荐用 Azure CLI 获取。

### 方式 A：Azure CLI（推荐）

```bash
az login
export GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)"
```

### 方式 B：手动获取

你也可以从已有管理工具拿到 Graph Access Token，然后：

```bash
export GRAPH_BOOTSTRAP_TOKEN='eyJ...'
```

> 注意：
> - 这个 token 必须是有权限管理应用注册的管理员账号签发。
> - token 有时效，过期后重新获取一次即可。

---

## 兼容分步流程（可选）

```bash
./graphctl tenant-init
./graphctl auth
./bootstrap.sh
```

---

## 常用命令

```bash
./graphctl up        # 启动
./graphctl down      # 停止
./graphctl logs      # 看日志
./graphctl auth      # 重新授权
./graphctl tenant-init # 自动创建应用并写入.env
./graphctl check       # 网络/容器自检
```

---

## 必填参数说明（.env）

- `CLIENT_ID`：Entra 应用 ID
- `CLIENT_SECRET`：应用密钥

推荐保留默认：
- `TENANT_ID=common`
- `GRAPH_API_PROFILE=full`
- `AUTH_SCOPES=offline_access openid profile User.Read`

可选：
- `TG_BOT_TOKEN` + `TG_SEND_ID`：开启 Telegram 通知
- `IS_API_URLS_EXTEND=true`：调用补充 API（需额外权限）

---

## 权限与模式说明

默认是 `full`（保留原策略，多接口调用）。

如果你想用“最小权限模式”，可手动改：
- `.env` 里设 `GRAPH_API_PROFILE=lite`
- 仅给权限：`User.Read` + `offline_access`

如果保持 `full`，请按旧版 README 授予对应 Graph 权限（Mail/Files/Sites/Directory 等），否则部分接口会 403。

---

## 目录说明

- `main.py`：主调用流程
- `update.py`：token 刷新与授权交换
- `auth_cli.py`：首次授权向导
- `graphctl`：常用运维命令
- `bootstrap.sh`：基础启动初始化
- `setup_all_in_one.sh`：一键跑完整流程（建应用+授权+启动+自检）
- `.env.example`：配置模板

---

## 注意

- 首次授权后会生成/更新 `token.txt`（敏感文件，勿外泄）
- 若容器网络 DNS 不稳，建议保持 `network_mode: host`（本仓库默认已开启）
