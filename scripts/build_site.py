#!/usr/bin/env python3
"""羊毛情报局 — 静态页面生成器。

读取 data/deals.json 与 data/meta.json，生成纯静态 index.html
（卡片全部是真实 HTML，方便搜索引擎抓取；筛选 / 手风琴 / 折叠由 app.js 增强）。

工程要点：
  · 时区统一北京时间（见 scripts/common.py）；
  · 分类区渲染完整 12 字段卡片，每个活动只出现一次（#deal-<id>）；首页每个分类只内联
    按 S 分排序的前 24 条（再加四个聚合分区用到的条目），其余由分类目录页承接；
  · 顶部热榜板（新收录 / 高价值榜 | 即将截止 / 抽奖）与各分区用精简跳转卡，
    点一下滚到分类区那张卡片并展开，这样 index.html 不重复三遍详情；
  · 所有图标抽成一份 <svg> sprite，卡片里只剩 <use href="#i-xxx">；
  · 搜索文本放进 <script id="search-index"> JSON，不再挂在每张 DOM 上；
  · 单语渲染：`/` 只输出中文、`/en/` 只输出英文，不再内联 <span class="t-zh">/…t-en> 双份文案；
    文案仍以 (中文, English) 成对维护在 scripts/i18n.py，构建时按页面语言取一侧；
  · 图标在构建时下载成 assets/fav/<domain>.webp（48×48，透明通道），境内直连 GitHub Pages 即可显示。
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
import shutil
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from common import (  # noqa: E402
    CAT_META,
    CATEGORY_DIR,
    CATEGORY_DIR_EN,
    CLOSING_SLOTS,
    CLOSING_WINDOW_DAYS,
    DATA,
    DEALS_DIR,
    DEALS_DIR_EN,
    EXPIRING_DAYS,
    FAV_DIR,
    FRESH_PER_CATEGORY,
    FRESH_SLOTS,
    META,
    OG_IMAGE,
    OG_IMAGE_EN,
    OUT,
    SITE_URL,
    TODAY_WINDOW_DAYS,
    TZ,
    added_date,
    cat_path,
    cat_url,
    compute_status,
    deal_path,
    deal_url,
    ensure_added_at,
    now_local,
    parse_date,
    short_date,
    today_local,
    value_expected,
    write_sitemap,
)
from i18n import (  # noqa: E402
    CATEGORY_PAGE,
    ascii_punct,
    CAT_EN,
    COST_EN,
    LEGAL_LINKS,
    LEGAL_PAGES,
    LEGAL_UPDATED,
    U,
    load_en,
    short_date_en,
    upair,
)
from check_schema import check_jsonld, expected_howto  # noqa: E402
from eligibility import eligibility_entries, geo_ld  # noqa: E402

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

# Cookie 同意开关：目前全站零追踪 / 零广告脚本，首访不主动弹面板（只写进 <html
# data-consent-required="0">，用户点页脚「Cookie 设置」时才打开）。以后接入
# GA4 / AdSense 时把这里改成 "1"，consent.js 就会给未做过选择的欧洲首访者弹出面板，
# 已同意 / 已拒绝的访客不会再被重复打扰。
CONSENT_REQUIRED = "0"

# ------------------------------------------------ 首页瘦身（2026-11-21 第七轮定稿）
# 分类区只内联按 S 分排序的前 N 条，其余全部交给分类目录页 /category/<slug>/ 承接；
# 四个聚合分区（新收录 / 高价值榜 / 即将截止 / 抽奖）用到的条目另外并入对应分类，
# 保证点跳转卡一定能滚到那张卡（#deal-<id> 必须存在）。
# 验收口径：首页 gzip ≤ 250KB、DOM ≤ 1.3 万、CLS = 0。
HOME_CAT_CARDS = 24
HOME_ARCHIVE_CARDS = 24

# 搜索索引里只收导语的头一小段：整段导语占 ~30K 字、gzip 多 +20KB，而常见关键词
# （开户 / 试用 / 邀请 等）几乎都出现在前 60 个字内；截到前 N 字后「开户」「试用」
# 这类词的命中条数与全文入库时一致，页尾体积却只多 ~7KB。
SEARCH_HIGHLIGHT_CHARS = 40

# 评分解释表：构建时落到 reports/score_explain.csv，只做内部回测用，
# 不进 sitemap、不被任何页面链接，也不进仓库（.gitignore + robots.txt 双保险）。
SCORE_REPORT = ROOT / "reports" / "score_explain.csv"

# ------------------------------------------------------- 两枚 3D 质感小徽标
# 按 Jun 的参考图手绘：都靠「多层实色 + 渐变」堆出立体感，14–16px 下要的还是
# 一块完整的色块轮廓，所以线条都取整、不留发丝细节。两枚的渐变统一放在页面里
# 唯一的 <defs> 容器（见 vector_defs()），symbol 里只引用 vs- / hg- 前缀的 id。
#
# 已核验：圆润厚实的浅天蓝盾面 + 右下方一块深蓝厚边（就是把盾面整条路径平移
# 1.35/0.95 垫在后面）+ 内凹浅描边槽 + 居中纯白对勾（自带蓝调投影与上缘高光）。
_SHIELD_PATH = (
    'M5.4 3.6Q12 1.95 18.6 3.6Q20 4.25 20 5.9L20 11.9C20 16.5 16.7 19.45 12.35 21.45'
    'Q12 21.6 11.65 21.45C7.3 19.45 4 16.5 4 11.9L4 5.9Q4 4.25 5.4 3.6Z'
)
_SHIELD_INNER = (
    f'<path d="{_SHIELD_PATH}" fill="url(#vs-side)" stroke="none" transform="translate(1.35 .95)"/>'
    f'<path d="{_SHIELD_PATH}" fill="url(#vs-face)" stroke="none"/>'
    '<path d="M5.95 5.5Q12 4.05 18.05 5.5Q18.75 5.85 18.75 6.85L18.75 11.85C18.75 15.6 16.05 18.15 12 20.2'
    'C7.95 18.15 5.25 15.6 5.25 11.85L5.25 6.85Q5.25 5.85 5.95 5.5Z"'
    ' fill="none" stroke="#AAC9FF" stroke-opacity=".6" stroke-width=".6"/>'
    '<path d="M6.55 6.55Q12 5.25 17.45 6.55Q18.05 6.85 18.05 7.65L18.05 11.8C18.05 15.05 15.5 17.35 12 19.2'
    'C8.5 17.35 5.95 15.05 5.95 11.8L5.95 7.65Q5.95 6.85 6.55 6.55Z"'
    ' fill="none" stroke="#2F5AD0" stroke-opacity=".16" stroke-width=".5"/>'
    '<path d="M7.55 12.95 10.25 15.65 16.1 9.1" stroke="#2B55C6" stroke-opacity=".32" stroke-width="3.5"'
    ' fill="none" transform="translate(.28 .72)"/>'
    '<path d="M7.55 12.95 10.25 15.65 16.1 9.1" stroke="#FFFFFF" stroke-width="2.6" fill="none"/>'
    '<path d="M7.55 12.95 10.1 15.4 15.95 8.9" stroke="#FFFFFF" stroke-opacity=".5" stroke-width=".95"'
    ' fill="none" transform="translate(-.3 -.32)"/>'
)

# 截止徽标：整体顺时针倾斜 12° 的暖橘木框沙漏——上下两块陶土橙圆角盘 + 两根立柱，
# 中间玻璃腔（淡蓝白、带白色高光弧），上腔未流完的沙 + 中间细沙流 + 下腔沙堆。
_HOURGLASS_INNER = (
    '<g transform="rotate(12 12 12)">'
    '<rect x="5.35" y="4.6" width="1.55" height="14.9" rx=".78" fill="url(#hg-wood-dark)" stroke="none"/>'
    '<rect x="17.1" y="4.6" width="1.6" height="14.9" rx=".8" fill="url(#hg-wood-dark)" stroke="none"/>'
    '<path d="M8.15 5.35 15.85 5.35 15.85 6.55C15.85 8.85 14.45 10.1 13.05 11.35L12.75 11.62 12.75 12.4'
    ' 13.05 12.65C14.45 13.9 15.85 15.15 15.85 17.45L15.85 18.65 8.15 18.65 8.15 17.45'
    'C8.15 15.15 9.55 13.9 10.95 12.65L11.25 12.4 11.25 11.62 10.95 11.35'
    'C9.55 10.1 8.15 8.85 8.15 6.55Z" fill="url(#hg-glass)" stroke="#FFFFFF" stroke-opacity=".9" stroke-width=".5"/>'
    '<path d="M11.55 11.3h.9v2.75h-.9Z" fill="url(#hg-sand)" stroke="none"/>'
    '<path d="M8.45 6.9 15.55 6.9C15.45 9 14.05 10.05 12.75 11.1 12.35 11.4 12.05 11.5 12 11.75'
    ' 11.95 11.5 11.65 11.4 11.25 11.1 9.95 10.05 8.55 9 8.45 6.9Z" fill="url(#hg-sand)" stroke="none"/>'
    '<path d="M8.35 18.55C8.45 16.35 9.85 14.85 12 14.85 14.15 14.85 15.55 16.35 15.65 18.55Z"'
    ' fill="url(#hg-sand)" stroke="none"/>'
    '<path d="M8.85 7.1C8.9 8.75 9.6 9.6 10.3 10.2" stroke="#FFFFFF" stroke-opacity=".95" stroke-width=".55"'
    ' stroke-linecap="round" fill="none"/>'
    '<path d="M8.75 18.1C8.85 16.9 9.45 16.1 10.15 15.7" stroke="#FFFFFF" stroke-opacity=".85"'
    ' stroke-width=".5" stroke-linecap="round" fill="none"/>'
    '<rect x="4.9" y="2.75" width="14.2" height="2.3" rx="1.15" fill="url(#hg-wood)" stroke="none"/>'
    '<rect x="4.9" y="18.95" width="14.2" height="2.3" rx="1.15" fill="url(#hg-wood)" stroke="none"/>'
    '<rect x="5.35" y="3.2" width="13.3" height=".62" rx=".31" fill="#FFD6B8" fill-opacity=".8" stroke="none"/>'
    '<rect x="5.35" y="19.35" width="13.3" height=".52" rx=".26" fill="#FFD6B8" fill-opacity=".4" stroke="none"/>'
    '</g>'
)

# 投稿弹窗右上角的发送徽标（Jun 发来的原始 SVG，viewBox 0 0 40 40）：
# 明黄 #FEE500 正圆 + #191919 折角纸飞机，路径原样保留。
SEND_BADGE_PATHS = (
    '<path d="M20,20m-20,0a20,20 0,1 1,40 0a20,20 0,1 1,-40 0" fill="#FEE500"/>'
    '<path d="M12.614,12.413C12.148,10.818 13.83,9.445 15.299,10.222L29.148,17.548C31.15,18.607 31.145,21.476'
    ' 29.139,22.527L15.294,29.779C13.823,30.549 12.148,29.173 12.618,27.58L14.252,22.047L14.298,21.923'
    'C14.425,21.644 14.681,21.441 14.988,21.386L21.437,20.222C21.518,20.208 21.543,20.18 21.554,20.166'
    'C21.572,20.142 21.592,20.098 21.592,20.038C21.592,19.978 21.573,19.934 21.555,19.91'
    'C21.544,19.896 21.518,19.866 21.437,19.851L14.986,18.677C14.635,18.612 14.351,18.356 14.251,18.014'
    'L12.614,12.413Z" fill="#191919"/>'
)

# 渐变定义：单独一份 0×0 的可见 svg（见 vector_defs 的 CSS 说明），
# 页面里只出现一次，symbol 复用同一个 id，220 张卡不会各带一份渐变。
VECTOR_GRADS = (
    '<linearGradient id="vs-face" x1=".18" y1="0" x2=".8" y2="1">'
    '<stop offset="0" stop-color="#8FBEFF"/><stop offset=".42" stop-color="#6399FF"/>'
    '<stop offset="1" stop-color="#4C7DF2"/></linearGradient>'
    '<linearGradient id="vs-side" x1=".05" y1=".05" x2=".6" y2="1">'
    '<stop offset="0" stop-color="#4E80F2"/><stop offset=".5" stop-color="#2E5BD6"/>'
    '<stop offset="1" stop-color="#1E45BC"/></linearGradient>'
    '<linearGradient id="hg-wood" x1="0" y1="0" x2=".35" y2="1">'
    '<stop offset="0" stop-color="#F9B181"/><stop offset=".42" stop-color="#EE8449"/>'
    '<stop offset="1" stop-color="#BF5528"/></linearGradient>'
    '<linearGradient id="hg-wood-dark" x1="0" y1="0" x2="1" y2=".25">'
    '<stop offset="0" stop-color="#F29459"/><stop offset=".5" stop-color="#D2662F"/>'
    '<stop offset="1" stop-color="#A2451D"/></linearGradient>'
    '<linearGradient id="hg-sand" x1=".2" y1="0" x2=".7" y2="1">'
    '<stop offset="0" stop-color="#FFE98C"/><stop offset=".45" stop-color="#FBC846"/>'
    '<stop offset="1" stop-color="#EFA01F"/></linearGradient>'
    '<linearGradient id="hg-glass" x1=".1" y1="0" x2=".9" y2="1">'
    '<stop offset="0" stop-color="#FFFFFF" stop-opacity=".98"/>'
    '<stop offset=".45" stop-color="#DFEBFB" stop-opacity=".92"/>'
    '<stop offset="1" stop-color="#C3D9F4" stop-opacity=".9"/></linearGradient>'
)

# ---------------------------------------------------------------- svg sprite
# (viewBox 边长, 内部图形, stroke-width)。所有图标统一 currentColor 描边，
# 有颜色的部位直接在图形上写 fill，跟以前逐处内联的效果一致。
_SYMBOLS: dict[str, tuple[int, str, float]] = {
    # 新收录：暖色火苗
    "today": (24, '<path d="M12 2.9c2.9 3.1 4.6 5.7 4.6 8.5a4.6 4.6 0 1 1-9.2 0c0-2.8 1.7-5.4 4.6-8.5Z" fill="#FDBA74"/>'
                  '<path d="M12 9.4c1.3 1.5 2 2.7 2 4a2 2 0 1 1-4 0c0-1.3.7-2.5 2-4Z" fill="#FEF3C7"/>', 1.9),
    # 发现（滑轨唯一的热榜入口）：Google Trends 风格的四色上升折线箭头——
    # 蓝 #4285F4 上升段 → 红 #EA4335 下折段 → 黄 #FBBC05 上升段 → 绿 #34A853 实心箭头。
    # 三段折线各 3.6 的粗描边、圆头圆角，17px 下每段仍是清楚的色块；颜色全走
    # --tr-1 … --tr-4 四个变量，选中态（薄荷绿实心底）整枚切成纯白，对比拉满。
    "trends": (24, '<path d="M3.3 18.4 7.7 14.0" stroke="var(--tr-1,#4285F4)" stroke-width="3.6"/>'
                   '<path d="M7.7 14.0 11.0 17.3" stroke="var(--tr-2,#EA4335)" stroke-width="3.6"/>'
                   '<path d="M11.0 17.3 17.4 10.9" stroke="var(--tr-3,#FBBC05)" stroke-width="3.6"/>'
                   '<path d="M22.0 6.5 20.58 12.16 16.34 7.92Z" fill="var(--tr-4,#34A853)" stroke="none"/>',
             1.9),
    # 榜单：奖杯
    "rank": (24, '<path d="M7.6 3.5h8.8v4.9a4.4 4.4 0 0 1-8.8 0V3.5Z" fill="#FCD34D"/>'
                 '<path d="M7.6 5.1H5.1a2.6 2.6 0 0 0 2.6 4.6"/>'
                 '<path d="M16.4 5.1h2.5a2.6 2.6 0 0 1-2.6 4.6"/>'
                 '<path d="M12 12.8v2.4"/><path d="M9.2 15.2h5.6v3.3H9.2z" fill="#FED7AA"/>'
                 '<path d="M7.8 18.5h8.4"/>', 1.9),
    # AI：AI 芯片（Jun 的原始 SVG，viewBox 512）：方芯 + 四则引脚 + 芯内「A」「I」。
    # 默认 #3292FF，滑轨该格选中（薄荷绿实心胶囊）时由 CSS 把 --ai-ic 换成纯白。
    "ai": (512, '<path d="M384,128L384,384L128,384L128,128L384,128ZM235.75,192L210.82,192L163.48,320L185.98,320'
                 'L194.91,294.98L251.58,294.98L260.32,320L284.17,320L235.75,192ZM324.09,192L301.69,192L301.69,320'
                 'L324.09,320L324.09,192ZM223.09,213.48L245.41,277.33L201.14,277.33L223.09,213.48ZM405.33,320L448,320'
                 'L448,362.67L405.33,362.67L405.33,320ZM149.33,405.33L192,405.33L192,448L149.33,448L149.33,405.33'
                 'ZM234.67,405.33L277.33,405.33L277.33,448L234.67,448L234.67,405.33ZM149.33,64L192,64L192,106.67'
                 'L149.33,106.67L149.33,64ZM320,405.33L362.67,405.33L362.67,448L320,448L320,405.33ZM234.67,64L277.33,64'
                 'L277.33,106.67L234.67,106.67L234.67,64ZM320,64L362.67,64L362.67,106.67L320,106.67L320,64'
                 'ZM405.33,234.67L448,234.67L448,277.33L405.33,277.33L405.33,234.67ZM64,320L106.67,320L106.67,362.67'
                 'L64,362.67L64,320ZM405.33,149.33L448,149.33L448,192L405.33,192L405.33,149.33ZM64,234.67L106.67,234.67'
                 'L106.67,277.33L64,277.33L64,234.67ZM64,149.33L106.67,149.33L106.67,192L64,192L64,149.33Z"'
                 ' fill="var(--ai-ic, #3292FF)" stroke="none"/>', 0),
    # 币：经典比特币徽标——亮橙正圆 + 微向右倾的纯白 ₿（选中态由 CSS 换成白圆绿 ₿）
    "crypto": (24, '<circle cx="12" cy="12" r="11" fill="var(--btc-bg, #F7931A)"/>'
                   '<g transform="rotate(14 12 12)" fill="var(--btc-fg, #FFFFFF)">'
                   '<rect x="9.15" y="4.4" width="2.2" height="15.2" rx="1.1"/>'
                   '<path d="M10.9 5.5h2.9a3.1 3.1 0 0 1 0 6.2h-2.9v-1.9h2.8a1.2 1.2 0 0 0 0-2.4h-2.8z"/>'
                   '<path d="M10.9 12.1h3.3a3.45 3.45 0 0 1 0 6.9h-3.3v-1.95h3.2a1.5 1.5 0 0 0 0-3h-3.2z"/>'
                   '<rect x="9.45" y="2.4" width="1.55" height="3.9" rx=".77"/>'
                   '<rect x="12.05" y="2.4" width="1.55" height="3.9" rx=".77"/>'
                   '<rect x="9.45" y="17.7" width="1.55" height="3.9" rx=".77"/>'
                   '<rect x="12.05" y="17.7" width="1.55" height="3.9" rx=".77"/>'
                   '</g>', 0),
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
    # 已核验：3D 蓝盾白勾（见文件上方 _SHIELD_INNER）
    "verified-shield": (24, _SHIELD_INNER, 1.9),
    # 截止：3D 倾斜沙漏（见文件上方 _HOURGLASS_INNER）
    "hourglass": (24, _HOURGLASS_INNER, 1.9),
    # 投稿：纸飞机 + 暖色尾迹
    "send": (24, '<path d="M20.8 3.5 3.6 10.6c-.9.4-.9 1.6 0 1.9l5.5 2 2 5.5c.4.9 1.6.9 1.9 0l7.1-17.2c.3-.8-.5-1.6-1.3-1.3Z" fill="#FDBA74"/>'
               '<path d="M9.1 14.5 20.3 4.1" stroke="#FFFFFF" stroke-opacity=".85"/>'
               '<path d="M11.2 13.9l-2.1 4.6" stroke="#C2410C" stroke-opacity=".55"/>', 1.7),
}

# 详情页专用符号：只在某条详情页真的用到时才写进那份小 sprite，
# 首页与分类页的全量 sprite 不带它们（首页 gzip 一字节不涨）。
_DP_SYMBOLS: dict[str, tuple[int, str, float]] = {
    # 可用平台：iOS 咬一口的苹果 / Android 小机器人 / Web 浏览器窗口（详情页资格行 14px 内联，
    # 零额外请求；fills 直接写死品牌色，strokes 也写死，跟旁边小字一起读得清）
    "plat-ios": (24, '<path d="M16.15 12.55c-.02-2.06 1.68-3.05 1.76-3.1-.96-1.4-2.45-1.6-2.98-1.62-1.27-.13-2.48.75-3.12.75-.64 0-1.64-.73-2.7-.71-1.39.02-2.67.81-3.38 2.05-1.44 2.5-.37 6.2 1.04 8.23.69.99 1.51 2.1 2.58 2.06 1.03-.04 1.42-.67 2.67-.67s1.6.67 2.7.65c1.11-.02 1.82-1.01 2.5-2 .79-1.14 1.11-2.24 1.13-2.3-.02-.01-2.17-.83-2.2-3.34Z" fill="#27272A" stroke="none"/>'
                     '<path d="M14.15 6.1c.55-.68.93-1.62.83-2.56-.8.03-1.77.53-2.35 1.2-.51.59-.96 1.55-.84 2.46.9.07 1.81-.45 2.36-1.1Z" fill="#27272A" stroke="none"/>', 0),
    "plat-android": (24, '<path d="M3 18.3a9 9 0 0 1 18 0Z" fill="#34A853" stroke="none"/>'
                         '<path d="M7.2 12 4.8 8.3M16.8 12 19.2 8.3" stroke="#34A853" stroke-width="2.3"/>'
                         '<circle cx="9.1" cy="14.6" r="1.35" fill="#FFFFFF" stroke="none"/>'
                         '<circle cx="14.9" cy="14.6" r="1.35" fill="#FFFFFF" stroke="none"/>', 1.9),
    "plat-web": (24, '<rect x="2.7" y="4.5" width="18.6" height="15" rx="3" stroke="#3B7DD8"/>'
                     '<path d="M3 9.2h18" stroke="#3B7DD8"/>'
                     '<circle cx="6" cy="6.85" r="1.3" fill="#3B7DD8" stroke="none"/>'
                     '<circle cx="9.3" cy="6.85" r="1.3" fill="#3B7DD8" stroke="none"/>', 1.9),
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


def sprite_svg(keys: tuple[str, ...] | None = None) -> str:
    """整页共用的一份图标 sprite：<symbol> 定义一次，各处 <use> 引用。

    keys 只为详情页准备：那 440 个独立页每种图标只用得到几个，
    只带需要的 symbol 能把每页体积压到一半。
    """
    parts = [
        '<svg class="sprite" style="display:none" aria-hidden="true" focusable="false">',
    ]
    items = (
        list(_SYMBOLS.items())
        if keys is None
        else [(k, _SYMBOLS.get(k) or _DP_SYMBOLS[k]) for k in dict.fromkeys(keys) if k in _SYMBOLS or k in _DP_SYMBOLS]
    )
    for key, (size, inner, sw) in items:
        parts.append(
            f'<symbol id="i-{key}" viewBox="0 0 {size} {size}" fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{inner}</symbol>'
        )
    parts.append("</svg>")
    return "".join(parts)


def icon(key: str, cls: str = "") -> str:
    return f'<svg class="i{" " + cls if cls else ""}" aria-hidden="true"><use href="#i-{key}"/></svg>'


def icon3d(key: str, cls: str = "") -> str:
    """3D 小徽标（蓝盾 / 沙漏）：行内排在文字前面，尺寸由 .ic3d 与各处的 class 决定。

    外层 svg 不写 viewBox / focusable：symbol 自带 viewBox，只留 class + aria-hidden，
    每处引用压到 80 字节上下（一张列表 200+ 处，省下来的都是 HTML 体积）。
    """
    return f'<svg class="ic3d{" " + cls if cls else ""}" aria-hidden="true"><use href="#i-{key}"/></svg>'


def plat_badges(items: list[tuple[str, str]]) -> str:
    """可用平台：图标 + 文字紧挨成一排的小徽标（只给 bank / esim 详情页的资格行）。

    图标走同一份 sprite 的 #i-plat-*，14×14、currentColor 以外的颜色写在 symbol 里。
    """
    return "".join(
        f'<span class="dp-plat"><svg class="dp-plat-i" aria-hidden="true">'
        f'<use href="#i-plat-{key}"/></svg>{e(text)}</span>'
        for key, text in items
    )


def vector_defs() -> str:
    """3D 蓝盾 / 3D 沙漏用到的渐变，全页只写一次。

    必须是一个「0×0 但可见」的 svg：放进 display:none 的精灵里，Chrome/Android 会让
    symbol 内的 url(#id) 失效（跟页头精灵那个坑同源）。所以用 position:absolute 压成
    0×0，既不占位也不影响 CLS。
    """
    return (
        '<svg class="vdefs" aria-hidden="true" focusable="false">'
        f"<defs>{VECTOR_GRADS}</defs></svg>"
    )


def send_badge(cls: str = "") -> str:
    """投稿弹窗发送键的明黄圆徽标（Jun 原始 SVG，viewBox 0 0 40 40）。"""
    return (
        f'<svg class="{cls}" viewBox="0 0 40 40" aria-hidden="true" focusable="false">{SEND_BADGE_PATHS}</svg>'
    )


# Telegram 纸飞机（圆底 + 折角）徽标：投稿弹窗顶栏与首屏行内的小徽标共用一份，
# 保证两处的图形完全一致；颜色走 currentColor，尺寸由各自的 class 决定。
def telegram_svg(cls: str = "") -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm4.62 7.06-1.53 7.2c-.11.51-.42.63-.85.39'
        'l-2.34-1.73-1.13 1.09c-.13.13-.24.24-.48.24l.17-2.4 4.38-3.95c.19-.17-.04-.27-.29-.1'
        'l-5.41 3.41-2.33-.73c-.5-.16-.51-.5.11-.74l9.11-3.51c.42-.15.79.1.65.83Z" fill="currentColor"/>'
        '</svg>'
    )


# 首屏行内的「Telegram 交流群」群聊徽标（Jun 发来的原始 SVG，viewBox 0 0 12 12）：
# 两个 #191919 实心圆角气泡（右下那枚带一个小尾巴，点出「群聊」），没有底色也没有
# 可见文字；语义由外层的 aria-label 与 title 承担。12×12 的图形按 1:1 缩放到
# 桌面 20px / 手机 18px，比原来那枚黑金立体徽标轻一档，跟首屏那行小字更同高。
# 原文件的 <clipPath id="clip0"> 改成页面里唯一的 `hero-tg-clip`：clipPath 的 id 是
# 全文档作用域，跟别的 SVG（Pickle 精灵、3D 蓝盾等）撞名会让其中一枚被裁没。
def hero_tg_badge() -> str:
    return (
        '<svg class="hero-tg-b" viewBox="0 0 12 12" aria-hidden="true" focusable="false">'
        '<defs><clipPath id="hero-tg-clip"><path d="M-.001 0h12v12h-12z"/></clipPath></defs>'
        '<g clip-path="url(#hero-tg-clip)" fill="#191919">'
        '<path d="M7.289 1.233C6.169 1.233 5.143 1.578 4.343 2.149C6.746 2.29 8.654 4.072 8.654 6.249'
        'C8.654 7.42 8.099 8.476 7.214 9.226C7.239 9.226 7.264 9.228 7.289 9.228C7.6 9.228 7.904 9.201'
        ' 8.198 9.15L9.852 10.213C10 10.298 10.184 10.192 10.184 10.021V8.349C11.241 7.616 11.917 6.492'
        ' 11.917 5.231C11.917 3.023 9.845 1.233 7.289 1.233Z"/>'
        '<path d="M4.035 3.063C3.808 3.063 3.586 3.084 3.37 3.118C1.651 3.389 .347 4.686 .347 6.249'
        'C.347 7.254 .886 8.15 1.728 8.734V10.066C1.728 10.09 1.733 10.111 1.741 10.13'
        'C1.743 10.135 1.744 10.139 1.746 10.143C1.756 10.162 1.767 10.179 1.781 10.193L1.783 10.194'
        'C1.797 10.207 1.814 10.218 1.832 10.226C1.835 10.228 1.84 10.229 1.844 10.231'
        'C1.863 10.238 1.883 10.243 1.903 10.243C1.91 10.243 1.917 10.241 1.923 10.24'
        'C1.932 10.239 1.94 10.239 1.948 10.237C1.961 10.234 1.974 10.228 1.987 10.221'
        'C1.988 10.22 1.99 10.22 1.992 10.219L3.31 9.372C3.544 9.413 3.787 9.434 4.035 9.434'
        'C4.957 9.434 5.798 9.14 6.444 8.657C6.542 8.584 6.636 8.507 6.724 8.425'
        'C7.343 7.856 7.724 7.091 7.724 6.249C7.724 4.49 6.072 3.063 4.035 3.063Z"/>'
        '</g></svg>'
    )


def calendar_badge(num: int, tone: str = "amber") -> str:
    """迷你日历小标：日历框里直接印数字（参考 Jun 的日历 App 图标）。

    15×16 的内联 SVG，不引额外请求；只能画在页面上，不走 <use>。
    tone="amber"（默认七天窗口）或 "mint"（这批用到了三十天窗口补足）。
    """
    ink, head = ("#B45309", "#F59E0B") if tone == "amber" else ("#047857", "#10B981")
    return (
        '<svg class="cal" viewBox="0 0 15 16" aria-hidden="true" focusable="false">'
        f'<rect x="1.1" y="2.6" width="12.8" height="12.4" rx="2.6" fill="#FFFDF9" '
        f'stroke="{ink}" stroke-width="1.2"/>'
        f'<path d="M1.1 5.2a2.6 2.6 0 0 1 2.6-2.6h7.6a2.6 2.6 0 0 1 2.6 2.6v1.1H1.1z" fill="{head}"/>'
        f'<rect x="4.1" y="1" width="1.5" height="2.9" rx=".75" fill="{ink}"/>'
        f'<rect x="9.4" y="1" width="1.5" height="2.9" rx=".75" fill="{ink}"/>'
        f'<text x="7.5" y="13.8" text-anchor="middle" font-family="Menlo, Consolas, monospace" '
        f'font-size="7" font-weight="700" fill="{ink}">{num}</text></svg>'
    )


def mascot_svg(cls: str = "", gid: str = "mintBody") -> str:
    """内联完整的小精灵：渐变、腮红、高光都在，直接画在页面上（不走 <use>）。"""
    body = _MASCOT_BODY.replace("{gid}", gid)
    return (
        f'<svg class="i{" " + cls if cls else ""}" viewBox="0 0 40 40" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0" stop-color="#B7F5DA"/><stop offset="1" stop-color="#7FE3B8"/>'
        f"</linearGradient></defs>{body}</svg>"
    )


# 右侧滑轨：新收录 / 高价值榜 / 即将截止 三块板同在页面顶部的一个聚合看板里，
# 合成一个「发现」锚点指向 .hot-board 顶部（#hot），放在原来「新收录」的位置。
NAV = [
    ("hot", "nav_hot", "trends"),
    ("ai", "nav_ai", "ai"),
    ("crypto", "nav_crypto", "crypto"),
    ("bank", "nav_bank", "bank"),
    ("cloud", "nav_cloud", "cloud"),
    ("esim", "nav_esim", "esim"),
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
    "羊毛情报局：每日核验的全球优惠情报导航。AI 工具大全、Crypto 空投与积分、海外银行·U卡·跨境汇款、"
    "全球 VPS 与云资源、全球 eSIM 指南、软件与数字服务——一屏看清价值、门槛与截止时间，点击直达官方活动页。"
)
EN_TITLE = "Deal Hunter · Verified global deals, free credits & sign-up bonuses"
EN_DESC = (
    "Deal Hunter: a directory of global offers, refreshed every 2 hours — AI tools and credits, crypto airdrops "
    "and points, overseas bank, card and remittance bonuses, VPS and cloud credits, free eSIM data and student "
    "software. Value, requirements and deadline on one card, straight to the official page."
)
EN_OG_DESC = (
    "AI tools and credits, crypto airdrops and points, bank and remittance bonuses, VPS and cloud credits, "
    "free eSIM data and student software — value, requirements and deadline at a glance."
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


def tt(zh: str, en: str) -> str:
    """原生 title 提示：纯图形徽标（没有可见文字）鼠标悬停时用同一句文案补一句说明。"""
    return f'title="{e(en if CUR_LANG == "en" else zh)}"'


def deadline_html(deal: dict, today) -> str:
    # 行内那枚 3D 沙漏只在卡片展开后才出现（CSS `.card.open .dl-hg`）：
    # 收起态的行高与行宽保持原样，首屏零增高，也不会把「剩余天数」挤到换行。
    hg = icon3d("hourglass", "hg-i dl-hg")
    end = parse_date(deal.get("end", ""))
    if not end:
        return f'<span class="deadline">{hg}{ui("ongoing")}</span>'
    if end < today:
        return f'<span class="deadline">{hg}{bi(short_date(deal["end"]) + " 结束", "Ended " + short_date_en(end))}</span>'
    # left 是「今天之后还剩几个自然日」：0 = 今天截止、1 = 明天截止。
    # 原来写成 left <= 1 会把「明天截止」也说成今天，用户会当成最后一天。
    left = (end - today).days
    if left == 0:
        return f'<span class="deadline hot">{hg}{ui("ends_today")}</span>'
    if left == 1:
        return f'<span class="deadline hot">{hg}{ui("ends_tomorrow")}</span>'
    if left <= 30:
        return (
            f'<span class="deadline hot">{hg}'
            f'{bi(f"剩 {left} 天 · {short_date(deal["end"])}", f"{left} days left · {short_date_en(end)}")}</span>'
        )
    return f'<span class="deadline">{hg}{bi(short_date(deal["end"]) + " 截止", "Ends " + short_date_en(end))}</span>'


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
        lp, rp = ("(", ")") if CUR_LANG == "en" else ("（", "）")
        new = raw[: m.start()] + lp + rest + rp + raw[m.end():]
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


# ------------------------------------------------------- 收起态价值胶囊
# 折叠卡右上角只放「一眼就知道值多少钱」：≈$ 折算值，或核心金额 + 极短单位。
# 括号里的补充说明、第二段条件全部留给展开态那个完整的「实际价值」气泡，
# 胶囊不再靠 text-overflow: ellipsis 截断成「$500 GLM-5.3 月用…」。
_EST_PREFIX_RE = re.compile(r"^[≈约]\s*\$\s*(\d[\d,]*(?:\.\d+)?)")
_BADGE_MONEY_RE = re.compile(
    r"(?:US|HK|A|C|NZ)?\$\s*\d[\d,]*(?:\.\d+)?"
    r"|[£€¥₹₩]\s*\d[\d,]*(?:\.\d+)?"
    r"|\d[\d,]*(?:\.\d+)?\s*(?:USDT|USD|HKD|AUD|CAD|EUR|GBP)"
)
# 紧跟在金额后面的型号 / 规格记号（GLM-5.3、GPT-5、H100、v2）：带着它才说得清
# 这笔额度是给哪个模型的，「$500/mo」去掉它就成了通用额度。
_MODEL_AFTER_RE = re.compile(
    r"\s*(?:of|on|for)?\s*([A-Za-z][A-Za-z0-9.\-]*)"
)
# 期间词：判定「/月」「/年」这类单位，以及它是挂在哪个金额上
_VAL_PERIOD_RE = re.compile(
    r"(月用量|年用量|每月|每年|每日|每周|每晚|/月|/年|/mo\b|/yr\b|monthly|per month|a month|per year|a year)",
    re.I,
)
_VAL_PAREN_RE = re.compile(r"[（(][^（）()]*[）)]")
# 句末逗号只认「全角，」和「后面跟空格的半角 ,」——“100,000”里的千位逗号不能当分句
_VAL_CLAUSE_RE = re.compile(r"\s*(?:[；;，]|,(?=\s)).*$")
_VAL_EDGE_RE = re.compile(r"^[\s/／·→+、]+|[\s/／·→+、]+$")
# 句子切分：中英文句末标点后切开（保留标点），给详情页描述拼句子用
_SENT_SPLIT_RE = re.compile(r"(?<=[。！？；!?;])\s*|(?<=[.])\s+")


# 英文徽标的长度预算：手机端卡片胶囊内容宽约 109px（.value 的 max-width:46% +
# 10px 等宽字体），实测 18 个字符以内完整显示，19 个字符起会被省略号截断
# （Hark 复查点名 8 条：19–23 字符）。中文页的 17 个视觉单位是老口径，保持不变。
_EN_BADGE_BUDGET = 18

# 英文长徽标的等价短写：只在超预算时才用，改完仍是完整的说法
_EN_BADGE_SHORT = (
    (r"^Free for a limited time$", "Free (limited)"),
    (r"^Unlimited for (\d+) hours?$", r"\1h unlimited"),
    (r"\bsandbox minutes\b", "sandbox min"),
    (r"\bwon Naver Pay$", "won"),
    (r"\btokens a night$", "tokens/night"),
    (r"^(\d+) fractional shares$", r"\1 free shares"),
    (r"^(\d+) hours of (.+)$", r"\1h \2"),
)


def _val_width(s: str) -> int:
    """视觉宽度：中文/全角算 2、半角算 1，用来估算胶囊放不放得下。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in s)


