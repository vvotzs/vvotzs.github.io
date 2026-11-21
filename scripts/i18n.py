#!/usr/bin/env python3
"""羊毛情报局 — 界面文案（中英成对维护，构建时按页面语言取一侧）。

界面文案全部以 (中文, English) 成对存放，build_site.py 渲染 `/` 时只取中文、
渲染 `/en/` 时只取英文（经 `bi()` / `ui()`），页面里只有一份 DOM，不再成对内联。
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
    # 顶栏胶囊只数 status=active；7 天内到期的那批单独算在「即将截止」里，
    # 悬停 / 读屏能看到这个口径，三个数字相加才等于全站条目数。
    "stat_active_hint": ("不含 {d} 天内即将截止的 {n} 条", "Excludes the {n} ending within {d} days"),
    "stat_expiring": ("即将截止", "Ending"),
    "stat_archived": ("已归档", "Archived"),
    # 胶囊组正下方那行 10px 小字：说明站内排序是 AI 综合打分的结果（不另起区块）
    "stat_rank_note": ("排序由 AI 综合打分生成", "Ranked by AI scoring"),
    "lang_switch": ("EN", "中文"),
    "lang_switch_aria": ("切换为英文版", "Switch to Chinese"),
    # 首屏
    "hero_h1": ("羊毛情报局", "Deal Hunter"),
    "hero_tag": ("全球高值羊毛 • 先看重点",
                 "Verified freebies & rewards"),
    # 首屏行内的 Telegram 群徽标是纯 SVG 图形（无可见文字），文案只用在 aria-label / title 上
    # （复用下面的 submit_tg_aria），不再需要长短两种可见写法。
    "updated": ("北京时间 {t} 更新", "Updated {t} (UTC+8)"),
    "updated_short": ("{t} 更新", "Updated {t}"),
    # 右侧滑轨（英文用 2–4 字母，避免撑宽 44px 的滑轨）
    "nav_hot": ("发现", "Discover"),
    "nav_ai": ("AI", "AI"),
    "nav_crypto": ("币", "Coin"),
    "nav_bank": ("卡", "Card"),
    "nav_cloud": ("云", "VPS"),
    "nav_esim": ("eSIM", "eSIM"),
    "nav_software": ("软件", "App"),
    "nav_archive": ("归档", "Old"),
    "nav_top": ("顶部", "Top"),
    "nav_aria": ("分区导航", "Section navigation"),
    # 滑轨正上方的投稿按钮（原生弹窗）
    "nav_submit": ("投稿", "Submit"),
    "nav_submit_aria": ("投稿优惠情报，打开投稿表单", "Submit a deal — open the submission form"),
    # 投稿弹窗（Gmail 写信风格：横线分行，左标签右输入）
    "submit_title": ("投稿", "Submit"),
    "submit_aria": ("投稿优惠情报", "Submit a deal"),
    "submit_name": ("名称", "Name"),
    "submit_ph_name": ("优惠名称", "Deal name"),
    "submit_link": ("链接", "Link"),
    "submit_ph_link": ("https:// 活动或来源链接", "https:// offer or source link"),
    "submit_region": ("地区", "Region"),
    "submit_ph_region": ("全球 / 美区 / 英区 / 日区 / 韩区", "Global / US / UK / JP / KR"),
    "submit_ph_notes": ("亮点与门槛说明（选填）…", "Highlights & requirements (optional)…"),
    "submit_tg": ("交流群", "TG Group"),
    "submit_tg_aria": ("加入 Telegram 交流群", "Join the Telegram group"),
    "submit_send": ("提交", "Send"),
    "submit_need_name": ("请填写优惠名称", "Please add a deal name"),
    "submit_need_link": ("请填写活动或来源链接", "Please add an offer or source link"),
    "submit_failed": ("没发出去，检查网络再试一次", "Couldn't send — check your connection and try again"),
    "submit_wait": ("刚提交过，请等几秒再试", "Just sent — please wait a few seconds"),
    "submit_success": ("已收到！核验后会尽快收录 ✨", "Received! We'll verify and list it soon."),
    "submit_again": ("再投一条", "Submit another"),
    # 热榜 tab / 分区标题与说明
    "tab_fresh": ("最新收录", "New"),
    "tab_rank": ("高价值榜", "Top"),
    "tab_closing": ("即将截止", "Closing"),
    "tab_lottery": ("抽奖", "Prizes"),
    "tab_fresh_long": ("最新收录", "New"),
    "tab_rank_long": ("高价值榜", "Top value"),
    "tab_closing_long": ("即将截止", "Closing soon"),
    "tab_lottery_long": ("抽奖 / 高上限", "Lotteries"),
    "hot_aria": ("热榜", "Leaderboards"),
    "mod_fresh": ("最新收录", "Just added"),
    "mod_fresh_desc": ("最近 {h} 小时最新收录、且仍在进行的优惠，按收录时间倒序。点一条即可跳到分类里的完整详情。",
                       "Added in the last {h} hours and still live, newest first. Tap one to jump to its full details."),
    "mod_rank": ("高价值榜", "Top value"),
    "mod_rank_desc": ("按可预期到手金额排序（抽奖类按期望值折算），先挑最值钱的。",
                      "Ranked by expected cash value (lotteries by expected value, not the headline cap)."),
    "mod_closing": ("即将截止", "Closing soon"),
    # 「即将截止」的口径说明：tab 上的 ⓘ 点开就是这个（也留在分区头里给搜索引擎与读屏）。
    "closing_info": ("{d} 天内到期的排最前，不足 {n} 条时用 {w} 天内的补足；tab 上那颗小日历里的数字就是这批用到的窗口天数（这批约 {w} 天）；顶栏数字只数 {d} 天内。",
                     "{d}-day deals come first, filled to {n} from the {w}-day window; the number in the little calendar at the tab is the window this batch used (about {w} days); the top-bar number counts {d}-day deals only."),
    # tab 上迷你日历里印的窗口天数：{d} 或 {w}（中英文同一个写法，不带单位）。
    "closing_badge_d": ("{d}", "{d}"),
    "closing_badge_w": ("{w}", "{w}"),
    "closing_info_aria": ("即将截止的排序与计数口径（这批用到 {n} 天窗口）",
                          "How closing-soon deals are ranked (this batch uses the {n}-day window)"),
    "mod_lottery": ("抽奖 / 高上限", "Lotteries & high caps"),
    "mod_lottery_desc": ("上限很高、到手看运气的抽奖与阶梯任务，按上限金额排序，别按上限做预算。",
                         "High headline caps where the payout is luck-based; ranked by cap — don't budget on it."),
    "mod_ai": ("AI 工具大全", "AI Tools & Credits"),
    "mod_ai_desc": ("ChatGPT、Gemini、Claude、Copilot、Cursor 等免费额度与限时赠送，含学生专属。",
                    "Free tiers, credits and student plans for ChatGPT, Gemini, Claude, Copilot, Cursor and more."),
    "mod_crypto": ("Crypto 空投与积分", "Crypto Airdrops & Points"),
    "mod_crypto_desc": ("交易所新人奖励、任务空投与积分计划；奖励多为返佣券或代币，注意可提现条件。",
                        "Exchange sign-up rewards, quest airdrops and points programs; most pay in fee vouchers or tokens — check withdrawal terms."),
    "mod_bank": ("海外银行·U卡·跨境汇款", "Global Banks, Cards & Transfers"),
    "mod_bank_desc": ("开户奖励、虚拟卡返现、可双向叠加的邀请奖励（Wise / Sendwave / Taptap Send / Remitly 等）。",
                      "Account bonuses, virtual-card cashback and two-sided referral rewards (Wise / Sendwave / Taptap Send / Remitly)."),
    "mod_cloud": ("全球 VPS 与云资源", "Global VPS & Cloud"),
    "mod_cloud_desc": ("永久免费实例、新人体验金与黑五主机折扣，部署前先看清到期与回收规则。",
                       "Always-free instances, trial credits and Black Friday hosting; check expiry and reclamation rules first."),
    "mod_esim": ("全球 eSIM 指南", "Global eSIM Guide"),
    "mod_esim_desc": ("免费试用与首单折扣，每条都标出可用国家或地区与注册限制——先试网，再买大套餐。",
                      "Free trials and first-order discounts, each with its usable countries and sign-up limits — test the network before buying a big plan."),
    "mod_software": ("软件与数字服务", "Software & Digital Services"),
    "mod_software_desc": ("学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠。",
                          "Student plans, developer packs, Black Friday subscription deals and other digital services."),
    "mod_archive": ("已结束活动档案", "Ended offers archive"),
    "mod_archive_desc": ("已过期活动全部保留供查档，可按截止时间翻看历史优惠。",
                         "Every expired offer is kept for reference, latest end date first."),
    "mod_empty": ("该分类暂无符合条件的优惠", "No offers match here yet"),
    # 首页每个分类只内联前 24 条，其余走分类目录页；锚文本里带分类名（头部关键词），
    # 既是给读者的去路，也是给分类页的一条站内锚文本。英文页不得出现中文。
    "see_all": ("查看全部 {n} 条 · {name} →", "View all {n} · {name} →"),
    "see_all_aria": ("打开分类页：{name}", "Open the {name} category page"),
    # 归档区超过内联上限时的一句说明（当前只有 4 条过期活动，平时不出现）
    "archive_capped": ("已归档 {n} 条 · 仅列最近 {m} 条", "{n} archived · showing the latest {m}"),
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
    "go_official_full": ("官网", "Official"),
    "go_official_short": ("官网", "Official"),
    "go_official_aria": ("官网活动页", "Open the official offer page"),
    "actual_value": ("实际价值", "Actual value"),
    # 勾号不再用字符：改由 3D 蓝盾 SVG 承担（见 build_site.icon3d），文字只留语义
    "verified": ("已核验", "Verified"),
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
    "ends_tomorrow": ("明天截止", "Ends tomorrow"),
    # 搜索与筛选
    "modal_title": ("搜索与筛选", "Search & filter"),
    "modal_aria": ("搜索与筛选", "Search and filter"),
    "close": ("关闭", "Close"),
    "search_field_aria": ("搜索优惠", "Search deals"),
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
    "cat_software": ("软件服务", "Software & services"),
    "f_cost": ("参与门槛", "Requirements"),
    "f_verify": ("核验状态", "Verification"),
    "match_before": ("匹配 ", ""),
    "match_after": (" 条", ""),
    "match_after_en": ("", " matching"),
    "reset": ("重置", "Reset"),
    "done": ("完成", "Done"),
    # 单条独立详情页（/d/<id>/ 与 /en/d/<id>/）
    "dp_back": ("返回首页", "Back to home"),
    "dp_back_aria": ("返回羊毛情报局首页", "Back to the Deal Hunter home page"),
    "dp_crumb_aria": ("面包屑", "Breadcrumb"),
    "dp_crumb_home": ("首页", "Home"),
    "dp_switch_aria": ("查看这一条的英文版", "Read this deal in English"),
    # 合规页（about / privacy / disclosure）用「这一页」而不是「这一条」
    "page_switch_aria": ("查看这一页的英文版", "Read this page in English"),
    "page_switch_aria_zh": ("查看这一页的中文版", "Read this page in Chinese"),
    "dp_switch_aria_zh": ("查看这一条的中文版", "Read this deal in Chinese"),
    "dp_switch": ("EN", "中文"),
    "dp_status_active": ("进行中", "Live"),
    "dp_status_soon": ("即将截止", "Ending soon"),
    "dp_status_expired": ("已结束 · 归档", "Ended · archived"),
    "dp_archived": (
        "已归档：活动已于 {d} 结束，本页内容仅作查档参考，官方入口可能已失效。",
        "Archived: this offer ended on {d}. Details are kept for reference and the official page may no longer work.",
    ),
    "dp_facts_status": ("状态", "Status"),
    "dp_facts_deadline": ("截止时间", "Deadline"),
    "dp_facts_period": ("活动时间", "Period"),
    "dp_facts_check": ("核验状态", "Verification"),
    "dp_facts_cost": ("参与门槛", "Requirement"),
    "dp_facts_value": ("实际价值", "Actual value"),
    "dp_highlight": ("亮点", "Highlight"),
    "dp_risk": ("风险提示", "Watch out"),
    "dp_content": ("优惠内容", "What you get"),
    "dp_eligibility": ("参与资格", "Eligibility"),
    "dp_source_block": ("来源与核验", "Source & verification"),
    "dp_official": ("前往官方活动页", "Open the official offer"),
    "dp_source_post": ("来源原帖", "Source post"),
    "dp_more": ("相关推荐", "Related deals"),
    "dp_more_all": ("查看全部优惠", "Browse all deals"),
    "dp_permalink": ("详情页", "Detail page"),
    # 首页 220 个「详情页 ↗」链向不同条目，读屏 / 搜索却念成同一句：
    # 给每条带上标题做 aria-label，可见文字保持简洁不变。
    "dp_permalink_aria": ("{t} · 详情页", "{t} · detail page"),
    "dp_link_aria": ("在新标签页打开", "opens in a new tab"),
    "dp_related_aria": ("相关推荐", "Related deals"),
    # 分类目录页（/category/<slug>/ 与 /en/category/<slug>/）
    "cat_count": ("{n} 条进行中的优惠", "{n} live offers"),
    "cat_sort_note": ("按可预期到手价值排序", "Sorted by expected value"),
    "cat_other": ("浏览其他分类", "Browse other categories"),
    "cat_aria": ("分类目录", "Category contents"),
    "cat_all_home": ("首页看全部优惠", "All deals on the home page"),
    "cat_empty": ("该分类暂无进行中的优惠", "No live offers in this category yet"),
    "cat_archive_note": ("该分类另有 {n} 条已结束活动，仍保留在归档里可随时回查。",
                         "{n} ended offers from this category are kept in the archive."),
    "cat_archive_link": ("查看归档", "Open the archive"),
    "cat_open": ("查看该分类全部优惠", "Browse this category"),
    "cat_switch_aria": ("查看这一分类的英文版", "Read this category in English"),
    "cat_switch_aria_zh": ("查看这一分类的中文版", "Read this category in Chinese"),
    # 已归档详情页顶部的「替代优惠」模块
    "alt_head": ("该活动已结束，推荐查看同类最新替代优惠",
                 "This offer has ended — check out active alternatives in the same category"),
    "alt_aria": ("同类替代优惠", "Alternative offers in the same category"),
    "dp_deadline_left": ("{d} 截止 · 剩 {n} 天", "Ends {d} · {n} days left"),
    "dp_deadline_only": ("{d} 截止", "Ends {d}"),
    "dp_deadline_ended": ("已于 {d} 结束", "Ended {d}"),
    # 页脚
    "foot_brand": ("羊毛情报局 · © {y}", "Deal Hunter · © {y}"),
    "foot_updated": ("更新 {t}", "Updated {t}"),
    "foot_top": ("回到顶部 ↑", "Back to top ↑"),
    # 页脚只加这三个词，不做免责长句（Jun 的偏好：页脚保持紧凑）
    "legal_about": ("关于", "About"),
    "legal_privacy": ("隐私", "Privacy"),
    "legal_disclosure": ("披露", "Disclosure"),
    "legal_aria": ("站点信息", "Site information"),
    "legal_updated": ("最后更新 {d}", "Last updated {d}"),
    "legal_nav_aria": ("站点信息页面", "Site information pages"),
    # 页脚 Cookie 设置按钮（点开同意面板）与推广 / 返佣小标
    "cookie_settings": ("Cookie 设置", "Cookie Settings"),
    "cookie_settings_aria": ("打开 Cookie 设置，管理统计与广告同意", "Open Cookie Settings to manage analytics and ads consent"),
    "aff_badge": ("推广", "Aff"),
    "aff_badge_full": ("推广链接", "Affiliate link"),
    "aff_note": (
        "本条目含推广链接；通过它注册或下单不会增加你的费用。",
        "This entry contains an affiliate link. Using it costs you nothing extra.",
    ),
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
    "ai": ("AI Tools & Credits", "AI tools credits artificial intelligence free tiers"),
    "crypto": ("Crypto Airdrops & Points", "Crypto airdrops points tokens cryptocurrency"),
    "bank": ("Global Banks, Cards & Transfers", "bank card remittance transfer overseas global"),
    "cloud": ("Global VPS & Cloud", "cloud VPS hosting server credits"),
    "esim": ("Global eSIM Guide", "eSIM data plan roaming guide"),
    "software": ("Software & Digital Services", "software digital services student"),
}

# 分类目录页文案：每个分类一份独立标题 / 导语 / meta description（中英各一）。
# 英文元数据只用于 /en/category/<slug>/，不得出现中文（check_en_pages 会扫）。
# desc 就是那一页的 meta description：中文≥120 字、英文≥120 字符，各自独立不靠拼接。
CATEGORY_PAGE: dict[str, dict[str, tuple[str, str]]] = {
    "ai": {
        "h1": ("AI 工具大全", "AI Tools & Credits"),
        "title": ("AI 工具大全：免费额度、学生优惠与 API Credits 合集 · 羊毛情报局",
                  "AI tools & credits: free tiers, student plans and API credits · Deal Hunter"),
        "lead": (
            "AI 工具大全收录 ChatGPT、Gemini、Claude、Cursor、Copilot 等 AI 工具与智能代理的免费额度、学生优惠"
            "和限时折扣，逐条核验后收录，标清实际到手价值、可用地区与截止时间。",
            "AI Tools & Credits collects free tiers, student plans and limited-time discounts for ChatGPT, Gemini, "
            "Claude, Cursor, Copilot and other AI tools and agents — each one verified, with expected value, "
            "region and deadline.",
        ),
        "desc": (
            "AI 工具大全：ChatGPT、Gemini、Claude、Cursor、Copilot 等 AI 工具与智能代理的免费额度、学生优惠和"
            "限时折扣，逐条核验后收录，标清实际到手价值、可用地区与截止时间。列表按可预期到手价值排序，"
            "涵盖 API 额度、订阅减免与新品首发活动。",
            "AI Tools & Credits: free tiers, student plans and discounts for ChatGPT, Gemini, Claude, Cursor and "
            "Copilot, each verified with value and deadline.",
        ),
    },
    "bank": {
        "h1": ("海外银行·U卡·跨境汇款", "Global Banks, Cards & Transfers"),
        "title": ("海外银行·U卡·跨境汇款：开户奖励 / 虚拟卡返现 / 汇款邀请合集 · 羊毛情报局",
                  "Global banks, cards & transfers: account bonuses, card cashback and remittance · Deal Hunter"),
        "lead": (
            "海外银行·U卡·跨境汇款收录开户奖励、虚拟卡（U 卡）返现与跨境汇款邀请奖励，含 Wise、Remitly、"
            "Taptap Send、Sendwave 等可双向叠加的通道，写清入金门槛、留存期与到账时间。",
            "Global Banks, Cards & Transfers collects account bonuses, virtual-card cashback and two-sided "
            "referral rewards from Wise, Remitly, Taptap Send, Sendwave and more — with deposit thresholds, "
            "holding periods and payout timing.",
        ),
        "desc": (
            "海外银行·U卡·跨境汇款：开户奖励、虚拟卡（U 卡）返现与跨境汇款邀请奖励，含 Wise、Remitly、"
            "Taptap Send、Sendwave "
            "等可双向叠加的通道，写清入金门槛、留存期与到账时间。每条都注明是否需要美国 / 英国 / 德国等区服身份与税号。",
            "Global Banks, Cards & Transfers: account bonuses, virtual-card cashback and two-sided remittance "
            "referrals, with deposit thresholds and holding periods.",
        ),
    },
    "crypto": {
        "h1": ("Crypto 空投与积分", "Crypto Airdrops & Points"),
        "title": ("Crypto 空投与积分：空投任务 / 交易所新人奖励 / 积分计划合集 · 羊毛情报局",
                  "Crypto airdrops & points: quests, exchange sign-up rewards and points · Deal Hunter"),
        "lead": (
            "Crypto 空投与积分收录交易所新人奖励、任务空投与积分计划，含 KYC 门槛、交易量要求与代币解锁规则；"
            "奖励多为返佣券或代币，到手金额不等于现金。",
            "Crypto Airdrops & Points collects exchange sign-up rewards, quest airdrops and points programs, "
            "with KYC steps, volume requirements and token unlock rules — most payouts arrive as fee vouchers "
            "or tokens, not cash.",
        ),
        "desc": (
            "Crypto 空投与积分：交易所新人奖励、任务空投与积分计划，含 KYC 门槛、交易量要求与代币解锁规则；奖励多为"
            "返佣券或代币，到手金额不等于现金。每条标出充值、交易量与可提现条件，并注明区服与身份限制；"
            "加密资产波动大，请按可预期到手价值而不是宣传上限判断。",
            "Crypto Airdrops & Points: exchange sign-up rewards, quest airdrops and points programs, with KYC "
            "steps, volume requirements and what can be withdrawn.",
        ),
    },
    "cloud": {
        "h1": ("全球 VPS 与云资源", "Global VPS & Cloud"),
        "title": ("全球 VPS 与云资源：永久免费实例 / 体验金 / 黑五主机折扣合集 · 羊毛情报局",
                  "Global VPS & cloud: free instances, trial credits and hosting deals · Deal Hunter"),
        "lead": (
            "全球 VPS 与云资源收录永久免费实例、新人体验金与黑五主机折扣，覆盖 Oracle、AWS、GCP、Azure、"
            "Hetzner、Cloudflare 等主流云与主机商，写清配额、到期与回收规则。",
            "Global VPS & Cloud collects always-free instances, trial credits and Black Friday hosting deals from "
            "Oracle, AWS, GCP, Azure, Hetzner, Cloudflare and more — with quotas, expiry and reclamation rules "
            "spelled out.",
        ),
        "desc": (
            "全球 VPS 与云资源：永久免费实例、新人体验金与黑五主机折扣，覆盖 Oracle、AWS、GCP、Azure、Hetzner、"
            "Cloudflare 等主流云与主机商，写清配额、到期与回收规则。免费额度通常需要绑卡验证，并有闲置回收或"
            "流量上限，避免试用结束后被扣费。",
            "Global VPS & Cloud: always-free instances, trial credits and hosting deals from Oracle, AWS, GCP, "
            "Azure, Hetzner and Cloudflare, with quotas spelled out.",
        ),
    },
    "esim": {
        "h1": ("全球 eSIM 指南", "Global eSIM Guide"),
        "title": ("全球 eSIM 指南：免费流量 / 首单折扣与可用国家整理 · 羊毛情报局",
                  "Global eSIM guide: free data, first-order discounts and coverage · Deal Hunter"),
        "lead": (
            "全球 eSIM 指南收录免费试用流量与首单折扣，覆盖 Airalo、Holafly、Nomad、Saily、Ubigi 等，"
            "逐条标出可用国家或地区、流量额度与注册限制。",
            "Global eSIM Guide collects free trial data and first-order discounts from Airalo, Holafly, Nomad, "
            "Saily, Ubigi and others, each labelled with usable countries, data allowance and sign-up limits.",
        ),
        "desc": (
            "全球 eSIM 指南：免费试用流量与首单折扣，覆盖 Airalo、Holafly、Nomad、Saily、Ubigi 等，逐条标出可用"
            "国家或地区、流量额度与注册限制。多数免费流量要求新用户身份或绑定支付方式，建议先领小额试用测一下"
            "当地网速再决定。",
            "Global eSIM Guide: free trial data and first-order discounts from Airalo, Holafly, Nomad, Saily and "
            "Ubigi, with usable countries and sign-up limits.",
        ),
    },
    "software": {
        "h1": ("软件与数字服务", "Software & Digital Services"),
        "title": ("软件与数字服务：学生免费计划 / 开发者礼包 / 订阅折扣合集 · 羊毛情报局",
                  "Software & digital services: student plans, developer packs and deals · Deal Hunter"),
        "lead": (
            "软件与数字服务收录学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠，覆盖 JetBrains、"
            "Notion、Figma、GitHub 等常用工具，写清资格审核与续期方式。",
            "Software & Digital Services collects student plans, developer packs, Black Friday subscription deals "
            "and other digital services from JetBrains, Notion, Figma, GitHub and more, with eligibility checks "
            "and renewal rules.",
        ),
        "desc": (
            "软件与数字服务：学生免费计划、开发者礼包、黑五订阅折扣与其他数字服务优惠，覆盖 JetBrains、Notion、"
            "Figma、GitHub 等常用工具，写清资格审核与续期方式。学生与教育优惠通常需要校园邮箱或学籍证明，"
            "审核通过后按年续期；商业授权与团队席位另作标注。",
            "Software & Digital Services: student plans, developer packs and subscription discounts for JetBrains, "
            "Notion, Figma, GitHub and more, with renewal rules.",
        ),
    },
}

# ---------------------------------------------------------------- 合规页面（AdSense）
# /about/ /privacy/ /disclosure/ 各一中一英，纯静态生成：面包屑、canonical、hreflang、
# 一段 WebPage + BreadcrumbList 结构化数据。页脚只放一行「关于 · 隐私 · 披露」文字链接，
# 不往页脚里塞免责长句（Jun 的要求：页脚保持紧凑、不撑高）。
# 文案里的事实（纯静态无后端、无自有推广链接、投稿字段）跟实现一致，改实现时同步改这里。
LEGAL_UPDATED = "2026-11-21"

LEGAL_PAGES: dict[str, dict[str, dict]] = {
    "about": {
        "zh": {
            "title": "关于羊毛情报局 · 人工核验的全球优惠情报",
            "desc": (
                "羊毛情报局是一个人工核验的全球优惠情报站，覆盖 AI 工具大全、Crypto 空投与积分、"
                "海外银行·U卡·跨境汇款、全球 VPS 与云资源、全球 eSIM 指南、软件与数字服务六大分区，"
                "每条写明价值、门槛、地区与截止时间，主按钮直达官方活动页。"
                "过期活动会留在归档页，方便对照往年力度。"
            ),
            "h1": "关于羊毛情报局",
            "lead": "一个人工核验的全球优惠情报站：只收录能追到官方条款的活动。",
            "sections": [
                ("这是什么", [
                    "羊毛情报局是一个人工核验的全球优惠情报站，覆盖六大分区：AI 工具大全、Crypto 空投与积分、"
                    "海外银行·U卡·跨境汇款、全球 VPS 与云资源、全球 eSIM 指南、软件与数字服务。",
                    "每条都写明可预期到手价值、参与门槛、可用地区与截止时间，主按钮直接指向官方活动页；"
                    "有社区原帖作为最早情报来源时，另给一个「原文链接」指过去。",
                ]),
                ("怎么核验", [
                    "先追到活动官网的条款页，核对金额、资格、截止时间、发放与追回条件；再读社区实测"
                    "（美卡论坛、NodeSeek、Linux.do、r/beermoneyuk、OzBargain、X 等），确认活动是否已经失效、"
                    "有没有隐藏门槛或风控砍单。",
                    "两边对不上时以官方条款为准，差异写进「风险」一栏；确实核不到的部分标为待核实，不写成确定事实。",
                ]),
                ("更新频率", [
                    "站点每 2.5 小时自动巡检一轮：发现新活动、回溯官网核验、把 7 天内即将截止的条目单独标出。"
                    "过期活动不会被删掉，而是移入归档页并保留历史记录，旧链接继续可访问。",
                ]),
                ("投稿与纠错", [
                    "发现新活动，或发现某条写错了、链接失效了，都可以写信到 vvotzs@gmail.com，"
                    "或点首页右下角的「投稿」按钮提交。",
                    "投稿会先回溯官网核验，通过后才收录，并在「来源」里注明来自投稿。投稿只需要名称、链接，"
                    "以及可选的地区与说明，不需要提供任何账号信息。",
                ]),
            ],
        },
        "en": {
            "title": "About Deal Hunter · verified global deals",
            "desc": (
                "Deal Hunter is a hand-checked directory of global deals, each with its value, requirements, "
                "region and deadline and a link to the official page."
            ),
            "h1": "About Deal Hunter",
            "lead": "A hand-checked directory of global deals: only offers we can trace to official terms.",
            "sections": [
                ("What this is", [
                    "Deal Hunter is a hand-checked directory of global deals in six sections: AI Tools & Credits, "
                    "Crypto Airdrops & Points, Global Banks, Cards & Transfers, Global VPS & Cloud, Global eSIM "
                    "Guide, and Software & Digital Services.",
                    "Every entry lists the expected value, the requirements, the regions it works in and the "
                    "deadline, and its main button goes to the official offer page. Where a community thread "
                    "broke the news first, a second link points to that original post.",
                ]),
                ("How we check", [
                    "We start from the brand's own terms page and verify the amount, eligibility, end date, "
                    "payout and clawback rules, then read community reports (US Card Forum, NodeSeek, Linux.do, "
                    "r/beermoneyuk, OzBargain, X) to see whether the offer is already dead, has a hidden catch, "
                    "or gets declined on risk checks.",
                    "Where the two disagree, the official terms win and the difference goes into the risk note. "
                    "Anything we cannot confirm is marked unverified instead of being stated as fact.",
                ]),
                ("Update cadence", [
                    "The site re-checks every 2.5 hours: new offers are found and verified against the official "
                    "page, and entries ending within 7 days are flagged separately. Expired offers are moved to "
                    "the archive rather than deleted, so their links keep working.",
                ]),
                ("Submissions and corrections", [
                    "If you spot a new offer, or an entry that is wrong or has a dead link, write to "
                    "vvotzs@gmail.com or use the Submit button on the home page.",
                    "Every submission is checked against the official page before it is listed, and the source "
                    "line says it came from a reader. All we need is a name, a link, and optionally the region "
                    "and a short note; no account details.",
                ]),
            ],
        },
    },
    "privacy": {
        "zh": {
            "title": "隐私政策 · 羊毛情报局",
            "desc": (
                "羊毛情报局是纯静态站点，没有账号也没有后端数据库。本页完整说明本站当前使用的 Cookie 与本地存储、"
                "EU/EEA/UK GDPR 与加州 CCPA/CPRA 赋予你的权利、同意管理与随时撤回的方式，以及如何联系我们。"
                "本站目前不加载任何追踪或广告脚本。"
            ),
            "h1": "隐私政策",
            "lead": "本站是纯静态站点：没有账号、没有后端存储；在开启统计或广告之前，不会加载任何追踪脚本。",
            "sections": [
                ("本站不收集登录信息", [
                    "羊毛情报局是纯静态站点：没有账号、没有登录，也没有后端数据库。所有页面在发布前就构建成 HTML，"
                    "浏览本站不需要注册，也不需要提交任何个人信息。",
                ]),
                ("当前实际使用的存储", [
                    "截至本页标注的更新日期，本站不加载任何统计、广告或第三方追踪脚本，也不设置任何追踪 Cookie。",
                    "浏览器里会用到两处本地存储，都属于必要项：一是标签页级别的 sessionStorage（键名 ydj_last_sent），"
                    "只记录投稿按钮 5 秒防重复的发送时间，关闭标签页即清除；二是本站域名下的 localStorage"
                    "（键名 dh_consent_v1），只在你调整页脚「Cookie 设置」时写入，内容是必要项、统计与广告两个开关"
                    "的状态和同意时间。",
                    "这些值只存在于你的浏览器里，不会上传到本站（本站没有可以接收它们的服务器）。清除浏览器数据即可"
                    "一并删除。",
                ]),
                ("Cookie 设置与同意", [
                    "页脚的「Cookie 设置」可以随时打开同意面板：选择「仅必要」，或分别允许统计与广告，之后随时回来修改。"
                    "面板固定悬浮在页面底部，不占用正文空间。",
                    "在你同意之前，本站不会主动加载任何统计或广告脚本；撤回同意后，已加载的第三方脚本会在下次刷新"
                    "页面时不再出现。",
                    "用浏览器隐私模式或禁用本地存储时，本站照常可以阅读，只是同意选择不会跨页面保存。",
                ]),
                ("以后可能接入的统计与广告", [
                    "如果将来接入 Google Analytics 4，它会在你同意「统计」后加载，用于了解匿名访问量与内容偏好；"
                    "如果站内投放 Google AdSense 广告，它会在你同意「广告」后加载，Google 及其合作伙伴可能通过 Cookie "
                    "或类似技术，根据你此前对本站或其他网站的访问投放广告，并收集页面、来源、设备类型与大致地区这类"
                    "匿名数据。",
                    "你可以在 Google 广告设置（google.com/settings/ads）停用个性化广告，也可以在页脚「Cookie 设置」里"
                    "撤回同意；这不会影响你阅读本站内容。",
                ]),
                ("处理的合法依据（GDPR）", [
                    "对 EU/EEA/UK 用户，我们按《通用数据保护条例》（GDPR）第 6 条处理数据：必要存储与站点安全运行"
                    "属于提供你请求的服务所必需、以及我们的正当利益（第 6(1)(b)、6(1)(f) 条）；统计与广告基于你的"
                    "同意（第 6(1)(a) 条），可以随时撤回，撤回不影响撤回前处理的合法性；投稿信息用于核验活动与必要"
                    "联系，属于第 6(1)(b)、6(1)(f) 条。",
                ]),
                ("你在 GDPR 下的权利", [
                    "你可以要求访问我们持有的与你有关的个人数据、要求更正或删除、限制或反对处理、以机器可读格式取得"
                    "副本（数据可携），并可以随时撤回同意。本站不做用户画像，也不做会产生法律效果的自动化决策。",
                    "如果认为我们的处理违反 GDPR，你可以向所在地的监管机构申诉：英国为信息专员办公室（ICO），"
                    "EU/EEA 为你所在成员国的数据保护机构。",
                    "行使上述权利请写信到 vvotzs@gmail.com 并说明请求内容；我们会在收到后一个月内答复，复杂请求最多"
                    "再延长两个月并告知原因。行使权利不收费。",
                ]),
                ("加州居民（CCPA/CPRA）", [
                    "本站不出售个人信息，也不为跨情境行为广告而共享（share）个人信息；过去 12 个月没有出售或共享，"
                    "也没有此类计划。本站不建立用户账号，不收集加州法律定义的敏感个人信息，也不掌握客户名单或支付信息。",
                    "加州居民有权：知情（我们收集的信息类别、来源与用途）、要求删除、要求更正、选择退出出售或共享、"
                    "限制敏感个人信息的使用，以及不因行使这些权利而受到歧视。由于本站不出售也不共享个人信息，"
                    "无需另行提供「Do Not Sell or Share My Personal Information」入口；如你仍希望提出请求，直接写信即可。",
                    "提出请求请写信到 vvotzs@gmail.com，标题写「CCPA request」，说明你想要知情、删除还是更正；"
                    "我们会在 45 天内答复，必要时再延长 45 天并说明原因。你也可以委托授权代理人提出请求，需要提供"
                    "书面授权。本站不面向 16 岁以下用户，也不会有意收集儿童的个人信息。",
                ]),
                ("投稿信息", [
                    "通过投稿表单或邮件投稿时，我们只会收到你填写的名称、链接、地区、说明，以及发件邮箱。这些信息"
                    "仅用于核验活动和必要时联系你，不会公开你的邮箱，也不会用于广告画像；投稿记录保留到核验完成并"
                    "归档后 24 个月，你可以随时来信要求提前删除。",
                ]),
                ("托管与跨境传输", [
                    "本站由 GitHub Pages 托管（GitHub, Inc.，美国）。访问时 GitHub 会按自己的日志政策处理 IP 地址、"
                    "请求时间等技术数据，这部分不受本站控制，详见 GitHub 隐私声明（docs.github.com/site-policy）。"
                    "如果这构成向美国传输数据，依据是提供你请求的页面所必需，或你对统计、广告的同意。",
                ]),
                ("外部链接", [
                    "站内链接指向品牌官网或社区原帖，这些网站的隐私做法由它们自己负责，请查看各自的隐私政策。",
                ]),
                ("政策更新", [
                    "本页顶部的日期是最后更新时间。如果以后开启统计或广告、或改变处理方式，我们会先更新本页并调整同意"
                    "设置，重大变更会在页首注明。",
                ]),
                ("联系", [
                    "隐私相关的问题、访问或删除请求，请写信到 vvotzs@gmail.com。",
                ]),
            ],
        },
        "en": {
            "title": "Privacy policy · Deal Hunter",
            "desc": (
                "Deal Hunter is a static site with no accounts. This policy covers cookies and storage, "
                "GDPR and CCPA/CPRA rights, consent choices and how to contact us."
            ),
            "h1": "Privacy policy",
            "lead": "A static site with no accounts and no server-side storage; no tracking script loads until you allow analytics or ads.",
            "sections": [
                ("No sign-in data", [
                    "Deal Hunter is a static site: there are no accounts, no sign-in and no backend database. Every page "
                    "is built as plain HTML before publishing, so reading the site needs no sign-up and no personal details.",
                ]),
                ("What we actually store", [
                    "As of the update date shown on this page, the site loads no analytics, advertising or third-party "
                    "tracking script, and sets no tracking cookies.",
                    "Two local values are used, both necessary: a tab-level sessionStorage entry (key ydj_last_sent) that "
                    "only records when you last sent a submission, so the button ignores double taps for 5 seconds and "
                    "expires when the tab closes; and a localStorage entry on this site (key dh_consent_v1) written only "
                    "when you change Cookie Settings, holding the necessary flag, your analytics and ads switches, and the "
                    "time you chose.",
                    "Both stay in your browser and are never uploaded here, because there is no server to receive them. "
                    "Clearing your browser data deletes them.",
                ]),
                ("Cookie settings and consent", [
                    "Cookie Settings in the footer opens the consent panel at any time: choose Essential only, or allow "
                    "analytics and ads separately, and change it whenever you like. The panel floats over the bottom of "
                    "the page and takes no space in the layout.",
                    "No analytics or ad script loads before you agree, and after you withdraw consent any third-party "
                    "script that was loaded stops appearing on the next page load.",
                    "With private browsing or storage disabled the site still reads normally; only the saved choice is "
                    "not kept between pages.",
                ]),
                ("Analytics and ads, if we add them", [
                    "If Google Analytics 4 is added later, it will load only after you allow analytics, to measure "
                    "anonymous traffic and see which pages help. If Google AdSense ads run here, they will load only "
                    "after you allow ads; Google and its partners may then use cookies or similar technologies to serve "
                    "ads based on your earlier visits to this or other websites, and may collect anonymous data such as "
                    "page, referrer, device type and rough region.",
                    "You can turn off personalised advertising in Google Ads Settings (google.com/settings/ads), or "
                    "withdraw consent in Cookie Settings. Either way the site stays readable.",
                ]),
                ("Legal bases (GDPR)", [
                    "For users in the EU/EEA/UK we process data under Article 6 of the General Data Protection Regulation: "
                    "necessary storage and keeping the site secure are needed to provide the pages you ask for and rest "
                    "on our legitimate interests (Art. 6(1)(b) and 6(1)(f)); analytics and advertising rest on your "
                    "consent (Art. 6(1)(a)), which you can withdraw at any time without affecting processing that "
                    "already happened; submission details are used to verify an offer and reply if needed, under "
                    "Art. 6(1)(b) and 6(1)(f).",
                ]),
                ("Your rights under the GDPR", [
                    "You can ask for access to the personal data we hold about you, ask us to correct or delete it, "
                    "restrict or object to processing, receive a portable copy, and withdraw consent at any time. We do "
                    "not profile readers or make automated decisions with legal effects.",
                    "If you believe our processing breaks the GDPR, you can complain to your local supervisory "
                    "authority: the Information Commissioner's Office (ICO) in the UK, or the data protection authority "
                    "of your EU/EEA member state.",
                    "To exercise these rights, write to vvotzs@gmail.com with what you want. We answer within one month "
                    "of receiving the request, and for complex requests may extend that by up to two further months "
                    "with an explanation. Exercising your rights is free.",
                ]),
                ("California residents (CCPA/CPRA)", [
                    "We do not sell personal information, and we do not share it for cross-context behavioural "
                    "advertising; we have not done so in the past 12 months and have no plans to. The site has no user "
                    "accounts, collects no sensitive personal information as defined by California law, and holds no "
                    "customer lists or payment details.",
                    "California residents have the right to know (the categories of information collected, their sources "
                    "and purposes), to delete, to correct, to opt out of sale or sharing, to limit the use of sensitive "
                    "personal information, and not to be discriminated against for exercising these rights. Because we "
                    "neither sell nor share personal information, a separate Do Not Sell or Share My Personal "
                    "Information link is not required; you can still send a request by email.",
                    "To make a request, write to vvotzs@gmail.com with the subject CCPA request and say whether you want "
                    "to know, delete or correct. We answer within 45 days, and may extend once by a further 45 days with "
                    "an explanation. You may use an authorised agent with written permission. The site is not directed "
                    "at children under 16 and we do not knowingly collect their personal information.",
                ]),
                ("Submissions", [
                    "When you submit an offer through the form or by email, we receive only the name, link, region and "
                    "note you enter, plus your sending address. That is used to verify the offer and to reply if "
                    "needed; your address is never published and never used for ad profiling. Submission records are "
                    "kept for 24 months after verification and archiving, and you can ask us to delete them sooner.",
                ]),
                ("Hosting and international transfers", [
                    "The site is hosted on GitHub Pages (GitHub, Inc., United States). GitHub processes technical data "
                    "such as IP address and request time under its own logging policy, which is outside our control; see "
                    "the GitHub Privacy Statement (docs.github.com/site-policy). Where that amounts to a transfer to the "
                    "United States, it rests on providing the pages you requested or on your consent for analytics and "
                    "ads.",
                ]),
                ("External links", [
                    "Links here point to brand sites or community posts. Their privacy practices are their own; please "
                    "read their policies.",
                ]),
                ("Changes to this policy", [
                    "The date at the top of this page is the last update. If analytics or ads are switched on, or our "
                    "processing changes, we will update this page and the consent settings first, and note material "
                    "changes at the top.",
                ]),
                ("Contact", [
                    "Privacy questions, access or deletion requests: vvotzs@gmail.com.",
                ]),
            ],
        },
    },
    "disclosure": {
        "zh": {
            "title": "链接与收录披露 · 羊毛情报局",
            "desc": (
                "羊毛情报局的链接与收录规则：主链接指向官方活动页，部分活动或产品链接可能包含推广/返佣链接，"
                "一律标注「推广」并加 rel=sponsored，不增加你的任何费用；未标注的链接没有报酬关系，"
                "所有金额、资格、截止时间与发放条件都以品牌官网条款为准。"
            ),
            "h1": "链接与收录披露",
            "lead": "主链接指向官方活动页；带推广或返佣的链接一律标注「推广」并加 rel=sponsored，不增加你的费用。",
            "sections": [
                ("收录与链接", [
                    "站内条目的主链接是官方活动页。如果活动最早来自社区（论坛、Reddit、X 等），会额外给一个"
                    "「原文链接」指向那条原帖，方便你核对信息出处。",
                ]),
                ("推广与返佣链接", [
                    "部分活动或产品链接可能包含推广或返佣链接（Affiliate / Partner links）。通过这类链接注册、下单"
                    "或充值，品牌方可能向我们支付一笔佣金；这不会增加你的任何费用，也不改变活动本身的价格、额度、"
                    "资格或条款。",
                    "所有推广链接都会在条目里明确标注「推广 / Sponsored」，并带上 rel=\"sponsored noopener\"；"
                    "没有标注的链接，代表我们与品牌方没有报酬关系。",
                ]),
                ("编辑独立性", [
                    "是否收录、怎么写、价值与风险怎么判断，只看活动能否核到官方条款，与是否有佣金无关。佣金不会让"
                    "已失效、门槛不清或条款有问题的活动进入站内，也不会让风险提示变轻。",
                ]),
                ("邀请与推荐码", [
                    "他人在社区分享的邀请码、推荐链接（例如某位投稿人自己的推荐码）不会被当作本站的「原文链接」"
                    "使用，条目只链官方页面；投稿里的推荐码不会被采用。",
                ]),
                ("金额与条款", [
                    "所有金额、资格、截止时间与发放条件都以品牌官网的条款为准。我们尽力核验，但不构成任何承诺，"
                    "活动可能随时调整或提前结束。",
                ]),
                ("纠错", [
                    "发现条目有误或链接失效，来信 vvotzs@gmail.com。",
                ]),
            ],
        },
        "en": {
            "title": "Links and listing disclosure · Deal Hunter",
            "desc": (
                "How Deal Hunter links offers: the main link goes to the official page, affiliate links are "
                "labelled and marked sponsored, at no extra cost to you."
            ),
            "h1": "Links and listing disclosure",
            "lead": "The main link goes to the official offer page; affiliate or partner links are always labelled and marked sponsored, at no extra cost to you.",
            "sections": [
                ("Linking", [
                    "The main link on every entry is the official offer page. If the offer first appeared in a "
                    "community thread (a forum, Reddit, X), a second link points to that original post so you can "
                    "check where the information came from.",
                ]),
                ("Affiliate and partner links", [
                    "Some offer or product links may be affiliate or partner links. If you sign up, buy or top up "
                    "through one of them, the brand may pay us a commission; that adds nothing to your cost and does "
                    "not change the price, amount, eligibility or terms of the offer itself.",
                    "Every affiliate link is labelled Sponsored in the entry and marked rel=\"sponsored noopener\". "
                    "A link without that label means we are paid nothing by the brand.",
                ]),
                ("Editorial independence", [
                    "Whether an offer is listed, how it is described and how its value and risks are judged depend only "
                    "on whether it can be verified against official terms, never on whether it pays. A commission does "
                    "not get an expired, unclear or flawed offer listed, and does not soften a risk note.",
                ]),
                ("Invite and referral codes", [
                    "Invite codes and referral links shared by other people, such as a submitter's own code, are never "
                    "used as the source link, and codes inside submissions are not adopted. Entries link to the "
                    "official page.",
                ]),
                ("Amounts and terms", [
                    "Amounts, eligibility, deadlines and payout conditions follow the brand's own terms. We check them "
                    "carefully but promise nothing, and an offer can change or end early.",
                ]),
                ("Corrections", [
                    "Spotted an error or a dead link? Write to vvotzs@gmail.com.",
                ]),
            ],
        },
    },
}

# 页脚那一行极简文字链接的顺序：(页面 slug, 文案 key)
LEGAL_LINKS = (("about", "legal_about"), ("privacy", "legal_privacy"), ("disclosure", "legal_disclosure"))

_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def short_date_en(value: date | None) -> str:
    return f"{_MON[value.month - 1]} {value.day}" if value else ""


def upair(key: str, **fmt) -> tuple[str, str]:
    """带占位符的界面文案对，供需要 (中文, English) 两段的渲染函数使用。"""
    zh, en = U[key]
    return (zh.format(**fmt), en.format(**fmt)) if fmt else (zh, en)


# 英文页里的全角标点：译文难免从中文站点抄来「（ ）」「；」「，」，在英文页上很扎眼，
# 读英文数据时统一换成半角（只换标点，不动数字与字母）。check_en_pages() 会在构建产物上
# 复核一遍，漏网的立刻停下构建。
_FW_PUNCT = str.maketrans({
    "（": "(", "）": ")", "【": "[", "】": "]", "《": '"', "》": '"',
    "「": '"', "」": '"', "『": '"', "』": '"',
    "，": ",", "。": ".", "、": ",", "：": ":", "；": ";",
    "！": "!", "？": "?", "“": '"', "”": '"', "‘": "'", "’": "'",
    "　": " ", "％": "%", "＋": "+", "－": "-", "／": "/", "～": "~",
    "￥": "¥",
})


def _ascii_punct(value: object) -> object:
    if isinstance(value, str):
        return value.translate(_FW_PUNCT)
    if isinstance(value, list):
        return [_ascii_punct(v) for v in value]
    if isinstance(value, dict):
        return {k: _ascii_punct(v) for k, v in value.items()}
    return value


def ascii_punct(value: object) -> object:
    """英文页用：全角标点换成半角（数字与字母不动）。"""
    return _ascii_punct(value)


def load_en() -> dict:
    """读 data/deals_en.json：{id: {title, brand_en, highlight, regions, value, content, ...}}"""
    if not EN_DATA.exists():
        return {}
    data = json.loads(EN_DATA.read_text(encoding="utf-8"))
    return {key: _ascii_punct(item) for key, item in data.items()}


def save_en(data: dict) -> None:
    EN_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
