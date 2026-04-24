#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Spittingjiu/graph_docker.git"
INSTALL_DIR="${GRAPH_DOCKER_DIR:-/opt/graph_docker}"
BRANCH="${GRAPH_DOCKER_BRANCH:-master}"

say() { echo "$*"; }

clear_screen() {
  if command -v clear >/dev/null 2>&1; then
    clear
  else
    printf '\033c'
  fi
}

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

ensure_repo() {
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

  # 安装/更新 gb 快捷命令
  install_gb_alias
}

install_gb_alias() {
  local gb_target="/usr/local/bin/gb"
  local tmp_file
  tmp_file="$(mktemp)"

  cat > "$tmp_file" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/install.sh" "\$@"
EOF

  sudo mv "$tmp_file" "$gb_target"
  sudo chmod +x "$gb_target"
  say "已安装快捷命令: gb"
}

run_graphctl() {
  local sub="$1"
  ensure_repo
  ./graphctl "$sub"
}

is_already_initialized() {
  [[ -f "$INSTALL_DIR/.env" ]] || return 1
  local cid csec
  cid="$(grep -E '^CLIENT_ID=' "$INSTALL_DIR/.env" | head -n1 | cut -d= -f2- || true)"
  csec="$(grep -E '^CLIENT_SECRET=' "$INSTALL_DIR/.env" | head -n1 | cut -d= -f2- || true)"
  [[ -n "$cid" && -n "$csec" ]]
}

has_token() {
  [[ -s "$INSTALL_DIR/token.txt" ]]
}

token_is_usable() {
  docker compose run --rm ms_graph_docker sh -lc "python3 - <<'PY'
import os, sys
import requests

client_id = os.getenv('CLIENT_ID', '').strip()
client_secret = os.getenv('CLIENT_SECRET', '').strip()
tenant_id = os.getenv('TENANT_ID', 'common').strip() or 'common'
redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:53682/').strip() or 'http://localhost:53682/'

if not client_id or not client_secret:
    print('missing CLIENT_ID/CLIENT_SECRET')
    sys.exit(1)

token_path = '/app/token.txt'
if not os.path.exists(token_path):
    print('token.txt not found')
    sys.exit(1)

with open(token_path, 'r', encoding='utf-8') as f:
    refresh_token = f.read().strip()

if len(refresh_token) < 10:
    print('refresh token empty/too short')
    sys.exit(1)

token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
data = {
    'grant_type': 'refresh_token',
    'refresh_token': refresh_token,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': redirect_uri,
}

try:
    r = requests.post(token_url, data=data, timeout=15)
    if r.status_code != 200:
        print(f'token refresh failed: {r.status_code}')
        sys.exit(1)
    js = r.json()
    if not js.get('refresh_token'):
        print('token refresh response missing refresh_token')
        sys.exit(1)
    print('token refresh check: ok')
    sys.exit(0)
except Exception as e:
    print(f'token refresh exception: {e!r}')
    sys.exit(1)
PY" >/dev/null 2>&1
}

install_or_update_and_init() {
  ensure_repo

  if is_already_initialized; then
    say "检测到已存在初始化配置（.env）。"

    if has_token; then
      say "检测到 token.txt，先做可用性检查..."
      if token_is_usable; then
        say "token 可用，执行：启动 + 自检"
        ./graphctl up
        ./graphctl check
        return
      fi
      say "token 不可用，自动进入授权向导（auth）..."
      ./graphctl auth
      say "授权完成后执行：启动 + 自检"
      ./graphctl up
      ./graphctl check
      return
    fi

    say "检测到 .env 但未发现 token.txt，自动进入授权向导（auth）..."
    ./graphctl auth
    say "授权完成后执行：启动 + 自检"
    ./graphctl up
    ./graphctl check
    return
  fi

  say "未检测到可复用配置，执行一键全流程初始化..."
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

  if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
  fi

  # 删除 gb 快捷命令
  sudo rm -f /usr/local/bin/gb || true

  say "卸载完成。"
}

show_menu() {
  cat <<EOF
=== graph_docker 运维菜单 ===
repo: $REPO_URL
dir : $INSTALL_DIR

请选择操作：
  1) 安装/更新并一键初始化（setup_all_in_one）
  2) 仅安装/更新仓库
  3) 首次授权向导（graphctl auth）
  4) 一键全流程初始化（setup_all_in_one）
  5) 自检（graphctl check）
  6) 启动服务（graphctl up）
  7) 查看日志（graphctl logs）
  8) 一键清除（graphctl clean）
  9) 卸载并清理（install.sh uninstall）
EOF
}

ACTION="${1:-}"

case "$ACTION" in
  install)
    install_or_update_and_init
    ;;
  update)
    ensure_repo
    ;;
  auth)
    run_graphctl auth
    ;;
  init)
    ensure_repo
    ./setup_all_in_one.sh
    ;;
  check)
    run_graphctl check
    ;;
  up)
    run_graphctl up
    ;;
  logs)
    ensure_repo
    ./graphctl logs "${2:-100}"
    ;;
  clean)
    run_graphctl clean
    ;;
  uninstall)
    uninstall_all
    ;;
  "")
    clear_screen
    show_menu
    read -r -p "输入 1-9: " choice
    case "$choice" in
      1) install_or_update_and_init ;;
      2) ensure_repo ;;
      3) run_graphctl auth ;;
      4) ensure_repo; ./setup_all_in_one.sh ;;
      5) run_graphctl check ;;
      6) run_graphctl up ;;
      7) ensure_repo; ./graphctl logs 100 ;;
      8) run_graphctl clean ;;
      9) uninstall_all ;;
      *) say "无效输入"; exit 1 ;;
    esac
    ;;
  *)
    say "用法:"
    say "  ./install.sh              # 菜单模式"
    say "  ./install.sh install      # 安装/更新+一键初始化"
    say "  ./install.sh update       # 仅安装/更新"
    say "  ./install.sh auth         # 首次授权向导"
    say "  ./install.sh init         # 一键全流程初始化"
    say "  ./install.sh check        # 自检"
    say "  ./install.sh up           # 启动"
    say "  ./install.sh logs [lines] # 日志"
    say "  ./install.sh clean        # 一键清除"
    say "  ./install.sh uninstall    # 卸载清理"
    exit 1
    ;;
esac
