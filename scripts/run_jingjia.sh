#!/usr/bin/env bash
# 每交易日北京时间 9:26 由 cron 拉起：本机无人值守跑 /jingjia 集合竞价分析，
# 产物写 ~/claudeCode/jingjia_<date>.md，由 publish_reviews.py（每10分钟 cron）自动发布上线。
# 日志：tail -f /home/ubuntu/fupan/.jingjia_auto.log
set -u

export HOME=/home/ubuntu
# claude 是 node 程序，需要 nvm 的 node 在 PATH 里（cron 默认 PATH 太窄）
export PATH="/home/ubuntu/.nvm/versions/node/v22.22.3/bin:/usr/local/bin:/usr/bin:/bin"

CLAUDE=/home/ubuntu/.nvm/versions/node/v22.22.3/bin/claude
PROMPT_FILE=/home/ubuntu/.claude/skills/jingjia/auto_run_prompt.md

cd /home/ubuntu || exit 1

echo "===== $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S') 启动 /jingjia 自动跑 ====="

# --dangerously-skip-permissions：无人值守必须，否则工具调用会卡在权限询问。
# --add-dir 把 fupan 项目挂进来，确保能读 scraper/venv。
"$CLAUDE" -p "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions \
    --add-dir /home/ubuntu/fupan

echo "===== $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S') 结束 ====="
