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

## 最快使用（推荐）

在 VPS 直接执行：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Spittingjiu/graph_docker/master/install.sh)"
```

安装完成后可直接输入：

```bash
gb
```

打开运维菜单（会显示更新状态：有新版本会提示按 2 更新）。

---

## 菜单功能（gb / install.sh）

- 安装/更新并智能处理（优先复用已有 .env/token；缺失才补授权/初始化）
- 仅安装/更新仓库
- 首次授权向导（auth）
- 一键全流程初始化（init）
- 自检（check，末尾给明确结论）
- 启动服务（up）
- 查看日志（logs）
- 一键清除（clean）
- 卸载并清理（uninstall）
- 定时保活计划（schedule，含多预设 + 一键清除；支持全天低频随机）

你也可以直接用命令：

```bash
gb install
gb update
gb auth
gb init
gb check
gb up
gb logs 200
gb clean
gb uninstall
gb schedule
gb schedule-show
gb schedule-clear
```

---

## 智能流程规则（核心）

`gb` 菜单选 1 时按下面顺序自动判断：

1) 有 `.env` + `token.txt` → 先校验 token 可用；可用才 `up + check`
2) 有 `.env` 但没 `token.txt` → 自动先 `auth`，再 `up + check`
3) `.env` 也没有 → 执行完整初始化流程（tenant-init）

也就是：优先复用已有配置，没有才问你。

---

## 一键全流程会做什么

`gb init`（或 `./setup_all_in_one.sh`）会自动：

1) 检测 `az`，缺失时询问是否自动安装（Ubuntu/Debian）
2) 自动创建 Entra 应用（可手输应用名；留空则自动生成随机名）并写入 `.env`
3) 暂停等待你完成管理员 consent（必须）
4) 运行首次授权向导，获取并写入 `token.txt`
5) 启动容器
6) 运行自检

---

## GRAPH_BOOTSTRAP_TOKEN（精简版）

如果脚本自动获取失败，可手动导出：

```bash
az login --allow-no-subscriptions
export GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)"
```

然后再跑：

```bash
gb init
```

如果账号在无订阅租户，或需要指定租户：

```bash
az login --tenant <tenant_id> --allow-no-subscriptions
```

---

## 常用清理与重试

- 清理当前安装（仅 graph_docker 相关）：

```bash
gb clean
```

`gb clean` 过程中会询问：是否同时删除云端应用注册（Entra）。
如果你选择 yes，并且已提供 `GRAPH_BOOTSTRAP_TOKEN`，会尝试删除当前 `CLIENT_ID` 对应的云端 application。

- 完整卸载（删除安装目录与快捷命令）：

```bash
gb uninstall
```

---

## 关键文件

- `install.sh`：总入口（菜单 + 子命令）
- `setup_all_in_one.sh`：一键全流程初始化
- `graphctl`：底层运维命令
- `tenant_init.py`：创建应用与写 `.env`
- `auth_cli.py`：首次授权
- `update.py`：token 交换与刷新

---

## 注意事项

- `token.txt`、`.env` 都是敏感信息，勿外泄。
- 若遇到 `AADSTS50076`，是租户要求 MFA，按提示完成即可。
- 默认 `full` 模式；如需最小权限模式请改 `.env` 的 `GRAPH_API_PROFILE=lite`。