def value_badge(text: str, lang: str = "zh") -> str:
    """折叠卡胶囊文案：能短就短，但不留半截话。

    1. 「≈$130 · £100 返现」这类已折算的，只留 ≈$130——横向可比的那个数；
    2. 先剥掉括号补充、分句补充，短得了就原样用；
    3. 还是太长，就退到「核心金额（+ 极短单位）」，绝不输出截断的残句。
    """
    t = " ".join((text or "").split())
    if not t:
        return ""
    est = _EST_PREFIX_RE.match(t)
    if est:
        return f"≈${est.group(1)}"

    t = _tight_value(_VAL_PAREN_RE.sub("", t), lang)
    t = _VAL_CLAUSE_RE.sub("", t)
    t = _VAL_EDGE_RE.sub("", " ".join(t.split()))
    # 英文的「a month / a year」尾巴收成 /mo、/yr（中文那头由下面的「每月→/月」管）
    t = re.sub(r"\s+(?:a|per)\s+month$", "/mo", t, flags=re.I)
    t = re.sub(r"\s+(?:a|per)\s+year$", "/yr", t, flags=re.I)
    t = re.sub(r"\s+(?:a|per)\s+day$", "/day", t, flags=re.I)
    t = re.sub(r"\s+(?:a|per)\s+week$", "/wk", t, flags=re.I)
    if lang == "en":
        for pat, rep in _EN_BADGE_SHORT:
            t = re.sub(pat, rep, t, flags=re.I)
    # 手机端胶囊内容宽约 109px：中文 17 个视觉单位 / 英文 18 个字符以内不截断；
    # 中文结尾是 /月、/年 这类单位后缀时再多给 3 个视觉单位的余量
    budget = 17 if lang == "zh" else _EN_BADGE_BUDGET
    if _val_width(t) <= budget + (
        3 if lang == "zh" and re.search(r"/(?:mo|yr|day|wk|月|年|日|周|晚)$", t) else 0
    ):
        return t

    amounts = list(_BADGE_MONEY_RE.finditer(t))
    if amounts:
        def _cash(match: re.Match) -> str:
            return re.sub(r"((?:US|HK|A|C|NZ)?\$|[£€¥₹₩])\s+", r"\1", match.group(0))

        core = _cash(amounts[0])
        period = _VAL_PERIOD_RE.search(t)
        if period:
            # 期间词只属于离它最近的那个金额。原文「$40 兑换码 + 每月 $10」里 /月 是 $10 的，
            # 一律套到第一个金额上就会变成「$40/月」——金额与期间张冠李戴。
            near = [a for a in amounts if a.end() <= period.start()]
            far = [a for a in amounts if a.start() >= period.end()]
            cands = [(period.start() - near[-1].end(), near[-1])] if near else []
            cands += [(far[0].start() - period.end(), far[0])] if far else []
            owner = min(cands, key=lambda c: c[0])[1] if cands else amounts[0]
            word = period.group(1).lower()
            if "month" in word or word in ("月用量", "每月", "/月", "/mo"):
                unit = "/mo" if lang == "en" else "/月"
            elif "year" in word or word in ("年用量", "每年", "/年", "/yr"):
                unit = "/yr" if lang == "en" else "/年"
            else:
                unit = ""   # 每日 / 每周 / 每晚没有短单位，就只留金额
            if owner is not amounts[0]:
                # 一次性部分 + 持续的每月部分，两段都留着：$40 + $10/月
                return f"{core} + {_cash(owner)}{unit}"
            model = _MODEL_AFTER_RE.match(t[owner.end():])
            # 只收带数字的型号记号（GLM-5.3 / GPT-5 / H100）；「monthly」「Go」这类词不算
            if model and re.search(r"\d", model.group(1)):
                core = f"{core} {model.group(1)}"
            return f"{core}{unit}"
        return core
    # 没有金额（免费 / 流量 / 名额类）：先把开头的时间状语收成后缀
    # （「每月 100,000 次请求」→「100,000 次请求/月」），再从分隔符或介词前收住
    suffix = ""
    for pre, suf in (("每月", "/月"), ("每年", "/年"), ("每日", "/日"), ("每周", "/周"), ("每晚", "/晚")):
        if t.startswith(pre):
            t, suffix = t[len(pre):].strip(), suf
            break
    # 英文的 /mo、/night 结尾先摘下来，避免下面按「/」分段时把单位切成半截
    if lang == "en":
        m_period = re.search(r"/(mo|yr|day|wk|night)$", t)
        if m_period:
            suffix = "/" + m_period.group(1)
            t = t[: m_period.start()].strip()
    # 先在符号处分段（「4GB global + 4GB APAC」→「4GB global」），
    # 再在介词前收住（「… plus 15 GB」→ 前半句）；短句宁可整句留着，不把话说半截
    for _ in range(2):
        sym = re.split(r"\s*[/／+·]\s*", t)
        if len(sym) > 1 and sym[0].strip():
            t = sym[0].strip()
            continue
        if _val_width(t + suffix) > (budget if lang == "en" else 23):
            cut = re.split(
                r"\s+\b(?:for|on|with|plus|from|after|that|when|and|of|at|to)\b\s*", t
            )[0].strip()
            if cut and cut != t:
                t = cut
                continue
        break
    # 英文还超预算：千分位收成 K（100,000 requests → 100K requests）
    if lang == "en" and _val_width(t + suffix) > budget:
        t = re.sub(r"(\d{1,3}),000\b", r"\1K", t)
    # 加了单位仍放不下：宁可留着完整短语，也不要半截单位
    if lang == "en" and _val_width(t + suffix) > budget:
        return _VAL_EDGE_RE.sub("", t)
    # 找不到语义断点就整句留着：宁可胶囊略宽，也不输出「Unlimited for 24」这种半截话
    return _VAL_EDGE_RE.sub("", t) + suffix


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
# 标点两侧的宽松空格全部收窄：「$10 / 月」→「$10/月」、「（Go 」→「（Go」
_VAL_TIGHT_RE = re.compile(r"\s*([/／·→;；])\s*")
_VAL_PAREN_TIGHT_RE = re.compile(r"\s*([（(])\s*")
_VAL_PAREN_END_RE = re.compile(r"\s+([）)])")
# 断点：符号留在上一块末尾（「$10/」「月；」），左括号自己开一块（「（Go ……」）
_VAL_BREAK_RE = re.compile(r"(?<=[/／·→;；])|(?=[（(])")


