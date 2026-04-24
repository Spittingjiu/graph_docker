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

## GRAPH_BOOTSTRAP_TOKEN 怎么获取（超详细）

这个 token 是给 `tenant-init` 用的，作用是：
- 自动创建 Entra 应用
- 自动配置 Graph 权限
- 自动生成 CLIENT_SECRET
- 自动写入 `.env`

如果没有这个 token，自动化就做不了上述动作。

### 前提条件

你登录的账号需要有“应用注册管理”能力（比如全局管理员/应用管理员）。
如果权限不足，后面会报 `403 Authorization_RequestDenied`。

---

### 方式 A：Azure CLI（推荐，最简单）

#### 第 1 步：安装 Azure CLI

- Ubuntu / Debian：
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

- RHEL / CentOS：
```bash
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo dnf install -y https://packages.microsoft.com/config/rhel/9.0/packages-microsoft-prod.rpm
sudo dnf install -y azure-cli
```

- macOS（brew）：
```bash
brew update && brew install azure-cli
```

装完先检查：
```bash
az version
```

#### 第 2 步：登录 Azure

```bash
az login
```

会弹浏览器登录。请用有管理权限的账号登录。

> 如果是服务器无桌面环境：
> 使用 `az login --use-device-code`，按提示去浏览器输入设备码登录。

#### 第 3 步：获取 Graph Bootstrap Token

```bash
export GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)"
```

#### 第 4 步：确认变量已生效

```bash
echo "$GRAPH_BOOTSTRAP_TOKEN" | cut -c1-30
```

能看到一串 `eyJ...` 开头字符就对了（不要完整打印到公开环境）。

#### 第 5 步：直接跑一键脚本

```bash
./setup_all_in_one.sh
```

---

### 方式 B：手动注入（已有 token 时）

如果你已经从别的系统拿到了 Graph Access Token，直接：

```bash
export GRAPH_BOOTSTRAP_TOKEN='eyJ...'
./setup_all_in_one.sh
```

---

### 常见报错与处理

- `az: command not found`
  - 说明 Azure CLI 没安装，先执行上面的安装命令。

- `Please run 'az login'`
  - 说明未登录，先执行 `az login`。

- `403 Authorization_RequestDenied`
  - 当前账号权限不够，换管理员账号登录，或给该账号应用注册管理权限。

- `GRAPH_BOOTSTRAP_TOKEN` 为空
  - 重新执行：
  - `export GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)"`

- 运行一段时间后又失败
  - token 过期了，重新获取一次再运行脚本即可。

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
