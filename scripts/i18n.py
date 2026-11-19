#!/usr/bin/env python3
"""羊毛情报局 — 双语文案。

界面文案全部以 (中文, English) 成对存放，由 build_site.py 渲染成
<span class="t-zh">…</span><span class="t-en">…</span>，靠 <html data-lang> 切换显示。
优惠条目本身的英文放在 data/deals_en.json（与 deals.json 用 id 对应）。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_DATA = ROOT / "data" / "deals_en.json"

# 界面文案：key -> (中文, English)
U: dict[str, tuple[str, str]] = {
    # 品牌 / 顶栏
    "brand": ("羊毛情报局", "Deal Hunter"),
    "brand_sub": ("全球优惠 · 每日核验", "Global deals · verified daily"),
    "brand_aria": ("羊毛情报局 首页", "Deal Hunter home"),
    "search_open": ("搜索优惠、可用地区、类别…", "Search deals, regions, categories…"),
    "search_open_aria": ("搜索优惠、可用地区、类别", "Search deals, regions and categories"),
    "stat_active": ("进行中", "Live"),
    "stat_expiring": ("即将截止", "Ending"),
    "stat_archived": ("已归档", "Archived"),
    "lang_switch": ("EN", "中文"),
    "lang_switch_aria": ("切换为英文版", "Switch to Chinese"),
    # 首屏
    "hero_h1": ("羊毛情报局", "Deal Hunter"),
    "hero_tag": ("全球免费额度与限时奖励，先看值得点的。",
                 "Free credits and limited-time rewards — only what's worth clicking."),
    "updated": ("北京时间 {t} 更新", "Updated {t} (UTC+8)"),
    "updated_short": ("{t} 更新", "{t} updated"),
    # 右侧滑轨（英文用 2–4 字母，避免撑宽 44px 的滑轨）
    "nav_fresh": ("新收录", "New"),
    "nav_rank": ("榜单", "Top"),
    "nav_ai": ("AI", "AI"),
    "nav_crypto": ("币", "Coin"),
    "nav_bank": ("卡", "Card"),
    "nav_cloud": ("云", "VPS"),
    "nav_esim": ("eSIM", "eSIM"),
    "nav_closing": ("截止", "End"),
    "nav_software": ("软件", "App"),
    "nav_archive": ("归档", "Old"),
    "nav_top": ("顶部", "Top"),
    "nav_aria": ("分区导航", "Section navigation"),
    # 滑轨正上方的投稿按钮（Tally 弹窗）
    "nav_submit": ("投稿", "Submit"),
    "nav_submit_aria": ("投稿优惠情报，打开投稿表单", "Submit a deal — open the submission form"),
    # 热榜 tab / 分区标题与说明
    "tab_fresh": ("新收录", "New"),
    "tab_rank": ("高价值榜", "Top"),
    "tab_closing": ("即将截止", "Closing"),
    "tab_lottery": ("抽奖", "Prizes"),
    "tab_fresh_long": ("新收录", "New"),
    "tab_rank_long": ("高价值榜", "Top value"),
    "tab_closing_long": ("即将截止", "Closing soon"),
    "tab_lottery_long": ("抽奖 / 高上限", "Lotteries"),
    "hot_aria": ("热榜", "Leaderboards"),
    "mod_fresh": ("新收录", "Just added"),
    "mod_fresh_desc": ("最近 {h} 小时新收录、且仍在进行的优惠，按收录时间倒序。点一条即可跳到分类里的完整详情。",
                       "Added in the last {h} hours and still live, newest first. Tap one to jump to its full details."),
    "mod_rank": ("高价值榜", "Top value"),
    "mod_rank_desc": ("按可预期到手金额排序（抽奖类按期望值折算），先挑最值钱的。",
                      "Ranked by expected cash value (lotteries by expected value, not the headline cap)."),
    "mod_closing": ("即将截止", "Closing soon"),
    "mod_closing_desc": ("{d} 天内到期的活动，按截止时间排序；标「剩 N 天」的请优先处理。",
                         "Ending within {d} days, soonest first — handle the ones with days left first."),
    "mod_lottery": ("抽奖 / 高上限", "Lotteries & high caps"),
    "mod_lottery_desc": ("上限很高、到手看运气的抽奖与阶梯任务，按上限金额排序，别按上限做预算。",
                         "High headline caps where the payout is luck-based; ranked by cap — don't budget on it."),
    "mod_ai": ("AI 工具免费与折扣", "AI tools: free tiers & discounts"),
    "mod_ai_desc": ("ChatGPT、Gemini、Claude、Copilot、Cursor 等免费额度与限时赠送，含学生专属。",
                    "Free tiers, credits and student plans for ChatGPT, Gemini, Claude, Copilot, Cursor and more."),
    "mod_crypto": ("Crypto 空投与积分", "Crypto airdrops & points"),
    "mod_crypto_desc": ("交易所新人奖励、任务空投与积分计划；奖励多为返佣券或代币，注意可提现条件。",
                        "Exchange sign-up rewards, quest airdrops and points programs; most pay in fee vouchers or tokens — check withdrawal terms."),
    "mod_bank": ("海外银行 · U 卡 · 跨境汇款", "Banks, cards & remittance"),
    "mod_bank_desc": ("开户奖励、虚拟卡返现、可双向叠加的邀请奖励（Wise / Sendwave / Taptap Send / Remitly 等）。",
                      "Account bonuses, virtual-card cashback and two-sided referral rewards (Wise / Sendwave / Taptap Send / Remitly)."),
    "mod_cloud": ("VPS 及云服务", "VPS & cloud credits"),
    "mod_cloud_desc": ("永久免费实例、新人体验金与黑五主机折扣，部署前先看清到期与回收规则。",
                       "Always-free instances, trial credits and Black Friday hosting; check expiry and reclamation rules first."),
    "mod_esim": ("eSIM 全球流量", "eSIM data worldwide"),
    "mod_esim_desc": ("免费试用与首单折扣，每条都标出可用国家或地区与注册限制——先试网，再买大套餐。",
                      "Free trials and first-order discounts, each with its usable countries and sign-up limits — test the network before buying a big plan."),
    "mod_software": ("软件与数字服务", "Software & digital services"),
    "mod_software_desc": ("学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠。",
                          "Student plans, developer packs, Black Friday subscription deals and other digital services."),
    "mod_archive": ("已结束活动档案", "Ended offers archive"),
    "mod_archive_desc": ("已过期活动全部保留供查档，可按截止时间翻看历史优惠。",
                         "Every expired offer is kept for reference, latest end date first."),
    "mod_empty": ("该分类暂无符合条件的优惠", "No offers match here yet"),
    "pager_prev": ("上一页", "Previous page"),
    "pager_next": ("下一页", "Next page"),
    # 卡片
    "see_official": ("见官方活动页", "See the official offer page"),
    "detail_open": ("详情", "Details"),
    "detail_expand": ("展开详情", "Expand details"),
    "detail_collapse": ("收起详情", "Collapse details"),
    "go_full": ("原文链接", "Source"),
    "go_short": ("原文", "Source"),
    "go_aria": ("原文链接", "Open the source link"),
    "actual_value": ("实际价值", "Actual value"),
    "verified": ("✓ 已核验", "✓ Verified"),
    "unverified": ("待核实", "Unverified"),
    "f_what": ("优惠内容", "What you get"),
    "f_conditions": ("参与条件", "Conditions"),
    "f_regions": ("适用国家或地区", "Countries & regions"),
    "f_period": ("开始及截止时间", "Starts & ends"),
    "f_steps": ("参与步骤", "Steps"),
    "f_link": ("官方活动链接", "Official link"),
    "f_source": ("来源", "Source"),
    "f_last_verified": ("最后验证", "Last verified"),
    "f_added": ("收录", "Added"),
    "not_announced": ("官方未公布", "Not announced"),
    "ongoing_not_announced": ("长期 / 官方未公布", "Ongoing / not announced"),
    "ongoing": ("长期有效", "Ongoing"),
    "ended_word": ("已结束", "Ended"),
    "ends_today": ("今天截止", "Ends today"),
    # 搜索与筛选
    "modal_title": ("搜索与筛选", "Search & filter"),
    "modal_aria": ("搜索与筛选", "Search and filter"),
    "close": ("关闭", "Close"),
    "search_ph": ("搜活动、品牌、国家或门槛，例如 eSIM 日本 / 学生 / 免手续费",
                  "Search offers, brands, countries or requirements — e.g. eSIM Japan / student / no fees"),
    "f_time": ("时间范围", "Time"),
    "time_all": ("全部时间", "Any time"),
    "time_24h": ("近 24 小时", "Last 24h"),
    "time_48h": ("近 48 小时", "Last 48h"),
    "time_7d": ("近 7 天", "Last 7 days"),
    "time_past": ("7 天前往期", "Older / ended"),
    "f_sort": ("排序", "Sort"),
    "sort_value": ("价值优先", "Best value"),
    "sort_new": ("最新收录", "Newest"),
    "sort_end": ("最近截止", "Ending first"),
    "f_cat": ("类别", "Category"),
    "all": ("全部", "All"),
    "cat_ai": ("AI 工具", "AI tools"),
    "cat_crypto": ("Crypto", "Crypto"),
    "cat_bank": ("银行 / 卡 / 汇款", "Banks & cards"),
    "cat_cloud": ("VPS / 云", "VPS & cloud"),
    "cat_esim": ("eSIM", "eSIM"),
    "cat_software": ("软件 / 其他", "Software & other"),
    "f_cost": ("参与门槛", "Requirements"),
    "f_verify": ("核验状态", "Verification"),
    "match_before": ("匹配 ", ""),
    "match_after": (" 条", ""),
    "match_after_en": ("", " matching"),
    "reset": ("重置", "Reset"),
    "done": ("完成", "Done"),
    # 页脚
    "foot_brand": ("羊毛情报局 · © {y}", "Deal Hunter · © {y}"),
    "foot_updated": ("更新 {t}", "Updated {t}"),
    "foot_top": ("回到顶部 ↑", "Back to top ↑"),
}

# 参与门槛：数据里存中文原值（筛选按钮 data-value 也用它），展示时按语言取标签
COST_EN = {
    "真正免费": "Free",
    "免费试用": "Free trial",
    "需要充值": "Deposit req.",
    "需要交易量": "Volume req.",
    "需要邀请条件": "Referral req.",
}

# 类别标签（详情面板徽标 / 搜索索引）
CAT_EN = {
    "ai": ("AI tools", "AI tools artificial intelligence"),
    "crypto": ("Crypto", "Crypto cryptocurrency tokens"),
    "bank": ("Banks & cards", "bank card remittance transfer"),
    "cloud": ("VPS & cloud", "cloud VPS hosting server"),
    "esim": ("eSIM", "eSIM data plan roaming"),
    "software": ("Software", "software digital services"),
}

_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def short_date_en(value: date | None) -> str:
    return f"{_MON[value.month - 1]} {value.day}" if value else ""


def upair(key: str, **fmt) -> tuple[str, str]:
    """带占位符的界面文案对，供需要 (中文, English) 两段的渲染函数使用。"""
    zh, en = U[key]
    return (zh.format(**fmt), en.format(**fmt)) if fmt else (zh, en)


def load_en() -> dict:
    """读 data/deals_en.json：{id: {title, highlight, regions, value, content, conditions, steps, risk, source}}"""
    if not EN_DATA.exists():
        return {}
    return json.loads(EN_DATA.read_text(encoding="utf-8"))


def save_en(data: dict) -> None:
    EN_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