def _tight_value(text: str, lang: str = "zh") -> str:
    """收窄价值串里符号周围的松散空格（数据里人手写的「 $40 → $1,000 」）。

    英文只在「/」「·」「→」两侧收，括号与分号保留正常英文间距
    （「on Go ($10/month); Go Plus」不能变成「Go($10/month);Go」）；
    中文连括号、分号一起收，避免中文标点前后多出一整格空白。
    """
    t = " ".join((text or "").split())
    if lang == "en":
        t = re.sub(r"\s*([/·→])\s*", r"\1", t)
        return t.replace("·", "\u2009·\u2009")  # 「≈$13 · £10」留一道细缝，不糊成一个词
    t = _VAL_TIGHT_RE.sub(r"\1", t)
    t = _VAL_PAREN_TIGHT_RE.sub(r"\1", t)
    t = _VAL_PAREN_END_RE.sub(r"\1", t)
    return t.replace("·", "\u2009·\u2009")


def value_tokens(text: str, lang: str = "zh") -> str:
    """把价值串切成小块（块之间包着分隔符）。

    手机端气泡宽度不够时要能换行，但优先只在「/」「·」「→」「；」「（」这些
    断点折行——「AUD 10」这类单个金额不会被拆成两行；英文整句说明这类长块
    仍可在词间断行，气泡不会越过卡片右边被裁掉。
    """
    t = _tight_value(text, lang)
    if not t:
        return ""
    blocks = [b for b in _VAL_BREAK_RE.split(t) if b.strip()]
    # 分隔符后面跟着的短块并回前一块：「$10/月」「$40→$1,000」不被拆开
    merged: list[str] = []
    for b in blocks:
        if merged and merged[-1][-1:] in "/／·→;；" and (
            len(b) <= 8 or len(merged[-1]) + len(b) <= 14
        ):
            merged[-1] += b
        else:
            merged.append(b)
    out = []
    for b in merged:
        # 中文块内的空格全部焊成不换行空格：中文本来就能在字间断行，
        # 不焊住会把「Go Plus 实付」和后面的金额拆到两行；
        # 英文不焊，保留词间空格正常折行，不会把一长串英文啃成一整块。
        if lang == "zh":
            b = b.replace(" ", "\u00a0")
        out.append(f'<span class="dval-t">{e(b)}</span>')
    return "".join(out)


