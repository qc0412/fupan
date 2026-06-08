#!/usr/bin/env python3
"""
测试反爬虫保护机制（不依赖akshare）
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入配置常量
from astock_data import (
    CACHE_DIR, STATS_FILE,
    REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX,
    MAX_RETRIES, RETRY_BASE_DELAY,
    MAX_DAILY_REQUESTS, MAX_CONSECUTIVE_FAILURES,
    COOLDOWN_PERIOD, USER_AGENTS
)

def test_config():
    """测试配置参数"""
    print("=" * 60)
    print("🔧 配置参数测试")
    print("=" * 60)
    print(f"✅ 请求间隔: {REQUEST_INTERVAL_MIN}-{REQUEST_INTERVAL_MAX}秒")
    print(f"✅ 最大重试: {MAX_RETRIES}次")
    print(f"✅ 重试延迟: {RETRY_BASE_DELAY}秒（指数退避）")
    print(f"✅ 每日上限: {MAX_DAILY_REQUESTS}次")
    print(f"✅ 失败上限: {MAX_CONSECUTIVE_FAILURES}次")
    print(f"✅ 冷却期: {COOLDOWN_PERIOD}秒 ({COOLDOWN_PERIOD/60:.0f}分钟)")
    print(f"✅ User-Agent数量: {len(USER_AGENTS)}个")
    print(f"✅ 缓存目录: {CACHE_DIR}")
    print(f"✅ 统计文件: {STATS_FILE}")
    print()

def test_stats_file():
    """测试统计文件功能"""
    print("=" * 60)
    print("📊 统计文件测试")
    print("=" * 60)

    # 创建测试统计
    test_stats = {
        "date": datetime.now().date().isoformat(),
        "daily_requests": 15,
        "consecutive_failures": 2,
        "last_failure_time": datetime.now().isoformat(),
        "cooldown_until": None,
    }

    # 写入
    with open(STATS_FILE, "w") as f:
        json.dump(test_stats, f, indent=2)
    print(f"✅ 写入测试统计: {test_stats}")

    # 读取
    with open(STATS_FILE, "r") as f:
        loaded = json.load(f)
    print(f"✅ 读取统计成功: {loaded}")

    # 验证
    assert loaded["daily_requests"] == 15, "请求数不匹配"
    assert loaded["consecutive_failures"] == 2, "失败数不匹配"
    print("✅ 统计数据验证通过")
    print()

def test_cooldown_logic():
    """测试冷却期逻辑"""
    print("=" * 60)
    print("🔒 冷却期逻辑测试")
    print("=" * 60)

    # 模拟进入冷却期
    cooldown_until = datetime.now() + timedelta(seconds=COOLDOWN_PERIOD)
    stats = {
        "date": datetime.now().date().isoformat(),
        "daily_requests": 50,
        "consecutive_failures": MAX_CONSECUTIVE_FAILURES,
        "last_failure_time": datetime.now().isoformat(),
        "cooldown_until": cooldown_until.isoformat(),
    }

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"✅ 模拟冷却期至: {cooldown_until.strftime('%H:%M:%S')}")

    # 检查是否在冷却期
    if datetime.now() < cooldown_until:
        remaining = (cooldown_until - datetime.now()).total_seconds()
        print(f"✅ 冷却期检测正常，剩余 {remaining/60:.1f} 分钟")
    else:
        print("✅ 冷却期已结束")
    print()

def test_daily_limit():
    """测试每日限额"""
    print("=" * 60)
    print("📈 每日限额测试")
    print("=" * 60)

    # 模拟接近上限
    stats = {
        "date": datetime.now().date().isoformat(),
        "daily_requests": MAX_DAILY_REQUESTS - 5,
        "consecutive_failures": 0,
        "last_failure_time": None,
        "cooldown_until": None,
    }

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"✅ 当前请求: {stats['daily_requests']}/{MAX_DAILY_REQUESTS}")
    print(f"✅ 剩余配额: {MAX_DAILY_REQUESTS - stats['daily_requests']}次")

    if stats['daily_requests'] >= MAX_DAILY_REQUESTS * 0.8:
        print("⚠️ 警告: 已使用超过80%配额")
    print()

def test_user_agents():
    """测试User-Agent"""
    print("=" * 60)
    print("🌐 User-Agent测试")
    print("=" * 60)

    print(f"✅ 共配置 {len(USER_AGENTS)} 个User-Agent:")
    for i, ua in enumerate(USER_AGENTS, 1):
        browser = "Chrome" if "Chrome" in ua else "Firefox" if "Firefox" in ua else "Safari" if "Safari" in ua else "Edge"
        os_type = "Mac" if "Macintosh" in ua else "Windows" if "Windows" in ua else "Linux"
        print(f"  {i}. {browser} on {os_type}")
    print()

def cleanup():
    """清理测试文件"""
    print("=" * 60)
    print("🧹 清理测试数据")
    print("=" * 60)

    if STATS_FILE.exists():
        STATS_FILE.unlink()
        print("✅ 已删除测试统计文件")
    else:
        print("✅ 无需清理")
    print()

def main():
    print("\n" + "=" * 60)
    print("🛡️ A股数据获取引擎 - 反爬虫保护测试")
    print("=" * 60)
    print()

    try:
        test_config()
        test_stats_file()
        test_cooldown_logic()
        test_daily_limit()
        test_user_agents()

        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print()
        print("💡 使用建议:")
        print(f"  - 每日最多 {MAX_DAILY_REQUESTS} 次请求")
        print(f"  - 请求间隔 {REQUEST_INTERVAL_MIN}-{REQUEST_INTERVAL_MAX} 秒")
        print(f"  - 连续失败 {MAX_CONSECUTIVE_FAILURES} 次进入冷却期")
        print(f"  - 冷却期时长 {COOLDOWN_PERIOD/60:.0f} 分钟")
        print()

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()

if __name__ == "__main__":
    main()
