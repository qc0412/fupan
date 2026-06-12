#!/usr/bin/env bash
# ⚠️ 2026-06-12 起本脚本已退出自动调度（9:25 自动跑归 OpenClaw cron：daily-jingjia-0925），
# 保留作【手动补跑工具】：OpenClaw 失败/节假日误判时人工执行一次即可。
# 产物写 ~/claudeCode/jingjia_<date>.md，写完立即发布（crontab 每10分钟 publish 兜底仍在）。
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
# 手动补跑要能看到失败：claude 失败或产物缺失时以非零码退出（不再静默吞掉）
[ "$CLAUDE_RC" -eq 0 ] && [ -s "$PRODUCT" ] || exit 1