def detail_tags(deal: dict, en: dict) -> str:
    cat = deal.get("category", "")
    cat_zh = CAT_META.get(cat, {"label": cat})["label"]
    cat_en = CAT_EN.get(cat, (cat, ""))[0]
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    cost_en = COST_EN.get(cost, cost)
    if deal.get("verified"):
        check = f'<span class="dcheck ok">{icon3d("verified-shield", "vs-i")}{ui("verified")}</span>'
    else:
        check = f'<span class="dcheck wait">{ui("unverified")}</span>'
    v_zh, v_en = value_pair(deal, en)
    # 一行紧凑标签：分类、门槛、核验状态。实际价值另起一个气泡放在下面，
    # 不再自已占三层，省掉两行上下留白。
    return (
        '<div class="detail-tags">'
        f'<span class="dtag cat">{bi(e(cat_zh), e(cat_en))}</span>'
        f'<span class="dtag tag {cost_cls}">{bi(e(cost), e(cost_en))}</span>'
        f"{check}"
        "</div>"
        f'<div class="dval"><span class="dval-k">{ui("actual_value")}</span>'
        f"<strong>{value_tokens(bi(v_zh, v_en), CUR_LANG)}</strong></div>"
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


def brand_name(deal: dict, en: dict | None = None, is_en: bool = False) -> str:
    """品牌名：英文页优先用 deals_en 里的 brand_en，别让 JSON-LD 的 seller 出现中文机构名。

    没有 brand_en 时把原文的半角 / 全角括号统一成英文写法（「Cloady（NeptoLab）」→
    「Cloady (NeptoLab)」）；中文页原样返回。
    """
    raw = str((en or {}).get("brand_en") or deal.get("brand") or "")
    if not is_en:
        return raw
    raw = str(ascii_punct(raw))
    return re.sub(r"\s*\(([^()]*)\)", r" (\1)", raw).strip()


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


def main_link_kind(deal: dict) -> tuple[str, str]:
    """卡片主按钮的去向与性质，返回 (kind, url)。

    kind = "source"：指向真正的来源原帖（source_url，或 source 里写的原帖链接），
    也包含「条目 url 本身就是第三方报道/论坛帖」的情况——那种页面点过去看到的
    是别人写的文章，不该冒充品牌官网。
    kind = "official"：确实只有官方活动页可点，按钮就老实写「官网」。
    """
    src = safe_url(deal.get("source_url"))
    if not src:
        m = _SRC_URL_RE.search(deal.get("source") or "")
        src = safe_url(m.group(0).rstrip("。.,；;") if m else "")
    official = safe_url(deal.get("url"))
    if src and official and src.rstrip("/") != official.rstrip("/"):
        return "source", src
    if not official:
        return "source", src
    host = (urllib.parse.urlparse(official).hostname or "").lower()
    dom = (deal.get("domain") or "").strip().lower()
    if dom and (host == dom or host.endswith("." + dom)):
        return "official", official
    return "source", official


def main_link(deal: dict) -> str:
    """卡片主按钮的去向：抓取来源优先，没有就回官网活动页。"""
    return main_link_kind(deal)[1]


def deal_affiliate(deal: dict) -> tuple[bool, str]:
    """推广 / 返佣条目的主链接：(是否推广条目, 实际跳转地址)。

    `aff_url` 存在时优先用它，只标了 `affiliate: true` 的条目退回官方 `url`；
    两个字段都没有就返回 (False, "")，现有 236 条数据不会有任何渲染变化。
    跳转地址同样过 safe_url() 白名单，`javascript:` 这类值不会变成可点链接。
    """
    aff_url = safe_url(deal.get("aff_url"))
    if aff_url:
        return True, aff_url
    if deal.get("affiliate"):
        return True, safe_url(deal.get("url"))
    return False, ""


def link_rel(aff: bool) -> str:
    """外链 rel：推广链接按广告披露要求标 sponsored，其他链接沿用 nofollow。"""
    return "sponsored noopener noreferrer" if aff else "noopener nofollow"


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
    # 只有真原帖才写「原文」，只剩官方活动页的写「官网」，别让人以为点的是原帖。
    # 推广条目（affiliate: true 或带 aff_url）主按钮改用推广链接并在旁边挂「推广」小标，
    # rel 换成 sponsored；没有推广字段的条目完全走原逻辑。
    aff, aff_link = deal_affiliate(deal)
    if aff and aff_link:
        link_kind, link = "official", aff_link
    else:
        link_kind, link = main_link_kind(deal)
    link = safe_url(link)
    if link_kind == "official":
        go_full, go_short = ui("go_official_full"), ui("go_official_short")
        go_aria = al(*U["go_official_aria"])
    else:
        go_full, go_short = ui("go_full"), ui("go_short")
        go_aria = al(*U["go_aria"])
    if link:
        go_html = (
            f'<a class="go" href="{e(link)}" target="_blank" rel="{link_rel(aff)}"\n'
            f'             {go_aria}><span class="go-full">{go_full}</span>'
            f'<span class="go-short">{go_short}</span>{icon("external")}</a>'
        )
    else:
        go_html = f'<span class="go">{go_short}</span>'

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

    badge_zh, badge_en = value_badge(v_zh), value_badge(v_en, "en")
    badge_html = (
        f'<span class="{value_cls}">{bi(e(badge_zh), e(badge_en))}</span>'
        if (badge_zh or badge_en) else ""
    )
    aff_html = (
        f'<span class="aff-tag" {tt(*U["aff_badge_full"])}>{ui("aff_badge")}</span>'
        if aff else ""
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
          {badge_html}
        </div>
        <p class="row2"><span class="tag {cost_cls}">{bi(e(cost), e(COST_EN.get(cost, cost)))}</span>{aff_html}{bi(hl_zh, hl_en)}</p>
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
      <div class="field wide"><dt>{ui("f_regions")}</dt><dd>{bi(e(deal['regions']), e(en.get('regions') or deal['regions']))}</dd></div>
      <div class="field"><dt>{ui("f_period")}</dt><dd>{period}</dd></div>
      <div class="field"><dt>{ui("f_link")}</dt>
        <dd>{url_dd}</dd></div>
      <div class="field wide"><dt>{ui("f_steps")}</dt><dd><ol>{steps}</ol></dd></div>
      </dl>
      <div class="risk">
        {icon('warn')}
        <span>{bi(e(deal['risk']), e(en.get('risk') or deal['risk']))}</span>
      </div>
      <div class="detail-foot">
        <a class="dlink" href="/{deal_path(deal_id, CUR_LANG)}"
           {al(*upair('dp_permalink_aria', t=title_text))}>{ui("dp_permalink")} \u2197</a>
        <span>{bi(e(f"{U['f_source'][0]} · {deal['source']}"), e(f"{U['f_source'][1]} · {en.get('source') or deal['source']}"))}</span>
        <span>{bi(e(f"{U['f_last_verified'][0]} · {deal['last_verified']}"), e(f"{U['f_last_verified'][1]} · {deal['last_verified']}"))}</span>
        <span>{bi(e(f"{U['f_added'][0]} · {added_day(deal, today)}"), e(f"{U['f_added'][1]} · {added_day(deal, today)}"))}</span>
      </div>
      <div class="vote-row">{vote_bar(deal_id)}</div>
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
        <span class="jump-sub"><span class="{value_cls}">{bi(e(value_badge(v_zh)), e(value_badge(v_en, 'en')))}</span><span class="jump-meta">{bi(e(meta_zh), e(meta_en))}</span></span>
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
    cat_slug: str | None = None,
    total: int | None = None,
) -> str:
    """一个分区。cat_slug 给出时，底部渲染「查看全部 N 条 · 分类名 →」指向分类目录页。

    N 是该分类在效条目的实数（total），与本页内联的条数（deals）不是一回事：
    首页只内联前 HOME_CAT_CARDS 条，剩下的都在分类页上。
    """
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
    # 分类模块底部的「查看全部 N 条 · 分类名 →」。锚文本带分类名（头部关键词），
    # 英文页用 CAT_EN 里的新分类名，零中文。
    tail = ""
    if cat_slug:
        cat_name = (CAT_EN.get(cat_slug, (CAT_META[cat_slug]["label"], ""))[0]
                    if CUR_LANG == "en" else CAT_META[cat_slug]["label"])
        n = len(deals) if total is None else total
        more = max(0, n - len(deals))
        if more:
            # 板块全库条数超过首页内联上限（HOME_CAT_CARDS）：胶囊里先说还没展开多少条，
            # 再给去分类页的「查看全部 N 条 →」。仍是同一颗胶囊，不另加按钮、不占新行。
            tail = (
                f'<a class="see-all has-more" href="/{e(cat_path(cat_slug, CUR_LANG))}" '
                f'{al(*upair("see_all_aria", name=cat_name))}>'
                f'<b class="sa-more">{ui("see_more", m=more)}</b>'
                f'<span class="sa-sep" aria-hidden="true"> · </span>'
                f'<span class="sa-go">{ui("see_all_n", n=n)}</span></a>'
            )
        else:
            tail = (
                f'<a class="see-all" href="/{e(cat_path(cat_slug, CUR_LANG))}" '
                f'{al(*upair("see_all_aria", name=cat_name))}>'
                f'{ui("see_all", n=n, name=e(cat_name))}</a>'
            )
    elif total is not None and total > len(deals):
        # 归档区没有独立页面：超上限时只给一句说明，不造假链接
        tail = f'<p class="all-note">{ui("archive_capped", n=total, m=len(deals))}</p>'
    return f"""
  <section class="module{(' hot-strip' if strip else '')}" id="{anchor}" data-mod="{anchor}" data-per="{per_page}" data-per-lg="{per_page_lg}"{' data-kind="jump"' if jump else ''}{' hidden' if hidden else ''}>
    <header class="module-head">
      <span class="module-badge" aria-hidden="true">{icon(icon_key)}</span>
      <h2><span class="mh-t">{bi(*title)}</span> <span class="count" data-count>{count}</span></h2>
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
    {tail}
  </section>"""


def compact_html(page: str) -> str:
    """去掉每行缩进和空行：生成物小一大截，源码可读性交给生成器。"""
    page = re.sub(r"\n[ \t]+", "\n", page)
    return re.sub(r"\n{2,}", "\n", page)


# ------------------------------------------------------- 单条独立详情页 /d/<id>/
# 每条优惠一份真实静态页（中文 /d/<id>/、英文 /en/d/<id>/），给外链、搜索结果
# 与站内「详情页」入口一个不会 404 的落脚点；已过期条目也照样生成，并在页顶
# 挂一条归档提示，这样当年发出去的链接永远能打开。
CAT_ICON = {"ai": "ai", "crypto": "crypto", "bank": "bank", "cloud": "cloud", "esim": "esim", "software": "software"}
DP_FAV_JS = (
    "<script>window.__favFallback=function(i){i.style.display='none';"
    "var f=i.nextElementSibling;if(f&&f.classList.contains('fav-fallback'))f.style.display='grid';};</script>"
)

DP_ICONS = (
    "external", "archive", "chevron",
    *[v for v in CAT_ICON.values() if v],
)


def dp_deadline(deal: dict, today) -> str:
    """详情页顶部的截止说明：「12月31日 截止 · 剩 41 天」这种一句话。"""
    end = parse_date(deal.get("end", ""))
    if not end:
        return ui("ongoing")
    day = bi(short_date(deal["end"]), short_date_en(end))
    left = (end - today).days
    if left < 0:
        return ui("dp_deadline_ended", d=day)
    if left == 0:
        return ui("ends_today")
    if left == 1:
        return ui("ends_tomorrow")
    if left <= 60:
        return ui("dp_deadline_left", d=day, n=left)
    return ui("dp_deadline_only", d=day)


def dp_period(deal: dict) -> str:
    """开始 → 截止的原始日期区间（未公布时写说明文字）。"""
    start = e(deal.get("start") or ui("not_announced"))
    end = e(deal.get("end") or ui("ongoing_not_announced"))
    return f"{start} \u2192 {end}"


def dp_status(deal: dict) -> tuple[str, str]:
    """状态胶囊文案与配色：[进行中 / 即将截止 / 已结束·归档]。"""
    state = deal.get("status")
    if state == "expired":
        return ui("dp_status_expired"), "is-old"
    if state == "expiring_soon":
        return ui("dp_status_soon"), "is-soon"
    return ui("dp_status_active"), "is-live"


def render_deal_page(deal: dict, en: dict, lang: str, today, en_map: dict, related: list[dict],
                     alternatives: list[dict] | None = None) -> str:
    """一条优惠的完整独立页：头部要点 + 全部字段 + 官方/原帖入口 + 同类内链。"""
    set_lang(lang)
    is_en = lang == "en"
    deal_id = deal["id"]
    cat = deal.get("category", "")
    cat_zh = CAT_META.get(cat, {"label": cat})["label"]
    cat_plain = CAT_EN.get(cat, (cat, ""))[0] if is_en else cat_zh
    cat_label = e(cat_plain)
    cat_icon = CAT_ICON.get(cat, "software")

    def pick(key: str, default: str = "") -> str:
        if is_en:
            return en.get(key) or deal.get(key) or default
        return deal.get(key) or default

    raw_title = pick("title")
    rtag, title_text = title_parts(raw_title)
    highlight = pick("highlight")
    content = pick("content")
    conditions = pick("conditions")
    risk = pick("risk")
    regions = pick("regions")
    source = pick("source")
    steps = (en.get("steps") or deal.get("steps") or []) if is_en else (deal.get("steps") or [])

    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    cost_label = COST_EN.get(cost, cost) if is_en else cost
    v_zh, v_en = value_pair(deal, en)
    value_now = v_en if is_en else v_zh
    st_label, st_cls = dp_status(deal)
    expired = deal.get("status") == "expired"

    official = official_link(deal)
    src = safe_url(deal.get("source_url"))
    if not src:
        hit = _SRC_URL_RE.search(deal.get("source") or "")
        src = safe_url(hit.group(0).rstrip("。.,；;") if hit else "")
    if src and official and src.rstrip("/") == official.rstrip("/"):
        src = ""

    # 推广条目：主按钮走 aff_url（没有就退回官方 url），rel 换成 sponsored 并附一行小字披露；
    # 普通条目仍是官方活动页，rel 保持 noopener noreferrer。
    aff, aff_link = deal_affiliate(deal)
    main_href = aff_link if (aff and aff_link) else official
    acts = []
    if main_href:
        acts.append(
            f'<a class="dp-btn mint" href="{e(main_href)}" target="_blank" rel="{link_rel(aff)}">'
            f'{ui("dp_official")}{icon("external", "dp-ico")}</a>'
        )
    if src:
        acts.append(
            f'<a class="dp-btn ghost" href="{e(src)}" target="_blank" rel="noopener noreferrer">'
            f'{ui("dp_source_post")}{icon("external", "dp-ico")}</a>'
        )
    if not acts:
        acts.append(f'<span class="dp-btn ghost">{ui("see_official")}</span>')

    def block(title: str, body: str, cls: str = "") -> str:
        return (
            f'<section class="dp-sec{(" " + cls) if cls else ""}"><h2>{title}</h2>{body}</section>'
        )

    steps_html = "".join(f"<li>{e(s)}</li>" for s in steps) or f"<li>{e(ui('see_official'))}</li>"

    secs = []
    # 少数老条目数据里没有 highlight：这一栏就不出现（不拿正文首句顶替，避免同段文字出现两遍）
    if highlight:
        secs.append(block(ui("dp_highlight"), f'<p class="dp-lead">{e(highlight)}</p>'))
    if content:
        secs.append(block(ui("dp_content"), f'<p>{e(content)}</p>'))
    if conditions:
        secs.append(block(ui("f_conditions"), f'<p>{e(conditions)}</p>'))
    # 参与资格：Bank / eSIM 的行内资格字段渲染成 <dl>，只出非默认值；
    # 标签与取值都走 scripts/eligibility.py 的枚举表，英文页天然零 CJK。
    elig_entries = eligibility_entries(deal, is_en)
    # 平台徽标只在该页真的用到时才塞进 sprite，其余详情页一张不增
    dp_icon_keys = ("external", "archive", "chevron", "verified-shield", "hourglass", cat_icon)
    if any(badges for _, _, badges in elig_entries):
        dp_icon_keys += ("plat-ios", "plat-android", "plat-web")
    if elig_entries:
        rows_html = []
        for label, value, badges in elig_entries:
            # 可用平台：有徽标就把「图标 + 文字」紧挨排成一行，其余行仍是纯文字
            cell = f'<span class="dp-plats">{plat_badges(badges)}</span>' if badges else e(value)
            rows_html.append(f'<div class="dp-elig-row"><dt>{e(label)}</dt><dd>{cell}</dd></div>')
        elig_html = "".join(rows_html)
        secs.append(
            block(
                ui("dp_eligibility"),
                f'<dl class="dp-elig">{elig_html}</dl>',
                "is-elig",
            )
        )
    secs.append(block(ui("f_steps"), f'<ol class="dp-steps">{steps_html}</ol>'))
    if risk:
        secs.append(block(ui("dp_risk"), f'<p>{e(risk)}</p>', "is-risk"))

    # 来源 / 核验 / 收录：SEO 与“这条到底谁说的”都要的细节
    meta_bits = [
        f'<span><i>{ui("f_source")}</i>{e(source)}</span>',
        f'<span><i>{ui("f_last_verified")}</i>{e(deal.get("last_verified") or ui("unverified"))}</span>',
        f'<span><i>{ui("f_added")}</i>{e(added_day(deal, today))}</span>',
    ]
    meta_html = "".join(meta_bits)

    facts = [
        f'<li><span>{ui("dp_facts_status")}</span><b><span class="dp-st {st_cls}">{st_label}</span></b></li>',
        f'<li><span>{ui("dp_facts_deadline")}</span><b class="dp-dl">{icon3d("hourglass", "hg-i")}'
        f'{e(dp_deadline(deal, today))}</b></li>',
        f'<li><span>{ui("dp_facts_period")}</span><b>{dp_period(deal)}</b></li>',
        f'<li><span>{ui("f_regions")}</span><b>{e(regions)}</b></li>',
        f'<li><span>{ui("dp_facts_cost")}</span><b><span class="dtag {cost_cls}">{e(cost_label)}</span></b></li>',
        f'<li><span>{"KYC 门槛" if not is_en else "KYC"}</span><b class="dp-kyc">{e(kyc_fact(deal, is_en))}</b></li>',
        # 详情页的「实际价值」跟卡片用同一套收窄，符号两侧的松散空格一致
        f'<li><span>{ui("dp_facts_value")}</span><b class="dp-val">{e(_tight_value(value_now, CUR_LANG))}</b></li>',
        f'<li><span>{ui("dp_facts_check")}</span><b class="{"dp-ok" if deal.get("verified") else "dp-wait"}">'
        f'{icon3d("verified-shield", "vs-i") + ui("verified") if deal.get("verified") else ui("unverified")}</b></li>',
    ]
    if deal.get("category") == "esim" and vowifi_fact(deal, is_en):
        facts.append(
            f'<li><span>{"VoWiFi" if not is_en else "VoWiFi"}</span><b class="dp-kyc">{e(vowifi_fact(deal, is_en))}</b></li>'
        )
        facts.extend(esim_comm_facts(deal, is_en))

    # 内链：给搜索引擎更多可爬路径，也给读者一个继续逛的入口
    rel_items = []
    for rel_deal in related:
        rel_en = en_map.get(rel_deal["id"], {})
        rel_raw = (rel_en.get("title") or rel_deal.get("title", "")) if is_en else rel_deal.get("title", "")
        rel_rtag, rel_title = title_parts(rel_raw)
        rel_v = (value_pair(rel_deal, rel_en)[1] if is_en else value_pair(rel_deal, rel_en)[0])
        rel_rtag_html = f'<i>{e(rel_rtag)}</i>' if rel_rtag else ""
        rel_items.append(
            f'<li><a href="/{e(deal_path(rel_deal["id"], lang))}">'
            f'<span class="dp-rel-t">{rel_rtag_html}{e(rel_title)}</span>'
            f'<span class="dp-rel-v">{e(value_badge(rel_v, lang))}</span></a></li>'
        )
    rel_html = ""
    if rel_items:
        rel_html = (
            f'<section class="dp-more" aria-label="{e(ui("dp_related_aria"))}">'
            f'<h2>{ui("dp_more")}</h2><ul>{"".join(rel_items)}</ul></section>'
        )

    aff_badge_html = (
        f'<span class="dtag aff">{e(ui("aff_badge_full"))}</span>' if aff else ""
    )
    aff_note_html = (
        f'<p class="dp-aff-note">{icon("external", "dp-aff-i")}{e(ui("aff_note"))}</p>'
        if aff else ""
    )

    home = "/en/" if is_en else "/"
    # 面包屑 / JSON-LD / 页脚导航里的分类名都指向静态分类目录页，
    # 不再回首页锚点：目录页能接住「AI 工具有哪些免费额度」这类分类级搜索。
    cat_href = "/" + cat_path(cat, lang) if cat in CAT_META else home + "#" + cat
    other = "/d/" if is_en else "/en/d/"
    switch_href = other + deal_id + "/"
    switch_lang = "zh-CN" if is_en else "en"
    switch_aria = ui("dp_switch_aria_zh") if is_en else ui("dp_switch_aria")
    canon = deal_url(deal_id, lang)
    site_name = "Deal Hunter" if is_en else "羊毛情报局"
    seo_title = f"{title_text} · {site_name}"

    desc = seo_description(highlight, content, conditions, strip_region_bracket(regions))
    if not desc:
        desc = re.sub(r"\s+", " ", title_text).strip()

    og_image = OG_IMAGE_EN if is_en else OG_IMAGE
    og_locale = "en_US" if is_en else "zh_CN"
    og_locale_alt = "zh_CN" if is_en else "en_US"

    ld = [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "@id": canon + "#webpage",
            "url": canon,
            "name": seo_title,
            "description": desc,
            "inLanguage": "en" if is_en else "zh-CN",
            "isPartOf": {"@type": "WebSite", "name": site_name, "url": SITE_URL + ("en/" if is_en else "")},
            "breadcrumb": {"@id": canon + "#breadcrumb"},
            "mainEntity": {"@id": canon + "#offer"},
            "datePublished": added_day(deal, today),
            "dateModified": str(deal.get("last_verified") or added_day(deal, today)),
            "primaryImageOfPage": {"@type": "ImageObject", "url": og_image},
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "@id": canon + "#breadcrumb",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": ui("dp_crumb_home"),
                    "item": SITE_URL + ("en/" if is_en else ""),
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": cat_plain,
                    "item": cat_url(cat, lang) if cat in CAT_META else SITE_URL + ("en/" if is_en else "") + "#" + cat,
                },
                {"@type": "ListItem", "position": 3, "name": title_text},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "Offer",
            "@id": canon + "#offer",
            "name": title_text,
            "description": highlight or content or title_text,
            "url": official or canon,
            "category": cat_plain,
            "availability": "https://schema.org/Discontinued" if expired else "https://schema.org/InStock",
            "areaServed": strip_region_bracket(regions) or regions,
            "seller": {"@type": "Organization", "name": brand_name(deal, en, is_en) or site_name},
        },
    ]
    eligible_region, ineligible_region = geo_ld(deal)
    if eligible_region:
        ld[2]["eligibleRegion"] = eligible_region
    if ineligible_region:
        ld[2]["ineligibleRegion"] = ineligible_region
    if deal.get("end"):
        ld[2]["validThrough"] = str(deal["end"]) + "T23:59:59+08:00"
    # HowTo：只要这一条有参与步骤就额外输出一份（与 Offer 并列，不抢它的位置）。
    # step 里的 text 用同一条清洗过的步骤文案；整段 JSON 最后统一把 `</` 转成 `<\/`，
    # 所以步骤里出现 `</script>` 之类也不会提前结束 JSON-LD 块。
    howto_steps = [re.sub(r"\s+", " ", str(s)).strip() for s in steps if str(s).strip()]
    if howto_steps:
        ld.append(
            {
                "@context": "https://schema.org",
                "@type": "HowTo",
                "name": title_text,
                "description": desc,
                "inLanguage": "en" if is_en else "zh-CN",
                "mainEntityOfPage": canon,
                "step": [
                    {"@type": "HowToStep", "position": i, "text": text}
                    for i, text in enumerate(howto_steps, start=1)
                ],
            }
        )
    jsonld = json.dumps(ld, ensure_ascii=False, indent=2).replace("</", "<\\/")

    archive_html = ""
    if expired:
        end_zh, end_en = dp_end_pair(deal)
        archive_html = (
            f'<p class="dp-note is-archive">{icon("archive", "dp-ico")}'
            f'<span>{ui("dp_archived", d=bi(end_zh, end_en))}</span></p>'
        )

    alt_html = ""
    if expired and alternatives:
        alt_items = []
        for alt in alternatives:
            alt_en = en_map.get(alt["id"], {})
            a_raw = (alt_en.get("title") or alt.get("title", "")) if is_en else alt.get("title", "")
            a_rtag, a_title = title_parts(a_raw)
            a_val = value_pair(alt, alt_en)[1 if is_en else 0]
            a_dl = short_deadline(alt, today)[1 if is_en else 0]
            a_tag = f'<i>{e(a_rtag)}</i>' if a_rtag else ""
            alt_items.append(
                f'<li><a class="dp-alt-card" href="/{e(deal_path(alt["id"], lang))}">'
                f'<span class="dp-alt-t">{a_tag}{e(a_title)}</span>'
                f'<span class="dp-alt-m"><span class="dp-alt-v">{e(value_badge(a_val, lang))}</span>'
                f'<span class="dp-alt-d">{e(a_dl)}</span></span></a></li>'
            )
        alt_html = (
            f'<section class="dp-alt" aria-label="{e(ui("alt_aria"))}">'
            f'<p class="dp-alt-head">{icon("archive", "dp-alt-i")}<span>{ui("alt_head")}</span></p>'
            f'<ul class="dp-alt-list">{"".join(alt_items)}</ul>'
            f'<a class="dp-alt-more" href="{cat_href}">{ui("cat_open")}{icon("chevron", "dp-alt-arr")}</a>'
            f"</section>"
        )

    title_tag = f'<span class="rtag">{e(rtag)}</span>' if rtag else ""

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'zh-CN'}" data-lang="{'en' if is_en else 'zh'}" data-today="{today.isoformat()}" data-consent-required="{CONSENT_REQUIRED}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<title>{e(seo_title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="author" content="{site_name}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#FAF7F2">
<link rel="canonical" href="{canon}">
<link rel="alternate" hreflang="zh-CN" href="{deal_url(deal_id, 'zh')}">
<link rel="alternate" hreflang="en" href="{deal_url(deal_id, 'en')}">
<link rel="alternate" hreflang="x-default" href="{deal_url(deal_id, 'zh')}">

<meta property="og:type" content="article">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:locale:alternate" content="{og_locale_alt}">
<meta property="og:title" content="{e(seo_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(seo_title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(seo_title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{og_image}">

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/assets/favicon-48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/style.css?v={asset_ver('assets/css/style.css')}">
<meta name="dh-votes-base" content="{SUBMIT_ENDPOINT}">

<script type="application/ld+json">
{jsonld}
</script>
</head>
<body class="dp">

{sprite_svg(dp_icon_keys)}
{vector_defs()}

<header class="topbar">
  <div class="shell topbar-in">
    <a class="brand" href="{home}" {al(*U['brand_aria'])}>
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpMintHead')}
      </span>
      <span class="brand-text">
        <span class="brand-name">{ui('brand')}</span>
        <span class="brand-sub">{ui('brand_sub')}</span>
      </span>
    </a>
    <div class="dp-top">
      <a class="dp-back" href="{home}">{icon('chevron', 'dp-back-i')}<span>{ui('dp_back')}</span></a>
      <a class="dp-switch" href="{switch_href}" hreflang="{switch_lang}" {al(switch_aria, switch_aria)}><span lang="{switch_lang}">{ui('dp_switch')}</span></a>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell dp-wrap">
    <nav class="dp-crumbs" {al(*U['dp_crumb_aria'])}>
      <a href="{home}">{ui('dp_crumb_home')}</a>
      <span class="dp-sep" aria-hidden="true">/</span>
      <a href="{cat_href}">{cat_label}</a>
      <span class="dp-sep" aria-hidden="true">/</span>
      <span class="dp-cur">{e(title_text)}</span>
    </nav>

    {archive_html}

    <article class="dp-card">
      <div class="dp-head">
        {fav_html(deal, 44, en)}
        <div class="dp-hgroup">
          <h1 class="dp-title">{title_tag} {e(title_text)}</h1>
          <div class="dp-badges">
            <span class="dtag cat">{icon(cat_icon, 'dp-cat-i')}{cat_label}</span>
            <span class="dp-st {st_cls}">{st_label}</span>
            {aff_badge_html}
          </div>
        </div>
      </div>

      <ul class="dp-facts">
        {''.join(facts)}
      </ul>

      <div class="dp-actions">
        {''.join(acts)}
        {aff_note_html}
      </div>

      <div class="dp-vote">{vote_bar(deal_id)}</div>
    </article>

    {alt_html}

    {''.join(secs)}

    <section class="dp-sec dp-meta-sec">
      <h2>{ui('dp_source_block')}</h2>
      <p class="dp-meta">{meta_html}</p>
    </section>

    {rel_html}

    <nav class="dp-nav" aria-label="{e(ui('dp_crumb_aria'))}">
      <a class="dp-nav-home" href="{home}">{ui('dp_back')}</a>
      <a href="{cat_href}">{ui('dp_more_all')}</a>
      <a href="{switch_href}" hreflang="{switch_lang}">{ui('dp_switch')}</a>
    </nav>
  </div>
</main>

<footer>
  <div class="shell foot-line">
    <span class="foot-brand">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpMintFoot')}
      </span>
      {ui('foot_brand', y=today.year)}
    </span>
    <span class="foot-up">{ui('f_last_verified')} {e(deal.get('last_verified') or added_day(deal, today))}</span>
    {legal_footer(lang)}
    <a class="foot-top" href="#top">↑</a>
  </div>
</footer>

{DP_FAV_JS}
<script src="/assets/js/consent.js?v={asset_ver('assets/js/consent.js')}" defer></script>
<script src="/assets/js/votes.js?v={asset_ver('assets/js/votes.js')}" defer></script>
</body>
</html>
"""


# SEO 描述：整句收尾，120–156 字。切句只认句末标点，整句放不下才退到逗号 / 分号边界，
# 绝不出现早先 `desc[:152] + "…"` 那种切在词中间的半句（Hark 复查数出 303 条）。
_DESC_MIN, _DESC_MAX = 120, 156
_DESC_ENDERS = "。！？…」』.!?"
_DESC_CLAUSE_MARKS = "，,；;、：:"
# 补句时最小增量：太短的分句残头（「ahamo。」）不加，凑不出 120 字宁可短一点也不写废话
_DESC_ADD_CLAUSE = 15
_DESC_ADD_WORD = 8


def _desc_chunks(parts: tuple[str, ...], is_en: bool) -> list[str]:
    """把全部素材切成一整句一句的候选块（句末标点留在句尾）。

    中文按「。！？；」断句（；在中文里本来就能结句）；英文只按「. ! ?」断，
    分号在英文里只是分句，切开再拼回去会变成「days. the bonus」这种小写开头。
    """
    split_re = re.compile(r"(?<=[.!?])\s+") if is_en else re.compile(r"(?<=[。！？；])\s*")
    out: list[str] = []
    for raw in parts:
        text = re.sub(r"\s+", " ", raw or "").strip()
        if not text:
            continue
        for sent in split_re.split(text):
            sent = sent.strip()
            if sent:
                out.append(sent)
    return out


def _desc_finish(text: str, end: str) -> str:
    """段末收口：去掉末尾的逗号顿号，「；」「：」这类不收句的标点换成句号。"""
    text = (text or "").strip()
    while text and text[-1] in " ，,、·":
        text = text[:-1]
    if text and text[-1] in "；;：:":
        text = text[:-1].rstrip(" ，,、·") + end
    return text


def _desc_join(prev: str, chunk: str, end: str, is_en: bool) -> str:
    """两句相接：中文句末标点直接接，英文句末标点补一个空格。"""
    if not prev:
        return chunk
    if prev[-1] in "。！？…":
        return prev + chunk
    if prev[-1] in "」』":
        return prev + end + (" " if is_en else "") + chunk
    if prev[-1] in ".!?":
        return prev + " " + chunk
    if prev[-1] in ";:":
        return prev + (" " if is_en else "") + chunk
    return prev + end + (" " if is_en else "") + chunk


def _desc_close(text: str, end: str) -> str:
    """补句末标点：按分句收尾时，最后一句末尾本来是没有标点的。"""
    return text if text and text[-1] in _DESC_ENDERS else text + end


_DESC_PAIRS = (("（", "）"), ("(", ")"), ("「", "」"), ("『", "』"), ("“", "”"))


def _desc_clause_cuts(text: str):
    """分句切点：逗号 / 分号 / 冒号 / 顿号，但跳过数字里的千分位逗号（$1,000 不能切成 $1）。"""
    for m in re.finditer(f"[{_DESC_CLAUSE_MARKS}]", text):
        i = m.start()
        # 千分位逗号（$1,000）与时刻冒号（23:59）都不是分句边界，切开数值就毁了
        if 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit():
            continue
        yield m


def _desc_balanced(text: str) -> bool:
    """括号 / 引号是否成对：切点不能落在「（……」中间，否则会出现「（历史最高。」这种残句。"""
    return all(text.count(a) == text.count(b) for a, b in _DESC_PAIRS)


# 收边时要去掉的尾巴：英文的连词 / 介词 / 冠词，中文的连词
_EN_TAIL_WORD_RE = re.compile(
    r"\s+(?:and|or|of|the|a|an|to|with|for|from|in|on|at|by|as|that|which|plus|but|so|if|when|than"
    r"|is|are|was|were|be|been|has|have|had|will|can|may|not)\s*$",
    re.I,
)
_ZH_TAIL_WORD_RE = re.compile(r"(?:以及|或者|并且|而且|还有|和|与|及|或|并)\s*$")


def _desc_soft_cut(text: str, room: int, end: str) -> str:
    """把一句话按词收短到 room 字以内：括号引号成对，末尾不留连词 / 介词 / 半截词。"""
    limit = min(room, len(text))
    head = text[:limit]

    def tidy(piece: str) -> str:
        piece = piece.rstrip(" ，,、·")
        for _ in range(3):           # 尾巴上可能叠着两三个虚词：「and the」「of a」
            trimmed = _EN_TAIL_WORD_RE.sub("", piece)
            trimmed = _ZH_TAIL_WORD_RE.sub("", trimmed)
            if trimmed == piece:
                break
            piece = trimmed.rstrip(" ，,、·")
        return piece

    # 从长到短找空格收口：落在括号引号成对的位置，绝不在英文词中间切开
    for m in reversed(list(re.finditer(r"\s", head))):
        cut = tidy(head[: m.start()])
        if _desc_balanced(cut):
            return _desc_finish(cut, end)
    # 连一个成对的空格都没有：去掉末尾没闭合的括号 / 引号（连同里面的内容）
    while head and not _desc_balanced(head):
        opens = [head.rfind(c) for c, _ in _DESC_PAIRS]
        if max(opens) < 0:
            break
        head = head[: max(opens)].rstrip(" ，,、·")
    return _desc_finish(tidy(head), end)


def _desc_fill(base: str, chunk: str, end: str, is_en: bool) -> tuple[str, bool]:
    """把 chunk 接到 base 后面：整句装得下就整句，装不下就用它最长的完整分句。

    返回 (接完的文本, 是否用了分句)；一点都接不上就原样返回 base。
    """
    cand = _desc_close(_desc_join(base, chunk, end, is_en), end)
    if len(cand) <= _DESC_MAX:
        return cand, False
    best = base
    for m in _desc_clause_cuts(chunk):
        head = chunk[: m.end()]
        if not _desc_balanced(head):
            continue
        cand = _desc_close(_desc_join(base, _desc_finish(head, end), end, is_en), end)
        if len(cand) > _DESC_MAX:
            break
        # 只加「有内容」的分句：像「ahamo。」这种两三个字的残头宁可不要
        if len(cand) - len(base) >= _DESC_ADD_CLAUSE and len(cand) > len(best):
            best = cand
    return best, best != base


# 描述收口方式计数：构建结束时打印——整句收口 / 用后续整句或完整分句补足 / 只能按词收边
_DESC_STATS = {"sentence": 0, "clause": 0, "word": 0}


def _desc_repair(text: str, end: str) -> str:
    """收口后兜底：去掉多余的右括号、截掉没闭合的左括号，保证句子不残。"""
    for left, right in _DESC_PAIRS:
        while text.count(right) > text.count(left):
            i = text.rfind(right)
            text = text[:i] + text[i + 1:]
    while text and not _desc_balanced(text):
        pos = max(text.rfind(c) for c, _ in _DESC_PAIRS)
        if pos < 0:
            break
        text = text[:pos].rstrip(" ，,、·")
    return _desc_close(_desc_finish(text, end), end)


def seo_description(*parts: str) -> str:
    """详情页 meta description：导语打头，补到 120–156 字并以句末标点收尾。

    1. 素材按句末标点切句，整句往描述里加，最后一整句使总长超过 156 字就停在那里；
    2. 不足 120 字就往后再补：整句装得下用整句，装不下用那一句最长的完整分句
       （括号、引号内部不切）；
    3. 仍然不到 120 字才按词收边（英文落在完整词上，末尾虚词去掉），绝不出省略号；
    4. 结尾一律是句末标点，中文的「；」「：」换成「。」。

    早先的做法是 `desc[:152].rstrip("，；") + "…"`，全站 303 页描述因此截在词中间
    （Hark 复查点名）。
    """
    is_en = CUR_LANG == "en"
    end = "." if is_en else "。"
    kept = [c for c in (_desc_finish(x, end) for x in _desc_chunks(parts, is_en)) if c]
    if not kept:
        return ""

    desc = ""
    used = 0
    for chunk in kept:
        cand = _desc_close(_desc_join(desc, chunk, end, is_en), end)
        if len(cand) > _DESC_MAX:
            break
        desc, used = cand, used + 1
    if used >= len(kept) or len(desc) >= _DESC_MAX:
        _DESC_STATS["sentence"] += 1
        return _desc_repair(desc or kept[0][: _DESC_MAX - 1], end)

    # 整句补到 120 字：能整句装下就整句，装不下用这一句最长的完整分句（括号引号内不切）
    idx = used
    clause_at = None
    while idx < len(kept) and len(desc) < _DESC_MIN:
        desc, used_clause = _desc_fill(desc, kept[idx], end, is_en)
        if used_clause and clause_at is None:
            clause_at = idx
        idx += 1
        if len(desc) >= _DESC_MIN:
            _DESC_STATS["clause" if used_clause else "sentence"] += 1
            return _desc_repair(desc, end)
    # 词边界补用哪一句：用过分句的话，从它的下一句起（避免把同一句的开头再写一遍）；
    # 一句都没用上就从第一句装不下的那句起
    idx = (clause_at + 1) if clause_at is not None else used

    # 还不到 120 字：按词收边补足。从第一句没能整句塞进去的那句起往后找，
    # 先要求「有内容」的增量，
    # 仍不到 120 字再放宽到任意增量（都落在完整词上，末尾虚词已去掉）
    word_used = False
    for min_add in (_DESC_ADD_WORD, 1):
        for j in range(max(idx, 0), len(kept)):
            if len(desc) >= _DESC_MIN:
                break
            room = _DESC_MAX - (len(desc) + len(end) + (1 if is_en else 0))
            if room < 8:
                break
            piece = _desc_soft_cut(kept[j], room, end)
            core = piece.strip(" 。.，,")
            if not core or core in desc:
                continue
            cand = _desc_close(_desc_join(desc, piece, end, is_en), end)
            if len(cand) - len(desc) >= min_add and len(cand) > len(desc):
                desc = cand
                word_used = True
        if len(desc) >= _DESC_MIN:
            break
    _DESC_STATS["word" if word_used else "sentence"] += 1
    return _desc_repair(desc, end)


# ------------------------------------------- 合规页面（/about/ /privacy/ /disclosure/）
# AdSense 审核要求的几个静态页：纯静态生成，面包屑 + canonical + hreflang + WebPage
# 结构化数据；页脚只加一行「关于 · 隐私 · 披露」文字链接，不写免责长句。


def legal_path(kind: str, lang: str) -> str:
    """合规页的相对路径：中文 /about/，英文 /en/about/。"""
    return ("en/" if lang == "en" else "") + kind + "/"


def legal_footer(lang: str) -> str:
    """页脚那一行极简文字链接（首页 / 分类页 / 详情页 / 合规页共用）。

    末尾的「Cookie 设置」沿用同一行小字，不额外占高度；它打开同意面板，
    面板本身是 position: fixed 的抽屉，打开前后都不推动页面（零 CLS）。
    """
    is_en = lang == "en"
    sep = '<span class="foot-legal-sep" aria-hidden="true">·</span>'
    links = sep.join(
        f'<a href="/{e(legal_path(kind, lang))}">{e(U[key][1] if is_en else U[key][0])}</a>'
        for kind, key in LEGAL_LINKS
    )
    cookie = (
        f'<button class="foot-cookie" type="button" data-consent-open '
        f'{al(*U["cookie_settings_aria"])}>{e(ui("cookie_settings"))}</button>'
    )
    return (
        f'<span class="foot-legal" {al(*U["legal_nav_aria"])}>'
        f'{links}{sep}{cookie}</span>'
    )


def render_legal_page(kind: str, lang: str, today) -> str:
    """一条合规页（单语）：顶栏 + 面包屑 + 标题导语 + 分节正文 + 页脚。"""
    set_lang(lang)
    is_en = lang == "en"
    page = LEGAL_PAGES[kind][lang]
    site_name = "Deal Hunter" if is_en else "羊毛情报局"
    home = "/en/" if is_en else "/"
    canon = SITE_URL + legal_path(kind, lang)
    other_lang = "zh" if is_en else "en"
    switch_href = "/" + legal_path(kind, other_lang)
    switch_lang = "zh-CN" if is_en else "en"
    switch_aria = ui("page_switch_aria_zh") if is_en else ui("page_switch_aria")
    og_image = OG_IMAGE_EN if is_en else OG_IMAGE

    sections = "".join(
        f'<section class="dp-sec"><h2>{e(heading)}</h2>'
        + "".join(f"<p>{e(para)}</p>" for para in paras)
        + "</section>"
        for heading, paras in page["sections"]
    )

    ld = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "@id": canon + "#webpage",
                "url": canon,
                "name": page["title"],
                "description": page["desc"],
                "inLanguage": "en" if is_en else "zh-CN",
                "isPartOf": {"@type": "WebSite", "name": site_name, "url": SITE_URL + ("en/" if is_en else "")},
                "breadcrumb": {"@id": canon + "#breadcrumb"},
                "dateModified": LEGAL_UPDATED,
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "@id": canon + "#breadcrumb",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": ui("dp_crumb_home"),
                        "item": SITE_URL + ("en/" if is_en else ""),
                    },
                    {"@type": "ListItem", "position": 2, "name": page["h1"], "item": canon},
                ],
            },
        ],
        ensure_ascii=False,
        indent=2,
    ).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="{"en" if is_en else "zh-CN"}" data-lang="{"en" if is_en else "zh"}" data-today="{today.isoformat()}" data-consent-required="{CONSENT_REQUIRED}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<title>{e(page["title"])}</title>
<meta name="description" content="{e(page["desc"])}">
<meta name="author" content="{site_name}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#FAF9F5">
<link rel="canonical" href="{canon}">
<link rel="alternate" hreflang="zh-CN" href="{SITE_URL + legal_path(kind, "zh")}">
<link rel="alternate" hreflang="en" href="{SITE_URL + legal_path(kind, "en")}">
<link rel="alternate" hreflang="x-default" href="{SITE_URL + legal_path(kind, "zh")}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="{"en_US" if is_en else "zh_CN"}">
<meta property="og:locale:alternate" content="{"zh_CN" if is_en else "en_US"}">
<meta property="og:title" content="{e(page["title"])}">
<meta property="og:description" content="{e(page["desc"])}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(page["title"])}">
<meta name="twitter:description" content="{e(page["desc"])}">
<meta name="twitter:image" content="{og_image}">

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/assets/favicon-48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/style.css?v={asset_ver('assets/css/style.css')}">

<script type="application/ld+json">
{ld}
</script>
</head>
<body class="dp">

{sprite_svg(("chevron",))}
{vector_defs()}

<header class="topbar">
  <div class="shell topbar-in">
    <a class="brand" href="{home}" {al(*U['brand_aria'])}>
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpLegalHead')}
      </span>
      <span class="brand-text">
        <span class="brand-name">{ui('brand')}</span>
        <span class="brand-sub">{ui('brand_sub')}</span>
      </span>
    </a>
    <div class="dp-top">
      <a class="dp-back" href="{home}">{icon('chevron', 'dp-back-i')}<span>{ui('dp_back')}</span></a>
      <a class="dp-switch" href="{switch_href}" hreflang="{switch_lang}" {al(switch_aria, switch_aria)}><span lang="{switch_lang}">{ui('dp_switch')}</span></a>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell dp-wrap">
    <nav class="dp-crumbs" {al(*U['dp_crumb_aria'])}>
      <a href="{home}">{ui('dp_crumb_home')}</a>
      <span class="dp-sep" aria-hidden="true">/</span>
      <span class="dp-cur">{e(page["h1"])}</span>
    </nav>

    <article class="dp-card">
      <h1 class="dp-title">{e(page["h1"])}</h1>
      <p class="legal-lead">{e(page["lead"])}</p>
      <p class="legal-stamp">{ui('legal_updated', d=LEGAL_UPDATED)}</p>
    </article>

    {sections}

    <nav class="dp-nav" aria-label="{e(ui('legal_nav_aria'))}">
      <a class="dp-nav-home" href="{home}">{ui('dp_back')}</a>
      {"".join(f'<a href="/{e(legal_path(kind2, lang))}">{e(U[key][1] if is_en else U[key][0])}</a>' for kind2, key in LEGAL_LINKS if kind2 != kind)}
    </nav>
  </div>
</main>

<footer>
  <div class="shell foot-line">
    <span class="foot-brand">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpLegalFoot')}
      </span>
      {ui('foot_brand', y=today.year)}
    </span>
    {legal_footer(lang)}
    <a class="foot-top" href="#top">{ui('foot_top')}</a>
  </div>
</footer>

<script src="/assets/js/consent.js?v={asset_ver('assets/js/consent.js')}" defer></script>
</body>
</html>
"""


def write_legal_pages(today) -> int:
    """写 6 个合规页：/about/ /privacy/ /disclosure/ 与 /en/ 下的三份。"""
    count = 0
    for kind in LEGAL_PAGES:
        for lang, base in (("zh", ROOT), ("en", ROOT / "en")):
            out = base / kind / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                compact_html(render_legal_page(kind, lang, today)), encoding="utf-8"
            )
            count += 1
    return count


def dp_end_pair(deal: dict) -> tuple[str, str]:
    end = parse_date(deal.get("end", ""))
    return short_date(deal.get("end")), short_date_en(end) if end else ""


def _region_key(deal: dict) -> str:
    """地区标签（[美区] / [英区] / [全球]…）：详情页「同地区」内链的依据。

    标题前的方括号与 regions 字段开头是同一个标签，优先用标题那个（更干净）。
    """
    rtag, _ = title_parts(deal.get("title", ""))
    if rtag:
        return rtag
    m = re.match(r"^\s*\[([^\]]{1,24})\]", str(deal.get("regions") or ""))
    return m.group(1) if m else ""


def related_deals(deal: dict, by_cat: dict[str, list[dict]], by_region: dict[str, list[dict]]) -> list[dict]:
    """详情页底部内链：同分类里相邻的 4 条 + 同地区 2 条，按条目 id 轮转。

    老版本按价值取同类前 4，结果 220 个页面里只有 30 个能从其他详情页拿到入链，
    前 5 页各被链 56–66 次。改成「相邻轮转」后每页都是 4 个邻居的前后条，
    再补 2 条同地区，入链分布拉平，也不再让少数页面吃掉全部站内权重。

    候选池先滤掉 `status == "expired"` 的条目：否则 20 个活跃页面的相关推荐里会
    混进已经结束的活动（Hark 复查点名 jio / mistral / gcp 三条被链了 12–14 次）。
    """
    limit = 6
    picks: list[dict] = []
    seen = {deal["id"]}

    def take(pool: list[dict], offsets: tuple[int, ...]) -> None:
        n = len(pool)
        if not n:
            return
        start = next((i for i, d in enumerate(pool) if d["id"] == deal["id"]), 0)
        for off in offsets:
            if len(picks) >= limit:
                return
            cand = pool[(start + off) % n]
            if cand["id"] in seen or cand.get("status") == "expired":
                continue
            seen.add(cand["id"])
            picks.append(cand)

    cat_list = by_cat.get(deal.get("category", ""), [])
    reg_list = by_region.get(_region_key(deal), [])
    take(cat_list, (1, 2, -1, -2))          # 同类里前后各两条
    take(reg_list, (1, -1))                 # 同地区按 id 轮转各一条
    take(cat_list, (3, 4, -3, -4, 5, 6, -5, -6))   # 同地区不足 2 条时，用同类更远的邻居补齐
    return picks


def alternative_deals(deal: dict, by_cat: dict[str, list[dict]], limit: int = 3) -> list[dict]:
    """已归档详情页顶上「替代优惠」的候选：同分类里当前仍在进行的条目。

    先按可预期到手价值取高价值，再用入库时间兜底：两次稳定排序保证同一份数据
    每次构建挑出同一组（静态页不能因为字典顺序不同而每天换一批推荐）。
    已过期 / 已归档的条目不进候选，否则又把人指向另一个已经结束的活动。
    """
    pool = [
        d
        for d in by_cat.get(deal.get("category", ""), [])
        if d["id"] != deal["id"] and d.get("status") != "expired"
    ]
    pool.sort(key=lambda d: str(d.get("added_at") or d.get("added") or ""), reverse=True)
    pool.sort(key=lambda d: value_expected(d), reverse=True)
    return pool[:limit]


def write_deal_pages(deals: list[dict], en_map: dict, today) -> int:
    """重建 d/ 与 en/d/：先整个删掉旧目录（清掉已不存在条目的残留），再逐条写。"""
    for base in (DEALS_DIR, DEALS_DIR_EN):
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True, exist_ok=True)

    # 内链的两个池子都按 id 排序：轮转相邻才稳定（与价值、入库时间无关）
    by_cat: dict[str, list[dict]] = {}
    by_region: dict[str, list[dict]] = {}
    for deal in sorted(deals, key=lambda d: d["id"]):
        by_cat.setdefault(deal.get("category", ""), []).append(deal)
        key = _region_key(deal)
        if key:
            by_region.setdefault(key, []).append(deal)

    count = 0
    for deal in deals:
        related = related_deals(deal, by_cat, by_region)
        alternatives = alternative_deals(deal, by_cat)
        en = en_map.get(deal["id"], {})
        for lang, base in (("zh", DEALS_DIR), ("en", DEALS_DIR_EN)):
            out = base / deal["id"] / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                compact_html(render_deal_page(deal, en, lang, today, en_map, related, alternatives)),
                encoding="utf-8",
            )
            count += 1
    return count


