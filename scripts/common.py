#!/usr/bin/env python3
"""羊毛情报局 — 共享常量与工具。

所有与时间、日期、类别、状态有关的规则都放在这里，
maintain_deals.py 与 build_site.py 共用，避免两处口径不一致。
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- 时间口径
# 站点面向中文用户，所有“今天 / 最近 N 天”一律按北京时间算，
# 不受运行机器的本地时区（GitHub Actions 是 UTC）影响。
TZ = ZoneInfo("Asia/Shanghai")

TODAY_WINDOW_DAYS = 2      # 「今日最新」= 最近 48 小时
EXPIRING_DAYS = 7          # 「即将截止」标记阈值（<= 7 天）
CLOSING_WINDOW_DAYS = 30   # 「即将截止」分区展示 30 天内到期的活动
ARCHIVE_DAYS = 30          # 过期活动保留天数，超过即清理

# ---------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "deals.json"
META = ROOT / "data" / "meta.json"
SITEMAP = ROOT / "sitemap.xml"
OUT = ROOT / "index.html"
FAV_DIR = ROOT / "assets" / "fav"

SITE_URL = "https://vvotzs.github.io/"
OG_IMAGE = SITE_URL + "assets/og-cover.png"

# ---------------------------------------------------------------- 类别
# label 用于详情面板展示；search 是搜索索引里额外补上的中文别名。
CAT_META = {
    "ai": {"label": "AI 工具", "search": "AI 工具 人工智能"},
    "crypto": {"label": "Crypto", "search": "Crypto 加密货币"},
    "bank": {"label": "海外银行 / U 卡 / 汇款", "search": "银行 银行卡 汇款 U卡"},
    "cloud": {"label": "VPS 与云服务", "search": "云 VPS 云服务"},
    "esim": {"label": "eSIM", "search": "eSIM 流量"},
    "software": {"label": "软件与数字服务", "search": "软件 数字服务"},
}


def today_local() -> date:
    """北京时间下的“今天”。"""
    return datetime.now(TZ).date()


def now_local() -> datetime:
    return datetime.now(TZ)


def parse_date(value: str | None) -> date | None:
    """把 YYYY-MM-DD 解析成 date；空值或格式不对返回 None。"""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def short_date(value: str | None) -> str:
    d = parse_date(value)
    return f"{d.month}月{d.day}日" if d else ""


def compute_status(deal: dict, today: date) -> str:
    """active / expiring_soon（<=7 天）/ expired。"""
    end = parse_date(deal.get("end", ""))
    if end and end < today:
        return "expired"
    if end and (end - today).days <= EXPIRING_DAYS:
        return "expiring_soon"
    return "active"


def value_expected(deal: dict) -> float:
    """排行榜用的“可预期价值”。

    「最高 $2,000」这类抽奖 / 阶梯任务的 value_num 是上限，
    直接拿来排名会把随机奖励排到真实到手的现金奖励前面，
    因此这类条目在数据里单独给 value_expected（实际期望值），
    没有填写的条目退回 value_num。
    """
    value = deal.get("value_expected")
    if isinstance(value, (int, float)):
        return float(value)
    return float(deal.get("value_num") or 0)
