#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== graph_docker 一键初始化 ==="

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少命令: $1"
    exit 1
  }
}

need_cmd docker
need_cmd python3

if ! docker compose version >/dev/null 2>&1; then
  echo "缺少 docker compose，请先安装。"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 .env"
fi

if [[ -z "${GRAPH_BOOTSTRAP_TOKEN:-}" ]]; then
  if command -v az >/dev/null 2>&1; then
    echo "未检测到 GRAPH_BOOTSTRAP_TOKEN，尝试使用 Azure CLI 自动获取..."
    if ! az account show >/dev/null 2>&1; then
      echo "Azure CLI 尚未登录，正在执行 az login --allow-no-subscriptions..."
      az login --allow-no-subscriptions >/dev/null
    fi
    GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv || true)"
    export GRAPH_BOOTSTRAP_TOKEN
  fi
fi

if [[ -z "${GRAPH_BOOTSTRAP_TOKEN:-}" ]]; then
  cat <<'EOF'
未获取到 GRAPH_BOOTSTRAP_TOKEN。
请二选一：

A) 推荐（Azure CLI）：
  az login --allow-no-subscriptions
  export GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv)"

B) 手动：
  export GRAPH_BOOTSTRAP_TOKEN='eyJ...'

然后重新执行本脚本。
EOF
  exit 1
fi

# 1) 自动创建应用 + 写入 .env
echo "\n[1/5] 自动创建 Entra 应用并写入 .env"
docker compose run --rm -e GRAPH_BOOTSTRAP_TOKEN="$GRAPH_BOOTSTRAP_TOKEN" ms_graph_docker python3 /app/tenant_init.py

# 2) 强制停顿：等待管理员 consent
echo "\n[2/5] 请先完成管理员 consent，再继续"
read -r -p "浏览器完成 consent 后，按回车继续..."

# 3) 首次授权向导（需要人工登录 + 粘贴回跳 URL）
echo "\n[3/5] 首次授权向导"
docker compose run --rm ms_graph_docker python3 /app/auth_cli.py

# 4) 启动容器
echo "\n[4/5] 启动服务"
docker compose up -d

# 5) 自检
echo "\n[5/5] 运行自检"
./graphctl check

echo "\n✅ 全部完成。"
echo "查看日志：./graphctl logs"
