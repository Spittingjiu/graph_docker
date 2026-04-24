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

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "当前不是 root 且未安装 sudo，无法自动安装依赖。"
    exit 1
  fi
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "缺少 docker compose，请先安装。"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 .env"
fi

if [[ -z "${GRAPH_BOOTSTRAP_TOKEN:-}" ]]; then
  if ! command -v az >/dev/null 2>&1; then
    echo "未检测到 Azure CLI（az）。"
    read -r -p "是否自动安装 Azure CLI（Ubuntu/Debian）? (y/N): " install_az
    case "${install_az,,}" in
      y|yes)
        if ! command -v curl >/dev/null 2>&1; then
          echo "缺少 curl，先安装 curl..."
          $SUDO apt-get update -y
          $SUDO apt-get install -y curl
        fi
        echo "正在安装 Azure CLI..."
        curl -sL https://aka.ms/InstallAzureCLIDeb | $SUDO bash
        ;;
      *)
        echo "你选择了不安装 Azure CLI。将继续等待你手动提供 GRAPH_BOOTSTRAP_TOKEN。"
        ;;
    esac
  fi

  if command -v az >/dev/null 2>&1; then
    echo "未检测到 GRAPH_BOOTSTRAP_TOKEN，尝试使用 Azure CLI 自动获取..."
    if az account show >/dev/null 2>&1; then
      GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv || true)"
      export GRAPH_BOOTSTRAP_TOKEN
      if [[ -n "${GRAPH_BOOTSTRAP_TOKEN:-}" ]]; then
        echo "已从当前 Azure 登录态获取到 GRAPH_BOOTSTRAP_TOKEN。"
      fi
    else
      echo "Azure CLI 尚未登录。"
      read -r -p "是否现在登录 Azure（az login）? (y/N): " do_az_login
      case "${do_az_login,,}" in
        y|yes)
          az login --allow-no-subscriptions >/dev/null
          GRAPH_BOOTSTRAP_TOKEN="$(az account get-access-token --resource-type ms-graph --query accessToken -o tsv || true)"
          export GRAPH_BOOTSTRAP_TOKEN
          ;;
        *)
          echo "已跳过 az login。你也可以手动 export GRAPH_BOOTSTRAP_TOKEN 后重试。"
          ;;
      esac
    fi
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
