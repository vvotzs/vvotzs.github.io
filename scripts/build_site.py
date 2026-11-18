#!/usr/bin/env python3
"""羊毛情报局 — 静态页面生成器。

读取 data/deals.json 与 data/meta.json，生成纯静态 index.html
（卡片全部是真实 HTML，方便搜索引擎抓取；筛选 / 手风琴 / 移动端分页由 app.js 增强）。

工程要点：
  · 时区统一北京时间（见 scripts/common.py）；
  · 分类区（C/D/E/F/I/J）渲染完整 12 字段卡片，每个活动只出现一次（#deal-<id>）；
  · 今日 / 榜单 / 截止三个分区渲染精简跳转卡，点一下滚到分类区那张卡片并展开，
    这样 index.html 不重复三遍详情，搜索计数也不会重复；
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

# ---------------------------------------------------------------- svg icons
_ICON_PATHS = {
    # 今日：暖色火苗
    "today": '<path d="M12 2.9c2.9 3.1 4.6 5.7 4.6 8.5a4.6 4.6 0 1 1-9.2 0c0-2.8 1.7-5.4 4.6-8.5Z" fill="#FDBA74"/>'
             '<path d="M12 9.4c1.3 1.5 2 2.7 2 4a2 2 0 1 1-4 0c0-1.3.7-2.5 2-4Z" fill="#FEF3C7"/>',
    # 榜单：奖杯
    "rank": '<path d="M7.6 3.5h8.8v4.9a4.4 4.4 0 0 1-8.8 0V3.5Z" fill="#FCD34D"/>'
            '<path d="M7.6 5.1H5.1a2.6 2.6 0 0 0 2.6 4.6"/>'
            '<path d="M16.4 5.1h2.5a2.6 2.6 0 0 1-2.6 4.6"/>'
            '<path d="M12 12.8v2.4"/>'
            '<path d="M9.2 15.2h5.6v3.3H9.2z" fill="#FED7AA"/>'
            '<path d="M7.8 18.5h8.4"/>',
    # AI：圆角徽标 + 粗体 AI
    "ai": '<rect x="2.4" y="5.2" width="19.2" height="13.6" rx="4.8" fill="#DBEAFE"/>'
          '<text x="11.2" y="15.6" text-anchor="middle" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif"'
          ' font-size="10.2" font-weight="800" fill="#1E40AF" stroke="none">AI</text>'
          '<path d="M19.4 3.1l.55 1.35 1.35.55-1.35.55-.55 1.35-.55-1.35-1.35-.55 1.35-.55.55-1.35Z" fill="#F59E0B"/>',
    # 币：金币 + ₿
    "crypto": '<circle cx="12" cy="12" r="8.5" fill="#FCD34D"/>'
              '<path d="M10.6 7.1v9.8M12.4 7.1v9.8" stroke="#92400E" stroke-width="1.15"/>'
              '<path d="M10.6 8.9h3.1a1.6 1.6 0 0 1 0 3.2h-3.1z" fill="#92400E"/>'
              '<path d="M10.6 12.1h3.5a1.75 1.75 0 0 1 0 3.5h-3.5z" fill="#92400E"/>',
    # 卡：银行卡（磁条 + 芯片）
    "bank": '<rect x="2.4" y="5.4" width="19.2" height="13.2" rx="3.2" fill="#BBF7D0"/>'
            '<path d="M2.4 9.2h19.2" stroke-width="2.4"/>'
            '<rect x="4.9" y="12.2" width="4.1" height="3.3" rx="1" fill="#FDE68A" stroke="none"/>'
            '<path d="M11.4 14.4h6.4"/>',
    # 云：云朵
    "cloud": '<path d="M7.4 17.9h9.2a3.5 3.5 0 0 0 .4-7A5.3 5.3 0 0 0 7 10.3a3.8 3.8 0 0 0 .4 7.6Z" fill="#BFDBFE"/>',
    # eSIM：SIM 卡（切角 + 信号弧）
    "esim": '<path d="M7.4 3.4h5.9l4.1 4.1v12.1a1.9 1.9 0 0 1-1.9 1.9H7.4a1.9 1.9 0 0 1-1.9-1.9V5.3a1.9 1.9 0 0 1 1.9-1.9Z" fill="#FED7AA"/>'
            '<rect x="8.3" y="11.3" width="6.2" height="5.5" rx="1.2" fill="#FFFDF9" stroke="none"/>'
            '<path d="M9.7 8.6a4.2 4.2 0 0 1 3.4 0"/>',
    # 截止：闹钟
    "clock": '<circle cx="12" cy="13.6" r="6.8" fill="#FECDD3"/>'
             '<path d="M12 10.1v3.6l2.3 1.5"/>'
             '<path d="M4.9 6.9 7 4.8M19.1 6.9 17 4.8"/>'
             '<path d="M9 20.4l-1.1 1.2M15 20.4l1.1 1.2"/>',
    # 软件：2×2 应用宫格
    "software": '<rect x="3.6" y="3.6" width="7.2" height="7.2" rx="2.1" fill="#C4B5FD" stroke="none"/>'
                '<rect x="13.2" y="3.6" width="7.2" height="7.2" rx="2.1" fill="#A5B4FC" stroke="none"/>'
                '<rect x="3.6" y="13.2" width="7.2" height="7.2" rx="2.1" fill="#A5B4FC" stroke="none"/>'
                '<rect x="13.2" y="13.2" width="7.2" height="7.2" rx="2.1" fill="#C4B5FD" stroke="none"/>',
    # 归档：档案盒
    "archive": '<rect x="3.4" y="4.2" width="17.2" height="4.4" rx="1.7" fill="#FED7AA"/>'
               '<path d="M4.9 8.6h14.2v9.6a1.8 1.8 0 0 1-1.8 1.8H6.7a1.8 1.8 0 0 1-1.8-1.8V8.6Z" fill="#E7E5E4"/>'
               '<path d="M9.6 12.3h4.8"/>',
}
ICONS = {
    key: (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + path
        + "</svg>"
    )
    for key, path in _ICON_PATHS.items()
}

ROCKET_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 2.7c3 2.3 4.6 5.7 4.6 9.3 0 2.1-.6 4-1.7 5.5H9.1c-1.1-1.5-1.7-3.4-1.7-5.5 0-3.6 1.6-7 4.6-9.3Z" fill="#FED7AA"/>'
    '<circle cx="12" cy="10.1" r="1.9" fill="#BFDBFE"/>'
    '<path d="M9.1 17.1 6.5 19.8c.1-1.9.6-3.3 1.5-4.3"/>'
    '<path d="M14.9 17.1l2.6 2.7c-.1-1.9-.6-3.3-1.5-4.3"/>'
    '<path d="M12 20.9c-.9 0-1.6-.9-1.6-2.1h3.2c0 1.2-.7 2.1-1.6 2.1Z" fill="#FDE68A"/>'
    "</svg>"
)

NAV = [
    ("today", "今日", ICONS["today"]),
    ("rank", "榜单", ICONS["rank"]),
    ("ai", "AI", ICONS["ai"]),
    ("crypto", "币", ICONS["crypto"]),
    ("bank", "卡", ICONS["bank"]),
    ("cloud", "云", ICONS["cloud"]),
    ("esim", "eSIM", ICONS["esim"]),
    ("closing", "截止", ICONS["clock"]),
    ("software", "软件", ICONS["software"]),
    ("archive", "归档", ICONS["archive"]),
]

COST_CLASS = {
    "真正免费": "cost-free",
    "免费试用": "cost-trial",
    "需要充值": "cost-deposit",
    "需要交易量": "cost-volume",
    "需要邀请条件": "cost-invite",
}


def mascot_svg(gradient_id: str = "mintBody") -> str:
    """页面里的薄荷小怪兽。页头 / 页脚各一份，渐变 id 必须唯一。"""
    return (
        '<svg viewBox="0 0 40 40" aria-hidden="true">'
        f'<defs><linearGradient id="{gradient_id}" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0" stop-color="#B7F5DA"/><stop offset="1" stop-color="#7FE3B8"/>'
        "</linearGradient></defs>"
        f'<path d="M20 3.6c8.6 0 13.1 5.9 13.1 14.2 0 9.6-5.4 18.6-13.1 18.6S6.9 27.4 6.9 17.8C6.9 9.5 11.4 3.6 20 3.6Z" fill="url(#{gradient_id})"/>'
        '<path d="M20 3.6c-2.6 0-4.9.6-6.8 1.7 2.4 2 8.9 2.1 12.9.2-1.8-1.2-3.9-1.9-6.1-1.9Z" fill="#5FD3A6" opacity=".55"/>'
        '<ellipse cx="20" cy="20.4" rx="9.1" ry="8.4" fill="#F3FFF9"/>'
        '<circle cx="16.8" cy="19.3" r="1.35" fill="#14532D"/>'
        '<circle cx="23.2" cy="19.3" r="1.35" fill="#14532D"/>'
        '<circle cx="15.9" cy="18.7" r=".4" fill="#FFFFFF" opacity=".9"/>'
        '<circle cx="22.3" cy="18.7" r=".4" fill="#FFFFFF" opacity=".9"/>'
        '<ellipse cx="13.6" cy="22.4" rx="1.6" ry="1.1" fill="#FCA5A5" opacity=".5"/>'
        '<ellipse cx="26.4" cy="22.4" rx="1.6" ry="1.1" fill="#FCA5A5" opacity=".5"/>'
        '<path d="M18.3 22.7c.5.85 2.9.85 3.4 0" fill="none" stroke="#14532D" stroke-width="1.25" stroke-linecap="round"/>'
        '<path d="M20 3.9c.1-1.5.9-2.5 2.3-2.9-.1 1.5-.9 2.5-2.3 2.9Z" fill="#34D399"/>'
        "</svg>"
    )


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
        f'<span class="dval"><span class="dval-k">实际价值</span><strong>{e(deal["value"])}</strong></span>'
        f'<span class="dtag {cost_cls}">{e(cost)}</span>'
        f"{check}"
        "</div>"
    )


def title_parts(raw_title: str) -> tuple[str, str]:
    """拆出标题前的 [地区] 标签与正文。"""
    m = re.match(r"^\[([^\]]{1,24})\]\s*(.*)$", raw_title)
    return (m.group(1), m.group(2)) if m else ("", raw_title)


def card(deal: dict, today, rank: int | None = None) -> str:
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    expired = bool(deal.get("status") == "expired")
    classes = "card is-expired" if expired else "card"
    cat_meta = CAT_META.get(deal.get("category", ""), {"label": "", "search": ""})

    badges = f'<span class="badge rank">#{rank}</span>' if rank is not None else ""

    steps = "".join(f"<li>{e(s)}</li>" for s in deal.get("steps", []))
    if not steps:
        steps = "<li>见官方活动页</li>"

    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"

    region_tag, title_text = title_parts(deal.get("title", ""))
    if region_tag:
        title_html = f'<span class="rtag">{e(region_tag)}</span>{e(title_text)}'
    else:
        title_html = e(title_text)

    hay = " ".join(
        [
            deal.get("title", ""),
            deal.get("highlight", ""),
            deal.get("regions", ""),
            deal.get("brand", ""),
            cost,
            cat_meta["label"],
            cat_meta["search"],
        ]
    )
    fav = f"assets/fav/{fav_name(deal.get('domain', ''))}.png"
    monogram = (deal.get("brand") or "?")[:1].upper()
    deal_id = e(deal["id"])

    return f"""<article class="{classes}" id="deal-{deal_id}" data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(deal.get('added', ''))}" data-val="{int(deal.get('value_num') or 0)}"
    data-val-exp="{value_expected(deal):g}" data-key="{deal_id}"
    data-hay="{e(hay)}">
    <div class="card-head">
      <img class="fav" src="{fav}" width="24" height="24" alt=""
           loading="lazy" decoding="async" data-fallback="{e(monogram)}"
           onerror="window.__favFallback&&window.__favFallback(this)">
      <span class="fav-fallback" style="display:none" aria-hidden="true">{e(monogram)}</span>
      <div class="card-body">
        <div class="row1">
          <h3>{title_html}</h3>
          {badges}
          <span class="{value_cls}">{e(deal['value'])}</span>
        </div>
        <p class="row2"><span class="tag {cost_cls}">{e(cost)}</span>{e(deal['highlight'])}</p>
        <div class="row3">
          <span class="region">{e(deal['regions'])}</span>
          <span class="sep">·</span>
          {deadline_html(deal, today)}
          <span class="grow"></span>
          <a class="go" href="{e(deal['url'])}" target="_blank" rel="noopener nofollow">直达原链接
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
                 stroke-linejoin="round" aria-hidden="true"><path d="M3 9 9 3M4.5 3H9v4.5"/></svg>
          </a>
          <button class="toggle" type="button" aria-expanded="false" aria-controls="detail-{deal_id}"
                  aria-label="展开详情">详情
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
                 stroke-linejoin="round" aria-hidden="true"><path d="m2.5 4.5 3.5 3.5 3.5-3.5"/></svg>
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
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" aria-hidden="true">
          <path d="M8 2.6 14.2 13H1.8L8 2.6Z"/><path d="M8 6.6v3.1M8 11.6v.1"/></svg>
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
    """精简跳转卡：点一下滚到 #deal-<id> 并展开，详情只存一份。"""
    region_tag, title_text = title_parts(deal.get("title", ""))
    cat_meta = CAT_META.get(deal.get("category", ""), {"label": "", "search": ""})
    cost = deal.get("cost", "")
    hay = " ".join(
        [
            deal.get("title", ""),
            deal.get("highlight", ""),
            deal.get("regions", ""),
            deal.get("brand", ""),
            cost,
            cat_meta["label"],
            cat_meta["search"],
        ]
    )
    fav = f"assets/fav/{fav_name(deal.get('domain', ''))}.png"
    monogram = (deal.get("brand") or "?")[:1].upper()
    deal_id = e(deal["id"])
    rank_html = f'<span class="jump-rank">#{rank}</span>' if rank is not None else ""
    meta = (f"{e(region_tag)} · " if region_tag else "") + deadline_html(deal, today)
    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"

    return f"""<a class="jump" href="#deal-{deal_id}" data-jump="deal-{deal_id}"
    data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(deal.get('added', ''))}" data-key="{deal_id}" data-hay="{e(hay)}">
      {rank_html}
      <img class="fav" src="{fav}" width="22" height="22" alt="" loading="lazy" decoding="async"
           data-fallback="{e(monogram)}" onerror="window.__favFallback&&window.__favFallback(this)">
      <span class="fav-fallback" style="display:none" aria-hidden="true">{e(monogram)}</span>
      <span class="jump-main">
        <span class="jump-title">{e(title_text)}</span>
        <span class="jump-meta">{meta}</span>
      </span>
      <span class="{value_cls}">{e(deal['value'])}</span>
      <svg class="jump-arrow" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9 9 3M4.5 3H9v4.5"/></svg>
    </a>"""


