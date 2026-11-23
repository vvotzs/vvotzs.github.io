#!/usr/bin/env python3
"""羊毛情报局 — 共享常量与工具。

所有与时间、日期、类别、状态有关的规则都放在这里，
maintain_deals.py 与 build_site.py 共用，避免两处口径不一致。
"""
from __future__ import annotations

import re
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
FRESH_SLOTS = 10           # 「最新收录」热榜面板固定 10 格
FRESH_PER_CATEGORY = 2     # 「最新收录」10 格里同一分类最多 2 条（防止某一类霸屏）
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
            (lastmod_of(d, today_iso) for d in deals if d.get("category") == slug),
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
        lastmod = lastmod_of(deal, today_iso)
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
    "ai": {"label": "AI 工具大全", "search": "AI 工具 AI 工具大全 人工智能 免费额度 credits"},
    "crypto": {"label": "Crypto 空投与积分", "search": "Crypto 空投 积分 加密货币 交易奖励"},
    "bank": {"label": "海外银行·U卡·跨境汇款", "search": "银行 银行卡 汇款 U卡 海外银行 跨境汇款"},
    "cloud": {"label": "全球 VPS 与云资源", "search": "云 VPS 云服务 云资源 免费实例"},
    "esim": {"label": "全球 eSIM 指南", "search": "eSIM 流量 指南 漫游"},
    "software": {"label": "软件与数字服务", "search": "软件 数字服务 学生优惠"},
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


def lastmod_of(deal: dict, fallback: str = "") -> str:
    """条目 / 分类页的 lastmod：只返回能解析的 YYYY-MM-DD。

    last_verified 可能是「待核实」这类占位文案（maintain_deals.py 给新条目的默认值），
    直接塞进 <lastmod> / JSON-LD 的 dateModified 会写出非日期，搜索引擎会把整条记录判为无效。
    先试 last_verified，再退回入库日期，都不行才用 fallback（没给就用今天，北京时间）。
    """
    for raw in (deal.get("last_verified"), added_date(deal)):
        text = str(raw or "").strip()[:10]
        if text and parse_date(text):
            return text
    return fallback or today_local().isoformat()


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


# ---------------------------------------------------------------- 去重键 dedup_key
# 格式 brand|category|market|offer_type，全部小写 ASCII，四段都不为空：
#   brand       品牌规范 slug（共用同一张表的标定值，见 BRAND_SLUGS）
#   category    六个分类之一（ai / crypto / bank / cloud / esim / software）
#               保留分类是为了让「同一家银行的存款奖」与「同一家交易所的空投」
#               不会因为品牌相同撞成同一条。
#   market      国家 / 地区代号，ISO 3166-1 alpha-2 小写（gb、us、ae…），多市场按
#               字母序用 - 连接；全球 = global，多区不定 = multi，
#               EEA / 亚太 / 东南亚 / 亚洲另有 eea、apac、sea、asia。
#               子区域（us-la、jp-tyo、cn-4837）一律收绠到国家级，子区域差异留在
#               offer_type 里，否则同一个活动换城市就会绕过判重。
#   offer_type  活动本身的 slug：条目 id 去掉开头的品牌 / 来源站 / 市场标记后的剩余部分。
MARKET_TAGS = {
    "全球": ["GLOBAL"], "全球站": ["GLOBAL"], "全球/国际站": ["GLOBAL"],
    "全球/按发卡地": ["GLOBAL"], "全球/中国站": ["GLOBAL"], "全球/中国区": ["GLOBAL"],
    "中国区/全球": ["GLOBAL"], "中国区/国际版": ["GLOBAL"], "瑞士/全球": ["GLOBAL"],
    "英区": ["GB"], "仅限美国": ["US"], "美区": ["US"], "中国区": ["CN"],
    "日区": ["JP"], "日本区": ["JP"], "香港": ["HK"], "澳门": ["MO"],
    "阿联酋": ["AE"], "韩区": ["KR"], "印度区": ["IN"], "泰区": ["TH"],
    "新加坡": ["SG"], "缅区": ["MM"], "菲区": ["PH"], "澳区": ["AU"],
    "法区": ["FR"], "德区": ["DE"], "荷区": ["NL"], "波区": ["PL"],
    "克区": ["HR"], "爱尔兰": ["IE"], "沙特": ["SA"], "卡塔尔": ["QA"],
    "黎巴嫩": ["LB"], "马来": ["MY"], "印尼": ["ID"], "秘鲁": ["PE"],
    "亚太发卡": ["APAC"], "亚洲 12 国": ["ASIA"], "欧区": ["EEA"],
    "EEA 欧区": ["EEA"], "欧区 17 国": ["EEA"], "欧洲+英国": ["EEA", "GB"],
    "多区": ["MULTI"], "美区/多区": ["MULTI"], "非美 47 国": ["MULTI"],
    "美/加区": ["US", "CA"], "美区/日本": ["US", "JP"], "美区/欧区": ["US", "EEA"],
    "英区/欧区": ["GB", "EEA"], "美/英/欧区": ["US", "GB", "EEA"],
    "英/美/加/澳": ["GB", "US", "CA", "AU"], "美/加/日/新/墨/澳": ["US", "CA", "JP", "SG", "MX", "AU"],
    "日/韩/美/加/澳/印": ["JP", "KR", "US", "CA", "AU", "IN"], "日区/韩区": ["JP", "KR"],
    "台/泰/马/越": ["TW", "TH", "MY", "VN"],
}

