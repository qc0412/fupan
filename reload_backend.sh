#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# 用户态后端热重载（无需 sudo）
CTL_SOCKET="${GUNICORN_CTL_SOCKET:-$HOME/.gunicorn/gunicorn.ctl}"
PIDFILE="${GUNICORN_PIDFILE:-$HOME/.gunicorn/gunicorn.pid}"

if [[ -S "$CTL_SOCKET" ]]; then
  echo "▶ reload gunicorn via control socket: $CTL_SOCKET"
  python3 - "$CTL_SOCKET" <<'PY'
import socket, sys
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(sys.argv[1])
sock.sendall(b'hup\n')
print(sock.recv(4096).decode('utf-8', 'ignore'))
sock.close()
PY
elif [[ -f "$PIDFILE" ]]; then
  pid=$(cat "$PIDFILE")
  echo "▶ reload gunicorn via HUP pid=$pid"
  kill -HUP "$pid"
else
  echo "✗ 未找到 gunicorn control socket 或 pidfile，无法无 sudo reload"
  exit 1
fi

echo "✅ backend reload signal sent"