def module_html(
    anchor: str,
    letter: str,
    title: str,
    desc: str,
    deals: list[dict],
    today,
    ranked: bool = False,
    alias: str | None = None,
    jump: bool = False,
) -> str:
    if jump:
        cards = [jump_card(deal, today, rank=i if ranked else None) for i, deal in enumerate(deals, start=1)]
        per_page = 6
    else:
        cards = [card(deal, today, rank=i if ranked else None) for i, deal in enumerate(deals, start=1)]
        per_page = 4
    count = len(deals)
    empty = (
        '<p class="module-empty" style="display:none">该分类暂无符合条件的优惠</p>'
        if count
        else '<p class="module-empty" style="display:block">该分类暂无符合条件的优惠</p>'
    )
    return f"""
  {f'<span class="anchor-alias" id="{alias}" aria-hidden="true"></span>' if alias else ''}<section class="module" id="{anchor}" data-mod="{anchor}" data-limit="{count}" data-per="{per_page}"{' data-kind="jump"' if jump else ''}>
    <header class="module-head">
      <span class="module-badge" aria-hidden="true">{letter}</span>
      <h2>{title} <span class="count" data-count>{count}</span></h2>
      <p class="module-desc">{desc}</p>
    </header>
    <div class="pager">
      <div class="track" data-track>
        <div class="grid" data-grid>
          {''.join(cards)}
        </div>
      </div>
      <div class="pager-bar" data-bar>
        <span class="pager-label" data-label>1–{min(per_page, count) if count else 0} / {count}</span>
        <div class="pager-nav">
          <button type="button" data-prev aria-label="上一页">‹</button>
          <button type="button" data-next aria-label="下一页">›</button>
        </div>
      </div>
    </div>
    {empty}
  </section>"""


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
    active_sorted = sorted(active, key=lambda d: (d.get("value_num") or 0), reverse=True)
    leaderboard = sorted(
        active,
        key=lambda d: (value_expected(d), d.get("value_num") or 0),
        reverse=True,
    )[:10]

    since = (today - timedelta(days=TODAY_WINDOW_DAYS)).isoformat()
    todays = sorted(
        [d for d in active if (d.get("added") or "") >= since],
        key=lambda d: ((d.get("added") or ""), d.get("value_num") or 0),
        reverse=True,
    )[:8]

    closing = sorted(
        [
            d
            for d in active
            if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= CLOSING_WINDOW_DAYS
        ],
        key=lambda d: parse_date(d["end"]),
    )

    by_cat = {k: [d for d in active_sorted if d["category"] == k] for k in CAT_META}

    last_updated = meta.get("last_updated_human") or now_local().strftime("%Y-%m-%d %H:%M")
    counts = {
        "active": len(active),
        "expiring": len(closing),
        "expired": len(expired),
        "total": len(deals),
    }

    rail = "".join(
        f'<a href="#{anchor}" data-target="{anchor}" aria-label="{label}">{icon}'
        f"<span>{label}</span></a>"
        for anchor, label, icon in NAV
    )
    rail += (
        '<div class="rail-sep" aria-hidden="true"></div>'
        f'<a class="rail-top" href="#top" aria-label="回到顶部">{ROCKET_ICON}'
        "<span>顶部</span></a>"
    )

    modules = "".join(
        [
            module_html(
                "today", "A", "今日最新优惠",
                f"最近 {TODAY_WINDOW_DAYS * 24} 小时新收录、且仍在进行的优惠。点一条即可跳到分类里的完整详情。",
                todays, today, jump=True,
            ),
            module_html(
                "rank", "B", "高价值优惠排行榜",
                "按可预期价值（实际到手金额）排序，抽奖类按期望值折算，先挑最值钱的。",
                leaderboard, today, ranked=True, jump=True,
            ),
            module_html(
                "ai", "C", "AI 工具免费与折扣",
                "ChatGPT、Gemini、Claude、Copilot、Cursor 等免费额度与限时赠送，含学生专属。",
                by_cat["ai"], today,
            ),
            module_html(
                "crypto", "D", "Crypto 空投与积分",
                "交易所新人奖励、任务空投与积分计划；奖励多为返佣券或代币，注意可提现条件。",
                by_cat["crypto"], today,
            ),
            module_html(
                "bank", "E", "海外银行 · U 卡 · 跨境汇款",
                "开户奖励、虚拟卡返现、可双向叠加的邀请奖励（Wise / Sendwave / Taptap Send / Remitly 等）。",
                by_cat["bank"], today,
            ),
            module_html(
                "cloud", "F", "VPS 及云服务",
                "永久免费实例、新人体验金与黑五主机折扣，部署前先看清到期与回收规则。",
                by_cat["cloud"], today,
            ),
            module_html(
                "esim", "I", "eSIM 全球流量",
                "免费试用与首单折扣，每条都标出可用国家或地区与注册限制——先试网，再买大套餐。",
                by_cat["esim"], today,
            ),
            module_html(
                "closing", "G", "即将截止",
                "30 天内到期的活动，按截止时间排序；标「剩 N 天」的请优先处理。",
                closing, today, alias="expiring", jump=True,
            ),
            module_html(
                "software", "J", "软件与数字服务",
                "学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠。",
                by_cat["software"], today,
            ),
            module_html(
                "archive", "H", "已结束活动档案",
                "已过期活动保留 30 天供查档，随后自动清理，避免陈旧信息占版面。",
                sorted(expired, key=lambda d: d.get("end") or "", reverse=True), today,
            ),
        ]
    )

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

