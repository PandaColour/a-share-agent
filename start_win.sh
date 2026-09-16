#!/bin/sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"

cd "$SCRIPT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf '找不到 Python：%s\n' "$PYTHON_BIN" >&2
    exit 1
fi

mkdir -p "$SCRIPT_DIR/logs"
LOG_FILE="$SCRIPT_DIR/logs/win_main.log"

# 脱离终端输入输出，并忽略终端关闭时发送的 SIGHUP。
nohup "$PYTHON_BIN" -u "$SCRIPT_DIR/win_main.py" "$@" </dev/null >>"$LOG_FILE" 2>&1 &
APP_PID=$!

if command -v caffeinate >/dev/null 2>&1; then
    # 允许锁屏/熄屏；应用退出后自动释放防睡眠断言（-s 仅在接电时生效）。
    nohup caffeinate -is -w "$APP_PID" </dev/null >>"$LOG_FILE" 2>&1 &
fi

printf '已提交后台启动，PID：%s\n日志：%s\n停止命令：kill %s\n' "$APP_PID" "$LOG_FILE" "$APP_PID"
