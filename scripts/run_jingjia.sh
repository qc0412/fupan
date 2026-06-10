#!/usr/bin/env bash
# 每交易日北京时间 9:26 由 cron 拉起：本机无人值守跑 /jingjia 集合竞价分析，
# 产物写 ~/claudeCode/jingjia_<date>.md，由 publish_reviews.py（每10分钟 cron）自动发布上线。
# 日志：tail -f /home/ubuntu/fupan/.jingjia_auto.log
set -u

# 防重入：拿不到锁说明上一次还在跑，直接退出（cron 重叠/手动误触都安全）
exec 200>/tmp/jingjia.lock
flock -n 200 || { echo "[$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')] 已有实例在跑（/tmp/jingjia.lock 被占用），退出"; exit 0; }

export HOME=/home/ubuntu
# claude 是 node 程序，需要 nvm 的 node 在 PATH 里（cron 默认 PATH 太窄）
export PATH="/home/ubuntu/.nvm/versions/node/v22.22.3/bin:/usr/local/bin:/usr/bin:/bin"

RECLAUDE=/home/ubuntu/.local/bin/reclaude
PROMPT_FILE=/home/ubuntu/.claude/skills/jingjia/auto_run_prompt.md

cd /home/ubuntu || exit 1

echo "===== $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S') 启动 /jingjia 自动跑 ====="

# 走 reclaude 入口，沿用本机 Claude Code 网关/鉴权与无人值守权限封装。
# --add-dir 把 fupan 项目挂进来，确保能读 scraper/venv。
# timeout 1800：claude 挂死最多占 30 分钟，防止僵尸进程堆积（124=超时被杀）。
timeout 1800 "$RECLAUDE" -p "$(cat "$PROMPT_FILE")" \
    --add-dir /home/ubuntu/fupan
CLAUDE_RC=$?

TODAY=$(TZ=Asia/Shanghai date '+%Y-%m-%d')
PRODUCT=/home/ubuntu/claudeCode/jingjia_${TODAY}.md

if [ "$CLAUDE_RC" -ne 0 ]; then
    echo "[ALERT] claude 退出码 $CLAUDE_RC（124=超时被杀），/jingjia 本次失败 $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')"
fi
if [ ! -s "$PRODUCT" ]; then
    echo "[ALERT] 产物缺失或为空：$PRODUCT（节假日数据判活跳过亦会如此，需人工确认）"
fi

# 跑完立刻发布上线，不必等每10分钟的 publish cron（本机 fupan.service 直读 data/reviews，落盘即生效）
echo "--- 立即发布 ---"
/usr/bin/python3 /home/ubuntu/fupan/scripts/publish_reviews.py

echo "===== $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S') 结束 ====="
