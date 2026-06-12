#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开盘啦「区间榜」数据 —— /fupan 第零步数据源之一（薄 CLI 包装）

⚠️ 唯一实现在仓库根的 kpl_api.py（接口封装 / 字段映射 / 四条接口脾气 /
   双向回退逻辑全在那里）。本文件只做 CLI 参数 + 人读输出，
   2026-06-12 起两份各自演化的副本已归一，改逻辑请改 kpl_api.py。

作用
----
拉取开盘啦自有口径的【区间个股榜】和【区间板块榜】：
  - 区间个股: 区间涨幅龙头 + 区间净额吸金王（两榜去重合并）
  - 区间板块: 区间强度榜 + 涨幅榜 + 净额榜（三榜去重合并）
直接服务【第四步:板块生命周期】(谁在加速/吸金) 与【周龙头评选】(区间涨幅/净额龙头)。
与 platerotat.py 互补: platerotat 给"短线侠板块排名矩阵走势", 本模块给
"开盘啦口径的区间真实净额(元) + 区间强度 + 个股区间龙头"。

输出字段、接口脾气（DEnd/DStart 非交易日整段空、历史区间个股数值脱敏、
板块榜只覆盖最近两个交易日等）详见 kpl_api.py 模块头。

用法
  python3 kpl_interval.py                          # 默认近 5 个工作日, 人读摘要
  python3 kpl_interval.py --days 3                 # /fupan 用近 3 个交易日
  python3 kpl_interval.py --start 2026-06-05 --end 2026-06-09
  python3 kpl_interval.py --json                   # JSON 到 stdout (供 /fupan 读取)
"""

import argparse
import json
import os
import sys

# 本文件位于 <repo>/.claude/skills/fupan/scripts/，引擎在仓库根；
# 经 ~/.claude/skills symlink 调用时 realpath 仍解析回仓库
_REPO_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from kpl_api import fetch_interval_all  # noqa: E402

BLOCKED_HINT = (
    "⚠️ 开盘啦区间榜返回空(List 为空)——此接口可能也已被验签拦截。"
    "请改用 AkShare/短线侠 platerotat.py 兜底, 并核对是否需补 kpl_sign 签名。"
)


def _fmt_money(yuan):
    if yuan is None:
        return "-"
    a = abs(yuan)
    if a >= 1e8:
        return f"{yuan / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{yuan / 1e4:.2f}万"
    return f"{yuan:.0f}"


def _print_human(d):
    r = d["range"]
    print(f"=== 开盘啦区间榜 {r['start']} ~ {r['end']} ===\n")
    if d.get("stocks_masked"):
        print("⚠️ 区间不含最新交易日, 个股榜数值被接口脱敏(置 None), 仅排名可信\n")
    print(f"【区间板块榜】(强度/涨幅/净额去重, 共 {len(d['sectors'])} 个)")
    for s in sorted(d["sectors"], key=lambda x: -(x.get("strength") or 0)):
        tags = []
        if s.get("rank_strength"):
            tags.append(f"强度#{s['rank_strength']}")
        if s.get("rank_rise"):
            tags.append(f"涨幅#{s['rank_rise']}")
        if s.get("rank_net"):
            tags.append(f"净额#{s['rank_net']}")
        print(f"  {s['name']:<8} 涨幅{s['zf_interval']}% 净额{_fmt_money(s['net_interval'])} "
              f"强度{s.get('strength')} [{'/'.join(tags)}]")
    print(f"\n【区间个股榜】(涨幅龙头/净额吸金, 共 {len(d['stocks'])} 只)")
    for s in d["stocks"]:
        tags = []
        if s.get("rank_rise"):
            tags.append(f"涨幅#{s['rank_rise']}")
        if s.get("rank_net"):
            tags.append(f"净额#{s['rank_net']}")
        print(f"  {s['name']:<7}({s['code']}) 区间涨幅{s['zf_interval']}% "
              f"净额{_fmt_money(s['net_interval'])} 换手{s['hsl_interval']}% "
              f"[{'/'.join(tags)}] {s['concept']}")
    if not d["sectors"] and not d["stocks"]:
        print(BLOCKED_HINT)


def main():
    ap = argparse.ArgumentParser(description="开盘啦区间榜(个股/板块)数据")
    ap.add_argument("--start", help="区间开始 YYYY-MM-DD(默认按 --days 推算)")
    ap.add_argument("--end", help="区间结束 YYYY-MM-DD(默认最近工作日)")
    ap.add_argument("--days", type=int, default=5,
                    help="未给 start/end 时取近 N 个工作日，默认 5；/fupan 近3天用 --days 3")
    ap.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = ap.parse_args()
    try:
        d = fetch_interval_all(args.start, args.end, days=args.days)
    except Exception as e:  # noqa: BLE001
        print(f"[kpl_interval] 请求失败: {type(e).__name__}: {e}", file=sys.stderr)
        print(BLOCKED_HINT, file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        _print_human(d)


if __name__ == "__main__":
    main()
