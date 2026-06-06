#!/usr/bin/env bash
# 构建 Vue 前端并发布到 nginx。用法：./deploy.sh
set -euo pipefail
cd "$(dirname "$0")/frontend"

# 加载 nvm 取得 node（非交互/cron 环境也可用）
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

echo "▶ 构建前端 (npm ci + build)..."
npm ci
npm run build

echo "▶ 发布 dist -> /var/www/fupan ..."
sudo rsync -a --delete dist/ /var/www/fupan/
sudo chown -R www-data:www-data /var/www/fupan

echo "▶ reload nginx ..."
sudo nginx -t && sudo systemctl reload nginx

echo "✅ 部署完成 -> http://124.220.78.135"
