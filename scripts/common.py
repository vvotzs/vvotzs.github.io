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
CLOSING_SLOTS = 10         # 「即将截止」热榜面板固定排 10 条（7 天内不足时用 8～30 天补足）
# 过期活动永久保留：作为 SEO 长尾落地页与查档页持续沉淀，任何条目都不再被删除。
ARCHIVE_RETENTION = "permanent"   # 写入 meta.json 的 archive_retention_days

# ---------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "deals.json"
META = ROOT / "data" / "meta.json"
SITEMAP = ROOT / "sitemap.xml"
OUT = ROOT / "index.html"
FAV_DIR = ROOT / "assets" / "fav"

SITE_URL = "https://vvotzs.github.io/"
OG_IMAGE = SITE_URL + "assets/og-cover.png"
OG_IMAGE_EN = SITE_URL + "assets/og-cover-en.png"

# 单条独立详情页：中文 /d/<id>/，英文 /en/d/<id>/（目录名就是条目 id）
DEALS_DIR = ROOT / "d"
DEALS_DIR_EN = ROOT / "en" / "d"

# 静态分类目录页：中文 /category/<slug>/，英文 /en/category/<slug>/
CATEGORY_DIR = ROOT / "category"
CATEGORY_DIR_EN = ROOT / "en" / "category"

# 合规页（AdSense 审核要求）：中文 /about/，英文 /en/about/；slug 见 i18n.LEGAL_PAGES
LEGAL_SLUGS = ("about", "privacy", "disclosure")


def deal_path(deal_id: str, lang: str = "zh") -> str:
    """条目的站内相对路径（不带开头的斜杠）：`d/<id>/` 或 `en/d/<id>/`。"""
    return ("en/" if lang == "en" else "") + f"d/{deal_id}/"


def deal_url(deal_id: str, lang: str = "zh") -> str:
    return SITE_URL + deal_path(deal_id, lang)


def cat_path(slug: str, lang: str = "zh") -> str:
    """分类目录页的站内相对路径：`category/<slug>/` 或 `en/category/<slug>/`。"""
    return ("en/" if lang == "en" else "") + f"category/{slug}/"


def cat_url(slug: str, lang: str = "zh") -> str:
    return SITE_URL + cat_path(slug, lang)


