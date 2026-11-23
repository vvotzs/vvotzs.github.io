#!/usr/bin/env python3
"""一次性数据标定：Bank / eSIM 的 6 个 SEO 资格字段逐条写入 data/deals.json。

六个字段的口径见 scripts/eligibility.py 顶部注释。本文件只放「每条实际填什么」：

  identity    身份资料门槛
  residency   居住地门槛
  platform    可用平台（数组，只能 ios / android / web 组合，默认三端都可）
  phone       手机号门槛
  funding     资金门槛
  geo         可参与国家 / 地区（ISO 3166-1 alpha-2；"GLOBAL" = 全球；"-XX" = 排除）

没写的字段自动落到默认值（email / none / 三端 / none / none / GLOBAL），
也就是「没有这个门槛」，页面上对应那行不显示。

判定原则（写在这里，方便以后复核）：
  1. 只写数据里说过的门槛。conditions / regions / kyc_note 明确写了才填，
     没写就留默认；拿不准的写进 conditions 或 risk，不在这里编。
  2. 受监管的银行 / 券商 / 支付账户（本地开户要身份证件与地址）：identity 记
     local_id，residency 记 local_address / local_resident；只用护照 + 人脸的
     钱包、汇款、eSIM 类记 photo_id。
  3. 设备 / 系统版本 / 银行卡组织这类限制不是「平台」的一部分，写 conditions / risk。
  4. 和 kyc_level 冲突时以这里的实际资格为准，脚本会把 kyc_level 改成对得上的值。

本脚本幂等：重复运行结果一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from eligibility import FIELDS, check_kyc, implied_kyc  # noqa: E402

DATA = ROOT / "data" / "deals.json"

ELIG: dict[str, dict] = {}

# =====================================================================
# Bank / 银行 · U 卡 · 券商 · 汇款（92 条）
# =====================================================================
ELIG.update(
    {
        # ---------------------------------------------------------- 美区存款 / 券商
        "clearstreet-3pct-cash-match": {
            "identity": "local_id", "residency": "local_address",
            "funding": "min_deposit", "geo": ["US"],
        },
        "tastytrade-sweetbonus-2000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["US"],
        },
        "bmo-relationship-checking-2000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "usbank-business-checking-1500": {
            "identity": "business", "residency": "local_address",
            "funding": "min_deposit", "geo": ["US"],
        },
        "raisin-stack-welcome-bonus-1000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["US"],
        },
        "apple-card-double-daily-cash": {
            "identity": "local_id", "geo": ["US"],
        },
        "mercury-business-checking-500": {
            "identity": "business", "residency": "local_address",
            "funding": "min_deposit", "geo": ["US"],
        },
        "boa-advantage-tiered-1000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        # 2026-11-23 巡检新增，当时只写进 deals.json（字段值与线上一致，这里补回标定表）
        "netspend-200-dd-400": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "capital-one-360-checking-400": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "direct_deposit", "geo": ["US"],
        },
        "citizens-bank-400-checking": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "sofi-checking-400-direct-deposit": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "pnc-virtual-wallet-400": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "etrade-max-rate-checking-400": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "chase-total-checking-400": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "wells-fargo-everyday-checking-325": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "ally-spending-300": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "td-bank-checking-300": {
            "identity": "local_id", "residency": "local_address",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "amex-rewards-checking-300": {
            "identity": "local_id", "residency": "local_address",
            "funding": "existing_card", "geo": ["US"],
        },
        "etrade-premium-savings-200": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["US"],
        },
        "rakuten-alliant-checking-200": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "schwab-referral-brokerage-1000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["US"],
        },
        "moomoo-us-black-friday-2026": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["US"],
        },
        "remitly-us-global-card": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "direct_deposit", "geo": ["US"],
        },
        "onepay-50-signup-bonus": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "direct_deposit", "geo": ["US"],
        },
        "sendwave-latam-tshirt": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["US"],
        },
        # ---------------------------------------------------------- 英区转户 / 开户
        "hsbc-premier-switch-500": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "barclays-uk-switch-300": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "direct_deposit", "geo": ["GB"],
        },
        "santander-everyday-switch-240": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "hsbc-uk-bank-account-switch-220": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "first-direct-1st-account-switch-210": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "club-lloyds-switch-200": {
            "identity": "local_id", "residency": "local_resident", "geo": ["GB"],
        },
        "natwest-select-switch-200": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "rbs-select-reward-switch-200": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "investengine-referral-20-200": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "coop-bank-switch-200": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "nationwide-flexaccount-switch-175": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "robinhood-uk-free-stock": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "jpm-personal-investing-invest-1000-100": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "quilter-invest-isa-100": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "freetrade-free-share-10-100": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "raisin-uk-refer-friend-100": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "fidelity-uk-refer-100-amazon": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "tide-business-referral-100": {
            "identity": "business", "residency": "local_address",
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GB"],
        },
        "chase-uk-referral-50": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "chip-uk-referral-50": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "wealthify-referral-50": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "lemfi-uk-referral-50": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "webull-uk-5-free-shares": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "ig-uk-refer-free-share-1000": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "oaknorth-referral-30": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "lloyds-uk-refer-friend-30": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "geo": ["GB"],
        },
        "paypal-uk-25-invite": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["GB"],
        },
        "tsb-uk-25-amazon-gift-card": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["GB"],
        },
        "worldremit-quidco-uk-cashback": {
            "identity": "photo_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "worldremit-uk-refer-a-friend": {
            "identity": "photo_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "taptap-send-uk-first-transfer": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "ria-uk-refer-a-friend-20": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "skrill-uk-raf-10-off-100": {
            "identity": "photo_id", "residency": "local_address",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "currensea-referral-10": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GB"],
        },
        "topcashback-uk-signup-10": {
            "residency": "local_resident", "funding": "purchase", "geo": ["GB"],
        },
        "quidco-refer-10": {
            "residency": "local_resident", "funding": "purchase", "geo": ["GB"],
        },
        "clearpay-invite-10": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GB"],
        },
        "moneygram-uk-invite-friends": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["GB"],
        },
        "remitly-uk-cashback": {
            "identity": "photo_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "zilch-refer-5": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GB"],
        },
        "nala-uk-first-transfer-5": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["GB"],
        },
        "monzo-uk-referral-bonus": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "any_number",
            "funding": "purchase", "geo": ["GB"],
        },
        "ace-money-transfer-uk-india-10": {
            "identity": "photo_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["AU", "CA", "EEA", "GB"],
        },
        # ---------------------------------------------------------- 欧区 / 多区 / 全球钱包
        "bybit-eu-card-welcome-120": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit",
            "geo": ["EEA", "-MT"],
        },
        "wise-invite": {
            "identity": "photo_id", "residency": "local_address", "geo": ["EEA", "GB"],
        },
        "lemfi-eu-referral-50": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["EEA"],
        },
        "revolut-referral": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit",
            "geo": ["AU", "EEA", "GB", "SG", "US"],
        },
        "revolut-uk-signup-20": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["EEA", "GB"],
        },
        "remitly-first-transfer": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit",
            "geo": ["AU", "CA", "EEA", "GB", "US"],
        },
        "sendwave-referral": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["EEA", "US"],
        },
        "taptap-send-referral": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit",
            "geo": ["DE", "ES", "FR", "GB", "IT", "NL", "US"],
        },
        "payangel-referral-10": {
            "identity": "photo_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "min_deposit",
            "geo": ["AU", "CA", "EEA", "GB", "US"],
        },
        "kast-5pct-fiat-funding-nov2026": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "funding": "min_deposit", "geo": ["GLOBAL"],
        },
        "starryblu-60sgd-signup": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "phone": "any_number", "geo": ["GLOBAL"],
        },
        "starryblu-free-virtual-card": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "phone": "any_number", "geo": ["GLOBAL"],
        },
        "uupay-new-user-1usdt-card": {
            "identity": "photo_id", "funding": "min_deposit", "geo": ["GLOBAL"],
        },
        # Quppy：App 内 KYC，居住地/国籍填英国则全部服务不可用（官方可用性目录 2026-08-11），故排除 GB
        "quppy-gb-iban-usdt-2026": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "phone": "any_number", "geo": ["GLOBAL", "-GB"],
        },
        # ---------------------------------------------------------- 阿联酋 / 香港 / 澳门 / 中国
        "adcb-emirati-youth-ai-cashback": {
            "identity": "local_id", "residency": "citizen_only",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["AE"],
        },
        "wio-creators-12-months-free": {
            "identity": "business", "residency": "local_resident",
            "platform": ["android", "ios"], "geo": ["AE"],
        },
        "za-bank-mgm-welcome-2000": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "funding": "min_deposit", "geo": ["HK"],
        },
        "pingandb-hk-new-customer-nov2026": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "funding": "min_deposit", "geo": ["HK"],
        },
        "antbank-macau-nov2026": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "funding": "min_deposit", "geo": ["MO"],
        },
        "octopus-mobile-welcome-150": {
            "identity": "none", "platform": ["android", "ios"],
            "phone": "local_number", "funding": "purchase", "geo": ["HK"],
        },
        "ifast-golden-ticket-50": {
            "identity": "photo_id", "funding": "min_deposit", "geo": ["GLOBAL"],
        },
        "citic-visa-30pct-overseas-2026h2": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["CN"],
        },
        "icbc-global-travel-plus-2pct": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["CN"],
        },
        "boc-unionpay-overseas-3pct": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["CN"],
        },
        "trading212-au-bonus-shares": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "min_deposit", "geo": ["AU"],
        },
        "qantas-amex-ultimate-75k": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "purchase", "geo": ["AU"],
        },
    }
)

# =====================================================================
# eSIM（80 条）
# =====================================================================
ELIG.update(
    {
        # ---------------------------------------------------------- 日韩运营商合约
        "wooriwon-mobile-black-friday": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["KR"],
        },
        "ymobile-yahoo-store-benefits": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["JP"],
        },
        "uq-mobile-sim-debut-20000": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["JP"],
        },
        "ahamo-mnp-20000-points": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["JP"],
        },
        "hellomobile-foreigner-180k-naverpay": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["KR"],
        },
        "uq-oyakouenwari-1100": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "paid_plan", "geo": ["JP"],
        },
        "ymobile-parent-child-discount": {
            "identity": "local_id", "residency": "local_resident",
            "funding": "paid_plan", "geo": ["JP"],
        },
        "ymobile-sim-trial-two-months-free": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number", "geo": ["JP"],
        },
        "iijmio-gigaplan-half-price": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["JP"],
        },
        "woori-bank-esim-1gb": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "existing_card", "geo": ["KR"],
        },
        "ktm-mobi-japan-esim-1plus1-zero": {
            "identity": "phone", "platform": ["android", "ios"],
            "phone": "local_number", "funding": "purchase", "geo": ["KR"],
        },
        "revolut-mobile-ireland": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "paid_plan", "geo": ["IE"],
        },
        "voxi-friends-with-benefits-20": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "paid_plan", "geo": ["GB"],
        },
        "talkmobile-150gb-half-price-3m": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "paid_plan", "geo": ["GB"],
        },
        # ---------------------------------------------------------- 美区免费试用
        "att-us-free-trial-30d": {
            "identity": "none", "platform": ["android", "ios"],
            "phone": "local_number", "geo": ["US"],
        },
        "verizon-free-trial-30d": {
            "identity": "none", "platform": ["android", "ios"],
            "phone": "local_number", "geo": ["US"],
        },
        "airvoice-us-free-trial-10gb": {
            "identity": "none", "platform": ["android", "ios"],
            "phone": "local_number", "geo": ["US"],
        },
        "cricket-free-trial-14d": {
            "identity": "none", "platform": ["android", "ios"],
            "phone": "local_number", "geo": ["US"],
        },
        # ---------------------------------------------------------- 阿联酋 / 中东 / 亚洲运营商
        "etisalat-wasel-flexi-10gb-esim": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "paid_plan", "geo": ["AE"],
        },
        "du-uae-free-tourist-esim": {
            "identity": "photo_id", "platform": ["android", "ios"], "geo": ["AE"],
        },
        "eand-uae-free-visitor-line-esim": {
            "identity": "photo_id", "platform": ["android", "ios"], "geo": ["AE"],
        },
        "ooredoo-qatar-easysim-welcome": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number", "geo": ["QA"],
        },
        # 2026-11-24 巡检新增
        "qatar-visit-saudi-holiday-free-esim": {
            "identity": "email", "residency": "none",
            "platform": ["android", "ios"], "geo": ["QA"],
        },
        "alrajhi-gigsky-free-unlimited-esim": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "funding": "existing_card", "geo": ["SA"],
        },
        "touch-lebanon-magic-welcome-3gb": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "min_deposit", "geo": ["LB"],
        },
        "airtel-postpaid-free-roaming": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "existing_card", "geo": ["IN"],
        },
        "airtel-jio-bogo-recharge": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "min_deposit", "geo": ["IN"],
        },
        "atom-flexi-friday-100gb-spin": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "purchase", "geo": ["MM"],
        },
        "mpt-po-pyaw-po-ya-10x-data": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "existing_card", "geo": ["MM"],
        },
        "xl-indonesia-free-esim-5gb": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number", "geo": ["ID"],
        },
        "umobile-ultra5g-tourist-esim-my": {
            "identity": "photo_id", "platform": ["web"], "geo": ["MY"],
        },
        "true-tat-asean-tourist-sim-8gb": {
            "identity": "photo_id", "platform": ["web"], "geo": ["IN", "SEA"],
        },
        "dito-esim-cloud-number-63": {
            "identity": "photo_id",
            "platform": ["android", "ios"], "funding": "min_deposit", "geo": ["PH"],
        },
        "bitel-peru-esim-7days-unlimited": {
            "identity": "local_id", "residency": "local_resident",
            "platform": ["android", "ios"], "phone": "local_number",
            "funding": "paid_plan", "geo": ["PE"],
        },
        # ---------------------------------------------------------- 欧洲预付 / 实名卡
        "play-pl-prepaid-esim-rwk": {
            "identity": "photo_id", "platform": ["web"],
            "funding": "min_deposit", "geo": ["PL"],
        },
        "vodafone-nl-prepaid-esim": {
            "identity": "none", "platform": ["web"], "funding": "min_deposit", "geo": ["NL"],
        },
        "ctexcel-hk-gba-prepaid": {
            "identity": "local_id", "funding": "min_deposit", "geo": ["HK"],
        },
        "sosim-hk-33-100gb-esim": {
            "identity": "photo_id", "platform": ["web"],
            "funding": "min_deposit", "geo": ["HK"],
        },
        "sosim-hk-esim-33-number": {
            "identity": "photo_id", "platform": ["web"],
            "funding": "min_deposit", "geo": ["HK"],
        },
        "a1-croatia-prepaid-esim": {
            "identity": "none", "platform": ["web"],
            "funding": "min_deposit", "geo": ["HR"],
        },
        "asda-mobile-payg-esim": {
            "identity": "none", "platform": ["web"],
            "funding": "min_deposit", "geo": ["GB"],
        },
        "lebara-uk-payg-esim": {
            "identity": "none", "platform": ["web"],
            "funding": "min_deposit", "geo": ["GB"],
        },
        "visible-us-free-trial-15d": {
            "identity": "none", "residency": "local_address",
            "platform": ["android", "ios"], "geo": ["US"],
        },
        "horizon-free-europe-esim": {
            "identity": "email", "platform": ["android", "ios"],
            "phone": "any_number", "geo": ["CH", "EEA", "GB"],
        },
        # ---------------------------------------------------------- 中国 / 日区
        "unicom-esim-xianxian-2026": {
            "identity": "local_id", "residency": "local_resident",
            "phone": "local_number", "funding": "existing_card", "geo": ["CN"],
        },
        "esim-san-japan-free-1gb": {
            "platform": ["web"], "geo": ["JP"],
        },
        # ---------------------------------------------------------- 全球 App 类免费/折扣
        # 2026-11-24 巡检新增（新加坡本地纯流量不过期套餐）
        "bnesim-sg-50gb-noexpiry-bf": {"identity": "none", "funding": "purchase", "geo": ["SG"]},
        "airalo-black25-unlimited": {"funding": "purchase", "geo": ["GLOBAL"]},
        "airalo-first-order": {"funding": "purchase", "geo": ["GLOBAL"]},
        "roamless-blackfriday50-5off": {
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"],
        },
        "roamless-free-trial-500mb": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "gigsky-free-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "gigsky-visa-complimentary-data": {
            "identity": "none", "platform": ["android", "ios"],
            "funding": "existing_card", "geo": ["GLOBAL"],
        },
        "gigsky-usbank-altitude": {
            "identity": "local_id", "residency": "local_address",
            "platform": ["android", "ios"], "funding": "existing_card", "geo": ["US"],
        },
        "flexiroam-mastercard-gdr-3gb": {
            "identity": "none", "platform": ["android", "ios"],
            "funding": "existing_card", "geo": ["GLOBAL"],
        },
        "saily-us-number-annual": {
            "identity": "photo_id", "platform": ["android", "ios"],
            "funding": "min_deposit", "geo": ["GLOBAL"],
        },
        "saily-referral": {
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"],
        },
        "ubigi-welcome": {
            "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"],
        },
        "nomad-trial-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "redbull-mobile-free-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "opera-android-free-esim-3gb": {
            "platform": ["android"],
            "geo": ["AE", "BR", "CA", "DE", "FR", "GB", "NL", "NO", "PL", "SE", "US"],
        },
        "rebtel-invite-10": {
            "identity": "phone", "platform": ["android", "ios"],
            "phone": "any_number", "funding": "min_deposit", "geo": ["GLOBAL"],
        },
        "pelago-krisflyer-esim": {
            "platform": ["android", "ios"], "geo": ["GLOBAL"],
        },
        "kolet-virgin-atlantic-free-esim": {
            "platform": ["android", "ios"], "phone": "any_number", "geo": ["GLOBAL"],
        },
        "garuda-esim-free-2gb": {
            "platform": ["android", "ios"], "geo": ["GLOBAL"],
        },
        "bitrefill-free-1gb-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "easysim-free-1gb-esim": {
            "identity": "phone", "platform": ["android", "ios"],
            "phone": "any_number", "geo": ["GLOBAL"],
        },
        "usims-free-esim-1gb": {
            "identity": "phone", "platform": ["android", "ios"],
            "phone": "specific_country", "funding": "purchase", "geo": ["GLOBAL"],
        },
        # 2026-11-22 归档补录（历史活动，资格按当时条款填写）
        "vodafone-london-network-trial-esim": {
            "residency": "local_address", "platform": ["web"],
            "phone": "specific_country", "geo": ["GB"],
        },
        "ubigi-cnet-free-500mb": {"geo": ["GLOBAL"]},
        "jetpac-eterna-free-esim": {
            "identity": "phone", "platform": ["android", "ios"],
            "phone": "specific_country",
            "geo": ["AU", "CA", "DE", "ES", "FR", "GB", "IT", "NL", "NZ", "US"],
        },
        "eskimo-free-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "eskimo-referral-500mb": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "mypal-kolet-free-1gb-esim": {
            "platform": ["android", "ios"], "geo": ["GLOBAL"],
        },
        "gohub-free-trial-esim": {"platform": ["android", "ios"], "geo": ["ASIA"]},
        "gomoworld-free-trial-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "roroesim-cs-trial-300mb": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "iroamly-free-500mb-trial": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "roami-free-100mb-esim": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "keepgo-free-trial-100mb": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "firsty-free-esim-global": {"platform": ["android", "ios"], "geo": ["GLOBAL"]},
        "bamboosim-bfcm-45off": {"funding": "purchase", "geo": ["GLOBAL"]},
        "travelgoogoo-visa-free-esim-apac": {
            "identity": "none", "platform": ["web"],
            "funding": "existing_card", "geo": ["APAC"],
        },
        "klook-data-bank-gift": {
            "residency": "local_resident", "platform": ["android", "ios"],
            "funding": "purchase", "geo": ["MY", "TH", "TW", "VN"],
        },
        "singlife-nomad-free-1gb-esim": {
            "residency": "local_resident", "platform": ["android", "ios"],
            "funding": "existing_card", "geo": ["SG"],
        },
        # 2026-11-22 巡检新增的 eSIM（当时只写进 deals.json，这里补回标定表，值与线上一致）
        "dtcpay-esim-5gb-6m": { "identity": "photo_id", "residency": "local_address", "platform": ["android", "ios"], "phone": "specific_country", "geo": ["GLOBAL"] },
        "sun-phuquoc-free-esim-5gb": { "identity": "photo_id", "platform": ["android", "ios", "web"], "funding": "purchase", "geo": ["GLOBAL"] },
        "trip-com-member-free-esim": { "identity": "email", "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"] },
        "norma-connect-start-esim": { "identity": "photo_id", "platform": ["web"], "funding": "purchase", "geo": ["DE"] },
        "vodafone-samoa-ding-tuesday-data": { "identity": "none", "platform": ["web", "android", "ios"], "funding": "purchase", "geo": ["WS"] },
        "sas-travel-esim-hubby": { "identity": "email", "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"] },
        "hahasim-hk-prepaid-number": { "identity": "none", "platform": ["web", "android", "ios"], "funding": "min_deposit", "geo": ["HK"] },
        "klook-rewards-free-esim": { "identity": "email", "platform": ["android", "ios", "web"], "funding": "purchase", "geo": ["GLOBAL"] },
        "airfrance-klm-kolet-free-1gb": { "identity": "email", "platform": ["android", "ios", "web"], "phone": "any_number", "geo": ["GLOBAL"] },
        "air-india-kolet-free-1gb": { "identity": "email", "platform": ["android", "ios", "web"], "phone": "any_number", "geo": ["GLOBAL"] },
        "tarom-ubigi-free-1gb": { "identity": "email", "platform": ["android", "ios", "web"], "funding": "purchase", "geo": ["GLOBAL"] },
        "agoda-vip-diamond-free-esim": { "identity": "email", "platform": ["android", "ios"], "funding": "purchase", "geo": ["GLOBAL"] },
        "omio-kolet-free-1gb": { "identity": "email", "platform": ["android", "ios", "web"], "phone": "any_number", "funding": "purchase", "geo": ["GLOBAL"] },
        "esimgg-estonia-372-number": { "identity": "none", "platform": ["web", "android", "ios"], "funding": "min_deposit", "geo": ["GLOBAL"] },
        "clubsim-hk-prepaid-number": { "identity": "photo_id", "platform": ["web", "android", "ios"], "funding": "min_deposit", "geo": ["HK"] },
        "jegotrip-cmlink-free-20gb-uk": { "identity": "email", "platform": ["android", "ios"], "phone": "specific_country", "geo": ["GB"] },
        # 2026-11-23：Roam 官方 App 与第三方 TG 机器人（两条 eSIM）
        "roam-app-quest-free-esim": {
            "identity": "none", "platform": ["android", "ios"], "geo": ["GLOBAL"],
        },
        "roam-esim-bot-drei-1gb": {
            "identity": "none", "platform": ["android", "ios"], "geo": ["GLOBAL"],
        },
        # 2026-11-23：Wanderly 免费试用（App 内领取，可能要求一次性验卡）
        "wanderly-free-esim-trial-500mb": {
            "identity": "email", "platform": ["android", "ios"],
            "funding": "existing_card", "geo": ["GLOBAL"],
        },
    }
)

# =====================================================================
# AI 免费 LLM API（2026-11-23 新增两条：官网注册建 Key、免绑卡、无地区限制）# =====================================================================
ELIG.update(
    {
        "plugsky-free-llm-api": {
            "identity": "email", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "merkium-free-llm-api": {
            "identity": "email", "platform": ["web"], "geo": ["GLOBAL"],
        },
        # 2026-11-24：Show HN 两款 AI 新品（官网注册即用、免绑卡、无地区限制）
        "sie-serverless-free-credits": {
            "identity": "email", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "klistra-free-350-credits": {
            "identity": "email", "platform": ["web"], "geo": ["GLOBAL"],
        },
        # 2026-11-23：RikkaHub 开源 Android 客户端（只发 Android 端，本体与内购全免）
        "rikkahub-android-llm-client": {
            "identity": "none", "platform": ["android"], "geo": ["GLOBAL"],
        },
        # 2026-11-23：SIMHub 读卡器 eSIM / VoWiFi 工具（无账号、免身份，三端自签安装；
        # macOS 不在 ios/android/web 枚举里，平台写进 conditions）
        "simhub-esim-reader-vowifi": {
            "identity": "none", "geo": ["GLOBAL"],
        },
        # 2026-11-23 crypto 比赛 7 条：领奖要护照/证件核验，全部网页端提交
        "tradingview-cme-the-leap-nov2026": {
            "identity": "photo_id", "platform": ["web"],
            "geo": ["GLOBAL", "-BY", "-CU", "-IR", "-KP", "-RU"],
        },
        "gnoland-gnome-tavern-hackathon": {
            "identity": "photo_id", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "gensyn-agent-arena-evidence-mining": {
            "identity": "photo_id", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "immunefi-base-everest-audit-comp": {
            "identity": "photo_id", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "reactive-omni-buildathon": {
            "identity": "email", "platform": ["web"], "geo": ["GLOBAL"],
        },
        "quote-trade-alphaleague-paper": {
            "identity": "photo_id", "platform": ["web"],
            "geo": ["GLOBAL", "-CU", "-IR", "-KP", "-SD", "-SY"],
        },
        "futuur-midterms-2026": {
            "identity": "photo_id", "platform": ["web"], "geo": ["GLOBAL"],
        },
    }
)

# 非 Bank / eSIM 分类里也手工挂了这组字段的条目（AI / 云 / 软件共 15 条）。
# main() 对这两类以外的条目一律清空字段以回到默认值，跑一次就会把它们删掉，
# 所以这里显式保留：只有明确列出的 id 才能留在非 Bank / eSIM 分类里。
KEEP_EXTRA = {
    "google-antigravity-science-free", "lovable-linkedin-premium-year",
    "claude-max-monthly-api-credits", "articul8-bivia-1b-tokens",
    "ultrapic-pro-plus-5000-credits", "genixnode-kvm-nvme-14-loc",
    "aws-quick-free-plus-trial", "razer-gold-8th-anniversary-bonus",
    "zcode-new-user-5day-8m", "tencent-lightvela-free-month",
    "urnetwork-free-tier-30gib", "databricks-free-edition",
    "dahl-inference-100m-tokens", "nodaroo-free-container-host",
    "plugsky-free-llm-api", "merkium-free-llm-api",
    "sie-serverless-free-credits", "klistra-free-350-credits",
    "rikkahub-android-llm-client",
    "simhub-esim-reader-vowifi",
    # 2026-11-23 crypto 比赛 7 条
    "tradingview-cme-the-leap-nov2026", "gnoland-gnome-tavern-hackathon",
    "gensyn-agent-arena-evidence-mining", "immunefi-base-everest-audit-comp",
    "reactive-omni-buildathon", "quote-trade-alphaleague-paper",
    "futuur-midterms-2026",
}


FIELD_NAMES = {
    "identity": "identity_requirement",
    "residency": "residency_requirement",
    "platform": "platform_requirement",
    "phone": "phone_requirement",
    "funding": "funding_requirement",
    "geo": "geo_restriction",
}


def main() -> None:
    deals = json.loads(DATA.read_text(encoding="utf-8"))
    ids = {d["id"] for d in deals}
    unknown = set(ELIG) - ids
    if unknown:
        raise SystemExit(f"标定表里有不存在的 id：{sorted(unknown)}")

    targets = [d for d in deals if d.get("category") in ("bank", "esim")]
    missing = [d["id"] for d in targets if d["id"] not in ELIG]
    if missing:
        raise SystemExit(f"Bank / eSIM 漏标：{missing}")

    conflicts: list[str] = []
    for deal in deals:
        entry = ELIG.get(deal["id"])
        if deal.get("category") not in ("bank", "esim"):
            if deal["id"] in KEEP_EXTRA:
                continue  # 手工标过的 AI / 云 / 软件条目原样保留
            for name in FIELDS:
                deal.pop(name, None)
            continue
        for short, full in FIELD_NAMES.items():
            value = (entry or {}).get(short)
            if value in (None, "", []):
                deal.pop(full, None)
            else:
                deal[full] = value

        # 资格字段与 kyc_level 冲突时，以资格字段为准把 kyc_level 拉回来
        note = check_kyc(deal)
        if note:
            implied = implied_kyc(deal)
            if implied:
                conflicts.append(f"{note} → 改为 {implied}")
                deal["kyc_level"] = implied

    DATA.write_text(json.dumps(deals, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    from collections import Counter

    print(f"Bank / eSIM 标定 {len(targets)} 条（bank "
          f"{sum(1 for d in targets if d['category'] == 'bank')} · esim "
          f"{sum(1 for d in targets if d['category'] == 'esim')}）")
    for full in FIELDS:
        filled = sum(1 for d in targets if d.get(full))
        print(f"  {full}: {filled}/{len(targets)} 条显式填写")
    print("  identity:", Counter(d.get("identity_requirement") for d in targets).most_common())
    print("  kyc_level:", Counter(d.get("kyc_level") for d in targets).most_common())
    if conflicts:
        print(f"kyc_level 与资格字段冲突并已按资格改正 {len(conflicts)} 条：")
        for line in conflicts:
            print("  -", line)
    else:
        print("kyc_level 与资格字段：无冲突")


if __name__ == "__main__":
    main()