# ---------------------------------------------------- 静态分类目录页 /category/<slug>/
# 12 个纯静态目录页（6 大分类 × 中英各一份）：给「AI 工具有哪些免费额度」这类
# 分类级搜索一个独立落地页，也给详情页面包屑一个比首页锚点更准的去处。
# 页面结构与详情页同源（同一个 .dp 窄容器、同一套 token），只是把单条内容换成列表。
CAT_PAGE_ICONS = ("external", "archive", "chevron", *CAT_ICON.values())


def cat_row(deal: dict, en: dict, lang: str, today) -> str:
    """目录页的一条：图标 + 标题 + 价值 / 门槛 / 截止 + 原标题行 + 地区。"""
    is_en = lang == "en"
    raw = (en.get("title") or deal.get("title", "")) if is_en else deal.get("title", "")
    rtag, title = title_parts(raw)
    tag = f'<i>{e(rtag)}</i>' if rtag else ""
    value_now = value_pair(deal, en)[1 if is_en else 0]
    cost = deal.get("cost", "")
    cost_cls = COST_CLASS.get(cost, "cost-invite")
    cost_label = (COST_EN.get(cost, cost) if is_en else cost)
    highlight = (en.get("highlight") or deal.get("highlight") or "") if is_en else (deal.get("highlight") or "")
    regions = (en.get("regions") or deal.get("regions", "")) if is_en else deal.get("regions", "")
    regions = strip_region_bracket(regions)
    dl = short_deadline(deal, today)[1 if is_en else 0]
    end = parse_date(deal.get("end", ""))
    hot = " hot" if end and 0 <= (end - today).days <= EXPIRING_DAYS else ""
    aff, _ = deal_affiliate(deal)
    aff_tag = f'<span class="aff-tag">{e(U["aff_badge"][1 if is_en else 0])}</span>' if aff else ""
    return (
        f'<li><a class="cat-card" href="/{e(deal_path(deal["id"], lang))}">'
        f'<span class="cat-crow">{fav_html(deal, 26, en)}<span class="cat-cmain">'
        f'<span class="cat-ct">{tag}{e(title)}</span>'
        f'<span class="cat-csub"><b class="cat-cv" title="{e(value_now)}">{e(value_badge(value_now, lang))}</b>'
        f'<span class="tag {cost_cls}">{e(cost_label)}</span>{aff_tag}'
        f'<span class="cat-cdl{hot}">{e(dl)}</span></span></span></span>'
        f'<span class="cat-snip">{e(highlight)}</span>'
        f'<span class="cat-region">{e(regions)}</span>'
        f"</a></li>"
    )


