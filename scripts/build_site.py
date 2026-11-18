#!/usr/bin/env python3
"""羊毛情报局 — 静态页面生成器。

读取 data/deals.json 与 data/meta.json，生成纯静态 index.html
（卡片全部是真实 HTML，方便搜索引擎抓取；筛选 / 手风琴 / 折叠由 app.js 增强）。

工程要点：
  · 时区统一北京时间（见 scripts/common.py）；
  · 分类区渲染完整 12 字段卡片，每个活动只出现一次（#deal-<id>）；
  · 顶部热榜板（新收录 / 高价值榜 | 即将截止 / 抽奖）与各分区用精简跳转卡，
    点一下滚到分类区那张卡片并展开，这样 index.html 不重复三遍详情；
  · 所有图标抽成一份 <svg> sprite，卡片里只剩 <use href="#i-xxx">；
  · 搜索文本放进 <script id="search-index"> JSON，不再挂在每张 DOM 上；
  · 图标在构建时下载到 assets/fav/<domain>.png，境内用户直连 GitHub Pages 即可显示。
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from common import (  # noqa: E402
    CAT_META,
    CLOSING_WINDOW_DAYS,
    DATA,
    FAV_DIR,
    META,
    OG_IMAGE,
    OUT,
    SITE_URL,
    TODAY_WINDOW_DAYS,
    compute_status,
    now_local,
    parse_date,
    short_date,
    today_local,
    value_expected,
)

try:
    from PIL import Image
except ImportError:  # Pillow 缺失时图标退化为字母块，不阻塞构建
    Image = None  # type: ignore[assignment]

FAV_UA = "Mozilla/5.0 (compatible; YangMaoBot/1.0; +https://vvotzs.github.io/)"
FAV_SIZE = 64

# ---------------------------------------------------------------- svg sprite
# (viewBox 边长, 内部图形, stroke-width)。所有图标统一 currentColor 描边，
# 有颜色的部位直接在图形上写 fill，跟以前逐处内联的效果一致。
_SYMBOLS: dict[str, tuple[int, str, float]] = {
    # 新收录：暖色火苗
    "today": (24, '<path d="M12 2.9c2.9 3.1 4.6 5.7 4.6 8.5a4.6 4.6 0 1 1-9.2 0c0-2.8 1.7-5.4 4.6-8.5Z" fill="#FDBA74"/>'
                  '<path d="M12 9.4c1.3 1.5 2 2.7 2 4a2 2 0 1 1-4 0c0-1.3.7-2.5 2-4Z" fill="#FEF3C7"/>', 1.9),
    # 榜单：奖杯
    "rank": (24, '<path d="M7.6 3.5h8.8v4.9a4.4 4.4 0 0 1-8.8 0V3.5Z" fill="#FCD34D"/>'
                 '<path d="M7.6 5.1H5.1a2.6 2.6 0 0 0 2.6 4.6"/>'
                 '<path d="M16.4 5.1h2.5a2.6 2.6 0 0 1-2.6 4.6"/>'
                 '<path d="M12 12.8v2.4"/><path d="M9.2 15.2h5.6v3.3H9.2z" fill="#FED7AA"/>'
                 '<path d="M7.8 18.5h8.4"/>', 1.9),
    # AI：圆角徽标 + 粗体 AI
    "ai": (24, '<rect x="2.4" y="5.2" width="19.2" height="13.6" rx="4.8" fill="#DBEAFE"/>'
               '<text x="11.2" y="15.6" text-anchor="middle" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif"'
               ' font-size="10.2" font-weight="800" fill="#1E40AF" stroke="none">AI</text>'
               '<path d="M19.4 3.1l.55 1.35 1.35.55-1.35.55-.55 1.35-.55-1.35-1.35-.55 1.35-.55.55-1.35Z" fill="#F59E0B"/>', 1.9),
    # 币：金币 + ₿
    "crypto": (24, '<circle cx="12" cy="12" r="8.5" fill="#FCD34D"/>'
                   '<path d="M10.6 7.1v9.8M12.4 7.1v9.8" stroke="#92400E" stroke-width="1.15"/>'
                   '<path d="M10.6 8.9h3.1a1.6 1.6 0 0 1 0 3.2h-3.1z" fill="#92400E"/>'
                   '<path d="M10.6 12.1h3.5a1.75 1.75 0 0 1 0 3.5h-3.5z" fill="#92400E"/>', 1.9),
    # 卡：银行卡（磁条 + 芯片）
    "bank": (24, '<rect x="2.4" y="5.4" width="19.2" height="13.2" rx="3.2" fill="#BBF7D0"/>'
                 '<path d="M2.4 9.2h19.2" stroke-width="2.4"/>'
                 '<rect x="4.9" y="12.2" width="4.1" height="3.3" rx="1" fill="#FDE68A" stroke="none"/>'
                 '<path d="M11.4 14.4h6.4"/>', 1.9),
    # 云：云朵
    "cloud": (24, '<path d="M7.4 17.9h9.2a3.5 3.5 0 0 0 .4-7A5.3 5.3 0 0 0 7 10.3a3.8 3.8 0 0 0 .4 7.6Z" fill="#BFDBFE"/>', 1.9),
    # eSIM：SIM 卡（切角 + 信号弧）
    "esim": (24, '<path d="M7.4 3.4h5.9l4.1 4.1v12.1a1.9 1.9 0 0 1-1.9 1.9H7.4a1.9 1.9 0 0 1-1.9-1.9V5.3a1.9 1.9 0 0 1 1.9-1.9Z" fill="#FED7AA"/>'
                '<rect x="8.3" y="11.3" width="6.2" height="5.5" rx="1.2" fill="#FFFDF9" stroke="none"/>'
                '<path d="M9.7 8.6a4.2 4.2 0 0 1 3.4 0"/>', 1.9),
    # 截止：闹钟
    "clock": (24, '<circle cx="12" cy="13.6" r="6.8" fill="#FECDD3"/>'
                  '<path d="M12 10.1v3.6l2.3 1.5"/>'
                  '<path d="M4.9 6.9 7 4.8M19.1 6.9 17 4.8"/>'
                  '<path d="M9 20.4l-1.1 1.2M15 20.4l1.1 1.2"/>', 1.9),
    # 软件：2×2 应用宫格
    "software": (24, '<rect x="3.6" y="3.6" width="7.2" height="7.2" rx="2.1" fill="#C4B5FD" stroke="none"/>'
                     '<rect x="13.2" y="3.6" width="7.2" height="7.2" rx="2.1" fill="#A5B4FC" stroke="none"/>'
                     '<rect x="3.6" y="13.2" width="7.2" height="7.2" rx="2.1" fill="#A5B4FC" stroke="none"/>'
                     '<rect x="13.2" y="13.2" width="7.2" height="7.2" rx="2.1" fill="#C4B5FD" stroke="none"/>', 1.9),
    # 抽奖：礼物盒
    "gift": (24, '<path d="M3.9 9.5h16.2v3.4H3.9z" fill="#FDE68A"/>'
                '<path d="M5.3 12.9h13.4v7.2a1.7 1.7 0 0 1-1.7 1.7H7a1.7 1.7 0 0 1-1.7-1.7v-7.2Z" fill="#FED7AA"/>'
                '<path d="M12 9.5v12.1"/>'
                '<path d="M12 9.2C10.6 5.9 9.3 4.9 7.9 4.9a2.05 2.05 0 0 0 0 4.1H12Zm0 0c1.4-3.3 2.7-4.3 4.1-4.3a2.05 2.05 0 0 1 0 4.1H12Z"/>', 1.9),
    # 归档：档案盒
    "archive": (24, '<rect x="3.4" y="4.2" width="17.2" height="4.4" rx="1.7" fill="#FED7AA"/>'
                    '<path d="M4.9 8.6h14.2v9.6a1.8 1.8 0 0 1-1.8 1.8H6.7a1.8 1.8 0 0 1-1.8-1.8V8.6Z" fill="#E7E5E4"/>'
                    '<path d="M9.6 12.3h4.8"/>', 1.9),
    # 火箭（回到顶部）
    "rocket": (24, '<path d="M12 2.7c3 2.3 4.6 5.7 4.6 9.3 0 2.1-.6 4-1.7 5.5H9.1c-1.1-1.5-1.7-3.4-1.7-5.5 0-3.6 1.6-7 4.6-9.3Z" fill="#FED7AA"/>'
                   '<circle cx="12" cy="10.1" r="1.9" fill="#BFDBFE"/>'
                   '<path d="M9.1 17.1 6.5 19.8c.1-1.9.6-3.3 1.5-4.3"/>'
                   '<path d="M14.9 17.1l2.6 2.7c-.1-1.9-.6-3.3-1.5-4.3"/>'
                   '<path d="M12 20.9c-.9 0-1.6-.9-1.6-2.1h3.2c0 1.2-.7 2.1-1.6 2.1Z" fill="#FDE68A"/>', 1.9),
    # 外链箭头
    "external": (12, '<path d="M3 9 9 3M4.5 3H9v4.5"/>', 1.6),
    # 展开箭头
    "chevron": (12, '<path d="m2.5 4.5 3.5 3.5 3.5-3.5"/>', 1.8),
    # 搜索
    "search": (16, '<circle cx="7" cy="7" r="4.4"/><path d="m10.4 10.4 3 3"/>', 1.6),
    # 风险提示
    "warn": (16, '<path d="M8 2.6 14.2 13H1.8L8 2.6Z"/><path d="M8 6.6v3.1M8 11.6v.1"/>', 1.4),
    # 薄荷小怪兽（页头 / 页脚共用，渐变在 sprite 的 defs 里只定义一次）
    "mascot": (40, '<path d="M20 3.6c8.6 0 13.1 5.9 13.1 14.2 0 9.6-5.4 18.6-13.1 18.6S6.9 27.4 6.9 17.8C6.9 9.5 11.4 3.6 20 3.6Z" fill="url(#mintBody)" stroke="none"/>'
                  '<path d="M20 3.6c-2.6 0-4.9.6-6.8 1.7 2.4 2 8.9 2.1 12.9.2-1.8-1.2-3.9-1.9-6.1-1.9Z" fill="#5FD3A6" opacity=".55" stroke="none"/>'
                  '<ellipse cx="20" cy="20.4" rx="9.1" ry="8.4" fill="#F3FFF9" stroke="none"/>'
                  '<circle cx="16.8" cy="19.3" r="1.35" fill="#14532D" stroke="none"/>'
                  '<circle cx="23.2" cy="19.3" r="1.35" fill="#14532D" stroke="none"/>'
                  '<circle cx="15.9" cy="18.7" r=".4" fill="#FFFFFF" opacity=".9" stroke="none"/>'
                  '<circle cx="22.3" cy="18.7" r=".4" fill="#FFFFFF" opacity=".9" stroke="none"/>'
                  '<ellipse cx="13.6" cy="22.4" rx="1.6" ry="1.1" fill="#FCA5A5" opacity=".5" stroke="none"/>'
                  '<ellipse cx="26.4" cy="22.4" rx="1.6" ry="1.1" fill="#FCA5A5" opacity=".5" stroke="none"/>'
                  '<path d="M18.3 22.7c.5.85 2.9.85 3.4 0" fill="none" stroke="#14532D" stroke-width="1.25" stroke-linecap="round"/>'
                  '<path d="M20 3.9c.1-1.5.9-2.5 2.3-2.9-.1 1.5-.9 2.5-2.3 2.9Z" fill="#34D399" stroke="none"/>', 1.9),
}


def sprite_svg() -> str:
    """整页共用的一份图标 sprite：<symbol> 定义一次，各处 <use> 引用。"""
    parts = [
        '<svg class="sprite" style="display:none" aria-hidden="true" focusable="false">',
        '<defs><linearGradient id="mintBody" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0" stop-color="#B7F5DA"/><stop offset="1" stop-color="#7FE3B8"/>'
        "</linearGradient></defs>",
    ]
    for key, (size, inner, sw) in _SYMBOLS.items():
        parts.append(
            f'<symbol id="i-{key}" viewBox="0 0 {size} {size}" fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{inner}</symbol>'
        )
    parts.append("</svg>")
    return "".join(parts)


def icon(key: str, cls: str = "") -> str:
    return f'<svg class="i{" " + cls if cls else ""}" aria-hidden="true"><use href="#i-{key}"/></svg>'


def mascot_svg(cls: str = "") -> str:
    return icon("mascot", cls)


NAV = [
    ("fresh", "新收录", "today"),
    ("rank", "榜单", "rank"),
    ("ai", "AI", "ai"),
    ("crypto", "币", "crypto"),
    ("bank", "卡", "bank"),
    ("cloud", "云", "cloud"),
    ("esim", "eSIM", "esim"),
    ("closing", "截止", "clock"),
    ("software", "软件", "software"),
    ("archive", "归档", "archive"),
]

COST_CLASS = {
    "真正免费": "cost-free",
    "免费试用": "cost-trial",
    "需要充值": "cost-deposit",
    "需要交易量": "cost-volume",
    "需要邀请条件": "cost-invite",
}


def asset_ver(rel: str) -> str:
    """给静态资源带上内容哈希，避免 GitHub Pages CDN 缓存旧样式。"""
    path = ROOT / rel
    if not path.exists():
        return "1"
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def deadline_html(deal: dict, today) -> str:
    end = parse_date(deal.get("end", ""))
    if not end:
        return '<span class="deadline">长期有效</span>'
    if end < today:
        return f'<span class="deadline">{short_date(deal["end"])} 结束</span>'
    left = (end - today).days
    if left <= 1:
        return '<span class="deadline hot">今天截止</span>'
    if left <= 30:
        return f'<span class="deadline hot">剩 {left} 天 · {short_date(deal["end"])}</span>'
    return f'<span class="deadline">{short_date(deal["end"])} 截止</span>'


def short_deadline(deal: dict, today) -> str:
    """跳转卡第二行用的极短截止提示。"""
    end = parse_date(deal.get("end", ""))
    if not end:
        return "长期有效"
    left = (end - today).days
    if left < 0:
        return "已结束"
    if left <= 1:
        return "今天截止"
    if left <= 30:
        return f"剩 {left} 天"
    return short_date(deal["end"])


# ---------------------------------------------------------------- 价值展示
# 只看「上限」会把 Coinbase 的 $2,000 排到第一，所以排序与展示都优先用
# value_expected（可预期到手金额）。单位统一折成 ≈$ 后再附原币，方便横向对比。
_USD_RATE = {
    "$": 1.0,
    "USDT": 1.0,
    "USD": 1.0,
    "£": 1.27,
    "€": 1.08,
    "¥": 0.14,
    "HKD": 0.128,
    "₹": 0.0119,
}
_MONEY_RE = re.compile(r"(USDT|USD|HKD|[$€£¥₹])\s*([\d,]+(?:\.\d+)?)")
_MONEY_SUFFIX_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(USDT|USD|HKD)")


def _paren_estimate(raw: str) -> tuple[float | None, str]:
    """把「（≈$42）」里的折算值抽出来，并把那段数字从原文里去掉。"""
    m = re.search(r"[（(]([^）()]*?[≈约]\s*(?:US)?\$\s*[\d,]+(?:\.\d+)?[^）()]*)[）)]", raw)
    if not m:
        return None, raw
    inner = m.group(1)
    found = re.search(r"[≈约]\s*(?:US)?\$\s*([\d,]+(?:\.\d+)?)", inner)
    if not found:
        return None, raw
    est = float(found.group(1).replace(",", ""))
    rest = re.sub(r"[,，\s]*[≈约]\s*(?:US)?\$\s*[\d,]+(?:\.\d+)?", "", inner).strip(" ，,、")
    if rest:
        new = raw[: m.start()] + "（" + rest + "）" + raw[m.end():]
    else:
        new = raw[: m.start()] + raw[m.end():]
    return est, new.strip()


def value_display(deal: dict) -> str:
    """统一成「≈$25 · 最高 $2,000」这种可比格式。"""
    raw = (deal.get("value") or "").strip()
    exp = value_expected(deal)

    est, rest = _paren_estimate(raw)
    if est is not None:
        return f"≈${est:,.0f} · {rest}" if rest else f"≈${est:,.0f}"

    if is_high_cap(deal):
        return f"≈${exp:,.0f} · {raw}" if raw else f"≈${exp:,.0f}"

    m = _MONEY_RE.search(raw) or None
    cur = num = None
    if m:
        cur, num = m.group(1), m.group(2)
    else:
        m2 = _MONEY_SUFFIX_RE.search(raw)
        if m2:
            num, cur = m2.group(1), m2.group(2)
    if cur and num:
        if cur in ("$", "USD", "USDT"):
            return raw  # 本来就是美元，不用再折一次
        usd = float(num.replace(",", "")) * _USD_RATE.get(cur, 1.0)
        return f"≈${usd:,.0f} · {raw}"

    if exp <= 0:
        return raw
    return f"≈${exp:,.0f} · {raw}" if raw else f"≈${exp:,.0f}"


def value_compact(deal: dict) -> str:
    """热榜窄条用的短价值：去括号补充说明，还长就只留「≈$X」。"""
    v = re.sub(r"[（(][^）)]*[）)]", "", value_display(deal)).strip()
    if len(v) > 18 and " · " in v:
        v = v.split(" · ")[0]
    return v


def title_parts(raw_title: str) -> tuple[str, str]:
    """拆出标题前的 [地区] 标签与正文。"""
    m = re.match(r"^\[([^\]]{1,24})\]\s*(.*)$", raw_title)
    return (m.group(1), m.group(2)) if m else ("", raw_title)


def strip_region_bracket(value: str) -> str:
    """卡片第三行的地区说明去掉 [美区] 这类前缀——标题前的胶囊已经有了。"""
    return re.sub(r"^\s*\[[^\]]{1,24}\]\s*", "", (value or "").strip())


def is_high_cap(deal: dict) -> bool:
    """上限远高于可预期到手金额：抽奖 / 随机 / 阶梯类。"""
    exp = deal.get("value_expected")
    vn = float(deal.get("value_num") or 0)
    return isinstance(exp, (int, float)) and vn > 0 and float(exp) < vn * 0.9


# ------------------------------------------------------------------ favicons
def fav_name(domain: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "_", (domain or "").lower()).strip("._") or "site"


def _download(url: str, timeout: float = 8.0) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": FAV_UA, "Accept": "image/*,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(2_000_000)
        return data or None
    except Exception:
        return None


def _save_icon(raw: bytes, dest: Path) -> bool:
    """把任意格式（png / ico / svg 转出的位图）统一成 64×64 PNG。"""
    if Image is None or not raw:
        return False
    try:
        icon = Image.open(io.BytesIO(raw))
        icon.load()
    except Exception:
        return False
    if icon.width < 8 or icon.height < 8:
        return False
    icon = icon.convert("RGBA")
    side = max(icon.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(icon, ((side - icon.width) // 2, (side - icon.height) // 2), icon)
    resample = Image.LANCZOS if side >= FAV_SIZE else Image.BICUBIC
    canvas.resize((FAV_SIZE, FAV_SIZE), resample).save(dest, "PNG", optimize=True)
    return True


def _icon_from_homepage(domain: str) -> bytes | None:
    """兜底：读首页 <link rel="...icon..."> 指到的图标（有些站点不在 /favicon.ico）。"""
    for base in (f"https://{domain}/", f"https://www.{domain}/"):
        page = _download(base)
        if not page:
            continue
        text = page.decode("utf-8", "ignore")
        for tag in re.findall(r"<link[^>]+>", text, re.I):
            if not re.search(r"rel=[\"'][^\"']*icon[^\"']*[\"']", tag, re.I):
                continue
            href = re.search(r"href=[\"']([^\"']+)[\"']", tag, re.I)
            if not href:
                continue
            url = urllib.parse.urljoin(base, href.group(1))
            raw = _download(url)
            if raw:
                return raw
    return None


def ensure_favicon(domain: str) -> bool:
    """把域名图标缓存成 assets/fav/<domain>.png；有缓存就直接复用。"""
    if not domain:
        return False
    FAV_DIR.mkdir(parents=True, exist_ok=True)
    dest = FAV_DIR / f"{fav_name(domain)}.png"
    if dest.exists() and dest.stat().st_size > 200:
        return True
    if Image is None:
        return False

    candidates = [
        f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
        f"https://icons.duckduckgo.com/ip3/{domain}.ico",
        f"https://{domain}/favicon.ico",
    ]
    if not domain.startswith("www."):
        # 有些站点裸域不解析（例如 www.antbank.mo），补一轮 www 变体
        candidates += [
            f"https://www.google.com/s2/favicons?domain=www.{domain}&sz=64",
            f"https://www.{domain}/favicon.ico",
        ]
    for url in candidates:
        if _save_icon(_download(url) or b"", dest):
            return True

    raw = _icon_from_homepage(domain)
    return _save_icon(raw or b"", dest)


# --------------------------------------------------------------------- cards
def detail_tags(deal: dict) -> str:
    cat = CAT_META.get(deal.get("category", ""), {"label": deal.get("category", "")})["label"]
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    if deal.get("verified"):
        check = '<span class="dcheck ok">✓ 已核验</span>'
    else:
        check = '<span class="dcheck wait">待核实</span>'
    return (
        '<div class="detail-tags">'
        f'<span class="dtag cat">{e(cat)}</span>'
        f'<span class="dval"><span class="dval-k">实际价值</span><strong>{e(value_display(deal))}</strong></span>'
        f'<span class="dtag {cost_cls}">{e(cost)}</span>'
        f"{check}"
        "</div>"
    )


def card(deal: dict, today) -> str:
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    expired = bool(deal.get("status") == "expired")
    classes = "card is-expired" if expired else "card"

    steps = "".join(f"<li>{e(s)}</li>" for s in deal.get("steps", []))
    if not steps:
        steps = "<li>见官方活动页</li>"

    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"

    region_tag, title_text = title_parts(deal.get("title", ""))
    if region_tag:
        title_html = f'<span class="rtag">{e(region_tag)}</span>{e(title_text)}'
    else:
        title_html = e(title_text)

    fav = f"assets/fav/{fav_name(deal.get('domain', ''))}.png"
    monogram = (deal.get("brand") or "?")[:1].upper()
    deal_id = e(deal["id"])

    return f"""<article class="{classes}" id="deal-{deal_id}" data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(deal.get('added', ''))}" data-val-exp="{value_expected(deal):g}" data-key="{deal_id}">
    <div class="card-head">
      <img class="fav" src="{fav}" width="24" height="24" alt=""
           loading="lazy" decoding="async" data-fallback="{e(monogram)}"
           onerror="window.__favFallback&&window.__favFallback(this)">
      <span class="fav-fallback" style="display:none" aria-hidden="true">{e(monogram)}</span>
      <div class="card-body">
        <div class="row1">
          <h3>{title_html}</h3>
          <span class="{value_cls}">{e(value_display(deal))}</span>
        </div>
        <p class="row2"><span class="tag {cost_cls}">{e(cost)}</span>{e(deal['highlight'])}</p>
        <div class="row3">
          <span class="region">{e(strip_region_bracket(deal['regions']))}</span>
          <span class="sep">·</span>
          {deadline_html(deal, today)}
          <span class="grow"></span>
          <a class="go" href="{e(deal['url'])}" target="_blank" rel="noopener nofollow">直达原链接
            {icon('external')}</a>
          <button class="toggle" type="button" aria-expanded="false" aria-controls="detail-{deal_id}"
                  aria-label="展开详情">详情
            {icon('chevron')}
          </button>
        </div>
      </div>
    </div>
    <div class="detail" id="detail-{deal_id}"><div class="detail-in"><div class="detail-body">
      {detail_tags(deal)}
      <div class="field wide"><dt>优惠内容</dt><dd>{e(deal['content'])}</dd></div>
      <div class="field wide"><dt>参与条件</dt><dd>{e(deal['conditions'])}</dd></div>
      <div class="field"><dt>适用国家或地区</dt><dd>{e(deal['regions'])}</dd></div>
      <div class="field"><dt>开始及截止时间</dt><dd>{e(deal.get('start') or '官方未公布')} → {e(deal.get('end') or '长期 / 官方未公布')}</dd></div>
      <div class="field wide"><dt>参与步骤</dt><ol>{steps}</ol></div>
      <div class="field wide"><dt>官方活动链接</dt>
        <dd><a class="url-link" href="{e(deal['url'])}" target="_blank" rel="noopener nofollow">{e(deal['url'])}</a></dd></div>
      <div class="risk">
        {icon('warn')}
        <span>{e(deal['risk'])}</span>
      </div>
      <div class="detail-foot">
        <span>来源 · {e(deal['source'])}</span>
        <span>最后验证 · {e(deal['last_verified'])}</span>
        <span>收录 · {e(deal.get('added', ''))}</span>
      </div>
    </div></div></div>
  </article>"""


def jump_card(deal: dict, today, rank: int | None = None) -> str:
    """精简跳转卡：点一下滚到 #deal-<id> 并展开，详情只存一份。

    标题独占第一行；价值徽标与地区/截止信息放第二行，标题能用到整行宽度。
    """
    region_tag, title_text = title_parts(deal.get("title", ""))
    cost = deal.get("cost", "")
    fav = f"assets/fav/{fav_name(deal.get('domain', ''))}.png"
    monogram = (deal.get("brand") or "?")[:1].upper()
    deal_id = e(deal["id"])
    if rank is None:
        rank_html = ""
    else:
        rank_cls = "jump-rank" + (f" r{rank}" if rank <= 3 else "")
        rank_html = f'<span class="{rank_cls}"><i>#</i>{rank}</span>'
    # 截止提示放前面：窄条里被截断时先舍地区，不舍截止
    meta = e(short_deadline(deal, today)) + (f" · {e(region_tag)}" if region_tag else "")
    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"

    return f"""<a class="jump" href="#deal-{deal_id}" data-jump="deal-{deal_id}"
    data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(deal.get('added', ''))}" data-key="{deal_id}">
      {rank_html}
      <img class="fav" src="{fav}" width="22" height="22" alt="" loading="lazy" decoding="async"
           data-fallback="{e(monogram)}" onerror="window.__favFallback&&window.__favFallback(this)">
      <span class="fav-fallback" style="display:none" aria-hidden="true">{e(monogram)}</span>
      <span class="jump-main">
        <span class="jump-title">{e(title_text)}</span>
        <span class="jump-sub"><span class="{value_cls}">{e(value_compact(deal))}</span><span class="jump-meta">{meta}</span></span>
      </span>
      {icon('external', 'jump-arrow')}
    </a>"""


def module_html(
    anchor: str,
    icon_key: str,
    title: str,
    desc: str,
    deals: list[dict],
    today,
    ranked: bool = False,
    jump: bool = False,
    strip: bool = False,
) -> str:
    if jump:
        cards = [jump_card(deal, today, rank=i if ranked else None) for i, deal in enumerate(deals, start=1)]
    else:
        cards = [card(deal, today) for deal in deals]
    count = len(deals)
    return f"""
  <section class="module{(' hot-strip' if strip else '')}" id="{anchor}" data-mod="{anchor}"{' data-kind="jump"' if jump else ''}>
    <header class="module-head">
      <span class="module-badge" aria-hidden="true">{icon(icon_key)}</span>
      <h2>{title} <span class="count" data-count>{count}</span></h2>
      <p class="module-desc">{desc}</p>
    </header>
    <div class="grid" data-grid>
      {''.join(cards)}
    </div>
    <p class="module-empty" style="display:none">该分类暂无符合条件的优惠</p>
    <button class="more" type="button" data-more hidden></button>
  </section>"""


def compact_html(page: str) -> str:
    """去掉每行缩进和空行：生成物小一大截，源码可读性交给生成器。"""
    page = re.sub(r"\n[ \t]+", "\n", page)
    return re.sub(r"\n{2,}", "\n", page)


def main() -> None:
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    today = today_local()

    for deal in deals:
        deal["status"] = compute_status(deal, today)

    # 图标：构建时落地到 assets/fav/，页面不再请求 google.com
    missing = []
    for deal in deals:
        if not ensure_favicon(deal.get("domain", "")):
            missing.append(deal.get("domain", "?"))

    active = [d for d in deals if d["status"] != "expired"]
    expired = [d for d in deals if d["status"] == "expired"]

    # 新收录：最近 48 小时，按收录时间倒序（原来的「今日优惠」是它的子集，已合并）
    since = (today - timedelta(days=TODAY_WINDOW_DAYS)).isoformat()
    fresh = sorted(
        [d for d in active if (d.get("added") or "") >= since],
        key=lambda d: ((d.get("added") or ""), value_expected(d)),
        reverse=True,
    )[:10]
    # 今天没有新条目时也保证板子不空
    if not fresh:
        fresh = sorted(active, key=lambda d: (d.get("added") or ""), reverse=True)[:10]

    # 高价值榜：按可预期到手金额（不是上限）排
    leaderboard = sorted(active, key=lambda d: (value_expected(d), d.get("value_num") or 0), reverse=True)[:10]

    closing = sorted(
        [
            d
            for d in active
            if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= CLOSING_WINDOW_DAYS
        ],
        key=lambda d: parse_date(d["end"]),
    )[:10]

    # 抽奖 / 随机 / 阶梯：上限很高但到手看运气，按上限金额排
    lottery = sorted(
        [d for d in active if is_high_cap(d)],
        key=lambda d: (d.get("value_num") or 0, value_expected(d)),
        reverse=True,
    )[:8]

    by_cat = {
        k: sorted([d for d in active if d["category"] == k], key=value_expected, reverse=True)
        for k in CAT_META
    }

    last_updated = meta.get("last_updated_human") or now_local().strftime("%Y-%m-%d %H:%M")
    beijing_time = last_updated if re.match(r"^\d{4}-\d{2}-\d{2}", last_updated) else now_local().strftime("%Y-%m-%d %H:%M")
    counts = {
        "active": len(active),
        "expiring": len(closing),
        "expired": len(expired),
        "total": len(deals),
    }

    rail = "".join(
        f'<a href="#{anchor}" data-target="{anchor}" aria-label="{label}">{icon(icon_key)}'
        f"<span>{label}</span></a>"
        for anchor, label, icon_key in NAV
    )
    rail += (
        '<div class="rail-sep" aria-hidden="true"></div>'
        f'<a class="rail-top" href="#top" aria-label="回到顶部">{icon("rocket")}'
        "<span>顶部</span></a>"
    )
    catbar = "".join(
        f'<a href="#{anchor}" data-target="{anchor}">{icon(icon_key)}<span>{label}</span></a>'
        for anchor, label, icon_key in NAV
    )

    board = {
        "fresh": module_html(
            "fresh", "today", "新收录",
            f"最近 {TODAY_WINDOW_DAYS * 24} 小时新收录、且仍在进行的优惠，按收录时间倒序。点一条即可跳到分类里的完整详情。",
            fresh, today, jump=True, strip=True,
        ),
        "rank": module_html(
            "rank", "rank", "高价值榜",
            "按可预期到手金额排序（抽奖类按期望值折算），先挑最值钱的。",
            leaderboard, today, ranked=True, jump=True, strip=True,
        ),
        "closing": module_html(
            "closing", "clock", "即将截止",
            f"{CLOSING_WINDOW_DAYS} 天内到期的活动，按截止时间排序；标「剩 N 天」的请优先处理。",
            closing, today, jump=True, strip=True,
        ),
        "lottery": module_html(
            "lottery", "gift", "抽奖 / 高上限",
            "上限很高、到手看运气的抽奖与阶梯任务，按上限金额排序，别按上限做预算。",
            lottery, today, ranked=True, jump=True, strip=True,
        ),
    }

    hot_board = f"""
  <div class="hot-board" data-hot-board>
    <div class="hot-tabs-mobile" role="tablist" aria-label="热榜">
      <a class="hot-tab on" href="#fresh" data-tab="fresh" aria-current="true">新收录 <b data-tabcount="fresh">{len(fresh)}</b></a>
      <a class="hot-tab" href="#rank" data-tab="rank">高价值榜 <b data-tabcount="rank">{len(leaderboard)}</b></a>
      <a class="hot-tab" href="#closing" data-tab="closing">即将截止 <b data-tabcount="closing">{len(closing)}</b></a>
      <a class="hot-tab" href="#lottery" data-tab="lottery">抽奖 <b data-tabcount="lottery">{len(lottery)}</b></a>
    </div>
    <div class="hot-panel hot-panel-main">
      <div class="hot-tablist">
        <a class="hot-tab on" href="#fresh" data-tab="fresh" aria-current="true">新收录 <b data-tabcount="fresh">{len(fresh)}</b></a>
        <a class="hot-tab" href="#rank" data-tab="rank">高价值榜 <b data-tabcount="rank">{len(leaderboard)}</b></a>
      </div>
      <div class="hot-panel-body" data-panel-body>
        {board["fresh"]}
        {board["rank"]}
      </div>
    </div>
    <div class="hot-panel hot-panel-alt">
      <div class="hot-tablist">
        <a class="hot-tab on" href="#closing" data-tab="closing" aria-current="true">即将截止 <b data-tabcount="closing">{len(closing)}</b></a>
        <a class="hot-tab" href="#lottery" data-tab="lottery">抽奖 / 高上限 <b data-tabcount="lottery">{len(lottery)}</b></a>
      </div>
      <div class="hot-panel-body" data-panel-body>
        {board["closing"]}
        {board["lottery"]}
      </div>
    </div>
  </div>"""

    modules = "".join(
        [
            module_html(
                "ai", "ai", "AI 工具免费与折扣",
                "ChatGPT、Gemini、Claude、Copilot、Cursor 等免费额度与限时赠送，含学生专属。",
                by_cat["ai"], today,
            ),
            module_html(
                "crypto", "crypto", "Crypto 空投与积分",
                "交易所新人奖励、任务空投与积分计划；奖励多为返佣券或代币，注意可提现条件。",
                by_cat["crypto"], today,
            ),
            module_html(
                "bank", "bank", "海外银行 · U 卡 · 跨境汇款",
                "开户奖励、虚拟卡返现、可双向叠加的邀请奖励（Wise / Sendwave / Taptap Send / Remitly 等）。",
                by_cat["bank"], today,
            ),
            module_html(
                "cloud", "cloud", "VPS 及云服务",
                "永久免费实例、新人体验金与黑五主机折扣，部署前先看清到期与回收规则。",
                by_cat["cloud"], today,
            ),
            module_html(
                "esim", "esim", "eSIM 全球流量",
                "免费试用与首单折扣，每条都标出可用国家或地区与注册限制——先试网，再买大套餐。",
                by_cat["esim"], today,
            ),
            module_html(
                "software", "software", "软件与数字服务",
                "学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠。",
                by_cat["software"], today,
            ),
            module_html(
                "archive", "archive", "已结束活动档案",
                "已过期活动保留 30 天供查档，随后自动清理，避免陈旧信息占版面。",
                sorted(expired, key=lambda d: d.get("end") or "", reverse=True), today,
            ),
        ]
    )

    # 搜索索引：每张卡只留 data-key，搜索文本统一放在这段 JSON 里
    search_index = {}
    for deal in deals:
        cat_meta = CAT_META.get(deal.get("category", ""), {"label": "", "search": ""})
        hay = " ".join(
            [
                deal.get("title", ""),
                deal.get("highlight", ""),
                deal.get("regions", ""),
                deal.get("brand", ""),
                deal.get("cost", ""),
                cat_meta.get("label", ""),
                cat_meta.get("search", ""),
            ]
        )
        search_index[deal["id"]] = re.sub(r"\s+", " ", hay).strip()
    search_json = json.dumps(search_index, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    item_list = []
    for i, deal in enumerate(leaderboard, start=1):
        item_list.append(
            {
                "@type": "ListItem",
                "position": i,
                "name": deal["title"],
                "url": deal["url"],
                "description": deal["highlight"],
            }
        )

    jsonld = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "羊毛情报局",
                "alternateName": "羊毛情报局 · 全球优惠情报",
                "url": SITE_URL,
                "inLanguage": "zh-CN",
                "description": "每日核验的全球优惠情报导航：AI 免费额度、Crypto 奖励、海外银行与汇款邀请、云服务额度、eSIM 免费流量、软件学生福利。",
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": SITE_URL + "?q={search_term_string}",
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": "高价值优惠排行榜",
                "itemListElement": item_list,
            },
        ],
        ensure_ascii=False,
        indent=2,
    )

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>羊毛情报局 · 全球优惠 / 免费额度 / 限时活动情报</title>
<meta name="description" content="羊毛情报局：每日核验的全球优惠情报导航。AI 工具免费额度、Crypto 空投与交易奖励、海外银行开户与跨境汇款邀请、VPS 云服务体验金、eSIM 免费流量、软件学生福利——一屏看清价值、门槛与截止时间，点击直达官方活动页。">
<meta name="author" content="羊毛情报局">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#FAF7F2">
<link rel="canonical" href="{SITE_URL}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="羊毛情报局">
<meta property="og:locale" content="zh_CN">
<meta property="og:title" content="羊毛情报局 · 全球优惠与免费额度情报">
<meta property="og:description" content="每日核验的全球优惠导航：AI、Crypto、海外银行与汇款、云服务、eSIM、软件学生福利。价值、门槛、截止时间一眼看清，直达官方链接。">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="羊毛情报局 · 每日核验的全球优惠情报">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="羊毛情报局 · 全球优惠与免费额度情报">
<meta name="twitter:description" content="每日核验的全球优惠导航：AI、Crypto、海外银行与汇款、云服务、eSIM、软件学生福利。">
<meta name="twitter:image" content="{OG_IMAGE}">

<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/css/style.css?v={asset_ver('assets/css/style.css')}">

<!-- Google AdSense：开通后把脚本放在这里，并给 .ad-slot 容器填入广告单元
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
-->

<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>

{sprite_svg()}

<header class="topbar">
  <div class="shell topbar-in">
    <a class="brand" href="{SITE_URL}" aria-label="羊毛情报局 首页">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg()}
      </span>
      <span class="brand-text">
        <span class="brand-name">羊毛情报局</span>
        <span class="brand-sub">全球优惠 · 每日核验</span>
      </span>
    </a>
    <button class="search-btn" id="open-search" type="button" aria-haspopup="dialog" aria-label="搜索优惠、可用地区、类别">
      <span class="sb-q">
        {icon('search')}
        <span class="sb-text">搜索优惠、可用地区、类别…</span>
      </span>
      <kbd>⌘K</kbd>
    </button>
    <div class="topbar-stats">
      <a class="stats-pill mint" href="#fresh">进行中 <b>{counts['active']}</b></a>
      <a class="stats-pill amber" href="#closing">即将截止 <b>{counts['expiring']}</b></a>
      <a class="stats-pill stone" href="#archive">已归档 <b>{counts['expired']}</b></a>
    </div>
  </div>
</header>

<nav class="catbar" aria-label="分类导航">
  <div class="catbar-in">{catbar}</div>
</nav>

<main id="top">
  <div class="shell">
    <section class="hero">
      <h1>羊毛情报局</h1>
      <p class="hero-tag">全球免费额度与限时奖励，先看值得点的。</p>
      <p class="hero-meta"><span class="dot" aria-hidden="true"></span>北京时间 {e(beijing_time)} 更新</p>
    </section>

    <div class="ad-slot" data-ad="top" aria-hidden="true"><!-- AdSense：顶部 / 桌面横幅 --></div>
  </div>

  <div class="shell">{hot_board}{modules}</div>

  <div class="shell">
    <div class="ad-slot" data-ad="bottom" aria-hidden="true"><!-- AdSense：底部 --></div>
  </div>
</main>

<nav class="rail" aria-label="分区导航">
  {rail}
</nav>

<div class="modal" id="search-modal" role="dialog" aria-modal="true" aria-label="搜索与筛选" aria-hidden="true">
  <div class="modal-bg" data-close></div>
  <div class="sheet">
    <div class="sheet-top">
      <h2>搜索与筛选</h2>
      <button class="sheet-close" type="button" data-close aria-label="关闭">✕</button>
    </div>
    <div class="input-wrap">
      {icon('search')}
      <input id="q" type="search" placeholder="搜活动、品牌、国家或门槛，例如 eSIM 日本 / 学生 / 免手续费" autocomplete="off" spellcheck="false">
    </div>

    <div class="filter-row">
      <div class="filter-label">时间范围</div>
      <div class="chips" data-group="time">
        <button class="chip on" type="button" data-value="all">全部时间</button>
        <button class="chip" type="button" data-value="24h">近 24 小时</button>
        <button class="chip" type="button" data-value="48h">近 48 小时</button>
        <button class="chip" type="button" data-value="7d">近 7 天</button>
        <button class="chip" type="button" data-value="past">7 天前往期</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">排序</div>
      <div class="chips" data-group="sort">
        <button class="chip on" type="button" data-value="value">价值优先</button>
        <button class="chip" type="button" data-value="new">最新收录</button>
        <button class="chip" type="button" data-value="end">最近截止</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">类别</div>
      <div class="chips" data-group="cat">
        <button class="chip on" type="button" data-value="all">全部</button>
        <button class="chip" type="button" data-value="ai">AI 工具</button>
        <button class="chip" type="button" data-value="crypto">Crypto</button>
        <button class="chip" type="button" data-value="bank">银行 / 卡 / 汇款</button>
        <button class="chip" type="button" data-value="cloud">VPS / 云</button>
        <button class="chip" type="button" data-value="esim">eSIM</button>
        <button class="chip" type="button" data-value="software">软件 / 其他</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">参与门槛</div>
      <div class="chips" data-group="cost">
        <button class="chip on" type="button" data-value="all">全部</button>
        <button class="chip" type="button" data-value="真正免费">真正免费</button>
        <button class="chip" type="button" data-value="免费试用">免费试用</button>
        <button class="chip" type="button" data-value="需要充值">需要充值</button>
        <button class="chip" type="button" data-value="需要交易量">需要交易量</button>
        <button class="chip" type="button" data-value="需要邀请条件">需要邀请条件</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">核验状态</div>
      <div class="chips" data-group="verify">
        <button class="chip on" type="button" data-value="all">全部</button>
        <button class="chip" type="button" data-value="1">已核验</button>
        <button class="chip" type="button" data-value="0">待核实</button>
      </div>
    </div>

    <div class="sheet-foot">
      <span class="result-count">匹配 <b data-result>0</b> 条</span>
      <span class="grow"></span>
      <button class="link-btn" type="button" data-reset>重置</button>
      <button class="solid-btn" type="button" data-close>完成</button>
    </div>
  </div>
</div>

<footer>
  <div class="shell foot-line">
    <span class="foot-brand">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg()}
      </span>
      羊毛情报局 · © {today.year}
    </span>
    <span class="foot-up">更新 {e(last_updated)}</span>
    <a class="foot-top" href="#top">回到顶部 ↑</a>
  </div>
</footer>

<script id="search-index" type="application/json">{search_json}</script>
<script src="assets/js/app.js?v={asset_ver('assets/js/app.js')}" defer></script>
</body>
</html>
"""
    OUT.write_text(compact_html(page), encoding="utf-8")
    print(f"index.html written · {len(active)} active / {len(expired)} expired / {len(fresh)} fresh")
    if missing:
        print(f"  ! 图标下载失败 {len(missing)} 个（回退字母块）：{', '.join(missing)}")
    else:
        print(f"  图标：{len(deals)} 个域名全部就绪（assets/fav/）")


if __name__ == "__main__":
    main()
