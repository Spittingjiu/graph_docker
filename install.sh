#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Spittingjiu/graph_docker.git"
INSTALL_DIR="${GRAPH_DOCKER_DIR:-/opt/graph_docker}"
BRANCH="${GRAPH_DOCKER_BRANCH:-master}"

echo "=== graph_docker 远程安装器 ==="
echo "repo: $REPO_URL"
echo "dir : $INSTALL_DIR"

auto_install_deps() {
  if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    echo "检测到缺少 git/curl，尝试自动安装（Ubuntu/Debian）..."
    sudo apt-get update -y
    sudo apt-get install -y git curl
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "未检测到 docker，请先安装 docker 后重试。"
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    echo "未检测到 docker compose，请先安装后重试。"
    exit 1
  fi
}

auto_install_deps

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "目录已存在，执行更新..."
  git -C "$INSTALL_DIR" fetch --all --tags
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  echo "首次安装，克隆仓库..."
  sudo mkdir -p "$(dirname "$INSTALL_DIR")"
  sudo chown -R "$(id -u):$(id -g)" "$(dirname "$INSTALL_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
chmod +x setup_all_in_one.sh graphctl bootstrap.sh auth_cli.py tenant_init.py install.sh

echo "开始执行一键初始化..."
./setup_all_in_one.sh
