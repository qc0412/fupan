#!/usr/bin/env bash
# 无 sudo 前端发布脚本。前提：/var/www/fupan 已一次性授权给 ubuntu 写入，或改成用户可写目录。
set -euo pipefail
cd "$(dirname "$0")/frontend"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

TARGET_DIR="${FUPAN_WEB_ROOT:-/var/www/fupan}"

echo "▶ build frontend"
npm ci
npm run build

echo "▶ publish dist -> $TARGET_DIR"
rsync -a --delete dist/ "$TARGET_DIR/"

echo "✅ frontend published to $TARGET_DIR"
