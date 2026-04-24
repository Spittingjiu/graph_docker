#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "[1/4] 检查 .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 .env，请先编辑后再执行。"
  exit 1
fi

echo "[2/4] 预检 docker compose"
docker compose config >/dev/null

echo "[3/4] 首次授权检查"
if [[ ! -s token.txt ]]; then
  echo "token.txt 为空，开始首次授权向导..."
  docker compose run --rm ms_graph_docker python3 /app/auth_cli.py
fi

echo "[4/4] 启动服务"
docker compose up -d

echo "完成。运行状态："
docker compose ps

echo "最近日志："
docker compose logs --tail=50
