#!/usr/bin/env python3
"""羊毛情报局 — 静态页面生成器。

读取 data/deals.json 与 data/meta.json，生成纯静态 index.html
（卡片全部是真实 HTML，方便搜索引擎抓取；筛选 / 手风琴 / 移动端分页由 app.js 增强）。
"""
from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "deals.json"
META = ROOT / "data" / "meta.json"
OUT = ROOT / "index.html"

SITE_URL = "https://vvotzs.github.io/"
LAST_UPDATED_FALLBACK = "2026-11-19 01:30"

CATEGORY_LABEL = {
    "ai": "AI 工具",
    "crypto": "Crypto",
    "bank": "海外银行 / U 卡 / 汇款",
    "cloud": "VPS 与云服务",
    "esim": "eSIM",
    "software": "软件与数字服务",
}

COST_CLASS = {
    "真正免费": "cost-free",
    "免费试用": "cost-trial",
    "需要充值": "cost-deposit",
    "需要交易量": "cost-volume",
    "需要邀请条件": "cost-invite",
}

# ---------------------------------------------------------------- svg icons
_ICON_PATHS = {
    "today": '<path d="M13 2 4.5 13.2h6L10 22l8.7-11.4h-6L13 2Z"/>',
    "rank": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "ai": '<path d="M12 3.2 13.7 8.3 18.8 10l-5.1 1.7L12 16.8l-1.7-5.1L5.2 10l5.1-1.7L12 3.2Z"/><path d="M18.4 15.2l.7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7.7-2.1Z"/>',
    "crypto": '<path d="M12 2.8 20 7.4v9.2L12 21.2 4 16.6V7.4l8-4.6Z"/><path d="M12 7.4v9.2M8 9.6l8 4.6M16 9.6l-8 4.6"/>',
    "bank": '<path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 11v7M10 11v7M14 11v7M18.5 11v7"/><path d="M3 20.5h18"/>',
    "cloud": '<path d="M7.2 18.5h9.6a3.7 3.7 0 0 0 .5-7.36 5.4 5.4 0 0 0-10.4-.6A3.88 3.88 0 0 0 7.2 18.5Z"/>',
    "clock": '<circle cx="12" cy="12" r="8.4"/><path d="M12 7.6V12l3 2"/>',
    "software": '<rect x="3.6" y="3.6" width="7" height="7" rx="1.8"/><rect x="13.4" y="3.6" width="7" height="7" rx="1.8"/><rect x="3.6" y="13.4" width="7" height="7" rx="1.8"/><rect x="13.4" y="13.4" width="7" height="7" rx="1.8"/>',
    "archive": '<rect x="3.4" y="4.2" width="17.2" height="4.2" rx="1.4"/><path d="M5.2 8.4v10a1.6 1.6 0 0 0 1.6 1.6h10.4a1.6 1.6 0 0 0 1.6-1.6v-10"/><path d="M9.6 12.4h4.8"/>',
}
ICONS = {
    key: (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + path
        + "</svg>"
    )
    for key, path in _ICON_PATHS.items()
}

ESIM_ICON = (
    '<svg class="esim-icon" viewBox="0 0 44 30" aria-hidden="true">'
    '<text x="0" y="22" font-family="-apple-system,Segoe UI,PingFang SC,sans-serif" '
    'font-size="21" font-weight="700" fill="currentColor" letter-spacing="-1">eSi</text>'
    '<rect x="27" y="17.5" width="4" height="6.5" rx="1" fill="#FFC24B"/>'
    '<rect x="32.6" y="12.5" width="4" height="11.5" rx="1" fill="#FF7A45"/>'
    '<rect x="38.2" y="7" width="4" height="17" rx="1" fill="#E5005F"/>'
    "</svg>"
)

NAV = [
    ("today", "今日", ICONS["today"]),
    ("rank", "榜单", ICONS["rank"]),
    ("ai", "AI", ICONS["ai"]),
    ("crypto", "Crypto", ICONS["crypto"]),
    ("bank", "银行", ICONS["bank"]),
    ("cloud", "云", ICONS["cloud"]),
    ("esim", "eSIM", ESIM_ICON),
    ("closing", "截止", ICONS["clock"]),
    ("software", "软件", ICONS["software"]),
    ("archive", "归档", ICONS["archive"]),
]