def is_global_deal(deal: dict) -> bool:
    """全球通用条目：regions 里写了“全球”，或标题以 [全球 开头。"""
    regions = str(deal.get("regions") or "")
    title = str(deal.get("title") or "").lstrip()
    return ("全球" in regions) or title.startswith("[全球")


# 需要本地身份 / 税号 / 高资产门槛才能开的银行类关键词（命中则放银行分区中后段）
BANK_LOCAL_ID_KEYS = (
    "SSN", "ITIN", "美国身份", "美国居民", "英国居民", "本地身份",
    "当地税号", "居民身份", "绿卡", "永居", "高额资产", "资产门槛", "年薪",
    "国籍", "公民", "国民",
)
BANK_LOCAL_ID_NEGATIONS = (
    "无需 SSN", "无需SSN", "不需要 SSN", "不需要SSN", "免 SSN", "免SSN",
    "不需 SSN", "不需SSN", "无需 ITIN", "无需ITIN", "不需要 ITIN", "不需要ITIN",
    "无需美国身份", "不需要美国身份", "无资产门槛", "无需资产",
)


def bank_needs_local_identity(deal: dict) -> bool:
    """US Bank 这类要 SSN / ITIN / 当地身份 / 高资产才开的优惠，普适性低，排到银行分区中部。"""
    text = " ".join(
        str(deal.get(k) or "") for k in ("title", "conditions", "highlight", "risk", "regions")
    )
    for neg in BANK_LOCAL_ID_NEGATIONS:
        text = text.replace(neg, "")
    return any(key in text for key in BANK_LOCAL_ID_KEYS)


def is_backlogged_deal(deal: dict) -> bool:
    """低通过率 / 长期积压的申请类条目：热度不高、几乎没人成功，排到同分类最后。"""
    text = " ".join(
        str(deal.get(k) or "")
        for k in ("title", "conditions", "risk", "highlight", "regions", "url", "source_url")
    ).lower()
    keys = (
        "eu.org", "nic.eu.org", "长期积压", "严重积压", "积压", "审批积压",
        "极难通过", "极难下号", "极低概率", "几乎不下号", "排队数月", "数月排队",
    )
    return any(key in text for key in keys)


# ------------------------------------------------------------ 打分与赞踩
# 一期静态分（Hark 五轮定稿 + 318 条实测）。分数只用于构建时排序，
# 不在页面上显示；详情页只展示由 kyc_level / vowifi 生成的事实标签。
VOTE_ITEMS: dict[str, list[int]] = {}
VOTE_TOTAL = 0

_COST_FACTOR = {
    "真正免费": 1.00,
    "免费试用": 0.85,
    "需要充值": 0.85,
    "需要邀请条件": 0.80,
    "需要交易量": 0.75,
}
_KYC_FACTOR = {"none": 1.00, "cn_ok": 0.95, "cn_ok_extra": 0.80, "foreign_only": 0.50}

# 赞踩的双重门槛：全站有效票数 / 单条票数（口径见 docs/scoring.md）
VOTE_SITE_GATE = 100
VOTE_ITEM_GATE = 10


def load_votes_snapshot() -> None:
    """读取 data/votes_snapshot.json（GAS 导出后由定时任务更新）。

    文件缺失或格式不对时按「全站 0 票」构建，构建永不因投票失败。
    """
    global VOTE_ITEMS, VOTE_TOTAL
    path = ROOT / "data" / "votes_snapshot.json"
    VOTE_ITEMS, VOTE_TOTAL = {}, 0
    if not path.exists():
        return
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
        if int(snap.get("schema", 0)) != 1:
            print(f"  ! votes_snapshot schema 不是 1，按 0 票构建", file=sys.stderr)
            return
        items = snap.get("items") or {}
        for deal_id, pair in items.items():
            if isinstance(pair, list) and len(pair) >= 2:
                up, down = int(pair[0]), int(pair[1])
                VOTE_ITEMS[str(deal_id)] = [max(0, up), max(0, down)]
        VOTE_TOTAL = sum(u + d for u, d in VOTE_ITEMS.values())
    except Exception as err:  # noqa: BLE001 - 快照坏了也照常建站
        print(f"  ! votes_snapshot 读取失败（{err}），按 0 票构建", file=sys.stderr)
        VOTE_ITEMS, VOTE_TOTAL = {}, 0


def _value_points(v: float) -> float:
    if not v or v <= 0:
        return 0.0
    return 40.0 * min(1.0, math.log1p(v) / math.log1p(501))


def scope_factor(deal: dict) -> float:
    """A：权益在哪里用。只对 eSIM / 本地消费类生效，其余分类一律 1.0。

    全球 / 大陆漫游 / 中国大陆区 1.0；港台日韩新马 0.9；其他地区 0.8。
    只认 regions 开头的方括号地区标签，避免正文里的「不支持中国大陆漫游」误判。
    """
    if deal.get("category") != "esim":
        return 1.0
    regions = str(deal.get("regions") or "")
    tag = re.match(r"\[([^\]]+)\]", regions)
    tag = tag.group(1) if tag else regions
    if any(k in tag for k in ("全球", "多区", "中国")) or "大陆漫游" in regions:
        return 1.0
    if any(k in tag for k in ("香港", "澳门", "台湾", "台/", "日", "韩", "新加坡", "马来")):
        return 0.9
    return 0.8


def _days_since(value: str | None, today) -> int | None:
    d = parse_date(value)
    return (today - d).days if d else None


def score_deal(deal: dict, today) -> dict:
    """计算一条优惠的静态分与各因子，返回 {S, ...} 供排序与 --explain 使用。"""
    v = value_expected(deal)
    base = 20.0 + _value_points(v) + (15.0 if deal.get("utility") else 0.0)
    a = scope_factor(deal)
    e = _COST_FACTOR.get(deal.get("cost"), 0.85)
    kyc = deal.get("kyc_level")
    g = _KYC_FACTOR.get(kyc, 0.90)
    if kyc not in _KYC_FACTOR:
        print(f"  ! {deal['id']} 未标 kyc_level，按 0.90 计", file=sys.stderr)
    h = 0.40 if is_backlogged_deal(deal) else 1.0
    t = 1.0 if deal.get("verified") is True else 0.85
    age_verified = _days_since(deal.get("last_verified"), today)
    if age_verified is None or age_verified <= 30:
        l = 1.0
    elif age_verified <= 60:
        l = 0.90
    else:
        l = 0.75
    r = 1.0
    end_days = _days_since(deal.get("end"), today)
    if (
        end_days is not None
        and -end_days >= 8
        and -end_days <= 30
        and e >= 0.85
        and g == 1.0
        and h == 1.0
    ):
        r = 1.10
    mult = max(0.2, a * e * g * h * t * l)
    # 赞踩：双重门槛（第七轮定稿）。全站先满 100 票，单条再满 10 票才算数——
    # 只有全站门槛时，一条 1 票的条目也能拿到 ±40 的量级，足以撬动整个分类排序；
    # 单条门槛挡住这种噪音，夹紧到 [-20, +12] 后单条最多只能动一档，翻不了盘。
    vote = 0.0
    up = down = 0
    if VOTE_TOTAL >= VOTE_SITE_GATE:
        up, down = VOTE_ITEMS.get(deal["id"], [0, 0])
        n = up + down
        if n >= VOTE_ITEM_GATE:
            vote = max(-20.0, min(12.0, 40.0 * (up - 0.7 * n) / (n + 10)))
    fresh = 0.0
    if deal.get("status") != "expired":
        added_age = _days_since(deal.get("added_at") or deal.get("added"), today)
        if added_age is not None and added_age < 60:
            fresh = 10.0 * (2 ** (-added_age / 7))
    return {
        "S": base * mult * r + vote + fresh,
        "base": base,
        "V": _value_points(v),
        "U": 15.0 if deal.get("utility") else 0.0,
        "A": a,
        "E": e,
        "G": g,
        "H": h,
        "T": t,
        "L": l,
        "R": r,
        "mult": mult,
        "vote": vote,
        "fresh": fresh,
    }


def provider_key(deal: dict) -> str:
    """多样性护栏用的服务商键：手工 provider 优先，否则按域名归一化。"""
    if deal.get("provider"):
        return str(deal["provider"]).strip().lower()
    domain = str(deal.get("domain") or "").strip().lower()
    domain = domain.removeprefix("www.")
    if domain:
        parts = domain.split(".")
        # co.uk / com.cn / com.au 这类二级公共后缀保留三段
        if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "edu", "ac"}:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    brand = re.sub(r"[^a-z0-9]+", "", str(deal.get("brand") or "").lower())
    return brand or deal["id"]


def diversity_guard(ordered: list[dict]) -> list[dict]:
    """每个分类前 10 条同一服务商最多 2 条，超出的顺延到第 11 位起。"""
    top: list[dict] = []
    deferred: list[dict] = []
    seen: Counter[str] = Counter()
    idx = 0
    while idx < len(ordered) and len(top) < 10:
        deal = ordered[idx]
        idx += 1
        key = provider_key(deal)
        if seen[key] >= 2:
            deferred.append(deal)
            continue
        seen[key] += 1
        top.append(deal)
    return top + deferred + ordered[idx:]


def vote_bar(deal_id: str) -> str:
    """紧凑的赞/踩胶囊：只显示票数，不重排；原因气泡由 votes.js 就地展开。

    理由气泡的容器（.vote-why）不再写进 HTML：首页 144 张卡、678 个详情页都挂一份空
    节点，DOM 数会被这 1 个节点/处顶上去；votes.js 的 whyOf() 在真要用的时候再建。
    """
    zh = CUR_LANG != "en"
    up_aria = "这条优惠有用" if zh else "This deal is useful"
    down_aria = "这条优惠没用" if zh else "This deal is not useful"
    return (
        f'<div class="vote-bar" data-vote="{e(deal_id)}">'
        f'<button class="vb up" type="button" data-v="1" aria-pressed="false" aria-label="{up_aria}">'
        '<span aria-hidden="true">👍</span><span class="vb-n" data-n="up">–</span></button>'
        f'<button class="vb down" type="button" data-v="-1" aria-pressed="false" aria-label="{down_aria}">'
        '<span aria-hidden="true">👎</span><span class="vb-n" data-n="down">–</span></button>'
        "</div>"
    )


def kyc_fact(deal: dict, is_en: bool) -> str:
    """详情页事实标签：由 kyc_level 生成，带一句具体卡点。"""
    level = deal.get("kyc_level")
    labels = {
        "none": ("免 KYC", "No KYC"),
        "cn_ok": ("大陆证件可 KYC", "Mainland ID accepted"),
        "cn_ok_extra": ("大陆证件 + 海外条件", "Mainland ID + overseas requirement"),
        "foreign_only": ("需当地身份/居留", "Local ID or residence required"),
    }
    zh, en = labels.get(level, ("未标定", "Not labelled"))
    text = en if is_en else zh
    note = deal.get("kyc_note")
    if note and not is_en:
        text += f"（{note}）"
    return text


def _yn3(value: object, is_en: bool) -> str:
    """三态：True / False / unknown（缺省也算 unknown）。"""
    if value is True:
        return "Yes" if is_en else "可"
    if value is False:
        return "No" if is_en else "不可"
    return "Unconfirmed" if is_en else "未确认"


def _kyc3(value: object, is_en: bool) -> str:
    """当地实名三态：需要 / 不需要 / 未确认。"""
    if value is True:
        return "Required" if is_en else "需要"
    if value is False:
        return "Not required" if is_en else "不需要"
    return "Unconfirmed" if is_en else "未确认"


def esim_comm_facts(deal: dict, is_en: bool) -> list[str]:
    """eSIM 详情页的 8 项通信参数（号码 / 大陆漫游 / 大陆收短信 / 保号 /
    年成本 / 开通方式 / 当地实名，VoWiFi 另由 vowifi_fact 出）。

    字段由 2026-11-21 的官网与实测核对写入 data/deals.json；缺字段的条目
    直接不出行，不猜值。
    """
    if not deal.get("has_number"):
        return []
    rows: list[tuple[str, str]] = []
    prefix = deal.get("phone_number") or ""
    rows.append(("号码" if not is_en else "Number",
                 (f"{prefix} 真号" if not is_en else f"Real {prefix} number") if prefix
                 else ("有" if not is_en else "Yes")))
    rows.append(("大陆漫游" if not is_en else "Roam in China", _yn3(deal.get("cn_roaming"), is_en)))
    rows.append(("大陆收短信" if not is_en else "Free SMS in China", _yn3(deal.get("free_sms_roam"), is_en)))
    rows.append(("长期保号" if not is_en else "Keep number", _yn3(deal.get("long_term_keep"), is_en)))
    cost = deal.get("annual_keep_cost_en" if is_en else "annual_keep_cost")
    if cost:
        rows.append(("年保号成本" if not is_en else "Yearly cost", cost))
    mode = deal.get("online_activation")
    modes = {
        "cloud": ("云开（线上）", "Online"),
        "partial": ("部分线上", "Partly online"),
        "on_site": ("需到店", "In store"),
        "on_arrival": ("需落地", "On arrival"),
    }
    if mode in modes:
        rows.append(("开通方式" if not is_en else "Activation", modes[mode][1 if is_en else 0]))
    rows.append(("当地实名" if not is_en else "Local KYC", _kyc3(deal.get("local_kyc"), is_en)))
    euicc = deal.get("euicc_compat")
    euicc_labels = {
        "works": ("可写入", "Works"),
        "partial": ("写入不兼容", "Writes but fails"),
        "blocked": ("会被拒", "Blocked"),
        "whitelist": ("需 EID 白名单", "EID whitelist"),
        "unknown": ("未确认", "Unconfirmed"),
    }
    if euicc in euicc_labels:
        rows.append(("实体 eUICC" if not is_en else "3rd-party eUICC", euicc_labels[euicc][1 if is_en else 0]))
    return [f'<li><span>{e(label)}</span><b class="dp-kyc">{e(value)}</b></li>' for label, value in rows]


def vowifi_fact(deal: dict, is_en: bool) -> str:
    level = deal.get("vowifi")
    labels = {
        "true": ("运营商支持 VoWiFi", "Carrier VoWiFi supported"),
        "false": ("不支持 VoWiFi", "No carrier VoWiFi"),
        "unknown": ("VoWiFi 未确认", "VoWiFi unconfirmed"),
    }
    if level not in labels:
        return ""
    text = labels[level][1 if is_en else 0]
    note = deal.get("vowifi_note_en" if is_en else "vowifi_note")
    if note:
        text += f" ({note})" if is_en else f"（{note}）"
    return text