def write_sitemap(deals: list[dict], today: date | None = None) -> Path:
    """写 sitemap.xml：首页中英两版 + 全部分类目录页 + 全部条目的中英详情页。

    maintain_deals.py（每轮巡检）与 build_site.py（每次构建）都调这里，
    保证「数据里有多少条」与「sitemap 里有多少个详情页」永远一致；
    每个 <url> 都带 hreflang 三件套，方便搜索引擎把中英两版当成一对。
    已过期条目同样保留在 sitemap 里：它们是长期有效的查档页。
    """
    day = today or today_local()
    today_iso = day.isoformat()

    def alt_block(alternates: list[tuple[str, str]]) -> str:
        return "".join(
            f'    <xhtml:link rel="alternate" hreflang="{h}" href="{href}"/>\n'
            for h, href in alternates
        )

    home_zh = SITE_URL
    home_en = SITE_URL + "en/"
    home_alt = [("zh-CN", home_zh), ("en", home_en), ("x-default", home_zh)]

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n',
    ]

    def add(loc: str, alts: list[tuple[str, str]], lastmod: str, freq: str, prio: str) -> None:
        parts.append("  <url>\n")
        parts.append(f"    <loc>{loc}</loc>\n")
        parts.append(alt_block(alts))
        parts.append(f"    <lastmod>{lastmod}</lastmod>\n")
        parts.append(f"    <changefreq>{freq}</changefreq>\n")
        parts.append(f"    <priority>{prio}</priority>\n")
        parts.append("  </url>\n")

    add(home_zh, home_alt, today_iso, "daily", "1.0")
    add(home_en, home_alt, today_iso, "daily", "0.8")

    # 分类目录页：每个分类中英各一份，lastmod 取该分类里最新一次核验 / 收录的日期
    for slug in CAT_META:
        cat_last = max(
            (str(d.get("last_verified") or added_date(d) or today_iso)[:10]
             for d in deals if d.get("category") == slug),
            default=today_iso,
        )
        zh = cat_url(slug, "zh")
        en = cat_url(slug, "en")
        # 目录页的 hreflang 用 zh-Hans（与页面 <head> 里的声明一致），中文是简体
        alts = [("zh-Hans", zh), ("en", en), ("x-default", zh)]
        add(zh, alts, cat_last, "daily", "0.9")
        add(en, alts, cat_last, "daily", "0.7")

    # 合规页：about / privacy / disclosure 中英各一份，lastmod 用相同的更新日
    for slug in LEGAL_SLUGS:
        zh = SITE_URL + slug + "/"
        en = SITE_URL + "en/" + slug + "/"
        alts = [("zh-CN", zh), ("en", en), ("x-default", zh)]
        add(zh, alts, today_iso, "monthly", "0.4")
        add(en, alts, today_iso, "monthly", "0.3")

    for deal in deals:
        deal_id = str(deal.get("id") or "").strip()
        if not deal_id:
            continue
        zh = deal_url(deal_id, "zh")
        en = deal_url(deal_id, "en")
        alts = [("zh-CN", zh), ("en", en), ("x-default", zh)]
        # 条目内容最后一次被核验 / 收录的日期；两者都缺就用今天
        lastmod = str(deal.get("last_verified") or added_date(deal) or today_iso)[:10]
        expired = deal.get("status") == "expired"
        freq, prio = ("yearly", "0.3") if expired else ("weekly", "0.6")
        add(zh, alts, lastmod, freq, prio)
        add(en, alts, lastmod, freq, prio)

    parts.append("</urlset>\n")
    SITEMAP.write_text("".join(parts), encoding="utf-8")
    return SITEMAP


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


def added_date(deal: dict) -> str:
    """条目的入库日期（YYYY-MM-DD）——「新收录」筛选与展示的唯一口径。

    added_at 是带时分的入库时间，added 是展示用的日期；两者必须落在同一天。
    """
    return str(deal.get("added_at") or deal.get("added") or "")[:10]


def ensure_added_at(deals: list[dict], when: datetime | None = None) -> bool:
    """补齐入库相关字段（added_at / added），返回是否改动。

    「新收录」要按入库先后排，而 added 只精确到日期、同一批往往几十条并列，
    所以每条需要一份带时分的 added_at。新条目入库时（维护 / 构建）自动补，
    人工往 deals.json 里追加也不用记着填。

    added（展示用的 YYYY-MM-DD）也要一起兜底：只写了 added_at 的条目，
    卡片底部会渲染成空的「收录 · 」。回填顺序是 added_at 的日期部分，
    两者都缺时再用当天（北京时间）。

    两个字段还会互相对齐：added 是人工登记的入库日期，added_at 的日期部分
    必须等于它。历史上一次性回填脚本按 commit 时间写过 added_at，把 26 条
    老条目记成了「今天」，卡片显示「收录 11-13」却排在真正的新条目前面。
    这里发现日期不一致就把 added_at 归一到 added 当天 00:00（北京时间），
    让筛选、排序、展示三处永远同一个日期。
    """
    now = when or now_local()
    stamp = now.isoformat(timespec="seconds")
    fallback_day = now.date().isoformat()
    changed = False
    for deal in deals:
        if not deal.get("added_at"):
            deal["added_at"] = stamp
            changed = True
        if not deal.get("added"):
            deal["added"] = added_date(deal) or fallback_day
            changed = True
        day = str(deal.get("added"))[:10]
        if day and str(deal["added_at"])[:10] != day:
            deal["added_at"] = day + "T00:00:00+08:00"
            changed = True
    return changed


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