# 品牌规范 slug：中文名、带符号或容易拆错的名字在这里定死，其余走默认规则
# （品牌名第一个 ASCII 词，取不到就用 id 的第一个词）。
BRAND_SLUGS = {
    "中信银行": "citic", "中国工商银行": "icbc", "中国银行": "boc",
    "中国联通": "unicom", "中国电信香港 CTExcel": "ctexcel",
    "中国电信 星辰": "teleagent", "平安数字银行（PingAnDB）": "pingandb",
    "螞蟻銀行（澳門）": "antbank", "阿里云国际站": "alibabacloud", "阿里云": "aliyun",
    "腾讯云": "tencentcloud", "腾讯云 TokenHub": "tencentcloud",
    "腾讯云 WorkBuddy": "tencentcloud", "百度智能云千帆": "baidu-qianfan",
    "联通云（CUCloud）": "cucloud", "网易 UU 远程": "netease-uu",
    "华为云 CodeArts": "huaweicloud", "智谱 AutoClaw（澳龙）": "zhipu",
    "阶跃星辰 StepFun": "stepfun", "小米 MiMo": "xiaomi", "小米 × Google": "xiaomi",
    "さくらのAI Engine": "sakura-ai", "超算互联网 SCNet": "scnet", "七牛云": "qiniu",
    "ModelScope 魔搭 × AMD": "modelscope", "八达通 Octopus": "octopus",
    "我们WON모바일 (Woori Bank)": "wooriwon-mobile", "U.S. Bank": "usbank",
    "E*TRADE": "etrade", "J.P. Morgan Personal Investing": "jpmorgan",
    "Charles Schwab": "schwab", "Bank of America": "bofa", "Wells Fargo": "wellsfargo",
    "first direct": "firstdirect", "Co-operative Bank": "coop-bank",
    "Al Rajhi Bank": "alrajhi", "e& UAE (etisalat)": "eand", "e& UAE": "eand",
    "Y!mobile": "ymobile", "Y!mobile（Yahoo!ショッピング店）": "ymobile",
    "UQ mobile": "uq-mobile", "UQ mobile（KDDI）": "uq-mobile",
    "LG HelloVision Hello Mobile": "hellomobile", "LG AI Research": "lgai",
    "Kite × Bitrefill": "kite", "GigSky × Visa": "gigsky", "GigSky": "gigsky",
    "SoSIM（和记电讯 3HK）": "sosim", "SoSIM (3HK)": "sosim", "True Corporation": "true",
    "Apple Card（Goldman Sachs 发行）": "apple", "Rakuten × Alliant Credit Union": "rakuten",
    "Amazon Music": "amazon", "Google Cloud": "google", "Google Gemini": "google",
    "Google Flow": "google", "Microsoft Azure": "microsoft", "Nous Research": "nous",
    "Cognition / Poke": "cognition", "American Express": "amex", "A1 Hrvatska": "a1",
    "TD Bank": "td", "Citizens Bank": "citizens", "Ally Bank": "ally", "PNC Bank": "pnc", "KT M mobile": "kt", "kt M mobile": "kt",
}