def order_category_deals(deals: list[dict], slug: str, today=None) -> list[dict]:
    """分类列表排序：静态打分 S 降序（口径见 docs/scoring.md），再做服务商多样性护栏。

    一期静态分（318 条实测标定）：
      S = (20 + V + 15·U) × max(0.2, A × E × G × H × T × L) × R_t + Vote + Fresh
    排序键 (-round(S,1), -value_expected, -added_at, id)；每个分类前 10 条同一
    服务商最多 2 条，超出的顺延到第 11 位起。Vote 由快照提供，全站满 100 票且单条满
    10 票才生效（双重门槛，见 docs/scoring.md），所以现在恒为 0。
    """
    today = today or today_local()
    scored = [(score_deal(d, today), d) for d in deals]
    # 四段稳定排序，等价于元组键 (-S, -value_expected, -added_at, id)
    scored.sort(key=lambda pair: pair[1]["id"])
    scored.sort(
        key=lambda pair: str(pair[1].get("added_at") or pair[1].get("added") or ""),
        reverse=True,
    )
    scored.sort(key=lambda pair: value_expected(pair[1]), reverse=True)
    scored.sort(key=lambda pair: round(pair[0]["S"], 1), reverse=True)
    return diversity_guard([d for _, d in scored])


def render_category_page(
    slug: str, cat_deals: list[dict], expired_n: int, en_map: dict, today, lang: str
) -> str:
    """一个分类目录页（单语）：面包屑 + 标题导语 + 全部活跃条目 + 其他分类导航。"""
    set_lang(lang)
    is_en = lang == "en"
    pick = 1 if is_en else 0
    meta = CATEGORY_PAGE[slug]
    h1 = meta["h1"][pick]
    seo_title = meta["title"][pick]
    lead = meta["lead"][pick]
    desc = meta["desc"][pick]

    site_name = "Deal Hunter" if is_en else "羊毛情报局"
    home = "/en/" if is_en else "/"
    canon = cat_url(slug, lang)
    other_lang = "zh" if is_en else "en"
    switch_href = "/" + cat_path(slug, other_lang)
    switch_lang = "zh-CN" if is_en else "en"
    switch_aria = ui("cat_switch_aria_zh") if is_en else ui("cat_switch_aria")
    cat_icon = CAT_ICON.get(slug, "software")
    og_image = OG_IMAGE_EN if is_en else OG_IMAGE
    og_locale = "en_US" if is_en else "zh_CN"
    og_locale_alt = "zh_CN" if is_en else "en_US"

    lastmod = max(
        (str(d.get("last_verified") or added_day(d, today))[:10] for d in cat_deals),
        default=today.isoformat(),
    )

    rows = "".join(cat_row(d, en_map.get(d["id"], {}), lang, today) for d in cat_deals)
    if not rows:
        rows = f'<li class="cat-empty">{ui("cat_empty")}</li>'

    # 其他 5 个分类的横向切换条（不包含当前分类），图标与首页分区一致
    chips = []
    for other_slug, other_meta in CAT_META.items():
        if other_slug == slug:
            continue
        label = CAT_EN.get(other_slug, (other_meta["label"], ""))[0] if is_en else other_meta["label"]
        chips.append(
            f'<a class="cat-chip" href="/{e(cat_path(other_slug, lang))}">'
            f'{icon(CAT_ICON.get(other_slug, "software"), "cat-chip-i")}<span>{e(label)}</span></a>'
        )

    archive_line = ""
    if expired_n:
        archive_line = (
            f'<p class="cat-arch">{icon("archive", "cat-arch-i")}'
            f'<span>{ui("cat_archive_note", n=expired_n)}</span>'
            f'<a href="{home}#archive">{ui("cat_archive_link")}</a></p>'
        )

    items = []
    for i, deal in enumerate(cat_deals, start=1):
        en = en_map.get(deal["id"], {})
        name = (en.get("title") or deal.get("title", "")) if is_en else deal.get("title", "")
        _, name = title_parts(name)
        items.append(
            {"@type": "ListItem", "position": i, "name": name, "url": deal_url(deal["id"], lang)}
        )

    ld = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "@id": canon + "#webpage",
                "url": canon,
                "name": seo_title,
                "description": desc,
                "inLanguage": "en" if is_en else "zh-CN",
                "isPartOf": {
                    "@type": "WebSite",
                    "name": site_name,
                    "url": SITE_URL + ("en/" if is_en else ""),
                },
                "breadcrumb": {"@id": canon + "#breadcrumb"},
                "mainEntity": {"@id": canon + "#itemlist"},
                "dateModified": lastmod,
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "@id": canon + "#breadcrumb",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": ui("dp_crumb_home"),
                        "item": SITE_URL + ("en/" if is_en else ""),
                    },
                    {"@type": "ListItem", "position": 2, "name": h1, "item": canon},
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "@id": canon + "#itemlist",
                "name": h1,
                "numberOfItems": len(cat_deals),
                "itemListElement": items,
            },
        ],
        ensure_ascii=False,
        indent=2,
    ).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'zh-CN'}" data-lang="{'en' if is_en else 'zh'}" data-today="{today.isoformat()}" data-consent-required="{CONSENT_REQUIRED}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<title>{e(seo_title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="author" content="{site_name}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#FAF7F2">
<link rel="canonical" href="{canon}">
<link rel="alternate" hreflang="zh-Hans" href="{cat_url(slug, 'zh')}">
<link rel="alternate" hreflang="en" href="{cat_url(slug, 'en')}">
<link rel="alternate" hreflang="x-default" href="{cat_url(slug, 'zh')}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:locale:alternate" content="{og_locale_alt}">
<meta property="og:title" content="{e(seo_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(h1)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(seo_title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{og_image}">

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/assets/favicon-48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/style.css?v={asset_ver('assets/css/style.css')}">
<meta name="dh-votes-base" content="{SUBMIT_ENDPOINT}">

<script type="application/ld+json">
{ld}
</script>
</head>
<body class="dp cat">

{sprite_svg(CAT_PAGE_ICONS)}

<header class="topbar">
  <div class="shell topbar-in">
    <a class="brand" href="{home}" {al(*U['brand_aria'])}>
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpCatHead')}
      </span>
      <span class="brand-text">
        <span class="brand-name">{ui('brand')}</span>
        <span class="brand-sub">{ui('brand_sub')}</span>
      </span>
    </a>
    <div class="dp-top">
      <a class="dp-back" href="{home}">{icon('chevron', 'dp-back-i')}<span>{ui('dp_back')}</span></a>
      <a class="dp-switch" href="{switch_href}" hreflang="{switch_lang}" {al(switch_aria, switch_aria)}><span lang="{switch_lang}">{ui('dp_switch')}</span></a>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell dp-wrap">
    <nav class="dp-crumbs" {al(*U['dp_crumb_aria'])}>
      <a href="{home}">{ui('dp_crumb_home')}</a>
      <span class="dp-sep" aria-hidden="true">/</span>
      <span class="dp-cur">{e(h1)}</span>
    </nav>

    <header class="cat-head">
      <h1 class="cat-h1"><span class="cat-h1-i" aria-hidden="true">{icon(cat_icon)}</span>{e(h1)}</h1>
      <p class="cat-meta"><span class="cat-count">{ui('cat_count', n=len(cat_deals))}</span>
        <span class="cat-dot" aria-hidden="true">·</span>
        <span class="cat-sortnote">{ui('cat_sort_note')}</span></p>
      <p class="cat-lead">{e(lead)}</p>
    </header>

    <ul class="cat-list">
      {rows}
    </ul>

    {archive_line}

    <nav class="cat-switch" aria-label="{e(ui('cat_aria'))}">
      <h2>{ui('cat_other')}</h2>
      <div class="cat-chips">{''.join(chips)}</div>
      <a class="cat-home" href="{home}">{ui('cat_all_home')}{icon('chevron', 'cat-home-i')}</a>
    </nav>
  </div>
</main>

<footer>
  <div class="shell foot-line">
    <span class="foot-brand">
      <span class="brand-mark" aria-hidden="true">
        {mascot_svg(gid='dpCatFoot')}
      </span>
      {ui('foot_brand', y=today.year)}
    </span>
    {legal_footer(lang)}
    <a class="foot-top" href="#top">↑</a>
  </div>
</footer>

{DP_FAV_JS}
<script src="/assets/js/consent.js?v={asset_ver('assets/js/consent.js')}" defer></script>
<script src="/assets/js/votes.js?v={asset_ver('assets/js/votes.js')}" defer></script>
</body>
</html>
"""


def write_category_pages(deals: list[dict], en_map: dict, today) -> int:
    """重建 category/ 与 en/category/：先整目录删掉，再按 6 个分类各写中英两份。"""
    for base in (CATEGORY_DIR, CATEGORY_DIR_EN):
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True, exist_ok=True)

    count = 0
    for slug in CAT_META:
        cat_deals = [d for d in deals if d.get("category") == slug and d.get("status") != "expired"]
        # 高价值在前；同一价值档里新收录的在前；AI 分类再让全球通用排在地区分服之前
        cat_deals = order_category_deals(cat_deals, slug, today)
        expired_n = len([d for d in deals if d.get("category") == slug and d.get("status") == "expired"])
        for lang, base in (("zh", CATEGORY_DIR), ("en", CATEGORY_DIR_EN)):
            out = base / slug / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                compact_html(render_category_page(slug, cat_deals, expired_n, en_map, today, lang)),
                encoding="utf-8",
            )
            count += 1
    return count


# 英文页里的中文兜底扫描：CJK 汉字 + 日文假名 + 全角标点（英文页里一律不许出现）
_EN_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_EN_FW_RE = re.compile(r"[\uff00-\uffef\u3000-\u303f]")


def _json_strings(node: object, path: str = "") -> list[tuple[str, str]]:
    """把一段 JSON-LD 里的所有字符串连同它的路径摊平，方便定位到具体字段。"""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out += _json_strings(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out += _json_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        out.append((path, node))
    return out


def check_en_pages(paths: list[Path]) -> None:
    """英文产物里不能再留中日文或全角标点：命中就列出位置并拒绝发布。

    deals_en.json 漏翻一个字段、或某条只写了中文的 risk / steps，/en/d/<id>/ 就会
    把中文原文直接漏到英文页上（上一轮 Hark 复查点名了 8 页）。JSON-LD 里的机构名
    （seller.name）和英文页里的「（ ）」这类全角标点也是同一类漏网，所以这里连
    ld+json 一起解析、按字段路径报错。
    唯一的白名单是语言切换徽标「中文」：那是给英文用户回中文站的入口，必须保留。
    """
    hits: list[str] = []
    for path in paths:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")

        # 1) JSON-LD：解析后逐字段扫（不可见，但结构化数据里出现中文同样算漏翻）
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            try:
                parsed = json.loads(block.replace("<\\/", "</"))
            except json.JSONDecodeError:
                continue
            for field, value in _json_strings(parsed):
                for needle, kind in ((_EN_CJK_RE, "中文"), (_EN_FW_RE, "全角标点")):
                    m = needle.search(value)
                    if m:
                        hits.append(f"{rel}：JSON-LD {field} 里有{kind}「{value[max(0, m.start() - 12): m.start() + 12]}」")

        # 2) 可见正文：去掉注释 / script / svg / data-* 之后扫描
        body = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        body = re.sub(r"<script\b.*?</script>|<svg\b.*?</svg>", " ", body, flags=re.S)
        body = re.sub(r"\sdata-[a-zA-Z0-9-]+=\"[^\"]*\"", " ", body)
        body = body.replace("中文", "")
        for needle, kind in ((_EN_CJK_RE, "中文 / 日文"), (_EN_FW_RE, "全角标点")):
            for m in needle.finditer(body):
                snippet = re.sub(r"\s+", " ", body[max(0, m.start() - 30): m.start() + 30]).strip()
                hits.append(f"{rel}：可见文字里有{kind}…{snippet}…")
    if hits:
        print("英文页里还有中文 / 全角标点残留，已停止构建：", file=sys.stderr)
        for line in hits[:20]:
            print("  · " + line, file=sys.stderr)
        raise SystemExit(1)


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
        for key in ("url", "source_url", "aff_url"):
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
    # 英文卡片的价值胶囊：手机端只有 109px，超过 18 个字符就被省略号截断
    for deal in deals:
        badge = value_badge(value_pair(deal, en_map.get(deal["id"], {}))[1], "en")
        if len(badge) > _EN_BADGE_BUDGET:
            errors.append(
                f"{deal['id']}: 英文价值徽标 {len(badge)} 字符，超出手机端 {_EN_BADGE_BUDGET} 字符预算（{badge}）"
            )
    # 参与资格：Bank / eSIM 必填 geo_restriction（标定脚本每次都写），漏填不阻断构建，
    # 但要报出来——否则新条目会悄悄少掉详情页的「参与资格」区块（见 docs/eligibility-fields.md）
    missing_elig = [
        d["id"] for d in deals
        if d.get("category") in ("bank", "esim") and not d.get("geo_restriction")
    ]
    if missing_elig:
        print(
            f"  ! 参与资格字段未填 {len(missing_elig)} 条（Bank/eSIM 应全量标定）："
            + ", ".join(missing_elig[:8]) + ("…" if len(missing_elig) > 8 else ""),
            file=sys.stderr,
        )

    if errors:
        print("数据体检未通过，已停止构建：", file=sys.stderr)
        for line in errors[:40]:
            print("  · " + line, file=sys.stderr)
        raise SystemExit(1)


def check_descriptions(deals: list[dict], en_map: dict) -> None:
    """详情页 meta description 体检：120–156 字、不以省略号收尾、括号引号成对。

    描述是按数据拼出来的，新条目一多就可能又拼出半句；这里在构建时全量跑一遍，
    不过就不发布（Hark 复查的那 303 条硬切就是这么被钉住的）。
    """
    bad: list[str] = []
    _DESC_STATS.update({"sentence": 0, "clause": 0, "word": 0})
    for lang in ("zh", "en"):
        set_lang(lang)
        for deal in deals:
            en = en_map.get(deal["id"], {}) if lang == "en" else {}
            pick = (
                (lambda key: en.get(key) or deal.get(key) or "")
                if lang == "en"
                else (lambda key: deal.get(key) or "")
            )
            desc = seo_description(
                pick("highlight"), pick("content"), pick("conditions"),
                strip_region_bracket(pick("regions")),
            )
            problems = []
            if not (_DESC_MIN <= len(desc) <= _DESC_MAX):
                problems.append(f"{len(desc)} 字")
            if desc.endswith("…"):
                problems.append("以省略号结尾")
            if desc[-1:] in "；：;:，,":
                problems.append("以分隔标点结尾")
            if not _desc_balanced(desc):
                problems.append("括号引号不成对")
            if problems:
                bad.append(f"{lang} {deal['id']}：{"、".join(problems)} → …{desc[-24:]}")
    set_lang("zh")
    _DESC_STATS.update({"sentence": 0, "clause": 0, "word": 0})
    if bad:
        print(f"meta description 体检未通过（{len(bad)} 页），已停止构建：", file=sys.stderr)
        for line in bad[:20]:
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
    # 描述体检：452 个详情页的 meta description 必须 120–156 字、整句收尾
    check_descriptions(deals, load_en())

    # 图标：构建时落地到 assets/fav/，页面不再请求 google.com
    missing = []
    for deal in deals:
        if not ensure_favicon(deal.get("domain", "")):
            missing.append(deal.get("domain", "?"))

    load_votes_snapshot()
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

    # 「最新收录」10 格的来源去重：同一个论坛 / 站点在里面最多出现两次。
    # 很多条目是从社区原帖收录的，首页反复出现同一家论坛，对方会以为被盯着抓、
    # 转头屏蔽我们的抓取；分类分区仍是全量收录，这里只约束首页这 10 格。
    def fresh_source_domain(deal: dict) -> str:
        """条目来源域名：优先 source_url（社区原帖），否则 url；归一化常见前缀与社交站。"""
        from urllib.parse import urlsplit

        raw = (deal.get("source_url") or deal.get("url") or "").strip()
        host = ""
        try:
            host = (urlsplit(raw).hostname or "").lower()
        except ValueError:
            host = ""
        for prefix in ("www.", "m.", "old.", "amp.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        if host in ("twitter.com", "x.com"):
            host = "x.com"
        if host == "reddit.com" or host.endswith(".reddit.com"):
            host = "reddit.com"
        return host or f"unknown:{deal.get('id', '')}"

    def pick_fresh(pool: list[dict], filler: list[dict], slots: int = FRESH_SLOTS) -> list[dict]:
        """两轮挑选：先每域名 1 条，再从剩余里补，同一域名最多 2 条，最后才兜底。

        同时硬性约束同一分类在 10 格里最多 FRESH_PER_CATEGORY 条。原来只限域名，
        同一天批量收录一批免费面板（全是 cloud）就能把「最新收录」整板占满，
        读者看不到其他类的新条目；分类分区仍是全量收录，这里只约束首页这 10 格。
        挑选次序仍是入库时间倒序：够格的条目先到先得，被拦住的是超配额的那几条。
        """
        chosen: list[dict] = []
        picked: set[str] = set()
        counts: dict[str, int] = {}
        cat_counts: dict[str, int] = {}

        def category_of(deal: dict) -> str:
            return deal.get("category") or "other"

        def has_room(deal: dict) -> bool:
            return cat_counts.get(category_of(deal), 0) < FRESH_PER_CATEGORY

        def take(deal: dict) -> None:
            domain = fresh_source_domain(deal)
            chosen.append(deal)
            picked.add(deal["id"])
            counts[domain] = counts.get(domain, 0) + 1
            cat = category_of(deal)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        for deal in pool:
            if len(chosen) >= slots:
                break
            domain = fresh_source_domain(deal)
            if counts.get(domain) or not has_room(deal):
                continue
            take(deal)

        for deal in pool:
            if len(chosen) >= slots:
                break
            if deal["id"] in picked or not has_room(deal):
                continue
            domain = fresh_source_domain(deal)
            if counts.get(domain, 0) >= 2:
                continue
            take(deal)

        # 兜底：48 小时内条目不够凑满时，从全量在效条目里按时间倒序补，
        # 分类上限同样生效，域名上限同样生效。
        for deal in filler:
            if len(chosen) >= slots:
                break
            if deal["id"] in picked or not has_room(deal):
                continue
            domain = fresh_source_domain(deal)
            if counts.get(domain, 0) >= 2:
                continue
            take(deal)

        # 再兜底：只放开域名上限（分类仍是硬约束），保证板子凑满 10 格。
        for deal in filler:
            if len(chosen) >= slots:
                break
            if deal["id"] in picked or not has_room(deal):
                continue
            take(deal)

        chosen.sort(key=lambda d: d.get("added_at") or d.get("added") or "", reverse=True)
        return chosen

    active_by_time = sorted(
        active, key=lambda d: d.get("added_at") or d.get("added") or "", reverse=True
    )
    fresh = pick_fresh(fresh_pool, active_by_time)
    if len(fresh) < FRESH_SLOTS:
        cats = {d.get("category") or "other" for d in active}
        print(
            f"注意：在效条目只覆盖 {len(cats)} 个分类，最新收录仅凑到 {len(fresh)} 条"
            f"（分类上限 {FRESH_PER_CATEGORY} 条/类）",
            file=sys.stderr,
        )
    # 今天没有新条目时也保证板子不空（同样走两轮去重）
    if not fresh:
        fresh = pick_fresh(active_by_time, active_by_time)

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
        k: order_category_deals([d for d in active if d["category"] == k], k, today)
        for k in CAT_META
    }

    # 首页只内联「四个聚合分区用到的卡 + 每个分类按 S 前 HOME_CAT_CARDS 条」：
    #   · 聚合分区用的是跳转卡，点下去要滚到 #deal-<id>，所以它用到的条目必须有一张真卡在页上；
    #   · 其余按 S 分排好序取前 24 条，剩下的全部交给分类目录页。
    # 并入的聚合条目按它原本的 S 名次插回去，不堆到末尾，分类内仍是「好条目在前」。
    agg_ids = {d["id"] for d in (*fresh, *leaderboard, *closing, *lottery)}
    home_by_cat: dict[str, list[dict]] = {}
    for slug, ordered in by_cat.items():
        pos = {d["id"]: i for i, d in enumerate(ordered)}
        keep = ordered[:HOME_CAT_CARDS]
        keep_ids = {d["id"] for d in keep}
        merged = keep + [d for d in ordered if d["id"] in agg_ids and d["id"] not in keep_ids]
        if len(merged) > len(keep):
            merged.sort(key=lambda d: pos[d["id"]])
        home_by_cat[slug] = merged
    # 内联条目的 id：搜索索引只给「没内联的」条目出轻量结果行，避免同一张卡两处出现
    inline_ids = {d["id"] for lst in home_by_cat.values() for d in lst}
    # 归档区没有独立页面，超过上限就只列最近的 24 条（当前全站只有 4 条过期条目）
    archive_all = sorted(expired, key=lambda d: d.get("end") or "", reverse=True)
    archive_inline = archive_all[:HOME_ARCHIVE_CARDS]

    last_updated = meta.get("last_updated_human") or now_local().strftime("%Y-%m-%d %H:%M")
    beijing_time = last_updated if re.match(r"^\d{4}-\d{2}-\d{2}", last_updated) else now_local().strftime("%Y-%m-%d %H:%M")
    # 手机首屏只放一行：更新时间的短写法（11-19 03:20）免得挤占卡片宽度
    beijing_short = beijing_time[5:] if re.match(r"^\d{4}-\d{2}-\d{2}", beijing_time) else beijing_time
    counts = {
        # 三个胶囊对应详情页上的三种状态，相加正好等于全站条目数：
        #   active（进行中）+ expiring_soon（7 天内到期）+ expired（已归档）。
        # 以前 active 用的是「未过期」全量（含 expiring_soon），219+8+3=228 与 220 对不上。
        "active": len([d for d in active if d["status"] == "active"]),
        "expiring": len(closing_pool),
        "expired": len(expired),
        "total": len(deals),
    }

    en_map = load_en()
    missing_en = [d["id"] for d in deals if d["id"] not in en_map]
    # 内部回测表：每次构建都落一份，给「改了公式前后前 20 名怎么变」留底
    score_rows = write_score_explain(deals, en_map, today)

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

        # tab 上的计数：不再占行内宽度，改成贴按钮右上角悬浮的小胶囊（见 CSS .hot-tab b）。
        # 标签文字在前、数字在后，读屏仍是「新收录 10」。
        def hot_tab(anchor: str, key: str, on: bool) -> str:
            cls = "hot-tab on" if on else "hot-tab"
            cur = ' aria-current="true"' if on else ""
            return (
                f'<a class="{cls}" href="#{anchor}" data-tab="{anchor}"{cur}>'
                f'{ui(key)}<b data-tabcount="{anchor}">{tab_counts[anchor]}</b></a>'
            )

        # 「即将截止」tab：标签 + 一颗迷你日历小标。
        # 日历里直接印窗口天数（7 / 30，中英文同一个写法，不带「天」也不带 ⓘ）：
        #   这批全部落在 EXPIRING_DAYS 天内 → 「7」暖橙；用到 8～30 天窗口补足 → 「30」薄荷绿。
        # 小标本身是按钮：点一下弹口径吐司；不再额外占一行宽度写「30天 / 30d」或单独 ⓘ。
        # 它必须是独立 <button>——<a> 里不能嵌按钮，否则键盘 / 读屏会把它当成链接的一部分。
        window_days = CLOSING_WINDOW_DAYS if closing_used_window else EXPIRING_DAYS
        info_btn = (
            '<button class="closing-cal" type="button" aria-expanded="false" '
            'aria-controls="closing-toast" '
            f'{al(*upair("closing_info_aria", n=window_days))}>'
            f'{calendar_badge(window_days, "mint" if closing_used_window else "amber")}</button>'
        )

        def closing_tab(key: str, on: bool) -> str:
            cls = "hot-tab on" if on else "hot-tab"
            cur = ' aria-current="true"' if on else ""
            return (
                '<span class="hot-tab-unit">'
                f'<a class="{cls}" href="#closing" data-tab="closing"{cur}>'
                f'{ui(key)}<b data-tabcount="closing">{tab_counts["closing"]}</b></a>'
                f'{info_btn}</span>'
            )

        hot_board = f"""
      <div class="hot-board" id="hot" data-hot-board>
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
                module_html("ai", "ai", U["mod_ai"], U["mod_ai_desc"], home_by_cat["ai"], en_map, today,
                            cat_slug="ai", total=len(by_cat["ai"])),
                module_html("crypto", "crypto", U["mod_crypto"], U["mod_crypto_desc"], home_by_cat["crypto"], en_map, today,
                            cat_slug="crypto", total=len(by_cat["crypto"])),
                module_html("bank", "bank", U["mod_bank"], U["mod_bank_desc"], home_by_cat["bank"], en_map, today,
                            cat_slug="bank", total=len(by_cat["bank"])),
                module_html("cloud", "cloud", U["mod_cloud"], U["mod_cloud_desc"], home_by_cat["cloud"], en_map, today,
                            cat_slug="cloud", total=len(by_cat["cloud"])),
                module_html("esim", "esim", U["mod_esim"], U["mod_esim_desc"], home_by_cat["esim"], en_map, today,
                            cat_slug="esim", total=len(by_cat["esim"])),
                module_html("software", "software", U["mod_software"], U["mod_software_desc"], home_by_cat["software"], en_map, today,
                            cat_slug="software", total=len(by_cat["software"])),
                module_html(
                    "archive", "archive", U["mod_archive"], U["mod_archive_desc"],
                    archive_inline, en_map, today, total=len(archive_all),
                ),
            ]
        )

        # 搜索索引：只存当前页面的语言，四张表越小越好（它占首页 1/4 体积）。
        # 首页只内联每类前 24 条，但搜索必须仍能搜全库，所以：
        #   h 检索词（品牌 / 地区 / 门槛 / 导语头一段）；分类词表 c 按分类存一次
        #   t 标题：只给「首页没内联的在效条目」；内联卡片的标题 app.js 直接从 DOM 的 h3 上取
        #   p 首页没内联的在效条目：搜到时出一行轻量卡，点进它的 /d/<id>/ 独立页
        # 早期版本的索引是 {id: "检索词"}、{zh:…, en:…} 或带 k 的 {t,h,k,c,p}，app.js 都能读。
        def _clean(value: object) -> str:
            return re.sub(r"\s+", " ", str(value or "")).strip()

        search_t: dict[str, str] = {}
        search_h: dict[str, str] = {}
        search_p: dict[str, list] = {}
        for deal in deals:
            slug = deal.get("category", "")
            en = en_map.get(deal["id"], {})
            if is_en:
                title = en.get("title") or deal.get("title", "")
                words = (
                    en.get("brand_en") or deal.get("brand", ""),
                    en.get("regions") or deal.get("regions", ""),
                    COST_EN.get(deal.get("cost", ""), ""),
                    (en.get("highlight") or "")[:SEARCH_HIGHLIGHT_CHARS],
                )
                cost_label = COST_EN.get(deal.get("cost", ""), deal.get("cost", ""))
            else:
                title = deal.get("title", "")
                words = (
                    deal.get("brand", ""),
                    deal.get("regions", ""),
                    deal.get("cost", ""),
                    (deal.get("highlight") or "")[:SEARCH_HIGHLIGHT_CHARS],
                )
                cost_label = deal.get("cost", "")
            search_h[deal["id"]] = _clean(" ".join(str(w) for w in words))
            # 已归档条目不进结果行：它们有独立页，归档区也自己列着，不混进在效搜索
            if deal["id"] in inline_ids or deal.get("status") == "expired":
                continue
            search_t[deal["id"]] = _clean(title)
            v_zh, v_en = value_pair(deal, en)
            fav = fav_name(deal.get("domain", ""))
            search_p[deal["id"]] = [
                slug,
                cost_label,
                1 if deal.get("verified") else 0,
                str(deal.get("added_at") or added_day(deal, today)),
                str(deal.get("end") or ""),
                f"{value_expected(deal):g}",
                fav if (FAV_DIR / f"{fav}.webp").exists() else "",
                monogram_for(deal, en),
                value_badge(v_en if is_en else v_zh, "en" if is_en else "zh"),
                short_deadline(deal, today)[1 if is_en else 0],
            ]
        search_c = {
            slug: (f"{CAT_EN.get(slug, ('', ''))[0]} {CAT_EN.get(slug, ('', ''))[1]}" if is_en
                   else f"{meta['label']} {meta.get('search', '')}")
            for slug, meta in CAT_META.items()
        }
        search_json = json.dumps(
            {"t": search_t, "h": search_h, "c": search_c, "p": search_p},
            ensure_ascii=False, separators=(",", ":"),
        ).replace("</", "<\\/")


        title = EN_TITLE if is_en else "羊毛情报局 · 全球优惠 / 免费额度 / 限时活动情报"
        desc = EN_DESC if is_en else ZH_DESC
        og_title = "Deal Hunter · Global deals & free credits" if is_en else "羊毛情报局 · 全球优惠与免费额度情报"
        og_desc = EN_OG_DESC if is_en else "每日核验的全球优惠导航：AI 工具大全、Crypto 空投与积分、海外银行·U卡·跨境汇款、全球 VPS 与云资源、全球 eSIM 指南、软件与数字服务。价值、门槛、截止时间一眼看清，直达官方链接。"
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
            # 指向站内详情页（/d/<id>/ 与 /en/d/<id>/），官网站外链接留在详情页里，
            # 这样 ItemList 的每条都能落到一个我们控制的、可长期访问的页面。
            item["url"] = deal_url(deal["id"], "en" if is_en else "zh")
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
<html lang="{'en' if is_en else 'zh-CN'}" data-lang="{'en' if is_en else 'zh'}" data-today="{today.isoformat()}" data-consent-required="{CONSENT_REQUIRED}">
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
<meta name="dh-votes-base" content="{SUBMIT_ENDPOINT}">
<noscript><style>.module:not(.hot-strip) .track > .card:nth-child(n + 6){{ display: block; }}
html:not(.js) .module:not(.hot-strip) .pager-bar{{ display: none; }}</style></noscript>

