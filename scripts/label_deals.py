#!/usr/bin/env python3
"""一次性数据标定：kyc_level / vowifi / utility（U）逐条写入 data/deals.json。

标定口径（2026-11-21 定稿，含 Jun 的补充）：
  kyc_level
    none         免 KYC（邮箱/App 注册即可）
    cn_ok        大陆身份证或护照线上可过（含香港/澳门数字银行、iFAST 英国、
                 Starryblu、UUPAY）
    cn_ok_extra  大陆证件可过，但另需海外手机号 / 海外 IP / 学生认证 / 海外卡
    foreign_only 需 SSN / ITIN / 当地税号（Steuer-ID、TIN）/ 英国 eVisa·BRP /
                 当地居留·地址证明·长期居住，或只能线下入境办理
  vowifi（仅 esim）
    true 运营商官方确认这张卡/套餐支持 Wi-Fi Calling；false 官方明确不支持；
    unknown 含号但未确认（计分按 false）；n/a 纯流量、无号码
  utility  U=1：真正免费且高普惠刚需（免费域名/容器/云电脑/接码保号），
           以及 eSIM B 案（含号 + 可云开 + 年保号 ≤¥100 + 有依据能在陆收短信）

本脚本幂等：重复运行结果一致；所有 318 条都必须落在明确标定里，漏标直接报错。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "deals.json"

# ---------------------------------------------------------------- kyc_level
KYC: dict[str, str] = {}

# 银行 / 钱包 / 券商 / 汇款 80 条
KYC.update(
    {
        # 美区：SSN / ITIN / 美国地址 / 美国身份
        "clearstreet-3pct-cash-match": "foreign_only",
        "usbank-business-checking-1500": "foreign_only",
        "raisin-stack-welcome-bonus-1000": "foreign_only",
        "apple-card-double-daily-cash": "foreign_only",
        "capital-one-360-checking-400": "foreign_only",
        "citizens-bank-400-checking": "foreign_only",
        "sofi-checking-400-direct-deposit": "foreign_only",
        "chase-total-checking-400": "foreign_only",
        "td-bank-checking-300": "foreign_only",
        "ally-spending-300": "foreign_only",
        "etrade-premium-savings-200": "foreign_only",
        "rakuten-alliant-checking-200": "foreign_only",
        "schwab-referral-brokerage-1000": "foreign_only",
        "onepay-50-signup-bonus": "foreign_only",
        "moomoo-us-black-friday-2026": "foreign_only",
        "remitly-us-global-card": "foreign_only",
        # 英区：英国居民 / 地址 / 税务居民
        "hsbc-premier-switch-500": "foreign_only",
        "barclays-uk-switch-300": "foreign_only",
        "santander-everyday-switch-240": "foreign_only",
        "hsbc-uk-bank-account-switch-220": "foreign_only",
        "first-direct-1st-account-switch-210": "foreign_only",
        "club-lloyds-switch-200": "foreign_only",
        "natwest-select-switch-200": "foreign_only",
        "rbs-select-reward-switch-200": "foreign_only",
        "investengine-referral-20-200": "foreign_only",
        "coop-bank-switch-200": "foreign_only",
        "nationwide-flexaccount-switch-175": "foreign_only",
        "robinhood-uk-free-stock": "foreign_only",
        "jpm-personal-investing-invest-1000-100": "foreign_only",
        "quilter-invest-isa-100": "foreign_only",
        "freetrade-free-share-10-100": "foreign_only",
        "raisin-uk-refer-friend-100": "foreign_only",
        "fidelity-uk-refer-100-amazon": "foreign_only",
        "tide-business-referral-100": "foreign_only",
        "chase-uk-referral-50": "foreign_only",
        "chip-uk-referral-50": "foreign_only",
        "wealthify-referral-50": "foreign_only",
        "lemfi-uk-referral-50": "foreign_only",
        "ig-uk-refer-free-share-1000": "foreign_only",
        "oaknorth-referral-30": "foreign_only",
        "lloyds-uk-refer-friend-30": "foreign_only",
        "paypal-uk-25-invite": "foreign_only",
        "tsb-uk-25-amazon-gift-card": "foreign_only",
        "taptap-send-uk-first-transfer": "foreign_only",
        "worldremit-uk-refer-a-friend": "foreign_only",
        "ria-uk-refer-a-friend-20": "foreign_only",
        "webull-uk-5-free-shares": "foreign_only",
        "topcashback-uk-signup-10": "foreign_only",
        "skrill-uk-raf-10-off-100": "foreign_only",
        "currensea-referral-10": "foreign_only",
        "quidco-refer-10": "foreign_only",
        "clearpay-invite-10": "foreign_only",
        "ace-money-transfer-uk-india-10": "foreign_only",
        "moneygram-uk-invite-friends": "foreign_only",
        "remitly-uk-cashback": "foreign_only",
        "zilch-refer-5": "foreign_only",
        "nala-uk-first-transfer-5": "foreign_only",
        "monzo-uk-referral-bonus": "foreign_only",
        "worldremit-quidco-uk-cashback": "foreign_only",
        "revolut-uk-signup-20": "foreign_only",
        # 欧区 / 多区：当地居留
        "bybit-eu-card-welcome-120": "foreign_only",
        "lemfi-eu-referral-50": "foreign_only",
        "revolut-referral": "foreign_only",
        "wise-invite": "foreign_only",
        "remitly-first-transfer": "foreign_only",
        "sendwave-referral": "foreign_only",
        "taptap-send-referral": "foreign_only",
        "payangel-referral-10": "foreign_only",
        "sendwave-latam-tshirt": "foreign_only",
        # 其他地区
        "adcb-emirati-youth-ai-cashback": "foreign_only",
        "wio-creators-12-months-free": "foreign_only",
        "trading212-au-bonus-shares": "foreign_only",
        # 大陆证件 / 港澳门槛内
        "citic-visa-30pct-overseas-2026h2": "cn_ok",
        "za-bank-mgm-welcome-2000": "cn_ok",
        "pingandb-hk-new-customer-nov2026": "cn_ok",
        "antbank-macau-nov2026": "cn_ok",
        "ifast-golden-ticket-50": "cn_ok",
        "starryblu-free-virtual-card": "cn_ok",
        "uupay-new-user-1usdt-card": "cn_ok",
        "kast-5pct-fiat-funding-nov2026": "cn_ok_extra",
    }
)

# AI / 云 / 软件 / 加密：有身份、居住地或地区门槛的条目
KYC.update(
    {
        "thai-aipass-free-ai-models": "foreign_only",
        "kiro-students-year-1000": "foreign_only",
        "codex-students-100": "foreign_only",
        "chatgpt-student-credits-fr": "foreign_only",
        "google-ai-student": "cn_ok_extra",
        "sakura-ai-engine-glm-deepseek-free": "cn_ok_extra",
        "sesame-voice-ai-free": "cn_ok_extra",
        "hark-pro-free-agent": "cn_ok_extra",
        "mistral-vibe-pro-lechonk-3m": "cn_ok_extra",
        "lg-exaone-25-free-api": "cn_ok_extra",
        "pickle-ai-free-agent-jpkr": "cn_ok_extra",
        "qiniu-conatus-free-100m-daily": "cn_ok",
        "baidu-qianfan-1m-free-tokens": "cn_ok",
        "qianfan-20-voucher-nov2026": "cn_ok",
        "tencent-tokenhub-new-user-pack": "cn_ok",
        "stepfun-stepaudio3-free-preview": "cn_ok",
        "autoclaw-weekly-100m-tokens": "cn_ok",
        "xiaomi-mimo-tts-free-api": "cn_ok",
        "azure-for-students-100": "cn_ok",
        "aliyun-yungongkaiwu-300": "cn_ok",
        "modelscope-amd-100h-gpu": "cn_ok",
        "tencent-lighthouse-4c4g-109": "cn_ok",
        "unicom-cloud-free-ai-desktop": "cn_ok",
        "scnet-maas-new-user-tokens": "cn_ok",
        "huawei-codearts-200-voucher": "cn_ok",
        "nodeseek-ytnet-hk-bgp-secondhand": "cn_ok",
        "neevcloud-1500-sandbox-min": "cn_ok",
        "github-student-pack": "cn_ok",
        "jetbrains-student-pack": "cn_ok",
        "amazon-prime-young-adults": "foreign_only",
        "amazon-prime-uk-young-adults-6m": "foreign_only",
        "whatnot-uk-credit-10-200": "foreign_only",
        "yahoo-japan-agent-i-stamp-rally": "foreign_only",
        "paypay-super-matsuri-scratch-2026": "foreign_only",
        "shopify-uk-1-pound-3-months": "cn_ok_extra",
        "names-free-co-uk-domain": "cn_ok_extra",
        "coinbase-new-user-bonus": "foreign_only",
        "binance-lite-vouchers": "foreign_only",
        "bybit-referral-tasks": "foreign_only",
        "okx-new-user-bonus": "foreign_only",
        "bitget-wallet-card-usdc": "foreign_only",
        "ethena-pay-virtual-visa-4pct": "cn_ok_extra",
        "gate-convert-new-user-20usdt": "cn_ok",
    }
)

# eSIM 73 条：数据漫游卡默认 none；含当地实名/居住/入境的单独标
KYC.update(
    {
        "wooriwon-mobile-black-friday": "foreign_only",
        "ymobile-yahoo-store-benefits": "foreign_only",
        "uq-mobile-sim-debut-20000": "foreign_only",
        "ahamo-mnp-20000-points": "foreign_only",
        "hellomobile-foreigner-180k-naverpay": "foreign_only",
        "uq-oyakouenwari-1100": "foreign_only",
        "ymobile-parent-child-discount": "foreign_only",
        "ymobile-sim-trial-two-months-free": "foreign_only",
        "revolut-mobile-ireland": "foreign_only",
        "alrajhi-gigsky-free-unlimited-esim": "foreign_only",
        "voxi-friends-with-benefits-20": "foreign_only",
        "airtel-postpaid-free-roaming": "foreign_only",
        "atom-flexi-friday-100gb-spin": "foreign_only",
        "iijmio-gigaplan-half-price": "foreign_only",
        "talkmobile-150gb-half-price-3m": "foreign_only",
        "ktm-mobi-japan-esim-1plus1-zero": "foreign_only",
        "umobile-ultra5g-tourist-esim-my": "foreign_only",
        "etisalat-wasel-flexi-10gb-esim": "foreign_only",
        "du-uae-free-tourist-esim": "foreign_only",
        "eand-uae-free-visitor-line-esim": "foreign_only",
        "bitel-peru-esim-7days-unlimited": "foreign_only",
        "touch-lebanon-magic-welcome-3gb": "foreign_only",
        "singlife-nomad-free-1gb-esim": "foreign_only",
        "woori-bank-esim-1gb": "foreign_only",
        "xl-indonesia-free-esim-5gb": "foreign_only",
        "true-tat-asean-tourist-sim-8gb": "foreign_only",
        "ooredoo-qatar-easysim-welcome": "foreign_only",
        "mpt-po-pyaw-po-ya-10x-data": "foreign_only",
        "airtel-jio-bogo-recharge": "foreign_only",
        "gigsky-usbank-altitude": "foreign_only",
        # 美国境内试用 / 特定市场发放
        "att-us-free-trial-30d": "cn_ok_extra",
        "verizon-free-trial-30d": "cn_ok_extra",
        "cricket-free-trial-14d": "cn_ok_extra",
        "airvoice-us-free-trial-10gb": "cn_ok_extra",
        "opera-android-free-esim-3gb": "cn_ok_extra",
        "jetpac-eterna-free-esim": "cn_ok_extra",
        "klook-data-bank-gift": "cn_ok_extra",
        # 大陆证件可线上过
        "unicom-esim-xianxian-2026": "cn_ok",
        "saily-us-number-annual": "cn_ok",
        "sosim-hk-esim-33-number": "cn_ok",
        "dito-esim-cloud-number-63": "cn_ok",
        "sosim-hk-33-100gb-esim": "cn_ok",
        # 纯流量 / 全球数据卡：无身份要求
        "airalo-black25-unlimited": "none",
        "roamless-blackfriday50-5off": "none",
        "gigsky-visa-complimentary-data": "none",
        "gigsky-free-esim": "none",
        "airalo-first-order": "none",
        "flexiroam-mastercard-gdr-3gb": "none",
        "pelago-krisflyer-esim": "none",
        "nomad-trial-esim": "none",
        "saily-referral": "none",
        "ubigi-welcome": "none",
        "redbull-mobile-free-esim": "none",
        "rebtel-invite-10": "none",
        "horizon-free-europe-esim": "none",
        "kolet-virgin-atlantic-free-esim": "none",
        "garuda-esim-free-2gb": "none",
        "bitrefill-free-1gb-esim": "none",
        "easysim-free-1gb-esim": "none",
        "eskimo-free-esim": "none",
        "mypal-kolet-free-1gb-esim": "none",
        "esim-san-japan-free-1gb": "none",
        "gohub-free-trial-esim": "none",
        "gomoworld-free-trial-esim": "none",
        "roroesim-cs-trial-300mb": "none",
        "iroamly-free-500mb-trial": "none",
        "eskimo-referral-500mb": "none",
        "roamless-free-trial-500mb": "none",
        "roami-free-100mb-esim": "none",
        "keepgo-free-trial-100mb": "none",
        "firsty-free-esim-global": "none",
        "bamboosim-bfcm-45off": "none",
        "travelgoogoo-visa-free-esim-apac": "none",
    }
)

KYC_NOTES: dict[str, str] = {
    "a1-croatia-prepaid-esim": "下单只填姓名/邮箱/电话，未见证件上传",
    "vodafone-nl-prepaid-esim": "无需证件，线上付款即开",
    "asda-mobile-payg-esim": "不看证件，但充值仅接受英国地址登记的卡",
    "lebara-uk-payg-esim": "不看证件，但非英国卡/地址常被反欺诈拦下",
    "play-pl-prepaid-esim-rwk": "护照 + 人脸拍照验证，需 PESEL 或证件号",
    "ctexcel-hk-gba-prepaid": "eSIM 须到香港湾仔服务点线下办理，实名可用旅行证件",
    "starryblu-60sgd-signup": "大陆护照 + 身份证地址证明",
    "clearstreet-3pct-cash-match": "需美国税号与住址",
    "usbank-business-checking-1500": "需 SSN/EIN 与美国网点所在州",
    "raisin-stack-welcome-bonus-1000": "需 SSN/ITIN",
    "apple-card-double-daily-cash": "需 SSN/ITIN 与美国信用记录",
    "capital-one-360-checking-400": "需 SSN/ITIN、美国地址与手机号",
    "citizens-bank-400-checking": "需 SSN/ITIN 与当地州地址",
    "sofi-checking-400-direct-deposit": "需美国身份与地址",
    "chase-total-checking-400": "需 SSN/ITIN 与美国地址",
    "td-bank-checking-300": "需美国当地州地址",
    "ally-spending-300": "需美国身份与地址",
    "etrade-premium-savings-200": "需美国居民身份",
    "rakuten-alliant-checking-200": "需美国居民或 U.S. Person",
    "schwab-referral-brokerage-1000": "需美国居民身份",
    "onepay-50-signup-bonus": "需 SSN/ITIN",
    "moomoo-us-black-friday-2026": "需 SSN，大陆不可开户",
    "bybit-eu-card-welcome-120": "仅 EEA 居民",
    "wise-invite": "外区 Wise 可能抽查当地居留许可证",
    "revolut-referral": "Revolut 要求当地合法居留证明",
    "revolut-uk-signup-20": "Revolut 要求当地合法居留证明",
    "hsbc-premier-switch-500": "需英国居民与 £10 万收入/资产",
    "za-bank-mgm-welcome-2000": "访港旅客可用内地证件开户",
    "pingandb-hk-new-customer-nov2026": "需本人到港，App 定位核验",
    "antbank-macau-nov2026": "需本人到澳门，身份证 + 港澳通行证",
    "ifast-golden-ticket-50": "内地用户可远程开户",
    "starryblu-free-virtual-card": "大陆护照 + 国内地址证明",
    "uupay-new-user-1usdt-card": "大陆身份证可 KYC",
    "kast-5pct-fiat-funding-nov2026": "护照 KYC，需海外银行入金",
    "kiro-students-year-1000": "名单内 133 所海外院校",
    "thai-aipass-free-ai-models": "仅泰国国籍，需 ThaID 实名",
    "codex-students-100": "仅美/加在读学生",
    "chatgpt-student-credits-fr": "仅法国在读学生",
    "google-ai-student": "需学生认证与非大陆区账号环境",
    "sakura-ai-engine-glm-deepseek-free": "需日本手机号与信用卡",
    "sesame-voice-ai-free": "App 未上架中国大陆与香港",
    "hark-pro-free-agent": "仅美/英/欧盟区 App Store",
    "mistral-vibe-pro-lechonk-3m": "需欧洲 IP",
    "lg-exaone-25-free-api": "中国大陆访问受限",
    "pickle-ai-free-agent-jpkr": "仅日/韩账号",
    "saily-us-number-annual": "护照 + 人脸 KYC",
    "sosim-hk-esim-33-number": "护照可实名",
    "dito-esim-cloud-number-63": "护照登记，可全程云开",
    "sosim-hk-33-100gb-esim": "香港使用须实名（护照可），纯外游可不登记",
    "umobile-ultra5g-tourist-esim-my": "须本人到马来西亚机场扫码",
    "du-uae-free-tourist-esim": "须入境阿联酋后领取",
    "eand-uae-free-visitor-line-esim": "须入境阿联酋后激活",
    "true-tat-asean-tourist-sim-8gb": "须在泰国机场现场领卡",
    "talkmobile-150gb-half-price-3m": "需英国地址、英国银行卡与信用检查",
    "opera-android-free-esim-3gb": "免费额度只在 11 个市场发放",
    "jetpac-eterna-free-esim": "仅 10 个合资格国家，其余进等候名单",
    "klook-data-bank-gift": "账户居住地须为台/泰/马/越",
}

# ---------------------------------------------------------------- 2026-11-21 五站首轮深挖新增
KYC.update(
    {
        "google-ai-blackfriday-annual-50": "cn_ok_extra",
        "octopus-mobile-welcome-150": "cn_ok_extra",
        "usims-free-esim-1gb": "cn_ok_extra",
        "openai-academic-researchers-plus-2026": "foreign_only",
        "wells-fargo-everyday-checking-325": "foreign_only",
        "mercury-business-checking-500": "foreign_only",
        "tastytrade-sweetbonus-2000": "foreign_only",
        "etrade-max-rate-checking-400": "foreign_only",
        "boa-advantage-tiered-1000": "foreign_only",
        "bmo-relationship-checking-2000": "foreign_only",
        "pnc-virtual-wallet-400": "foreign_only",
        "amex-rewards-checking-300": "foreign_only",
        "boc-unionpay-overseas-3pct": "cn_ok",
        "icbc-global-travel-plus-2pct": "cn_ok",
    }
)
KYC_NOTES.update(
    {
        "google-ai-blackfriday-annual-50": "需已有付费订阅与可用的 Google 支付方式",
        "octopus-mobile-welcome-150": "需八达通 App/银包，Android 还需 Google Wallet",
        "usims-free-esim-1gb": "需非 +86 号码收验证码；须 eSIM 机型",
        "openai-academic-researchers-plus-2026": "需海外合资格高校研究型教职/博后",
        "wells-fargo-everyday-checking-325": "需 SSN/ITIN 与美国地址，且排除签 W-8 的非居民",
        "mercury-business-checking-500": "需美国注册公司与 EIN，个体户不行",
        "tastytrade-sweetbonus-2000": "仅美国合法居民",
        "etrade-max-rate-checking-400": "需美国税号与地址",
        "boa-advantage-tiered-1000": "需 SSN/ITIN 与美国地址",
        "bmo-relationship-checking-2000": "需美国 BMO 客户与专属 promo code",
        "pnc-virtual-wallet-400": "需美国税号与地址，非居民线上多被拒",
        "amex-rewards-checking-300": "需已有 Amex 美国卡或储蓄/CD 关系",
        "boc-unionpay-overseas-3pct": "持大陆中行银联信用卡即可，报名走中行 App/公众号",
        "icbc-global-travel-plus-2pct": "持大陆工行环球旅行 Plus 卡即可",
    }
)

KYC.update({
    "a1-croatia-prepaid-esim": "none",
    "vodafone-nl-prepaid-esim": "none",
    "asda-mobile-payg-esim": "none",
    "lebara-uk-payg-esim": "none",
    "play-pl-prepaid-esim-rwk": "cn_ok",
    "ctexcel-hk-gba-prepaid": "foreign_only",
    "starryblu-60sgd-signup": "cn_ok",
})

# 2026-11-23 crypto 比赛 7 条：领奖核验用护照 / 证件 + 地址证明，大陆可过
KYC.update(
    {
        "tradingview-cme-the-leap-nov2026": "cn_ok",
        "gnoland-gnome-tavern-hackathon": "cn_ok",
        "gensyn-agent-arena-evidence-mining": "cn_ok",
        "immunefi-base-everest-audit-comp": "cn_ok",
        "reactive-omni-buildathon": "none",
        "quote-trade-alphaleague-paper": "cn_ok",
        "futuur-midterms-2026": "cn_ok",
    }
)
KYC_NOTES.update(
    {
        "tradingview-cme-the-leap-nov2026": "免费 Basic 账号可参赛，领奖时可能核验年龄/身份/居住地",
        "gnoland-gnome-tavern-hackathon": "先报名参赛，获奖者才需 KYC（护照可过）",
        "gensyn-agent-arena-evidence-mining": "领奖需 KYC 与制裁筛查，护照可过",
        "immunefi-base-everest-audit-comp": "KYC 需护照或政府证件 + 地址证明",
        "quote-trade-alphaleague-paper": "领奖前核验身份与所在地，美国用户仅限 Paper",
        "futuur-midterms-2026": "领奖可能核验身份、年龄与所在地",
    }
)

# ------------------------------------------------------------------ vowifi
VOWIFI: dict[str, str] = {}

_NUMBERED = {
    # 含号 / 可收短信的 eSIM（运营商是否支持 VoWiFi 未见官方确认 → unknown）
    "wooriwon-mobile-black-friday",
    "ymobile-yahoo-store-benefits",
    "uq-mobile-sim-debut-20000",
    "ahamo-mnp-20000-points",
    "hellomobile-foreigner-180k-naverpay",
    "uq-oyakouenwari-1100",
    "ymobile-parent-child-discount",
    "ymobile-sim-trial-two-months-free",
    "att-us-free-trial-30d",
    "verizon-free-trial-30d",
    "cricket-free-trial-14d",
    "unicom-esim-xianxian-2026",
    "revolut-mobile-ireland",
    "airvoice-us-free-trial-10gb",
    "voxi-friends-with-benefits-20",
    "airtel-postpaid-free-roaming",
    "etisalat-wasel-flexi-10gb-esim",
    "eand-uae-free-visitor-line-esim",
    "bitel-peru-esim-7days-unlimited",
    "touch-lebanon-magic-welcome-3gb",
    "sosim-hk-33-100gb-esim",
    "sosim-hk-esim-33-number",
    "xl-indonesia-free-esim-5gb",
    "ooredoo-qatar-easysim-welcome",
    "dito-esim-cloud-number-63",
    "mpt-po-pyaw-po-ya-10x-data",
    "atom-flexi-friday-100gb-spin",
    "true-tat-asean-tourist-sim-8gb",
}
VOWIFI.update({i: "unknown" for i in _NUMBERED})
VOWIFI["saily-us-number-annual"] = "false"  # App 内 VoIP，不是运营商 VoWiFi
VOWIFI["asda-mobile-payg-esim"] = "true"  # 官方 Wi-Fi 通话对所有客户免费
VOWIFI.update({i: "unknown" for i in ("a1-croatia-prepaid-esim","vodafone-nl-prepaid-esim","lebara-uk-payg-esim","play-pl-prepaid-esim-rwk","ctexcel-hk-gba-prepaid")})

# ---------------------------------------------------------------- utility
UTILITY = {
    # 免费域名 / 免费主机、容器、VPS、云电脑（长期白拿、无需付款）
    "oracle-always-free",
    "cloudflare-workers-free",
    "digitalplat-freedomain-dpdns",
    "gravatar-free-domain-1y",
    "l53-ggff-free-domain-2y-2026",
    "hoody-free-cloud-computers",
    "altare-always-free-container",
    "cloady-free-tier",
    "instabox-free-cloud-machine",
    "lxi-be-free-hosting-5gb",
    "antideploy-free-1vcpu-1gb",
    "vyce-cloud-free-vps",
    # eSIM B 案：含号 + 可云开 + 年保号 ≤¥100 + 有依据能在陆收短信
    "dito-esim-cloud-number-63",
    "sosim-hk-esim-33-number",
    # 免费虚拟卡
    "starryblu-free-virtual-card",
    "a1-croatia-prepaid-esim",
}

# 需要补「抽查居留」提示的条目
RESIDENCY_RISK = {
    "wise-invite": "2026-10 起外区 Wise 会在护照国与注册居住国不一致时抽查当地居留许可证、≥90 天长签或 UK eVisa（含 share code），英区/加区已有大批账号被抽查；国区账号无实体卡。",
    "revolut-referral": "Revolut 明确要求当地合法居留证明，可能抽查居留许可证；无当地居留的云开账号有被清退风险。",
    "revolut-uk-signup-20": "Revolut 明确要求当地合法居留证明，可能抽查居留许可证；无当地居留的云开账号有被清退风险。",
}


def main() -> None:
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    ids = {d["id"] for d in deals}
    unknown = (set(KYC) | set(KYC_NOTES) | set(VOWIFI) | UTILITY | set(RESIDENCY_RISK)) - ids
    if unknown:
        raise SystemExit(f"标定表里有不存在的 id：{sorted(unknown)}")

    missing = []
    for d in deals:
        cat = d.get("category")
        if cat == "esim":
            if d["id"] not in KYC:
                missing.append((d["id"], "kyc_level"))
            if d["id"] not in VOWIFI:
                VOWIFI[d["id"]] = "n/a"
        elif cat == "bank":
            if d["id"] not in KYC:
                missing.append((d["id"], "kyc_level"))
        elif d["id"] not in KYC:
            KYC[d["id"]] = "none"
    if missing:
        raise SystemExit(f"漏标：{missing}")

    for d in deals:
        d["kyc_level"] = KYC[d["id"]]
        if d.get("category") == "esim":
            d["vowifi"] = VOWIFI[d["id"]]
        else:
            d.pop("vowifi", None)
        d["utility"] = 1 if d["id"] in UTILITY else 0
        if d["id"] in KYC_NOTES:
            d["kyc_note"] = KYC_NOTES[d["id"]]
        else:
            d.pop("kyc_note", None)
        if d["id"] in RESIDENCY_RISK:
            note = RESIDENCY_RISK[d["id"]]
            if note not in (d.get("risk") or ""):
                d["risk"] = (d.get("risk") or "").rstrip("。") + "。" + note if d.get("risk") else note

    DATA.write_text(
        json.dumps(deals, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    from collections import Counter

    print("kyc_level:", Counter(d["kyc_level"] for d in deals))
    print("vowifi:", Counter(d.get("vowifi") for d in deals if d["category"] == "esim"))
    print("utility:", sum(d["utility"] for d in deals))


if __name__ == "__main__":
    main()