def asset_ver(rel: str) -> str:
    """给静态资源带上内容哈希，避免 GitHub Pages CDN 缓存旧样式。"""
    path = ROOT / rel
    if not path.exists():
        return "1"
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def short_date(value: str) -> str:
    d = parse_date(value)
    return f"{d.month}月{d.day}日" if d else ""


def deadline_html(deal: dict, today: date) -> str:
    end = parse_date(deal.get("end", ""))
    if not end:
        return '<span class="deadline">长期有效</span>'
    if end < today:
        return f'<span class="deadline">{short_date(deal["end"])} 结束</span>'
    left = (end - today).days
    if left <= 1:
        return f'<span class="deadline hot">今天截止</span>'
    if left <= 30:
        return f'<span class="deadline hot">剩 {left} 天 · {short_date(deal["end"])}</span>'
    return f'<span class="deadline">{short_date(deal["end"])} 截止</span>'


def card(deal: dict, today: date, rank: int | None = None) -> str:
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    expired = bool(deal.get("status") == "expired")
    classes = "card"
    if expired:
        classes += " is-expired"

    badges = ""
    if rank is not None:
        badges = f'<span class="badge rank">#{rank}</span>'

    steps = "".join(f"<li>{e(s)}</li>" for s in deal.get("steps", []))
    if not steps:
        steps = "<li>见官方活动页</li>"

    marks = ""
    if deal.get("verified"):
        marks = '<span class="verified">✓ 已核验</span>'
    else:
        marks = '<span>待核实</span>'

    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"

    return f"""<article class="{classes}" data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(deal.get('added', ''))}" data-val="{int(deal.get('value_num') or 0)}"
    data-key="{e(deal['id'])}" data-hay="{e(' '.join([deal.get('title',''), deal.get('highlight',''), deal.get('regions',''), deal.get('brand',''), cost]))}">
    <div class="card-head" role="button" tabindex="0" aria-expanded="false">
      <img class="fav" src="https://www.google.com/s2/favicons?domain={e(deal['domain'])}&amp;sz=64" alt=""
           loading="lazy" decoding="async" referrerpolicy="no-referrer"
           data-fallback="{e((deal.get('brand') or '?')[:1].upper())}"
           onerror="window.__favFallback&&window.__favFallback(this)">
      <span class="fav-fallback" style="display:none">{e((deal.get('brand') or '?')[:1].upper())}</span>
      <div class="card-body">
        <div class="row1">
          <h3>{e(deal['title'])}</h3>
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
          <button class="toggle" type="button" aria-label="展开详情">详情
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
                 stroke-linejoin="round" aria-hidden="true"><path d="m2.5 4.5 3.5 3.5 3.5-3.5"/></svg>
          </button>
        </div>
      </div>
    </div>
    <div class="detail"><div class="detail-in"><div class="detail-body">
      <div class="field wide"><dt>优惠内容</dt><dd>{e(deal['content'])}</dd></div>
      <div class="field"><dt>实际价值</dt><dd><strong>{e(deal['value'])}</strong></dd></div>
      <div class="field"><dt>所属类别</dt><dd>{e(CATEGORY_LABEL.get(deal['category'], deal['category']))}</dd></div>
      <div class="field wide"><dt>参与条件</dt><dd>{e(deal['conditions'])}</dd></div>
      <div class="field"><dt>适用国家或地区</dt><dd>{e(deal['regions'])}</dd></div>
      <div class="field"><dt>开始及截止时间</dt><dd>{e(deal.get('start') or '官方未公布')} → {e(deal.get('end') or '长期 / 官方未公布')}</dd></div>
      <div class="field wide"><dt>参与步骤</dt><ol>{steps}</ol></div>
      <div class="field wide"><dt>官方活动链接</dt>
        <dd><a class="go" href="{e(deal['url'])}" target="_blank" rel="noopener nofollow">{e(deal['url'])}</a></dd></div>
      <div class="risk">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" aria-hidden="true">
          <path d="M8 2.6 14.2 13H1.8L8 2.6Z"/><path d="M8 6.6v3.1M8 11.6v.1"/></svg>
        <span>{e(deal['risk'])}</span>
      </div>
      <div class="detail-foot">
        <span>{marks}</span>
        <span>来源 · {e(deal['source'])}</span>
        <span>最后验证 · {e(deal['last_verified'])}</span>
        <span>收录 · {e(deal.get('added', ''))}</span>
      </div>
    </div></div></div>
  </article>"""