MARKET_TOKENS = {
    "us", "uk", "gb", "cn", "hk", "mo", "tw", "jp", "kr", "sg", "my", "th",
    "vn", "ph", "id", "in", "mm", "lb", "qa", "ae", "sa", "il", "au", "nz",
    "ca", "mx", "br", "pe", "ch", "ie", "nl", "be", "pl", "cz", "sk", "hu",
    "ro", "hr", "de", "fr", "es", "it", "pt", "at", "dk", "se", "fi", "no",
    "gr", "ee", "lt", "lv", "bg", "cy", "mt", "tr", "eg", "eu", "eea", "sea",
    "apac", "asia", "global", "multi", "la", "tyo", "las", "4837",
}
SOURCE_PREFIXES = {"nodeseek", "vps-taxi", "reddit", "hackernews", "hn", "tg", "telegram"}
OFFER_STOP = {"bank", "card", "app", "official", "com", "www"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", str(text or "").lower()) if t]


def market_codes(deal: dict) -> list[str]:
    """从标题开头的 [区域] 标签取市场代号；取不到时退回 regions 字段的标签写法。"""
    text = str(deal.get("title") or "")
    match = re.match(r"^\s*[\[【]([^\]】]{1,32})[\]】]", text)
    tag = match.group(1).strip() if match else ""
    if tag in MARKET_TAGS:
        return MARKET_TAGS[tag]
    if tag:
        # 标签写成其它组合时按分隔符拆开逐段翻译，漏掉的段直接忽略
        codes: list[str] = []
        for piece in re.split(r"[/、，,+＋]", tag):
            piece = piece.strip()
            if piece in MARKET_TAGS:
                codes.extend(MARKET_TAGS[piece])
                continue
            for key, val in MARKET_TAGS.items():
                if not key.endswith("国") and piece.startswith(key):
                    codes.extend(val)
                    break
        if codes:
            return codes
    return ["MULTI"]


def market_code(deal: dict) -> str:
    codes = market_codes(deal)
    if "GLOBAL" in codes:
        return "global"
    if "MULTI" in codes or not codes:
        return "multi"
    return "-".join(sorted({c.lower() for c in codes}))


def brand_slug(deal: dict) -> str:
    brand = str(deal.get("brand") or "").strip()
    if brand in BRAND_SLUGS:
        return BRAND_SLUGS[brand]
    words = [w for w in _tokens(brand) if w not in MARKET_TOKENS and len(w) > 1]
    if not words:
        words = [w for w in _tokens(brand) if w not in MARKET_TOKENS]
    if words:
        slug = "-".join(words[:2])
        return slug if len(slug) <= 12 else words[0]
    ids = _tokens(deal.get("id"))
    return ids[0] if ids else "unknown"


def offer_slug(deal: dict, brand: str | None = None) -> str:
    """活动 slug：id 去掉开头的品牌 / 来源站 / 市场 / 通用词。"""
    brand = brand or brand_slug(deal)
    compact = brand.replace("-", "")
    tokens = _tokens(deal.get("id"))
    drop = set(_tokens(brand)) | MARKET_TOKENS | SOURCE_PREFIXES | OFFER_STOP
    while tokens and (tokens[0] in drop or tokens[0] in compact):
        tokens.pop(0)
    slug = "-".join(tokens)
    return slug or "-".join(_tokens(deal.get("id"))) or "offer"


def dedup_key(deal: dict) -> str:
    """brand|category|market|offer_type；四个字段都不为空，可直接入库。"""
    brand = brand_slug(deal)
    category = str(deal.get("category") or "").strip().lower() or "unknown"
    return "|".join([brand, category, market_code(deal), offer_slug(deal, brand)])