<header class="topbar">
  <div class="shell topbar-in">
    <a class="brand" href="{SITE_URL}" aria-label="羊毛情报局 首页">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg("mintBody")}
      </span>
      <span>
        <span class="brand-name">羊毛情报局</span>
        <span class="brand-sub">更新 {e(last_updated)}</span>
      </span>
    </a>
    <button class="search-btn" id="open-search" type="button" aria-haspopup="dialog" aria-label="搜索优惠、可用地区、类别">
      <span class="sb-q">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
          <circle cx="7" cy="7" r="4.4"/><path d="m10.4 10.4 3 3"/>
        </svg>
        <span class="sb-text">搜索优惠、可用地区、类别…</span>
        <span class="sb-text-short">搜索 / 筛选</span>
      </span>
      <kbd>⌘K</kbd>
    </button>
    <div class="topbar-stats">
      <a class="stats-pill mint" href="#today">进行中 <b>{counts['active']}</b></a>
      <a class="stats-pill amber" href="#expiring">即将截止 <b>{counts['expiring']}</b></a>
      <a class="stats-pill stone" href="#archive">已归档 <b>{counts['expired']}</b></a>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell">
    <section class="hero">
      <div class="hero-kicker"><span class="dot"></span>情报更新 · {e(today.isoformat())}</div>
      <h1>全球的免费额度与限时奖励，<br><em>先看值得点的。</em></h1>
      <p class="hero-desc">每条都回到官方页面核对过：值多少、门槛、截止日。想细看就展开，不想就直接点原链接。</p>
      <p class="hero-mini">
        <a class="stats-pill mint" href="#today">进行中 <b>{counts['active']}</b></a>
        <a class="stats-pill amber" href="#expiring">即将截止 <b>{counts['expiring']}</b></a>
        <a class="stats-pill stone" href="#archive">已归档 <b>{counts['expired']}</b></a>
      </p>
      <div class="hero-stats">
        <span class="stat live">进行中 <b>{counts['active']}</b></span>
        <span class="stat hot">即将截止 <b>{counts['expiring']}</b></span>
        <span class="stat">已归档 <b>{counts['expired']}</b></span>
        <span class="stat">覆盖分类 <b>6</b></span>
      </div>
    </section>

    <div class="ad-slot" data-ad="top" aria-hidden="true"><!-- AdSense：顶部 / 桌面横幅 --></div>
  </div>

  <div class="shell">{modules}</div>

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
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
        <circle cx="7" cy="7" r="4.4"/><path d="m10.4 10.4 3 3"/>
      </svg>
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
        {mascot_svg("mintBodyFoot")}
      </span>
      羊毛情报局 · © {today.year}
    </span>
    <span class="foot-up">更新 {e(last_updated)}</span>
    <a class="foot-top" href="#top">回到顶部 ↑</a>
  </div>
</footer>

<script src="assets/js/app.js?v={asset_ver('assets/js/app.js')}" defer></script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"index.html written · {len(active)} active / {len(expired)} expired / {len(todays)} today")
    if missing:
        print(f"  ! 图标下载失败 {len(missing)} 个（回退字母块）：{', '.join(missing)}")
    else:
        print(f"  图标：{len(deals)} 个域名全部就绪（assets/fav/）")


if __name__ == "__main__":
    main()
