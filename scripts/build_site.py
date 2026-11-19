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
  · 单语渲染：`/` 只输出中文、`/en/` 只输出英文，不再内联 <span class="t-zh">/…t-en> 双份文案；
    文案仍以 (中文, English) 成对维护在 scripts/i18n.py，构建时按页面语言取一侧；
  · 图标在构建时下载成 assets/fav/<domain>.webp（48×48，透明通道），境内直连 GitHub Pages 即可显示。
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
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from common import (  # noqa: E402
    CAT_META,
    CLOSING_SLOTS,
    CLOSING_WINDOW_DAYS,
    DATA,
    EXPIRING_DAYS,
    FAV_DIR,
    META,
    OG_IMAGE,
    OG_IMAGE_EN,
    OUT,
    SITE_URL,
    TODAY_WINDOW_DAYS,
    TZ,
    added_date,
    compute_status,
    ensure_added_at,
    now_local,
    parse_date,
    short_date,
    today_local,
    value_expected,
)
from i18n import (  # noqa: E402
    CAT_EN,
    COST_EN,
    U,
    load_en,
    short_date_en,
    upair,
)

# 英文版页面：/en/index.html（纯英文 DOM），中文首页 /index.html（纯中文 DOM）。
# 两页各自独立，语言切换直接跳转；老外链 /?lang=en 由 <head> 里的极短脚本转到 /en/。
EN_OUT = ROOT / "en" / "index.html"

try:
    from PIL import Image
except ImportError:  # Pillow 缺失时图标退化为字母块，不阻塞构建
    Image = None  # type: ignore[assignment]

FAV_UA = "Mozilla/5.0 (compatible; YangMaoBot/1.0; +https://vvotzs.github.io/)"
FAV_SIZE = 48
FAV_QUALITY = 82
FAV_METHOD = 6

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
    # 口径说明（ⓘ）：细圈 + 小写 i
    "info": (16, '<circle cx="8" cy="8" r="6.3"/><path d="M8 7.3v4.1"/><path d="M8 4.8v.1"/>', 1.35),
    # 展开箭头
    "chevron": (12, '<path d="m2.5 4.5 3.5 3.5 3.5-3.5"/>', 1.8),
    # 搜索
    "search": (16, '<circle cx="7" cy="7" r="4.4"/><path d="m10.4 10.4 3 3"/>', 1.6),
    # 风险提示
    "warn": (16, '<path d="M8 2.6 14.2 13H1.8L8 2.6Z"/><path d="M8 6.6v3.1M8 11.6v.1"/>', 1.4),
    # 投稿：纸飞机 + 暖色尾迹
    "send": (24, '<path d="M20.8 3.5 3.6 10.6c-.9.4-.9 1.6 0 1.9l5.5 2 2 5.5c.4.9 1.6.9 1.9 0l7.1-17.2c.3-.8-.5-1.6-1.3-1.3Z" fill="#FDBA74"/>'
               '<path d="M9.1 14.5 20.3 4.1" stroke="#FFFFFF" stroke-opacity=".85"/>'
               '<path d="M11.2 13.9l-2.1 4.6" stroke="#C2410C" stroke-opacity=".55"/>', 1.7),
}

# 投稿：纯原生 <dialog> 弹窗 → fetch 直接 POST 到 Google Apps Script Web App，
# 由脚本用 MailApp 发信到 vvotzs@gmail.com（免费，不占第三方表单额度，也没有水印）。
# 换接口只改这一处再重建；app.js 从弹窗的 data-endpoint 读地址。
SUBMIT_ENDPOINT = (
    "https://script.google.com/macros/s/"
    "AKfycbytBigdTS4LTwtRh6K_jiTPXHOf-6MvljhVuYFDZ9VLfUuTmzgNqNATK_oX2UELJzCJTg/exec"
)
TG_GROUP_URL = "https://t.me/+aAqP0DbW_YMxMmNh"

# 薄荷绿 Pickle 小精灵（页头 / 页脚直接内联，不走 sprite）。
# 渐变必须写在可见的 <svg> 自己的 <defs> 里：放进 display:none 的 sprite 后，
# Chrome/Android 的 <use> 会让 url(#id) 失效，身体变透明只剩一张白脸。
# 每处内联用一个独立的渐变 id，避免同一页出现重复 id。
_MASCOT_BODY = (
    '<path d="M20 3.6c8.6 0 13.1 5.9 13.1 14.2 0 9.6-5.4 18.6-13.1 18.6S6.9 27.4 6.9 17.8C6.9 9.5 11.4 3.6 20 3.6Z" fill="url(#{gid})"/>'
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
)


