#!/usr/bin/env python3
"""羊毛情报局 — 数据维护脚本。

做四件事：
  1. 去重：同一活动（同标题或同链接）只保留信息更全 / 更新更近的一条；
  2. 状态：按截止时间标记 active / expiring_soon(<=7 天) / expired；
  3. 归档：过期条目全部归入档案并永久保留（供 SEO 长尾收录与查档，不再按天数清理）；
  4. 输出：回写 data/deals.json、更新 data/meta.json 与 sitemap.xml。

用法：python3 scripts/maintain_deals.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from common import (  # noqa: E402
    ARCHIVE_RETENTION,
    CAT_META,
    CLOSING_WINDOW_DAYS,
    DATA,
    EXPIRING_DAYS,
    META,
    compute_status,
    dedup_key,
    ensure_added_at,
    now_local,
    parse_date,
    today_local,
    write_sitemap,
)


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

    today = today_local()
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    before = len(deals)

    deals, dropped = dedupe(deals)

    archived, pruned = 0, []
    for deal in deals:
        deal["status"] = compute_status(deal, today)
        if deal["status"] == "expired":
            archived += 1
        # 过期条目一律保留：pruned 恒为空，不做任何删除（SEO 长尾需要长期收录）。

    deals = [d for d in deals if d["id"] not in pruned]

    # 入库时间：新条目补 added_at，老条目已回填过，不动
    if ensure_added_at(deals):
        print("  - 入库时间：为新条目补写了 added_at")

    for deal in deals:
        # 去重键每轮重算：手工追加的条目不用记着填，改了品牌 / 分类 / 区域也会自动跟上
        deal["dedup_key"] = dedup_key(deal)
        deal.setdefault("last_verified", "待核实")
        if deal["status"] == "expired":
            deal["value_num"] = 0

    active = [d for d in deals if d["status"] == "active"]
    expiring = [d for d in deals if d["status"] == "expiring_soon"]
    expired = [d for d in deals if d["status"] == "expired"]
    closing_30d = [
        d
        for d in active + expiring
        if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= CLOSING_WINDOW_DAYS
    ]

    # 排序：进行中按价值降序，即将截止紧随其后，过期按结束日期降序
    deals.sort(
        key=lambda d: (
            {"active": 0, "expiring_soon": 1, "expired": 2}[d["status"]],
            -(d.get("value_num") or 0),
            d.get("end") or "9999-12-31",
        )
    )

    now = now_local()
    meta = {
        "last_updated": now.isoformat(timespec="seconds"),
        "last_updated_human": now.strftime("%Y-%m-%d %H:%M"),
        "timezone": "Asia/Shanghai",
        "counts": {
            "total": len(deals),
            "active": len(active) + len(expiring),
            "expiring_soon": len(expiring),
            "closing_30d": len(closing_30d),
            "expired": len(expired),
        },
        "categories": {
            key: len([d for d in active + expiring if d.get("category") == key])
            for key in CAT_META
        },
        "archive_retention_days": ARCHIVE_RETENTION,
        "expiring_threshold_days": EXPIRING_DAYS,
    }

    print(f"载入 {before} 条 → 去重后 {len(deals)} 条")
    for line in dropped:
        print(f"  - 去重：{line}")
    print(f"  状态：进行中 {meta['counts']['active']}（其中 7 天内截止 {len(expiring)}）· 已归档 {len(expired)}")
    if pruned:
        for pid in pruned:
            print(f"  - 清理：{pid}")
    else:
        print("  - 清理：无（过期条目永久保留，不再删除）")

    if args.dry_run:
        print("dry-run：未写入任何文件")
        return 0

    DATA.write_text(json.dumps(deals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_sitemap(deals, today)
    print(f"已写入 {DATA.name}、{META.name}、sitemap.xml（含中英详情页）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
