# graph_docker

轻量的 Microsoft Graph 保活工具（自维护版）。

> 维护说明
>
> 本仓库由 `Spittingjiu/ms_graph_docker` 迁移而来，后续功能迭代、修复与发布由本仓库独立维护。

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

打开运维菜单。

---

## 菜单功能（gb / install.sh）

- 安装/更新并一键初始化
- 仅安装/更新仓库
- 首次授权向导（auth）
- 一键全流程初始化（init）
- 自检（check，末尾给明确结论）
- 启动服务（up）
- 查看日志（logs）
- 一键清除（clean）
- 卸载并清理（uninstall）

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
```

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
