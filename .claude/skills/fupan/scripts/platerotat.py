#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块轮动强度数据 —— /fupan 第零步数据源之一
来源: 短线侠 https://www.duanxianxia.com/web/platerotat

作用
----
拉取「开盘啦板块 / 同花顺板块」近 N 日的强度排名矩阵，并算出每个板块的
排名走势，直接服务【第四步：板块生命周期判断】（启动/加速/分化/衰退）。

接口（POST https://www.duanxianxia.com/api/<name>，无 token/签名/验证码）
  getPlateRotatData   {from, days, dates}  -> 板块强度排名表
  getPlateRotatChart  {from, days, dates}  -> Top5 板块上榜走势
  getPlateDayChart    {platecode,days,dates} -> 单板块强度/量能序列
  getLongByPlate      {platecode,days,dates} -> 单板块领涨/连板个股

反爬说明
  实测接口不强制 cookie/Referer，无 IP 封禁风险。复盘一天一拉。
  脚本仍内置会话保持 + 指数退避重试。

用法
  python3 platerotat.py                 # 开盘啦板块·近20日·人读摘要
  python3 platerotat.py --json          # 输出 JSON 到 stdout（供 /fupan 读取）
  python3 platerotat.py --src ths --days 30
  python3 platerotat.py --deep          # 额外逐板块拉强度序列+领涨个股（会限速）