def module_html(
    anchor: str,
    letter: str,
    kicker: str,
    title: str,
    desc: str,
    deals: list[dict],
    today: date,
    ranked: bool = False,
) -> str:
    cards = []
    for i, deal in enumerate(deals, start=1):
        cards.append(card(deal, today, rank=i if ranked else None))
    count = len(deals)
    empty = (
        '<p class="module-empty" style="display:none">该分类暂无符合条件的优惠</p>'
        if count
        else '<p class="module-empty" style="display:block">该分类暂无符合条件的优惠</p>'
    )
    return f"""
  <section class="module" id="{anchor}" data-mod="{anchor}" data-limit="{count}">
    <header class="module-head">
      <div class="module-kicker"><span class="num">{letter}</span><span>{kicker}</span><span class="rule"></span></div>
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
        <span class="pager-label" data-label>1–{min(4, count) if count else 0} / {count}</span>
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
    today = date.today()

    for deal in deals:
        end = parse_date(deal.get("end", ""))
        if end and end < today:
            deal["status"] = "expired"
        elif end and (end - today).days <= 7:
            deal["status"] = "expiring_soon"
        else:
            deal["status"] = "active"

    active = [d for d in deals if d["status"] != "expired"]
    expired = [d for d in deals if d["status"] == "expired"]
    active_sorted = sorted(active, key=lambda d: (d.get("value_num") or 0), reverse=True)

    since = (today - timedelta(days=2)).isoformat()
    todays = sorted(
        [d for d in active if (d.get("added") or "") >= since],
        key=lambda d: ((d.get("added") or ""), d.get("value_num") or 0),
        reverse=True,
    )[:8]

    closing = sorted(
        [d for d in active if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= 30],
        key=lambda d: parse_date(d["end"]),
    )

    by_cat = {k: [d for d in active_sorted if d["category"] == k] for k in CATEGORY_LABEL}

    last_updated = meta.get("last_updated_human") or LAST_UPDATED_FALLBACK
    counts = {
        "active": len(active),
        "expiring": len(closing),
        "expired": len(expired),
        "total": len(deals),
    }

    rail = "".join(
        f'<a href="#{anchor}" data-target="{anchor}" aria-label="{label}">{icon}'
        f'<span>{label}</span></a>'
        for anchor, label, icon in NAV
    )

    modules = "".join(
        [
            module_html(
                "today", "A", "Today", "今日最新优惠",
                f"最近 48 小时新收录、且仍在进行的优惠。今天重点看这 {len(todays)} 条，其余按分类往下翻。",
                todays, today,
            ),
            module_html(
                "rank", "B", "Ranking", "高价值优惠排行榜",
                "按实际价值（现金奖励 / 额度 / 年费）排序，先挑最值钱的。金额为官方标注上限，达标条件见详情。",
                active_sorted[:10], today, ranked=True,
            ),
            module_html(
                "ai", "C", "AI Tools", "AI 工具免费与折扣",
                "ChatGPT、Gemini、Claude、Copilot、Cursor 等免费额度与限时赠送，含学生专属。",
                by_cat["ai"], today,
            ),
            module_html(
                "crypto", "D", "Crypto", "Crypto 空投与积分",
                "交易所新人奖励、任务空投与积分计划；奖励多为返佣券或代币，注意可提现条件。",
                by_cat["crypto"], today,
            ),
            module_html(
                "bank", "E", "Banks & Remittance", "海外银行 · U 卡 · 跨境汇款",
                "开户奖励、虚拟卡返现、可双向叠加的邀请奖励（Wise / Sendwave / Taptap Send / Remitly 等）。",
                by_cat["bank"], today,
            ),
            module_html(
                "cloud", "F", "VPS & Cloud", "VPS 及云服务",
                "永久免费实例、新人体验金与黑五主机折扣，部署前先看清到期与回收规则。",
                by_cat["cloud"], today,
            ),
            module_html(
                "esim", "I", "eSIM", "eSIM 全球流量",
                "免费试用与首单折扣，每条都标出可用国家或地区与注册限制——先试网，再买大套餐。",
                by_cat["esim"], today,
            ),
            module_html(
                "closing", "G", "Closing Soon", "即将截止",
                "30 天内到期的活动，按截止时间排序；标「剩 N 天」的请优先处理。",
                closing, today,
            ),
            module_html(
                "software", "J", "Software", "软件与数字服务",
                "学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠。",
                by_cat["software"], today,
            ),
            module_html(
                "archive", "H", "Archive", "已结束活动档案",
                "已过期活动保留 30 天供查档，随后自动清理，避免陈旧信息占版面。",
                sorted(expired, key=lambda d: d.get("end") or "", reverse=True), today,
            ),
        ]
    )

    item_list = []
    for i, deal in enumerate(active_sorted[:10], start=1):
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
<meta name="keywords" content="羊毛,优惠情报,免费额度,AI 免费,eSIM 免费流量,海外银行开户奖励,跨境汇款邀请奖励,VPS 免费,云服务额度,空投,积分计划,学生优惠,黑五优惠">
<meta name="author" content="羊毛情报局">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#07090b">
<link rel="canonical" href="{SITE_URL}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="羊毛情报局">
<meta property="og:locale" content="zh_CN">
<meta property="og:title" content="羊毛情报局 · 全球优惠与免费额度情报">
<meta property="og:description" content="每日核验的全球优惠导航：AI、Crypto、海外银行与汇款、云服务、eSIM、软件学生福利。价值、门槛、截止时间一眼看清，直达官方链接。">
<meta property="og:url" content="{SITE_URL}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="羊毛情报局 · 全球优惠与免费额度情报">
<meta name="twitter:description" content="每日核验的全球优惠导航：AI、Crypto、海外银行与汇款、云服务、eSIM、软件学生福利。">

<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/favicon.svg">
<link rel="preconnect" href="https://www.google.com" crossorigin>
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
        <svg viewBox="0 0 24 24" fill="none" stroke="#04140d" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
          <path d="M13 2.6 5.2 13h5.4L10.4 21.4 18.8 10h-5.4L13 2.6Z"/>
        </svg>
      </span>
      <span>
        <span class="brand-name">羊毛情报局</span>
        <span class="brand-sub">最后更新 {e(last_updated)}</span>
      </span>
    </a>
    <div class="topbar-stats">
      <span class="k">进行中 <b style="color:#7bf0bd">{counts['active']}</b></span>
      <span class="sep">·</span>
      <span class="k">即将截止 <b style="color:#e6b45f">{counts['expiring']}</b></span>
    </div>
    <span class="spacer"></span>
    <button class="search-btn" id="open-search" type="button" aria-haspopup="dialog">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
        <circle cx="7" cy="7" r="4.4"/><path d="m10.4 10.4 3 3"/>
      </svg>
      搜索 / 筛选
      <kbd>⌘K</kbd>
    </button>
  </div>
</header>

<main id="top">
  <div class="shell">
    <section class="hero">
      <div class="hero-kicker"><span class="dot"></span>情报更新 · {e(today.isoformat())}</div>
      <h1>全球的免费额度与限时奖励，<br><em>先看值得点的。</em></h1>
      <p>每条都回到官方页面核对过：值多少、门槛、截止日。想细看就展开，不想就直接点原链接。</p>
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
  <div class="shell foot-in">
    <div>
      <div class="foot-brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="#04140d" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M13 2.6 5.2 13h5.4L10.4 21.4 18.8 10h-5.4L13 2.6Z"/>
          </svg>
        </span>
        羊毛情报局
      </div>
      <p class="foot-note">所有优惠均来自各活动官方页面，具体条款、名额与到账时间以官方为准。部分活动涉及入金、开户或交易，请量力参与；本站不提供投资建议，也不代收任何费用。</p>
    </div>
    <div class="foot-meta">
      <span>最后更新 · {e(last_updated)}</span>
      <span>已核验 {counts['active']} 条进行中 · 归档 {counts['expired']} 条</span>
      <span>© {today.year} 羊毛情报局</span>
    </div>
  </div>
</footer>

<script src="assets/js/app.js?v={asset_ver('assets/js/app.js')}" defer></script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"index.html written · {len(active)} active / {len(expired)} expired / {len(todays)} today")


if __name__ == "__main__":
    main()
