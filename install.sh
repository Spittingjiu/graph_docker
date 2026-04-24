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

get_update_status_line() {
  if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    echo "更新状态: 未安装（按 1 安装）"
    return
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "更新状态: 无法检查（git 不可用）"
    return
  fi

  local local_head remote_head
  local_head="$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true)"
  remote_head="$(git -C "$INSTALL_DIR" ls-remote --heads origin "$BRANCH" 2>/dev/null | awk '{print $1}' | head -n1 || true)"

  if [[ -z "$local_head" || -z "$remote_head" ]]; then
    echo "更新状态: 无法检查（网络或远端异常）"
    return
  fi

  if [[ "$local_head" == "$remote_head" ]]; then
    echo "更新状态: 当前已是最新版"
  else
    echo "更新状态: 检测到新版本（按 2 更新）"
  fi
}

cron_file_path() {
  echo "/etc/cron.d/graph_docker"
}

cron_log_path() {
  echo "/var/log/graph_docker_cron.log"
}

write_cron_schedule() {
  local schedule_name="$1"
  local cron_entries="$2"
  local cron_file
  cron_file="$(cron_file_path)"
  local tmp
  tmp="$(mktemp)"

  cat > "$tmp" <<EOF
# graph_docker scheduled keepalive
# profile: $schedule_name
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

$cron_entries
EOF

  sudo mv "$tmp" "$cron_file"
  sudo chmod 644 "$cron_file"
  touch "$(cron_log_path)" || true
  say "已写入定时计划：$schedule_name"
  say "当前定时文件: $cron_file"
  say "日志文件: $(cron_log_path)"
}

show_cron_schedule() {
  local cron_file
  cron_file="$(cron_file_path)"
  if [[ -f "$cron_file" ]]; then
    echo "---- 当前定时计划 ----"
    cat "$cron_file"
    echo "---------------------"
  else
    echo "当前未配置定时计划"
  fi
}

clear_cron_schedule() {
  local cron_file
  cron_file="$(cron_file_path)"
  if [[ -f "$cron_file" ]]; then
    sudo rm -f "$cron_file"
    say "已清除定时计划"
  else
    say "未检测到定时计划，无需清除"
  fi
}

schedule_menu() {
  ensure_repo
  local run_cmd="cd $INSTALL_DIR && /usr/local/bin/gb up >> $(cron_log_path) 2>&1"

  cat <<EOF
=== 定时保活计划 ===
目标：贴近人类使用节奏，定时确保服务可用

请选择：
  1) 午间三次：12:00 / 12:20 / 12:40
  2) 工作日通勤节奏：09:30 / 13:30 / 18:30（周一到周五）
  3) 每日三段：09:00 / 15:00 / 21:00
  4) 全天低频：08:00-22:00 每2小时一次
  5) 非整点拟人：08:17 / 12:43 / 19:26
  6) 工作日+周末混合：工作日12:15，周末11:15/20:15
  7) 仅每日一次：12:00
  8) 每日四次：08:30 / 12:00 / 16:30 / 21:30
  9) 自定义 cron 表达式（你自己输入）
  s) 查看当前定时计划
  c) 清除定时计划
  q) 返回上一级
EOF

  read -r -p "输入选项: " sopt
  case "$sopt" in
    1)
      write_cron_schedule "lunch-3x" "0,20,40 12 * * * root $run_cmd"
      ;;
    2)
      write_cron_schedule "workday-commute" "30 9,13,18 * * 1-5 root $run_cmd"
      ;;
    3)
      write_cron_schedule "daily-3block" "0 9,15,21 * * * root $run_cmd"
      ;;
    4)
      write_cron_schedule "daily-every2h" "0 8-22/2 * * * root $run_cmd"
      ;;
    5)
      write_cron_schedule "humanized-nonhour" "17 8 * * * root $run_cmd
43 12 * * * root $run_cmd
26 19 * * * root $run_cmd"
      ;;
    6)
      write_cron_schedule "weekday-weekend-mix" "15 12 * * 1-5 root $run_cmd
15 11,20 * * 6,0 root $run_cmd"
      ;;
    7)
      write_cron_schedule "daily-once" "0 12 * * * root $run_cmd"
      ;;
    8)
      write_cron_schedule "daily-4x" "30 8,16,21 * * * root $run_cmd
0 12 * * * root $run_cmd"
      ;;
    9)
      read -r -p "输入 cron（五段）例如: 0 12 * * * : " custom_expr
      if [[ -z "$custom_expr" ]]; then
        say "未输入，已取消"
      else
        write_cron_schedule "custom" "$custom_expr root $run_cmd"
      fi
      ;;
    s|S)
      show_cron_schedule
      ;;
    c|C)
      clear_cron_schedule
      ;;
    q|Q)
      ;;
    *)
      say "无效输入"
      ;;
  esac
}

show_menu() {
  local update_line
  update_line="$(get_update_status_line)"

  cat <<EOF
=== graph_docker 运维菜单 ===
repo: $REPO_URL
dir : $INSTALL_DIR
$update_line

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
 10) 定时保活计划（新增）
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
  schedule)
    schedule_menu
    ;;
  schedule-show)
    show_cron_schedule
    ;;
  schedule-clear)
    clear_cron_schedule
    ;;
  "")
    clear_screen
    show_menu
    read -r -p "输入 1-10: " choice
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
      10) schedule_menu ;;
      *) say "无效输入"; exit 1 ;;
    esac
    ;;
  *)
    say "用法:"
    say "  ./install.sh                    # 菜单模式"
    say "  ./install.sh install            # 安装/更新+一键初始化"
    say "  ./install.sh update             # 仅安装/更新"
    say "  ./install.sh auth               # 首次授权向导"
    say "  ./install.sh init               # 一键全流程初始化"
    say "  ./install.sh check              # 自检"
    say "  ./install.sh up                 # 启动"
    say "  ./install.sh logs [lines]       # 日志"
    say "  ./install.sh clean              # 一键清除"
    say "  ./install.sh uninstall          # 卸载清理"
    say "  ./install.sh schedule           # 定时计划菜单"
    say "  ./install.sh schedule-show      # 查看定时计划"
    say "  ./install.sh schedule-clear     # 清除定时计划"
    exit 1
    ;;
esac
