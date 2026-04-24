#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Spittingjiu/graph_docker.git"
INSTALL_DIR="${GRAPH_DOCKER_DIR:-/opt/graph_docker}"
BRANCH="${GRAPH_DOCKER_BRANCH:-master}"

say() { echo "$*"; }

auto_install_deps() {
  if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    say "检测到缺少 git/curl，尝试自动安装（Ubuntu/Debian）..."
    sudo apt-get update -y
    sudo apt-get install -y git curl
  fi

  if ! command -v docker >/dev/null 2>&1; then
    say "未检测到 docker，请先安装 docker 后重试。"
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    say "未检测到 docker compose，请先安装后重试。"
    exit 1
  fi
}

install_or_update() {
  auto_install_deps

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    say "目录已存在，执行更新..."
    git -C "$INSTALL_DIR" fetch --all --tags
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  else
    say "首次安装，克隆仓库..."
    sudo mkdir -p "$(dirname "$INSTALL_DIR")"
    sudo chown -R "$(id -u):$(id -g)" "$(dirname "$INSTALL_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi

  cd "$INSTALL_DIR"
  chmod +x setup_all_in_one.sh graphctl bootstrap.sh auth_cli.py tenant_init.py install.sh || true

  say "开始执行一键初始化..."
  ./setup_all_in_one.sh
}

uninstall_all() {
  say "准备卸载 graph_docker"
  say "安装目录: $INSTALL_DIR"

  read -r -p "确认卸载并清理数据？(yes/no): " ans
  if [[ "$ans" != "yes" ]]; then
    say "已取消"
    exit 0
  fi

  if [[ -d "$INSTALL_DIR" ]]; then
    if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
      (cd "$INSTALL_DIR" && docker compose down --remove-orphans || true)
    fi
    (cd "$INSTALL_DIR" && docker image rm -f graph_docker:local >/dev/null 2>&1 || true)
  fi

  # 兼容旧容器名
  docker rm -f ms_graph_docker >/dev/null 2>&1 || true

  # 删除目录
  if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
  fi

  say "卸载完成。"
}

show_menu() {
  cat <<EOF
=== graph_docker 安装器 ===
repo: $REPO_URL
dir : $INSTALL_DIR

请选择操作：
  1) 安装/更新并初始化
  2) 卸载并清理
EOF
}

# 支持非交互参数
#   ./install.sh install
#   ./install.sh uninstall
ACTION="${1:-}"

case "$ACTION" in
  install)
    install_or_update
    ;;
  uninstall)
    uninstall_all
    ;;
  "")
    show_menu
    read -r -p "输入 1 或 2: " choice
    case "$choice" in
      1) install_or_update ;;
      2) uninstall_all ;;
      *) say "无效输入"; exit 1 ;;
    esac
    ;;
  *)
    say "用法:"
    say "  ./install.sh            # 菜单模式"
    say "  ./install.sh install    # 安装/更新"
    say "  ./install.sh uninstall  # 卸载清理"
    exit 1
    ;;
esac
