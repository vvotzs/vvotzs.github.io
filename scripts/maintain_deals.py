#!/usr/bin/env python3
"""羊毛情报局 — 数据维护脚本。

做四件事：
  1. 去重：同一活动（同标题或同链接）只保留信息更全 / 更新更近的一条；
  2. 状态：按截止时间标记 active / expiring_soon(<=7 天) / expired；
  3. 归档与清理：已过期超过 30 天的条目自动删除（保留短档期）；
  4. 输出：回写 data/deals.json、更新 data/meta.json 与 sitemap.xml。

用法：python3 scripts/maintain_deals.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "deals.json"
META = ROOT / "data" / "meta.json"
SITEMAP = ROOT / "sitemap.xml"

SITE_URL = "https://vvotzs.github.io/"
ARCHIVE_DAYS = 30
EXPIRING_DAYS = 7

CATEGORIES = {
    "ai": "AI 工具",
    "crypto": "Crypto",
    "bank": "海外银行 / U 卡 / 汇款",
    "cloud": "VPS 与云服务",
    "esim": "eSIM",
    "software": "软件与数字服务",
}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def norm_title(title: str) -> str:
    """用于判重的标题归一化：去空白、标点与常见后缀词。"""
    text = title.lower()
    text = re.sub(r"[\(\)\[\]【】（）·\-—_/|,:：，。!！?？\"'“”‘’\s]+", "", text)
    return text


def region_signature(deal: dict) -> str:
    """同品牌不同区（美区 / 英区 / EEA 欧区 / 全球站 …）不得视为同一条。

    优先取标题开头的 [区域] 标签；没有标签时退回 regions 字段前段文字，
    保证旧数据与新增条目都不会把两个地区版本合并掉。
    """
    match = re.match(r"^\s*[\[【]([^\]】]{1,24})[\]】]", deal.get("title") or "")
    tag = match.group(1) if match else ""
    tag = re.sub(r"[\s·,，。;；:：/|()（）\-—]+", "", tag.lower())
    body = re.sub(r"[\s·,，。;；:：/|()（）\-—]+", "", (deal.get("regions") or "").lower())[:60]
    return tag or body


def completeness(deal: dict) -> int:
    score = 0
    for key in ("content", "conditions", "regions", "url", "source", "risk", "highlight"):
        if deal.get(key):
            score += 1
    score += len(deal.get("steps") or [])
    if deal.get("verified"):
        score += 2
    return score


def dedupe(deals: list[dict]) -> tuple[list[dict], list[str]]:
    """同标题 + 同区域，或同官方链接 + 同区域才算重复，保留更完整的一条。

    区域参与判重：TopCashback 美区/英区/德区、Sendwave 美区/欧区这类同名活动
    必须各自保留。
    """
    kept: list[dict] = []
    dropped: list[str] = []
    seen_title: dict[str, int] = {}
    seen_url: dict[str, int] = {}

    for deal in deals:
        region = region_signature(deal)
        title_key = f"{norm_title(deal.get('title', ''))}@@{region}"
        url_key = "|".join(
            [
                (deal.get("url") or "").rstrip("/").lower(),
                deal.get("category", ""),
                deal.get("value", ""),
                region,
            ]
        )
        existing_idx = None
        if title_key in seen_title:
            existing_idx = seen_title[title_key]
        elif url_key.strip("|") and url_key in seen_url:
            existing_idx = seen_url[url_key]

        if existing_idx is None:
            idx = len(kept)
            kept.append(deal)
            seen_title[title_key] = idx
            if url_key:
                seen_url[url_key] = idx
            continue

        old = kept[existing_idx]
        if completeness(deal) > completeness(old):
            dropped.append(f"{old['id']}（重复，保留更完整的 {deal['id']}）")
            kept[existing_idx] = deal
            seen_title[title_key] = existing_idx
            if url_key:
                seen_url[url_key] = existing_idx
        else:
            dropped.append(f"{deal['id']}（重复于 {old['id']}）")
    return kept, dropped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    args = parser.parse_args()

    if not DATA.exists():
        print(f"missing {DATA}", file=sys.stderr)
        return 1

    today = date.today()
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    before = len(deals)

    deals, dropped = dedupe(deals)

    archived, pruned = 0, []
    for deal in deals:
        end = parse_date(deal.get("end", ""))
        if end and end < today:
            deal["status"] = "expired"
            archived += 1
            if (today - end).days > ARCHIVE_DAYS:
                pruned.append(deal["id"])
        elif end and (end - today).days <= EXPIRING_DAYS:
            deal["status"] = "expiring_soon"
        else:
            deal["status"] = "active"

    deals = [d for d in deals if d["id"] not in pruned]

    for deal in deals:
        deal.setdefault("last_verified", "待核实")
        if deal["status"] == "expired":
            deal["value_num"] = 0

    active = [d for d in deals if d["status"] == "active"]
    expiring = [d for d in deals if d["status"] == "expiring_soon"]
    expired = [d for d in deals if d["status"] == "expired"]
    closing_30d = [
        d
        for d in active + expiring
        if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= 30
    ]

    # 排序：进行中按价值降序，即将截止紧随其后，过期按结束日期降序
    deals.sort(
        key=lambda d: (
            {"active": 0, "expiring_soon": 1, "expired": 2}[d["status"]],
            -(d.get("value_num") or 0),
            d.get("end") or "9999-12-31",
        )
    )

    now = datetime.now()
    meta = {
        "last_updated": now.isoformat(timespec="seconds"),
        "last_updated_human": now.strftime("%Y-%m-%d %H:%M"),
        "counts": {
            "total": len(deals),
            "active": len(active) + len(expiring),
            "expiring_soon": len(expiring),
            "closing_30d": len(closing_30d),
            "expired": len(expired),
        },
        "categories": {
            key: len([d for d in active + expiring if d.get("category") == key])
            for key in CATEGORIES
        },
        "archive_retention_days": ARCHIVE_DAYS,
        "expiring_threshold_days": EXPIRING_DAYS,
    }

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{SITE_URL}</loc>\n"
        f"    <lastmod>{today.isoformat()}</lastmod>\n"
        "    <changefreq>hourly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )

    print(f"载入 {before} 条 → 去重后 {len(deals)} 条")
    for line in dropped:
        print(f"  - 去重：{line}")
    print(f"  状态：进行中 {meta['counts']['active']}（其中 7 天内截止 {len(expiring)}）· 已归档 {len(expired)}")
    if pruned:
        for pid in pruned:
            print(f"  - 清理：{pid}（过期超过 {ARCHIVE_DAYS} 天）")
    else:
        print(f"  - 清理：无（过期超过 {ARCHIVE_DAYS} 天的条目才会删除）")

    if args.dry_run:
        print("dry-run：未写入任何文件")
        return 0

    DATA.write_text(json.dumps(deals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SITEMAP.write_text(sitemap, encoding="utf-8")
    print(f"已写入 {DATA.name}、{META.name}、{SITEMAP.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