<!-- Google AdSense：开通后把脚本放在这里，并给 .ad-slot 容器填入广告单元
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
-->

<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>

{sprite_svg()}
{vector_defs()}

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
      <div class="topbar-pills">
        <a class="stats-pill mint" href="#fresh" {tt(*upair('stat_active_hint', d=EXPIRING_DAYS, n=counts['expiring']))}>{ui('stat_active')} <b>{counts['active']}</b></a>
        <a class="stats-pill amber" href="#closing">{icon3d('hourglass', 'hg-i')}{ui('stat_expiring')} <b>{counts['expiring']}</b></a>
        <a class="stats-pill stone" href="#archive">{ui('stat_archived')} <b>{counts['expired']}</b></a>
      </div>
      <span class="topbar-rank-note">{ui('stat_rank_note')}</span>
    </div>
  </div>
</header>

<main id="top">
  <div class="shell">
    <section class="hero">
      <h1>{ui('hero_h1')}</h1>
      <p class="hero-tag">{ui('hero_tag')}</p>
      <a class="hero-tg" href="{TG_GROUP_URL}" target="_blank" rel="noopener noreferrer"
         {al(*U['submit_tg_aria'])} {tt(*U['submit_tg_aria'])}>{hero_tg_badge()}</a>
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

<!-- 「即将截止」口径吐司：点 tab 上那颗迷你日历显示，3.5 秒自动消失，点空白 / 再点一次也关。
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
        <button class="chip" type="button" data-value="end">{icon3d('hourglass', 'hg-i')}{ui('sort_end')}</button>
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
        <button class="chip" type="button" data-value="1">{icon3d('verified-shield', 'vs-i')}{bi('已核验', 'Verified')}</button>
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
        {telegram_svg('sd-tg-i')}
        <span>{ui('submit_tg')}</span>
      </a>
      <button class="sd-send" type="button"
              {al(*U['submit_send'])}>
        {send_badge()}
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
    {legal_footer(lang)}
    <a class="foot-top" href="#top">{ui('foot_top')}</a>
  </div>
</footer>

<script id="search-index" type="application/json">{search_json}</script>
<script src="/assets/js/app.js?v={asset_ver('assets/js/app.js')}" defer></script>
<script src="/assets/js/consent.js?v={asset_ver('assets/js/consent.js')}" defer></script>
<script src="/assets/js/votes.js?v={asset_ver('assets/js/votes.js')}" defer></script>
</body>
</html>
"""
        return compact_html(head)

    OUT.write_text(render_page("zh"), encoding="utf-8")
    EN_OUT.parent.mkdir(parents=True, exist_ok=True)
    EN_OUT.write_text(render_page("en"), encoding="utf-8")

    # 单条独立页：每条一份中文 /d/<id>/、一份英文 /en/d/<id>/（含已归档条目）
    set_lang("zh")
    pages = write_deal_pages(deals, en_map, today)
    # 6 个合规页：/about/ /privacy/ /disclosure/ 与 /en/ 下的三份
    legal_pages = write_legal_pages(today)
    # 6 大类 × 中英 = 12 个静态目录页
    cat_pages = write_category_pages(deals, en_map, today)
    # 英文产物冒烟：任何中日文残留都要在这里拦住，不带上线
    check_en_pages(
        [EN_OUT]
        + sorted(DEALS_DIR_EN.glob("*/index.html"))
        + sorted(CATEGORY_DIR_EN.glob("*/index.html"))
        + [ROOT / "en" / kind / "index.html" for kind in LEGAL_PAGES]
    )
    # 结构化数据体检：每一段 ld+json 必须是合法 JSON，Offer / HowTo 字段齐全
    schema_errors = check_jsonld(ROOT, expected_howto(deals, en_map))
    if schema_errors:
        print("JSON-LD 体检未通过，已停止构建：", file=sys.stderr)
        for line in schema_errors[:20]:
            print("  · " + line, file=sys.stderr)
        raise SystemExit(1)
    # sitemap 与详情页同时生成，保证「数据里有几条」与「站点上有几页」永远对得上
    write_sitemap(deals, today)
    print(f"index.html + en/index.html written · {len(active)} active / {len(expired)} expired / {len(fresh)} fresh")
    print(f"  单条详情页：{pages} 个（d/ 与 en/d/ 各 {pages // 2} 个）· sitemap.xml 已同步")
    print(f"  分类目录页：{cat_pages} 个（category/ 与 en/category/ 各 {cat_pages // 2} 个）")
    print(f"  合规页：{legal_pages} 个（about / privacy / disclosure 中英各一份）")
    print(
        "  meta description：整句收口 {sentence} 页 · 完整分句收口 {clause} 页 · "
        "英文按词收边补足 {word} 页；零省略号、零半词".format(**_DESC_STATS)
    )
    print(f"  内部回测表：reports/score_explain.csv（{score_rows} 行，不进站点 / sitemap）")
    print(f"  英文条目：{len(deals) - len(missing_en)}/{len(deals)} 条有翻译")
    if missing_en:
        print(f"  ! 缺少英文翻译 {len(missing_en)} 条：{', '.join(missing_en[:12])}{' …' if len(missing_en) > 12 else ''}")
    src_hits = [d for d in deals if main_link_kind(d)[0] == "source"]
    print(
        f"  主按钮：{len(src_hits)} 条指向抓取来源原帖（「原文」），"
        f"{len(deals) - len(src_hits)} 条只有官方活动页（「官网」）"
    )
    if missing:
        print(f"  ! 图标下载失败 {len(missing)} 个（回退字母块）：{', '.join(missing)}")
    else:
        print(f"  图标：{len(deals)} 个域名全部就绪（assets/fav/）")
    if "--explain" in sys.argv:
        explain_scoring(deals, today)



def write_score_explain(deals: list[dict], en_map: dict, today) -> int:
    """构建时输出内部回测表 `reports/score_explain.csv`（每次构建都重写）。

    列：id、标题、分类、V、U、A、E、G、H、T、L、R_t、Vote、Fresh、S、分类内名次。
    改公式后拿两版的前 20 名直接对比，就是回测；分数本身不在页面上显示。
    只落在 `reports/` 下：不进 sitemap、没有任何页面链接、也不进仓库
    （.gitignore 忽略 + robots.txt 屏蔽，双保险）。
    """
    SCORE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    active = [d for d in deals if d.get("status") != "expired"]
    rows: list[list[str]] = []
    for slug in CAT_META:
        ordered = order_category_deals([d for d in active if d.get("category") == slug], slug, today)
        for rank, deal in enumerate(ordered, 1):
            sc = score_deal(deal, today)
            en = en_map.get(deal["id"], {})
            title = str(deal.get("title") or en.get("title") or "")
            rows.append(
                [deal["id"], title, slug]
                + [f"{sc[k]:.3f}" for k in ("V", "U", "A", "E", "G", "H", "T", "L", "R", "vote", "fresh")]
                + [f"{sc['S']:.2f}", str(rank)]
            )
    with SCORE_REPORT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["id", "title", "category", "V", "U", "A", "E", "G", "H", "T", "L",
             "R_t", "Vote", "Fresh", "S", "rank_in_category"]
        )
        writer.writerows(rows)
    return len(rows)


def explain_scoring(deals: list[dict], today) -> None:
    """--explain：按分类打印前 12 名及全部因子，并写 build/score_debug.csv。"""
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)
    cols = ["category", "rank", "id", "S", "base", "V", "U", "A", "E", "G", "H", "T", "L", "R", "mult", "vote", "fresh", "value_expected"]
    rows = [",".join(cols)]
    active = [d for d in deals if d.get("status") != "expired"]
    print(f"\n== 打分解释（Vote 全站 {VOTE_TOTAL} 票，满 100 票才生效）==")
    for slug in CAT_META:
        ordered = order_category_deals([d for d in active if d.get("category") == slug], slug, today)
        print(f"\n-- {slug}（{len(ordered)} 条）")
        for i, deal in enumerate(ordered, 1):
            sc = score_deal(deal, today)
            rows.append(
                ",".join(
                    [slug, str(i), deal["id"]]
                    + [f"{sc[k]:.3f}" for k in ("S", "base", "V", "U", "A", "E", "G", "H", "T", "L", "R", "mult", "vote", "fresh")]
                    + [f"{value_expected(deal):g}"]
                )
            )
            if i <= 12:
                print(
                    f"  {i:2d}. {sc['S']:5.1f} | base {sc['base']:5.1f} ×{sc['mult']:.3f} ×R{sc['R']:.2f}"
                    f" +f{sc['fresh']:.1f} | G{sc['G']:.2f} E{sc['E']:.2f} A{sc['A']:.1f} | {deal['title'][:66]}"
                )
    (out_dir / "score_debug.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"\n  明细已写入 build/score_debug.csv（{len(rows) - 1} 行）")


if __name__ == "__main__":
    main()