def sprite_svg() -> str:
    """整页共用的一份图标 sprite：<symbol> 定义一次，各处 <use> 引用。"""
    parts = [
        '<svg class="sprite" style="display:none" aria-hidden="true" focusable="false">',
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


def mascot_svg(cls: str = "", gid: str = "mintBody") -> str:
    """内联完整的小精灵：渐变、腮红、高光都在，直接画在页面上（不走 <use>）。"""
    body = _MASCOT_BODY.replace("{gid}", gid)
    return (
        f'<svg class="i{" " + cls if cls else ""}" viewBox="0 0 40 40" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0" stop-color="#B7F5DA"/><stop offset="1" stop-color="#7FE3B8"/>'
        f"</linearGradient></defs>{body}</svg>"
    )


NAV = [
    ("fresh", "nav_fresh", "today"),
    ("rank", "nav_rank", "rank"),
    ("ai", "nav_ai", "ai"),
    ("crypto", "nav_crypto", "crypto"),
    ("bank", "nav_bank", "bank"),
    ("cloud", "nav_cloud", "cloud"),
    ("esim", "nav_esim", "esim"),
    ("closing", "nav_closing", "clock"),
    ("software", "nav_software", "software"),
    ("archive", "nav_archive", "archive"),
]

COST_CLASS = {
    "真正免费": "cost-free",
    "免费试用": "cost-trial",
    "需要充值": "cost-deposit",
    "需要交易量": "cost-volume",
    "需要邀请条件": "cost-invite",
}


ZH_DESC = (
    "羊毛情报局：每日核验的全球优惠情报导航。AI 工具免费额度、Crypto 空投与交易奖励、"
    "海外银行开户与跨境汇款邀请、VPS 云服务体验金、eSIM 免费流量、软件学生福利——"
    "一屏看清价值、门槛与截止时间，点击直达官方活动页。"
)
EN_TITLE = "Deal Hunter · Verified global deals, free credits & sign-up bonuses"
EN_DESC = (
    "Deal Hunter: a directory of global offers, refreshed every 2 hours — free AI credits, crypto sign-up rewards, "
    "overseas bank and remittance bonuses, VPS credits, free eSIM data and student software. "
    "Value, requirements and deadline on one card, straight to the official page."
)
EN_OG_DESC = (
    "Free AI credits, crypto rewards, bank and remittance bonuses, VPS credits, free eSIM data and "
    "student software — value, requirements and deadline at a glance."
)

# 老外链兼容：页面上只有一种语言，语言由 URL 决定。之前发到 X / Dev.to / Hashnode / Medium
# 的 `/?lang=en` 链接会在 <head> 最前面立刻跳到 /en/（反之 /en/?lang=zh 跳回 /），
# 保留 #hash 与 ?q= 等其他参数；脚本失败时页面照常按自己的语言渲染。
LANG_BOOT = (
    "<script>!function(){try{var p=new URLSearchParams(location.search),l=p.get('lang'),to='';"
    "if(/^\\/en(\\/|$)/.test(location.pathname)){if(l==='zh')to='/';}"
    "else if(l==='en'){to='/en/';}"
    "if(to){p.delete('lang');var q=p.toString();"
    "location.replace(to+(q?'?'+q:'')+location.hash);}}catch(e){}}();</script>"
)


def asset_ver(rel: str) -> str:
    """给静态资源带上内容哈希，避免 GitHub Pages CDN 缓存旧样式。"""
    path = ROOT / rel
    if not path.exists():
        return "1"
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_url(value: object) -> str:
    """只放行 http:// 与 https://。

    href 里的 `javascript:` / `data:` / `vbscript:` 在 HTML 转义后依然可执行，
    所以外链（url / source_url / source 里抓到的原帖）在渲染前统一过一遍协议白名单。
    不通过就返回空串，调用处渲染成不可点的文本。
    """
    s = ("" if value is None else str(value)).strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("https://") or low.startswith("http://"):
        return s
    return ""


# 当前正在渲染的页面语言。main() 里每个页面渲染前设置一次，`bi()` / `ui()` 据此只取一侧文案，
# 页面里不再同时存在中英两份 DOM。
CUR_LANG = "zh"


def set_lang(lang: str) -> None:
    global CUR_LANG
    CUR_LANG = "en" if lang == "en" else "zh"


def bi(zh: str, en: str, cls: str = "") -> str:
    """单语片段：只输出当前页面语言的一份文案（zh / en 都已转义）。

    文案仍在调用处成对书写，方便一处维护两种语言；构建时按页面语言取一侧，
    不再生成 <span class="t-zh"> + <span class="t-en"> 的双份 DOM（体积与节点数减半）。
    cls 参数保留给旧调用点，单语输出下已无需要。
    """
    return en if CUR_LANG == "en" else zh


def ui(key: str, **fmt) -> str:
    """界面文案的单语片段；带占位符的 key 用 fmt 填。"""
    zh, en = U[key]
    if fmt:
        return bi(zh.format(**fmt), en.format(**fmt))
    return bi(zh, en)


def al(zh: str, en: str) -> str:
    """无障碍标签：构建时按当前语言直接写成 aria-label，不用再在 DOM 上挂 data-al-zh/-en 让 JS 回填。"""
    return f'aria-label="{e(en if CUR_LANG == "en" else zh)}"'


def deadline_html(deal: dict, today) -> str:
    end = parse_date(deal.get("end", ""))
    if not end:
        return f'<span class="deadline">{ui("ongoing")}</span>'
    if end < today:
        return f'<span class="deadline">{bi(short_date(deal["end"]) + " 结束", "Ended " + short_date_en(end))}</span>'
    # left 是「今天之后还剩几个自然日」：0 = 今天截止、1 = 明天截止。
    # 原来写成 left <= 1 会把「明天截止」也说成今天，用户会当成最后一天。
    left = (end - today).days
    if left == 0:
        return f'<span class="deadline hot">{ui("ends_today")}</span>'
    if left == 1:
        return f'<span class="deadline hot">{ui("ends_tomorrow")}</span>'
    if left <= 30:
        return (
            f'<span class="deadline hot">'
            f'{bi(f"剩 {left} 天 · {short_date(deal["end"])}", f"{left} days left · {short_date_en(end)}")}</span>'
        )
    return f'<span class="deadline">{bi(short_date(deal["end"]) + " 截止", "Ends " + short_date_en(end))}</span>'


def added_day(deal: dict, today) -> str:
    """卡片上展示的收录日期（YYYY-MM-DD）。

    数据里理论上一定有 added，但外部脚本 / 手工追加可能只写了 added_at，
    渲染层再兜一层，保证不会出现空的「收录 · 」。
    """
    return str(deal.get("added") or deal.get("added_at") or today.isoformat())[:10]


def short_deadline(deal: dict, today) -> tuple[str, str]:
    """跳转卡第二行用的极短截止提示（(中文, English)）。"""
    end = parse_date(deal.get("end", ""))
    if not end:
        return U["ongoing"]
    left = (end - today).days
    if left < 0:
        return (U["ended_word"][0], U["ended_word"][1])
    if left == 0:
        return U["ends_today"]
    if left == 1:
        return U["ends_tomorrow"]
    if left <= 30:
        return (f"剩 {left} 天", f"{left}d left")
    return (short_date(deal["end"]), short_date_en(end))


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
    return value_text((deal.get("value") or "").strip(), deal)


def value_text(raw: str, deal: dict) -> str:
    """对任意语言的 value 原文做同一套折算：
    括号里的折算值提前、非美元金额补 ≈$ 对照、上限型补期望值。"""
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


def value_pair(deal: dict, en: dict) -> tuple[str, str]:
    """卡面价值徽标：中文取 value，英文取 value_en（缺字段时退回原文）。"""
    raw_en = (en.get("value") or "").strip() or (deal.get("value") or "").strip()
    return value_text((deal.get("value") or "").strip(), deal), value_text(raw_en, deal)


def value_compact(v: str, lang: str = "zh") -> str:
    """热榜窄条用的短价值：去括号补充说明，还长就只留「≈$X」。"""
    v = re.sub(r"[（(][^）)]*[）)]", "", v).strip()
    # 英文单词更长，宽度阈值放多一点（约合同样像素宽度）
    limit = 18 if lang == "zh" else 22
    if len(v) > limit and " · " in v:
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
    """把任意格式（png / ico / svg 转出的位图）统一成 48×48 WebP（保留透明通道）。"""
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
    canvas.resize((FAV_SIZE, FAV_SIZE), resample).save(
        dest, "WEBP", quality=FAV_QUALITY, method=FAV_METHOD
    )
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
    """把域名图标缓存成 assets/fav/<domain>.webp；有缓存就直接复用。"""
    if not domain:
        return False
    FAV_DIR.mkdir(parents=True, exist_ok=True)
    dest = FAV_DIR / f"{fav_name(domain)}.webp"
    if dest.exists() and dest.stat().st_size > 100:
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
def detail_tags(deal: dict, en: dict) -> str:
    cat = deal.get("category", "")
    cat_zh = CAT_META.get(cat, {"label": cat})["label"]
    cat_en = CAT_EN.get(cat, (cat, ""))[0]
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    cost_en = COST_EN.get(cost, cost)
    if deal.get("verified"):
        check = f'<span class="dcheck ok">{ui("verified")}</span>'
    else:
        check = f'<span class="dcheck wait">{ui("unverified")}</span>'
    v_zh, v_en = value_pair(deal, en)
    return (
        '<div class="detail-tags">'
        f'<span class="dtag cat">{bi(e(cat_zh), e(cat_en))}</span>'
        f'<span class="dval"><span class="dval-k">{ui("actual_value")}</span>'
        f"<strong>{bi(e(v_zh), e(v_en))}</strong></span>"
        f'<span class="dtag {cost_cls}">{bi(e(cost), e(cost_en))}</span>'
        f"{check}"
        "</div>"
    )


# 「直达」按钮指向抓取来源（nodeseek / nodeloc / linux.do / Reddit 等原帖），
# 只有条目显式给了 source_url，或 source 里写了原帖链接时才切换；官网链接始终留在详情里。
_SRC_URL_RE = re.compile(r"https?://[^\s）)，,；;】]+")


def monogram_for(deal: dict, en: dict | None) -> str:
    """图标兜底的字母块。

    中文页取品牌首字（「币」「华」），英文页取英文标题的首个字母数字
    （标题带 [Global] 这类前缀时先剥掉），拿不到再退域名首字母——
    英文页不能出现中文字符。
    """
    if CUR_LANG == "en":
        _, title = title_parts((en or {}).get("title") or deal.get("title", ""))
        hit = re.search(r"[A-Za-z0-9]", title)
        if hit:
            return hit.group(0).upper()
        dom = (deal.get("domain") or "").strip()
        return dom[:1].upper() if dom else "?"
    return (deal.get("brand") or "?")[:1].upper()


def fav_html(deal: dict, size: int, en: dict | None = None) -> str:
    """站点图标：构建时已落地的用 <img>（WebP）；个别域名下载不到就直接给字母块，避免页面上出现 404。"""
    name = fav_name(deal.get("domain", ""))
    monogram = e(monogram_for(deal, en))
    if (FAV_DIR / f"{name}.webp").exists():
        return (
            f'<img class="fav" src="/assets/fav/{name}.webp" width="{size}" height="{size}" alt="" '
            f'loading="lazy" decoding="async" data-fallback="{monogram}" '
            f'onerror="window.__favFallback&&window.__favFallback(this)">'
            f'<span class="fav-fallback" style="display:none" aria-hidden="true">{monogram}</span>'
        )
    return f'<span class="fav-fallback" style="display:grid" aria-hidden="true">{monogram}</span>'


def main_link(deal: dict) -> str:
    """卡片主按钮的去向：抓取来源优先，没有就回官网活动页。"""
    src = safe_url(deal.get("source_url"))
    if not src:
        m = _SRC_URL_RE.search(deal.get("source") or "")
        src = safe_url(m.group(0).rstrip("。.,；;") if m else "")
    official = safe_url(deal.get("url"))
    if src and src.rstrip("/") != official.rstrip("/"):
        return src
    return official


def official_link(deal: dict) -> str:
    return safe_url(deal.get("url"))


def card(deal: dict, en: dict, today) -> str:
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    expired = bool(deal.get("status") == "expired")
    classes = "card is-expired" if expired else "card"

    steps_src = (en.get("steps") or []) if CUR_LANG == "en" else deal.get("steps", [])
    steps = "".join(f"<li>{e(s)}</li>" for s in steps_src)
    if not steps:
        steps = f"<li>{e(U['see_official'][1] if CUR_LANG == 'en' else U['see_official'][0])}</li>"

    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"
    v_zh, v_en = value_pair(deal, en)

    region_text_zh = strip_region_bracket(deal["regions"])
    region_text_en = strip_region_bracket(en.get("regions") or deal["regions"])
    region_html = ""
    if region_text_zh:
        region_html = (
            f'<span class="sep">·</span><span class="region">'
            f"{bi(e(region_text_zh), e(region_text_en))}</span>"
        )

    rtag, title_text = title_parts(
        (en.get("title") or deal.get("title", "")) if CUR_LANG == "en" else deal.get("title", "")
    )
    title_html = f'<span class="rtag">{e(rtag)}</span>' if rtag else ""
    title_html += e(title_text)

    hl_zh = e(deal.get("highlight", ""))
    hl_en = e(en.get("highlight") or deal.get("highlight", ""))

    deal_id = e(deal["id"])

    # 外链一律过协议白名单：只有 http(s) 才渲染成可点的 <a>，
    # javascript: / data: 这类值退化成纯文本，不会变成可执行的链接。
    link = safe_url(main_link(deal))
    if link:
        go_html = (
            f'<a class="go" href="{e(link)}" target="_blank" rel="noopener nofollow"\n'
            f'             {al("原文链接", "Open the source link")}><span class="go-full">{ui("go_full")}</span>'
            f'<span class="go-short">{ui("go_short")}</span>{icon("external")}</a>'
        )
    else:
        go_html = f'<span class="go">{ui("go_short")}</span>'

    official = safe_url(deal.get("url"))
    if official:
        url_dd = (
            f'<a class="url-link" href="{e(official)}" target="_blank" rel="noopener nofollow">'
            f"{e(official)}</a>"
        )
    else:
        url_dd = e(deal.get("url", ""))

    period = bi(
        f"{e(deal.get('start') or U['not_announced'][0])} → {e(deal.get('end') or U['ongoing_not_announced'][0])}",
        f"{e(deal.get('start') or U['not_announced'][1])} → {e(deal.get('end') or U['ongoing_not_announced'][1])}",
    )

    return f"""<article class="{classes}" id="deal-{deal_id}" data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(added_day(deal, today))}" data-added-at="{e(deal.get('added_at') or added_day(deal, today))}"
    data-val-exp="{value_expected(deal):g}" data-key="{deal_id}">
    <div class="card-head">
      {fav_html(deal, 24, en)}
      <div class="card-body">
        <div class="row1">
          <h3>{title_html}</h3>
          <span class="{value_cls}">{bi(e(v_zh), e(v_en))}</span>
        </div>
        <p class="row2"><span class="tag {cost_cls}">{bi(e(cost), e(COST_EN.get(cost, cost)))}</span>{bi(hl_zh, hl_en)}</p>
        <div class="row3">
          {deadline_html(deal, today)}
          {region_html}
          <span class="grow"></span>
          {go_html}
          <button class="toggle" type="button" aria-expanded="false" aria-controls="detail-{deal_id}"
                  {al('展开详情', 'Expand details')}>{ui("detail_open")}
            {icon('chevron')}
          </button>
        </div>
      </div>
    </div>
    <div class="detail" id="detail-{deal_id}"><div class="detail-in"><div class="detail-body">
      {detail_tags(deal, en)}
      <dl class="detail-fields">
      <div class="field wide"><dt>{ui("f_what")}</dt><dd>{bi(e(deal['content']), e(en.get('content') or deal['content']))}</dd></div>
      <div class="field wide"><dt>{ui("f_conditions")}</dt><dd>{bi(e(deal['conditions']), e(en.get('conditions') or deal['conditions']))}</dd></div>
      <div class="field"><dt>{ui("f_regions")}</dt><dd>{bi(e(deal['regions']), e(en.get('regions') or deal['regions']))}</dd></div>
      <div class="field"><dt>{ui("f_period")}</dt><dd>{period}</dd></div>
      <div class="field wide"><dt>{ui("f_steps")}</dt><dd><ol>{steps}</ol></dd></div>
      <div class="field wide"><dt>{ui("f_link")}</dt>
        <dd>{url_dd}</dd></div>
      </dl>
      <div class="risk">
        {icon('warn')}
        <span>{bi(e(deal['risk']), e(en.get('risk') or deal['risk']))}</span>
      </div>
      <div class="detail-foot">
        <span>{bi(e(f"{U['f_source'][0]} · {deal['source']}"), e(f"{U['f_source'][1]} · {en.get('source') or deal['source']}"))}</span>
        <span>{bi(e(f"{U['f_last_verified'][0]} · {deal['last_verified']}"), e(f"{U['f_last_verified'][1]} · {deal['last_verified']}"))}</span>
        <span>{bi(e(f"{U['f_added'][0]} · {added_day(deal, today)}"), e(f"{U['f_added'][1]} · {added_day(deal, today)}"))}</span>
      </div>
    </div></div></div>
  </article>"""


def jump_card(deal: dict, en: dict, today, rank: int | None = None) -> str:
    """精简跳转卡：点一下滚到 #deal-<id> 并展开，详情只存一份。

    标题独占第一行；价值徽标与地区/截止信息放第二行，标题能用到整行宽度。
    """
    rtag_zh, title_zh = title_parts(deal.get("title", ""))
    rtag_en, title_en = title_parts(en.get("title") or deal.get("title", ""))
    cost = deal.get("cost", "")
    deal_id = e(deal["id"])
    if rank is None:
        rank_html = ""
    else:
        rank_cls = "jump-rank" + (f" r{rank}" if rank <= 3 else "")
        rank_html = f'<span class="{rank_cls}"><i>#</i>{rank}</span>'
    # 截止提示放前面：窄条里被截断时先舍地区，不舍截止
    sd_zh, sd_en = short_deadline(deal, today)
    meta_zh = sd_zh + (f" · {rtag_zh}" if rtag_zh else "")
    meta_en = sd_en + (f" · {rtag_en}" if rtag_en else "")
    value_cls = "value gold" if (deal.get("value_num") or 0) >= 100 else "value"
    v_zh, v_en = value_pair(deal, en)

    return f"""<a class="jump" href="#deal-{deal_id}" data-jump="deal-{deal_id}"
    data-cat="{e(deal.get('category'))}" data-cost="{e(cost)}"
    data-verified="{1 if deal.get('verified') else 0}" data-end="{e(deal.get('end', ''))}"
    data-added="{e(added_day(deal, today))}" data-added-at="{e(deal.get('added_at') or added_day(deal, today))}"
    data-val-exp="{value_expected(deal):g}" data-key="{deal_id}">
      {rank_html}
      {fav_html(deal, 22, en)}
      <span class="jump-main">
        <span class="jump-title">{bi(e(title_zh), e(title_en))}</span>
        <span class="jump-sub"><span class="{value_cls}">{bi(e(value_compact(v_zh)), e(value_compact(v_en, 'en')))}</span><span class="jump-meta">{bi(e(meta_zh), e(meta_en))}</span></span>
      </span>
      {icon('external', 'jump-arrow')}
    </a>"""


def module_html(
    anchor: str,
    icon_key: str,
    title: tuple[str, str],
    desc: tuple[str, str],
    deals: list[dict],
    en_map: dict,
    today,
    ranked: bool = False,
    jump: bool = False,
    strip: bool = False,
    hidden: bool = False,
) -> str:
    if jump:
        cards = [
            jump_card(deal, en_map.get(deal["id"], {}), today, rank=i if ranked else None)
            for i, deal in enumerate(deals, start=1)
        ]
    else:
        cards = [card(deal, en_map.get(deal["id"], {}), today) for deal in deals]
    count = len(deals)
    # 分类内左右横滑翻页：手机一页 5 张（一屏装得下）、桌面双列一页 8 张；热榜跳转卡不翻页
    per_page = 6 if jump else 5
    per_page_lg = 6 if jump else 8
    pages = max(1, -(-count // per_page))
    # 说明文字统一留在标题行里（热榜条没有标题行，跟着一起隐藏），
    # 手机端「即将截止」的口径改由 tab 上的 ⓘ 吐司说明，不再占一行高度。
    desc_html = f'<p class="module-desc">{bi(*desc)}</p>'
    return f"""
  <section class="module{(' hot-strip' if strip else '')}" id="{anchor}" data-mod="{anchor}" data-per="{per_page}" data-per-lg="{per_page_lg}"{' data-kind="jump"' if jump else ''}{' hidden' if hidden else ''}>
    <header class="module-head">
      <span class="module-badge" aria-hidden="true">{icon(icon_key)}</span>
      <h2>{bi(*title)} <span class="count" data-count>{count}</span></h2>
      {desc_html}
    </header>
    <div class="track" data-track>
      {''.join(cards)}
    </div>
    <div class="pager-bar" data-bar>
      <button class="pg" type="button" data-prev {al('上一页', 'Previous page')}>‹</button>
      <span class="pager-label" data-label>1 / {pages}</span>
      <button class="pg" type="button" data-next {al('下一页', 'Next page')}>›</button>
    </div>
    <p class="module-empty" style="display:none">{ui("mod_empty")}</p>
    <button class="more" type="button" data-more hidden></button>
  </section>"""


def compact_html(page: str) -> str:
    """去掉每行缩进和空行：生成物小一大截，源码可读性交给生成器。"""
    page = re.sub(r"\n[ \t]+", "\n", page)
    return re.sub(r"\n{2,}", "\n", page)


def validate(deals: list[dict], en_map: dict) -> None:
    """构建前的数据体检：有硬伤就直接报错退出，宁愿不发布。

    重点是把可注入 / 可跺页面的值挡在渲染之前：
      · url / source_url 必须是 http(s)（javascript: / data: 一律拒绝）
      · id 唯一、必填字段齐全
      · end / start 是 YYYY-MM-DD，且 end 不早于 start
      · category / cost 在枚举范围内
      · deals_en 里的 id 能在 deals 里找到（单向：允许英文翻译暂缺）
    """
    errors: list[str] = []
    seen: set[str] = set()
    required = ("id", "title", "url", "category", "cost", "regions", "content", "conditions", "risk", "source")
    for i, deal in enumerate(deals):
        tag = deal.get("id") or f"#{i}"
        for key in required:
            if not str(deal.get(key) or "").strip():
                errors.append(f"{tag}: 缺字段 {key}")
        if tag in seen:
            errors.append(f"{tag}: id 重复")
        seen.add(tag)
        for key in ("url", "source_url"):
            raw = str(deal.get(key) or "").strip()
            if raw and not safe_url(raw):
                errors.append(f"{tag}: {key} 不是 http(s) 链接（{raw[:40]}）")
        start = parse_date(deal.get("start", ""))
        end = parse_date(deal.get("end", ""))
        if deal.get("start") and not start:
            errors.append(f"{tag}: start 日期格式不对（{deal.get('start')}）")
        if deal.get("end") and not end:
            errors.append(f"{tag}: end 日期格式不对（{deal.get('end')}）")
        if start and end and end < start:
            errors.append(f"{tag}: end 早于 start")
        if deal.get("category") not in CAT_META:
            errors.append(f"{tag}: category 不在枚举内（{deal.get('category')}）")
        if deal.get("cost") not in COST_CLASS:
            errors.append(f"{tag}: cost 不在枚举内（{deal.get('cost')}）")
    for key in en_map:
        if key not in seen:
            errors.append(f"deals_en: 多出未对应的 id {key}")
    if errors:
        print("数据体检未通过，已停止构建：", file=sys.stderr)
        for line in errors[:40]:
            print("  · " + line, file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    today = today_local()

    for deal in deals:
        deal["status"] = compute_status(deal, today)

    # 数据体检：外链协议、必填字段、日期、枚举；不通过直接拒绝构建。
    validate(deals, load_en())

    # 图标：构建时落地到 assets/fav/，页面不再请求 google.com
    missing = []
    for deal in deals:
        if not ensure_favicon(deal.get("domain", "")):
            missing.append(deal.get("domain", "?"))

    active = [d for d in deals if d["status"] != "expired"]
    expired = [d for d in deals if d["status"] == "expired"]
    # 入库时在 deals.json 里的位置（仅用作同一时刻入库的条目之间的稳定次序）
    idx_of = {d["id"]: i for i, d in enumerate(deals)}

    # 手动追加条目、只跑 build_site 的路径也要有入库时间：缺的补上并回写数据文件
    if ensure_added_at(deals):
        DATA.write_text(json.dumps(deals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已为缺入库时间的条目补写 added_at 并回写 {DATA.name}")

    # 新收录：最近 48 小时按「入库先后」倒序。
    # 不能用 value_expected / 文件下标当次序：added 只精确到日期，同一天上百条并列，
    # 一加价值键就会退化成第二个「高价值榜」（大额银行奖把当天新条目全压下去）；
    # 而 deals.json 每次维护都按价值重排过，下标本身就是价值序。
    # 真正的入库时间写在 added_at，主次序只认它；只有同一批次（时间戳相同）内
    # 才按价值高低排，让同一批里更值钱的先出现。
    # 筛选与排序都只认入库日期（added_at 的日期部分，与卡片展示的 added 同一天）：
    # 只看 added 会漏掉只有 added_at 的条目，只看 added_at 又会把回填成今天的老条目放进来。
    # 真正的「最近 48 小时」：拿 added_at 的时间戳和当前时刻比，而不是拿日期比。
    # 原来用 added >= today-2（按日期）实际把今天、昨天、前天三个自然日都算了进来
    # （最多 72 小时），与板子上写的「最近 48 小时」对不上。
    now = now_local()
    cutoff = now - timedelta(hours=TODAY_WINDOW_DAYS * 24)

    def added_stamp(deal: dict) -> datetime | None:
        """入库时刻（带时区）；只有日期时按北京零点算。"""
        raw = str(deal.get("added_at") or "")
        try:
            stamp = datetime.fromisoformat(raw)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=TZ)
            return stamp
        except ValueError:
            day = parse_date(added_date(deal))
            return datetime(day.year, day.month, day.day, tzinfo=TZ) if day else None

    fresh_pool = [d for d in active if (stamp := added_stamp(d)) and stamp >= cutoff]
    fresh_pool.sort(key=lambda d: (-value_expected(d), idx_of.get(d["id"], 0)))
    fresh_pool.sort(key=lambda d: d.get("added_at") or d.get("added") or "", reverse=True)
    fresh = fresh_pool[:10]
    # 今天没有新条目时也保证板子不空
    if not fresh:
        fresh = sorted(
            active,
            key=lambda d: (d.get("added_at") or d.get("added") or "",),
            reverse=True,
        )[:10]

    # 高价值榜：按可预期到手金额（不是上限）排
    leaderboard = sorted(active, key=lambda d: (value_expected(d), d.get("value_num") or 0), reverse=True)[:10]

    # 「即将截止」分两层，两个口径各管各的，别混：
    #   · closing_pool —— EXPIRING_DAYS（7 天）内到期。顶栏胶囊的计数与 meta.json
    #     的 expiring_soon 仍旧只认它，口径不变。
    #   · closing —— 热榜面板实际展示的 CLOSING_SLOTS 条：7 天内的按到期日升序排在前面，
    #     不足 10 条时用 8～30 天（CLOSING_WINDOW_DAYS）内到期的按到期日升序补足。
    #     这样桌面右侧板不会只剩三四行留白，同时排在前面的永远是最该先处理的。
    closing_pool = sorted(
        [
            d
            for d in active
            if parse_date(d.get("end", "")) and 0 <= (parse_date(d["end"]) - today).days <= EXPIRING_DAYS
        ],
        key=lambda d: parse_date(d["end"]),
    )
    closing_fill = sorted(
        [
            d
            for d in active
            if parse_date(d.get("end", ""))
            and EXPIRING_DAYS < (parse_date(d["end"]) - today).days <= CLOSING_WINDOW_DAYS
        ],
        key=lambda d: parse_date(d["end"]),
    )
    closing = (closing_pool + closing_fill)[:CLOSING_SLOTS]
    # tab 上的小徽标按「面板实际展示的这批条目」算，不按池子算：
    # 全部落在 EXPIRING_DAYS 天内 → 7天；只要用到 8～30 天窗口补足 → 30天。
    closing_used_window = any(
        (parse_date(d["end"]) - today).days > EXPIRING_DAYS for d in closing
    )

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
    # 手机首屏只放一行：更新时间的短写法（11-19 03:20）免得挤占卡片宽度
    beijing_short = beijing_time[5:] if re.match(r"^\d{4}-\d{2}-\d{2}", beijing_time) else beijing_time
    counts = {
        "active": len(active),
        "expiring": len(closing_pool),
        "expired": len(expired),
        "total": len(deals),
    }

    en_map = load_en()
    missing_en = [d["id"] for d in deals if d["id"] not in en_map]

    def render_page(lang: str) -> str:
        """整页渲染：先定语言，rail / 热榜 / 分区 / 搜索索引 / head 全部只出这一页的语言。"""
        set_lang(lang)
        is_en = lang == "en"

        rail = "".join(
            f'<a href="#{anchor}" data-target="{anchor}" {al(U[key][0], U[key][1])}>{icon(icon_key)}'
            f"<span>{ui(key)}</span></a>"
            for anchor, key, icon_key in NAV
        )
        rail += (
            '<div class="rail-sep" aria-hidden="true"></div>'
            f'<a class="rail-top" href="#top" {al("回到顶部", "Back to top")}>{icon("rocket")}'
            f"<span>{ui('nav_top')}</span></a>"
        )
        board = {
            "fresh": module_html(
                "fresh", "today", U["mod_fresh"], upair("mod_fresh_desc", h=TODAY_WINDOW_DAYS * 24),
                fresh, en_map, today, jump=True, strip=True,
            ),
            "rank": module_html(
                "rank", "rank", U["mod_rank"], U["mod_rank_desc"],
                leaderboard, en_map, today, ranked=True, jump=True, strip=True, hidden=True,
            ),
            "closing": module_html(
                "closing", "clock", U["mod_closing"],
                upair("closing_info", d=EXPIRING_DAYS, w=CLOSING_WINDOW_DAYS, n=CLOSING_SLOTS),
                closing, en_map, today, jump=True, strip=True,
            ),
            "lottery": module_html(
                "lottery", "gift", U["mod_lottery"], U["mod_lottery_desc"],
                lottery, en_map, today, ranked=True, jump=True, strip=True, hidden=True,
            ),
        }

        tab_counts = {
            "fresh": len(fresh),
            "rank": len(leaderboard),
            "closing": len(closing),
            "lottery": len(lottery),
        }

        def hot_tab(anchor: str, key: str, on: bool) -> str:
            cls = "hot-tab on" if on else "hot-tab"
            cur = ' aria-current="true"' if on else ""
            return (
                f'<a class="{cls}" href="#{anchor}" data-tab="{anchor}"{cur}>'
                f'{ui(key)} <b data-tabcount="{anchor}">{tab_counts[anchor]}</b></a>'
            )

        # 「即将截止」tab：标签 + 动态小徽标 + 一个小巧的 ⓘ。
        # 徽标只说明「当前这批条目落在哪个窗口」，构建期按实际展示的条目算：
        #   全部在 EXPIRING_DAYS 天内 → 「7天 / 7d」；用到 8～30 天窗口补足 → 「30天 / 30d」。
        # 徽标本身不是交互元素，留在 <a> 里（点了就是切 tab）；ⓘ 是独立 <button>
        # ——<a> 里不能嵌按钮，否则键盘 / 读屏都会把它当成链接的一部分。
        badge_html = (
            '<span class="closing-badge">'
            + ui(
                "closing_badge_w" if closing_used_window else "closing_badge_d",
                d=EXPIRING_DAYS,
                w=CLOSING_WINDOW_DAYS,
            )
            + "</span>"
        )
        info_btn = (
            '<button class="closing-info" type="button" aria-expanded="false" '
            'aria-controls="closing-toast" '
            f'{al(*U["closing_info_aria"])}>{icon("info")}</button>'
        )

        def closing_tab(key: str, on: bool) -> str:
            cls = "hot-tab on" if on else "hot-tab"
            cur = ' aria-current="true"' if on else ""
            return (
                '<span class="hot-tab-unit">'
                f'<a class="{cls}" href="#closing" data-tab="closing"{cur}>'
                f'{ui(key)} <b data-tabcount="closing">{tab_counts["closing"]}</b>{badge_html}</a>'
                f'{info_btn}</span>'
            )

        hot_board = f"""
      <div class="hot-board" data-hot-board>
        <div class="hot-tabs-mobile" role="group" {al(*U['hot_aria'])}>
          {hot_tab('fresh', 'tab_fresh', True)}
          {hot_tab('rank', 'tab_rank', False)}
          {closing_tab('tab_closing', False)}
          {hot_tab('lottery', 'tab_lottery', False)}
        </div>
        <div class="hot-panel hot-panel-main">
          <div class="hot-tablist">
            {hot_tab('fresh', 'tab_fresh_long', True)}
            {hot_tab('rank', 'tab_rank_long', False)}
          </div>
          <div class="hot-panel-body" data-panel-body>
            {board["fresh"]}
            {board["rank"]}
          </div>
        </div>
        <div class="hot-panel hot-panel-alt">
          <div class="hot-tablist">
            {closing_tab('tab_closing_long', True)}
            {hot_tab('lottery', 'tab_lottery_long', False)}
          </div>
          <div class="hot-panel-body" data-panel-body>
            {board["closing"]}
            {board["lottery"]}
          </div>
        </div>
      </div>"""

        modules = "".join(
            [
                module_html("ai", "ai", U["mod_ai"], U["mod_ai_desc"], by_cat["ai"], en_map, today),
                module_html("crypto", "crypto", U["mod_crypto"], U["mod_crypto_desc"], by_cat["crypto"], en_map, today),
                module_html("bank", "bank", U["mod_bank"], U["mod_bank_desc"], by_cat["bank"], en_map, today),
                module_html("cloud", "cloud", U["mod_cloud"], U["mod_cloud_desc"], by_cat["cloud"], en_map, today),
                module_html("esim", "esim", U["mod_esim"], U["mod_esim_desc"], by_cat["esim"], en_map, today),
                module_html("software", "software", U["mod_software"], U["mod_software_desc"], by_cat["software"], en_map, today),
                module_html(
                    "archive", "archive", U["mod_archive"], U["mod_archive_desc"],
                    sorted(expired, key=lambda d: d.get("end") or "", reverse=True), en_map, today,
                ),
            ]
        )

        # 搜索索引：每张卡只留 data-key，搜索文本统一放在这段 JSON 里（只存当前页面的语言）
        search_map: dict[str, str] = {}
        for deal in deals:
            cat_meta = CAT_META.get(deal.get("category", ""), {"label": "", "search": ""})
            cat_en = CAT_EN.get(deal.get("category", ""), ("", ""))
            en = en_map.get(deal["id"], {})
            if is_en:
                haystack = " ".join(
                    [
                        en.get("title", ""),
                        en.get("highlight", ""),
                        en.get("regions", ""),
                        deal.get("brand", ""),
                        COST_EN.get(deal.get("cost", ""), ""),
                        cat_en[0],
                        cat_en[1],
                    ]
                )
            else:
                haystack = " ".join(
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
            search_map[deal["id"]] = re.sub(r"\s+", " ", haystack).strip()
        search_json = json.dumps(search_map, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


        title = EN_TITLE if is_en else "羊毛情报局 · 全球优惠 / 免费额度 / 限时活动情报"
        desc = EN_DESC if is_en else ZH_DESC
        og_title = "Deal Hunter · Global deals & free credits" if is_en else "羊毛情报局 · 全球优惠与免费额度情报"
        og_desc = EN_OG_DESC if is_en else "每日核验的全球优惠导航：AI、Crypto、海外银行与汇款、云服务、eSIM、软件学生福利。价值、门槛、截止时间一眼看清，直达官方链接。"
        site_name = "Deal Hunter" if is_en else "羊毛情报局"
        home = "/en/" if is_en else "/"
        canonical = SITE_URL + ("en/" if is_en else "")

        item_list = []
        for i, deal in enumerate(leaderboard, start=1):
            en = en_map.get(deal["id"], {})
            name = (en.get("title") or deal.get("title", "")) if is_en else deal.get("title", "")
            desc_text = (
                (en.get("highlight") or deal.get("highlight") or "") if is_en
                else (deal.get("highlight") or "")
            )
            item = {"@type": "ListItem", "position": i, "name": name}
            url = official_link(deal)
            if url:
                item["url"] = url
            if desc_text:
                item["description"] = desc_text
            item_list.append(item)

        jsonld = json.dumps(
            [
                {
                    "@context": "https://schema.org",
                    "@type": "WebSite",
                    "name": site_name,
                    "alternateName": "Deal Hunter · global deals" if is_en else "羊毛情报局 · 全球优惠情报",
                    "url": canonical,
                    "inLanguage": "en" if is_en else "zh-CN",
                    "description": desc,
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": canonical + "?q={search_term_string}",
                        "query-input": "required name=search_term_string",
                    },
                },
                {
                    "@context": "https://schema.org",
                    "@type": "ItemList",
                    "name": "Top value deals" if is_en else "高价值优惠排行榜",
                    "itemListElement": item_list,
                },
            ],
            ensure_ascii=False,
            indent=2,
        ).replace("</", "<\\/")   # 防止数据里的 </script> 提前结束 JSON-LD 块

        def pht(key: str) -> str:
            """placeholder 只能是一个字符串：按当前页面语言取。"""
            return e(U[key][1] if is_en else U[key][0])

        # 分享图：英文页用英文封面，中文页用中文封面
        og_image = OG_IMAGE_EN if is_en else OG_IMAGE
        og_locale = "en_US" if is_en else "zh_CN"
        og_locale_alt = "zh_CN" if is_en else "en_US"
        # 语言切换链接：带上 hreflang / lang，让读屏与搜索引擎知道目标页语言
        switch_href = "/" if is_en else "/en/"
        switch_hreflang = "zh-CN" if is_en else "en"

        head = f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'zh-CN'}" data-lang="{'en' if is_en else 'zh'}" data-today="{today.isoformat()}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
{LANG_BOOT}
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="author" content="{site_name}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#FAF7F2">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="zh-CN" href="{SITE_URL}">
<link rel="alternate" hreflang="en" href="{SITE_URL}en/">
<link rel="alternate" hreflang="x-default" href="{SITE_URL}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:locale:alternate" content="{og_locale_alt}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{site_name} · {'verified global deals' if is_en else '每日核验的全球优惠情报'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
<meta name="twitter:image" content="{og_image}">

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/assets/favicon-48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/style.css?v={asset_ver('assets/css/style.css')}">

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
    <a class="brand" href="{home}" {al(*U['brand_aria'])}>
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='mintBodyHead')}
      </span>
      <span class="brand-text">
        <span class="brand-name">{ui('brand')}</span>
        <span class="brand-sub">{ui('brand_sub')}</span>
      </span>
    </a>
    <button class="search-btn" id="open-search" type="button" aria-haspopup="dialog"
            {al(*U['search_open_aria'])}>
      <span class="sb-q">
        {icon('search')}
        <span class="sb-text">{ui('search_open')}</span>
      </span>
      <kbd>⌘K</kbd>
    </button>
    <div class="topbar-stats">
      <a class="stats-pill mint" href="#ai">{ui('stat_active')} <b>{counts['active']}</b></a>
      <a class="stats-pill amber" href="#closing">{ui('stat_expiring')} <b>{counts['expiring']}</b></a>
      <a class="stats-pill stone" href="#archive">{ui('stat_archived')} <b>{counts['expired']}</b></a>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell">
    <section class="hero">
      <h1>{ui('hero_h1')}</h1>
      <p class="hero-tag">{ui('hero_tag')}</p>
      <p class="hero-meta"><span class="dot" aria-hidden="true"></span><span class="hm-long">{ui('updated', t=e(beijing_time))}</span><span class="hm-short">{ui('updated_short', t=e(beijing_short))}</span></p>
    </section>

    <div class="ad-slot" data-ad="top" aria-hidden="true"><!-- AdSense：顶部 / 桌面横幅 --></div>
  </div>

  <div class="shell">{hot_board}{modules}</div>

  <div class="shell">
    <div class="ad-slot" data-ad="bottom" aria-hidden="true"><!-- AdSense：底部 --></div>
  </div>
</main>

<div class="rail-dock">
  <a class="rail-submit" id="open-submit" href="{TG_GROUP_URL}" target="_blank" rel="noopener"
     {al(*U['nav_submit_aria'])}>
    {icon('send')}
    <span>{ui('nav_submit')}</span>
  </a>
  <nav class="rail" {al(*U['nav_aria'])}>
  {rail}
  </nav>
</div>

<!-- 语言徽标：lang 只挂在内部可见文字的 <span> 上，<a> 本身不声明 lang，
     否则读屏会把整条链接按目标语言念（例如中文页把「EN」念成英文单词）。 -->
<a class="lang-switch" id="lang-switch" href="{switch_href}" hreflang="{switch_hreflang}" {al(*U['lang_switch_aria'])}><span lang="{switch_hreflang}">{ui('lang_switch')}</span></a>

<!-- 「即将截止」口径吐司：tab 上的 ⓘ 点开显示，3.5 秒自动消失，点空白 / 再点一次也关。
     固定定位 + JS 量位置，不占文档流，手机 375px 下也不会挤出横向滚动条。 -->
<div class="closing-toast" id="closing-toast" role="status" aria-live="polite" hidden>{ui('closing_info', d=EXPIRING_DAYS, n=CLOSING_SLOTS, w=CLOSING_WINDOW_DAYS)}</div>

<div class="modal" id="search-modal" role="dialog" aria-modal="true" aria-hidden="true"
     {al(*U['modal_aria'])}>
  <div class="modal-bg" data-close></div>
  <div class="sheet">
    <div class="sheet-top">
      <h2>{ui('modal_title')}</h2>
      <button class="sheet-close" type="button" data-close {al('关闭', 'Close')}>✕</button>
    </div>
    <div class="input-wrap">
      {icon('search')}
      <input id="q" type="search" {al(*U['search_field_aria'])} placeholder="{pht('search_ph')}" autocomplete="off" spellcheck="false">
    </div>

    <div class="filter-row">
      <div class="filter-label">{ui('f_time')}</div>
      <div class="chips" data-group="time">
        <button class="chip on" type="button" data-value="all">{ui('time_all')}</button>
        <button class="chip" type="button" data-value="24h">{ui('time_24h')}</button>
        <button class="chip" type="button" data-value="48h">{ui('time_48h')}</button>
        <button class="chip" type="button" data-value="7d">{ui('time_7d')}</button>
        <button class="chip" type="button" data-value="past">{ui('time_past')}</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">{ui('f_sort')}</div>
      <div class="chips" data-group="sort">
        <button class="chip on" type="button" data-value="value">{ui('sort_value')}</button>
        <button class="chip" type="button" data-value="new">{ui('sort_new')}</button>
        <button class="chip" type="button" data-value="end">{ui('sort_end')}</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">{ui('f_cat')}</div>
      <div class="chips" data-group="cat">
        <button class="chip on" type="button" data-value="all">{ui('all')}</button>
        <button class="chip" type="button" data-value="ai">{ui('cat_ai')}</button>
        <button class="chip" type="button" data-value="crypto">{ui('cat_crypto')}</button>
        <button class="chip" type="button" data-value="bank">{ui('cat_bank')}</button>
        <button class="chip" type="button" data-value="cloud">{ui('cat_cloud')}</button>
        <button class="chip" type="button" data-value="esim">{ui('cat_esim')}</button>
        <button class="chip" type="button" data-value="software">{ui('cat_software')}</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">{ui('f_cost')}</div>
      <div class="chips" data-group="cost">
        <button class="chip on" type="button" data-value="all">{ui('all')}</button>
        <button class="chip" type="button" data-value="真正免费">{bi('真正免费', 'Free')}</button>
        <button class="chip" type="button" data-value="免费试用">{bi('免费试用', 'Free trial')}</button>
        <button class="chip" type="button" data-value="需要充值">{bi('需要充值', 'Deposit')}</button>
        <button class="chip" type="button" data-value="需要交易量">{bi('需要交易量', 'Volume')}</button>
        <button class="chip" type="button" data-value="需要邀请条件">{bi('需要邀请条件', 'Referral')}</button>
      </div>
    </div>

    <div class="filter-row">
      <div class="filter-label">{ui('f_verify')}</div>
      <div class="chips" data-group="verify">
        <button class="chip on" type="button" data-value="all">{ui('all')}</button>
        <button class="chip" type="button" data-value="1">{bi('已核验', 'Verified')}</button>
        <button class="chip" type="button" data-value="0">{bi('待核实', 'Unverified')}</button>
      </div>
    </div>

    <div class="sheet-foot">
      <span class="result-count">{'<b data-result>0</b> matching' if is_en else '匹配 <b data-result>0</b> 条'}</span>
      <span class="grow"></span>
      <button class="link-btn" type="button" data-reset>{ui('reset')}</button>
      <button class="solid-btn" type="button" data-close>{ui('done')}</button>
    </div>
  </div>
</div>

<dialog class="submit-dialog" id="submit-dialog" data-endpoint="{SUBMIT_ENDPOINT}"
        tabindex="-1"
        aria-labelledby="submit-title"
        data-msg-name="{e(U['submit_need_name'][1] if is_en else U['submit_need_name'][0])}"
        data-msg-link="{e(U['submit_need_link'][1] if is_en else U['submit_need_link'][0])}"
        data-msg-failed="{e(U['submit_failed'][1] if is_en else U['submit_failed'][0])}"
        data-msg-wait="{e(U['submit_wait'][1] if is_en else U['submit_wait'][0])}">
  <!-- 故意不用 <form>：安卓 Chrome 的 Autofill 启发式会忽略 autocomplete="off"，只要看到 <form>
       加带 name / region 之类关键词的输入框，就在键盘上方弹出钥匙 / 银行卡 / 地址填充条。
       这里用 <div> 承载，发送由 app.js 的按钮点击 + Enter 键驱动，校验 / 冷却 / 蜜罐逻辑一模一样。 -->
  <div class="sd-form" id="submit-form" role="group"
       aria-labelledby="submit-title"
       autocomplete="nope" autocorrect="off" autocapitalize="off"
       data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other">
    <!-- 蜜罐：机器人才会填的陷阱字段。视觉上移出屏幕（不是 display:none，否则部分脚本会跳过），
         读屏与 Tab 键都碰不到；一旦有值，app.js 静默丢弃这次提交，不发请求。 -->
    <div class="sd-hp" aria-hidden="true">
      <!-- 不设 name 属性（没有 <form> 可提交，JS 直接读 .value）；也不用 website / email 这类名字，
           免得密码管理器把蜜罐填上、把真人误判成机器人。 -->
      <!-- 用 textarea 而不是 input type="text"：<dialog>.showModal() 打开时 Chrome 会扫到弹窗里
           唯一的文本 input 并聚焦它，于是键盘上方闪出 🔑💳📍 填充辅助栏；换成 textarea 就不会。 -->
      <textarea id="sd-hp" rows="1" tabindex="-1" autocomplete="off" spellcheck="false"
                data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other"></textarea>
    </div>
    <div class="sd-top">
      <button class="sd-back" type="button" data-submit-close
              {al(*U['close'])}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12h-15"/><path d="m11.5 19-7-7 7-7"/></svg>
      </button>
      <span class="sd-avatar" aria-hidden="true">{mascot_svg(gid='mintBodySubmit')}</span>
      <h2 id="submit-title">{ui('submit_title')}</h2>
      <a class="sd-tg" href="{TG_GROUP_URL}" target="_blank" rel="noopener"
         {al(*U['submit_tg_aria'])}>
        <svg class="sd-tg-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm4.62 7.06-1.53 7.2c-.11.51-.42.63-.85.39l-2.34-1.73-1.13 1.09c-.13.13-.24.24-.48.24l.17-2.4 4.38-3.95c.19-.17-.04-.27-.29-.1l-5.41 3.41-2.33-.73c-.5-.16-.51-.5.11-.74l9.11-3.51c.42-.15.79.1.65.83Z" fill="currentColor"/></svg>
        <span>{ui('submit_tg')}</span>
      </a>
      <button class="sd-send" type="button"
              {al(*U['submit_send'])}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.4 11.1 20.2 4.2c.8-.3 1.6.5 1.3 1.3l-6.9 16.8c-.3.8-1.5.8-1.9 0l-1.9-5.2-5.2-1.9c-.8-.4-.8-1.6 0-1.9Z" fill="currentColor"/>
          <path d="M10.8 13.2 20 5.1" stroke="#FFFFFF" stroke-width="1.5" stroke-linecap="round" opacity=".9"/>
        </svg>
      </button>
    </div>

    <!-- 单行字段一律用 <textarea rows="1"> 而不是 input type="text"：真机实测（安卓 Chrome）只有 textarea
         不弹键盘上方那条 🔑💳📍 填充辅助栏——它不看 autocomplete / name / id，只按控件类型判断，
         所以改标签是唯一稳的办法。单行外观、Enter 发送、粘贴多行折成一行由 style.css 的
         .sd-field-single 与 app.js 的 beforeinput / input 拦截负责。 -->
    <label class="sd-row">
      <span class="sd-label">{ui('submit_name')}<i class="req" aria-hidden="true">*</i></span>
      <textarea class="sd-input sd-field-single" id="sd-f1" rows="1" wrap="off" maxlength="80" autocomplete="nope" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other" enterkeyhint="send" aria-required="true"
                placeholder="{pht('submit_ph_name')}"></textarea>
    </label>
    <label class="sd-row">
      <span class="sd-label">{ui('submit_link')}<i class="req" aria-hidden="true">*</i></span>
      <textarea class="sd-input sd-field-single" id="sd-f2" rows="1" wrap="off" maxlength="500" autocomplete="nope" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other" enterkeyhint="send" aria-required="true"
                placeholder="{pht('submit_ph_link')}"></textarea>
    </label>
    <label class="sd-row">
      <span class="sd-label">{ui('submit_region')}</span>
      <textarea class="sd-input sd-field-single" id="sd-f3" rows="1" wrap="off" maxlength="60" autocomplete="nope" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other" enterkeyhint="send"
                placeholder="{pht('submit_ph_region')}"></textarea>
    </label>
    <label class="sd-notes">
      <textarea class="sd-textarea" id="sd-f4" rows="3" maxlength="800" autocomplete="nope" autocorrect="off" autocapitalize="off" data-lpignore="true" data-1p-ignore data-bwignore data-form-type="other"
                {al('亮点与门槛说明', 'Highlights and requirements')}
                placeholder="{pht('submit_ph_notes')}"></textarea>
    </label>
    <p class="sd-err" id="sd-err" role="alert" hidden></p>
  </div>

  <div class="sd-done" id="sd-done" hidden>
    <span class="sd-done-mark" aria-hidden="true">
      <svg viewBox="0 0 48 48">
        <defs>
          <linearGradient id="sdDoneGrad" x1="0" y1="0" x2="0.5" y2="1">
            <stop offset="0" stop-color="#34D399"/><stop offset="1" stop-color="#16A34A"/>
          </linearGradient>
        </defs>
        <circle cx="24" cy="24" r="22" fill="url(#sdDoneGrad)"/>
        <path d="m14.4 24.6 6.6 6.6 12.6-13.2" fill="none" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </span>
    <p class="sd-done-t">{ui('submit_success')}</p>
    <div class="sd-actions">
      <button class="sd-btn sd-btn-ghost" type="button" data-submit-close>{ui('close')}</button>
      <button class="sd-btn sd-btn-mint" type="button" data-submit-again>{ui('submit_again')}</button>
    </div>
  </div>
</dialog>

<footer>
  <div class="shell foot-line">
    <span class="foot-brand">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='mintBodyFoot')}
      </span>
      {ui('foot_brand', y=today.year)}
    </span>
    <span class="foot-up">{ui('foot_updated', t=e(last_updated))}</span>
    <a class="foot-top" href="#top">{ui('foot_top')}</a>
  </div>
</footer>

<script id="search-index" type="application/json">{search_json}</script>
<script src="/assets/js/app.js?v={asset_ver('assets/js/app.js')}" defer></script>
</body>
</html>
"""
        return compact_html(head)

    OUT.write_text(render_page("zh"), encoding="utf-8")
    EN_OUT.parent.mkdir(parents=True, exist_ok=True)
    EN_OUT.write_text(render_page("en"), encoding="utf-8")
    print(f"index.html + en/index.html written · {len(active)} active / {len(expired)} expired / {len(fresh)} fresh")
    print(f"  英文条目：{len(deals) - len(missing_en)}/{len(deals)} 条有翻译")
    if missing_en:
        print(f"  ! 缺少英文翻译 {len(missing_en)} 条：{', '.join(missing_en[:12])}{' …' if len(missing_en) > 12 else ''}")
    src_hits = [d for d in deals if main_link(d) != official_link(d)]
    print(f"  原文链接：{len(src_hits)} 条指向抓取来源原帖，{len(deals) - len(src_hits)} 条回落到官方页（source_url 或 source 里带原帖 URL 时自动切换）")
    if missing:
        print(f"  ! 图标下载失败 {len(missing)} 个（回退字母块）：{', '.join(missing)}")
    else:
        print(f"  图标：{len(deals)} 个域名全部就绪（assets/fav/）")


if __name__ == "__main__":
    main()