"""

import argparse
import json
import random
import re
import sys
import time

import requests

BASE = "https://www.duanxianxia.com"
PAGE = f"{BASE}/web/platerotat"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DELAY_RANGE = (0.8, 2.0)
MAX_RETRY = 4


class DuanxianxiaClient:
    """短线侠板块轮动接口客户端。"""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Referer": PAGE,
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE,
        })
        try:
            self.s.get(PAGE, timeout=15)          # 拿一次 PHPSESSID
        except requests.RequestException:
            pass

    def _post(self, name, data):
        url = f"{BASE}/api/{name}"
        for attempt in range(1, MAX_RETRY + 1):
            try:
                r = self.s.post(url, data=data, timeout=20)
                if r.status_code == 429:
                    raise requests.RequestException("429 rate limited")
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f"  [重试 {attempt}/{MAX_RETRY}] {name}: {e} -> 等 {wait:.1f}s",
                      file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"接口 {name} 连续 {MAX_RETRY} 次失败")

    @staticmethod
    def _sleep():
        time.sleep(random.uniform(*DELAY_RANGE))

    def get_rotat_data(self, src="kaipan", days=20, dates=""):
        return self._post("getPlateRotatData",
                          {"from": src, "days": days, "dates": dates})

    def get_rotat_chart(self, src="kaipan", days=20, dates=""):
        return self._post("getPlateRotatChart",
                          {"from": src, "days": days, "dates": dates})

    def get_day_chart(self, platecode, days=20, dates=""):
        return self._post("getPlateDayChart",
                          {"platecode": platecode, "days": days, "dates": dates})

    def get_long_by_plate(self, platecode, days=20, dates=""):
        return self._post("getLongByPlate",
                          {"platecode": platecode, "days": days, "dates": dates})


# ---- 解析 ----------------------------------------------------------------
def parse_rotat_table(html):
    """html 字段 -> {dates:[...], rows:[{rank, cells:[{date,code,name,strength}]}]}"""
    trs = re.findall(r"<tr>(.*?)</tr>", html, re.S)
    if not trs:
        return {"dates": [], "rows": []}
    head = re.findall(r"<td[^>]*>(.*?)</td>", trs[0], re.S)
    dates = [re.sub(r"<[^>]+>", "", c).strip() for c in head[1:]]
    rows = []
    for tr in trs[1:]:
        tds = re.findall(r"<td[^>]*>.*?</td>", tr, re.S)
        if not tds:
            continue
        rank = re.sub(r"<[^>]+>", "", tds[0]).strip()
        cells = []
        for i, td in enumerate(tds[1:]):
            code = re.search(r"code='(\d+)'", td)
            name = re.search(r"name='([^']*)'", td)
            nums = re.findall(r">(\d+)<", td)
            cells.append({
                "date": dates[i] if i < len(dates) else "",
                "code": code.group(1) if code else "",
                "name": name.group(1) if name else "",
                "strength": int(nums[-1]) if nums else None,
            })
        rows.append({"rank": rank, "cells": cells})
    return {"dates": dates, "rows": rows}


def parse_long_stocks(html):
    """getLongByPlate 的 html -> 个股列表。"""
    out = []
    for m in re.finditer(r"<div class='kline' code='(\d+)'>(.*?)</div>", html, re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()
        out.append({"code": m.group(1), "text": text})
    return out


def build_plate_trends(table):
    """
    把排名矩阵转置成「每个板块的排名走势」，直接服务板块生命周期判断。
    返回 list，按最新一天排名升序：
      {code, name, ranks:[最新...最早], strengths:[...],
       cur_rank, cur_strength, on_board_days, trend}
    trend: 上升 / 下降 / 持稳 / 新进  —— 供启动/加速/分化/衰退参考
    """
    dates = table["dates"]
    n = len(dates)
    plates = {}                                   # code -> {name, rank[], str[]}
    for row in table["rows"]:
        try:
            rk = int(row["rank"])
        except (ValueError, TypeError):
            continue
        for i, c in enumerate(row["cells"][:n]):
            if not c["code"]:
                continue
            p = plates.setdefault(c["code"],
                                  {"name": c["name"],
                                   "ranks": [None] * n,
                                   "strengths": [None] * n})
            p["ranks"][i] = rk
            p["strengths"][i] = c["strength"]

    out = []
    for code, p in plates.items():
        ranks = p["ranks"]                        # index 0 = 最新一天
        cur = ranks[0]
        if cur is None:                           # 最新一天没上榜的跳过
            continue
        on_board = sum(1 for r in ranks if r is not None)
        # 趋势：比较最新与「最近一次上榜的上一日」
        prev = next((r for r in ranks[1:] if r is not None), None)
        if prev is None:
            trend = "新进"
        elif cur < prev:
            trend = "上升"
        elif cur > prev:
            trend = "下降"
        else:
            trend = "持稳"
        out.append({
            "code": code, "name": p["name"],
            "cur_rank": cur, "cur_strength": p["strengths"][0],
            "on_board_days": on_board,
            "ranks": ranks, "strengths": p["strengths"],
            "trend": trend,
        })
    out.sort(key=lambda x: x["cur_rank"])
    return out


# ---- 抓取 ----------------------------------------------------------------
def fetch(src="kaipan", days=20, deep=False):
    cli = DuanxianxiaClient()
    table = parse_rotat_table(cli.get_rotat_data(src, days)["html"])
    chart = cli.get_rotat_chart(src, days)
    trends = build_plate_trends(table)

    result = {
        "source": src, "days": days,
        "dates": table["dates"],
        "plate_trends": trends,                   # 核心：板块排名走势
        "top5_legend": chart.get("legend", []),   # 区间累计上榜 Top5
    }
    if deep:
        per = {}
        for p in trends:
            cli._sleep()
            day = cli.get_day_chart(p["code"], days)
            cli._sleep()
            lng = cli.get_long_by_plate(p["code"], days)
            per[p["code"]] = {
                "name": p["name"],
                "strength_series": day.get("series1"),   # 强度
                "volume_series": day.get("series2"),     # 量能
                "long_stocks": parse_long_stocks(lng.get("html", "")),
            }
        result["plate_detail"] = per
    return result


# ---- 人读摘要 ------------------------------------------------------------
def print_summary(r):
    src_cn = {"kaipan": "开盘啦板块", "ths": "同花顺板块"}.get(r["source"], r["source"])
    print(f"\n板块轮动强度 · {src_cn} · 近{r['days']}日 "
          f"({r['dates'][-1] if r['dates'] else '?'} ~ "
          f"{r['dates'][0] if r['dates'] else '?'})")
    print(f"区间累计上榜 Top5: {', '.join(r['top5_legend'])}\n")
    print(f"{'排名':>3} {'板块':<12}{'强度':>8}{'上榜天数':>7}  趋势   近5日排名")
    for p in r["plate_trends"]:
        recent = " ".join(str(x) if x is not None else "-" for x in p["ranks"][:5])
        print(f"{p['cur_rank']:>3} {p['name']:<12}{p['cur_strength']:>8}"
              f"{p['on_board_days']:>6}日  {p['trend']:<4} {recent}")
    if "plate_detail" in r:
        print(f"\n已深挖 {len(r['plate_detail'])} 个板块（强度/量能序列 + 领涨个股）")


def main():
    ap = argparse.ArgumentParser(description="板块轮动强度数据抓取")
    ap.add_argument("--src", choices=["kaipan", "ths"], default="kaipan",
                    help="kaipan=开盘啦板块 ths=同花顺板块")
    ap.add_argument("--days", type=int, default=20, choices=[10, 20, 30, 50])
    ap.add_argument("--deep", action="store_true",
                    help="逐板块拉强度序列+领涨个股（会限速）")
    ap.add_argument("--json", action="store_true",
                    help="输出 JSON 到 stdout（供 /fupan 读取）")
    args = ap.parse_args()

    data = fetch(args.src, args.days, args.deep)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_summary(data)


if __name__ == "__main__":
    main()
