#!/usr/bin/env python3
"""参与资格（Eligibility）字段：枚举、默认值、双语标签与详情页 / JSON-LD 取数。

六个字段写在 data/deals.json 的每条条目上（Bank 与 eSIM 全量），口径由
label_eligibility.py 逐条标定；这里只放“口径本身”，让标定脚本与构建脚本
共用同一份枚举，避免两边说法不一致。

字段（全部用英文 code 存库，页面按语言渲染成文案，天然零 CJK 泄漏到英文页）：

  identity_requirement   身份资料门槛
    none        无需任何身份资料（直接下单即可）
    email       邮箱注册（网购默认前提，默认值，页面不显示）
    phone       需手机号验证 / 接码
    photo_id    护照或身份证 + 人脸识别
    local_id    需当地证件 / 税号（SSN、ITIN、NIK、PESEL、外国人登录证…）
    student     需学生身份认证
    business    企业 / 营业执照 / 公司注册资料

  residency_requirement  居住地门槛
    none            无居住地要求（默认值）
    local_address   需当地地址（账单地址 / 住址证明）
    local_resident  需当地居民 / 居留许可 / 税务居民
    citizen_only    仅限本国公民

  platform_requirement   可用的平台，数组，元素只能是 ios / android / web 的自由组合
                         默认 ["android","ios","web"]（不限平台，页面不显示）；
                         只能用 App 的写成 ["android","ios"]，只发 iOS 的写 ["ios"]。
                         设备 / 系统版本等更细的限制写进 conditions、risk，不放这里。

  phone_requirement      手机号门槛
    none              不需要手机号（默认值）
    any_number        任意号码都行（含 +86）
    local_number      必须是活动国本地号码
    specific_country  必须是某个指定国家的号码（具体国家写在 conditions / geo_restriction）

  funding_requirement    资金门槛
    none            无入金 / 付费要求（默认值）
    min_deposit     需入金 / 存款 / 充值 / 换汇达到门槛
    direct_deposit  需工资或政府类直存（direct deposit）
    purchase        需先消费 / 购买商品
    paid_plan       需订购付费套餐 / 订阅
    existing_card   需已持有指定卡 / 账户 / 保单才能领

  geo_restriction        可参与的国家 / 地区，ISO 3166-1 alpha-2 数组；区域代号另见
                         REGION_NAMES（EEA / GLOBAL / APAC …）；"GLOBAL" 表示全球无限制
                         （默认值，页面不显示）。元素前加 "-" 表示排除该市场，
                         例如 ["GLOBAL","-US"] = 全球但不含美国。

kyc_level 与这六项冲突时以这六项为准（label_eligibility.py 会核对并给出提示）。
"""
from __future__ import annotations

import re

FIELDS = (
    "identity_requirement",
    "residency_requirement",
    "platform_requirement",
    "phone_requirement",
    "funding_requirement",
    "geo_restriction",
)

PLATFORMS = ("ios", "android", "web")
ALL_PLATFORMS = ["android", "ios", "web"]
# 平台徽标只出现在「要开银行卡的 App」与 eSIM 这两类详情页（Jun 2026-11-21 的口径）
PLATFORM_CATEGORIES = ("bank", "esim")

DEFAULTS: dict[str, object] = {
    "identity_requirement": "email",
    "residency_requirement": "none",
    "platform_requirement": ALL_PLATFORMS,
    "phone_requirement": "none",
    "funding_requirement": "none",
    "geo_restriction": ["GLOBAL"],
}

# ------------------------------------------------------------------ 标签
IDENTITY_LABELS = {
    "none": ("无需身份资料", "No identity documents"),
    "email": ("邮箱注册", "Email sign-up"),
    "phone": ("手机号验证", "Phone verification"),
    "photo_id": ("护照/证件 + 人脸", "Passport or ID + selfie"),
    "local_id": ("当地证件/税号", "Local ID or tax number"),
    "student": ("学生身份认证", "Student verification"),
    "business": ("企业资料", "Business documents"),
}

RESIDENCY_LABELS = {
    "none": ("无居住地要求", "No residency requirement"),
    "local_address": ("需当地地址", "Local address required"),
    "local_resident": ("需当地居民/居留", "Local residency required"),
    "citizen_only": ("仅本国公民", "Citizens only"),
}

PHONE_LABELS = {
    "none": ("无需手机号", "No phone number"),
    "any_number": ("任意号码（含 +86）", "Any number, +86 included"),
    "local_number": ("须当地号码", "Local number required"),
    "specific_country": ("须指定国家号码", "Number from a specified country"),
}

FUNDING_LABELS = {
    "none": ("无需入金", "No deposit required"),
    "min_deposit": ("需入金/存款", "Deposit required"),
    "direct_deposit": ("需工资/政府直存", "Direct deposit required"),
    "purchase": ("需先消费/购买", "Purchase required"),
    "paid_plan": ("需订购付费套餐", "Paid plan required"),
    "existing_card": ("需已持指定卡/账户", "Existing card or account required"),
}

PLATFORM_LABELS = {
    "ios": ("iOS App", "iOS app"),
    "android": ("Android App", "Android app"),
    "web": ("网页端", "Web"),
}

# 国家 / 地区代号 → 中英名（只为数据里实际用到、以及常见邻国准备）
REGION_NAMES = {
    "GLOBAL": ("全球", "Global"),
    "EEA": ("欧洲经济区", "EEA"),
    "EU": ("欧盟", "EU"),
    "APAC": ("亚太区", "Asia-Pacific"),
    "ASIA": ("亚洲", "Asia"),
    "SEA": ("东南亚", "Southeast Asia"),
    "US": ("美国", "United States"),
    "GB": ("英国", "United Kingdom"),
    "CN": ("中国大陆", "Chinese mainland"),
    "HK": ("香港", "Hong Kong"),
    "MO": ("澳门", "Macau"),
    "TW": ("台湾", "Taiwan"),
    "JP": ("日本", "Japan"),
    "KR": ("韩国", "South Korea"),
    "SG": ("新加坡", "Singapore"),
    "MY": ("马来西亚", "Malaysia"),
    "TH": ("泰国", "Thailand"),
    "VN": ("越南", "Vietnam"),
    "PH": ("菲律宾", "Philippines"),
    "ID": ("印尼", "Indonesia"),
    "IN": ("印度", "India"),
    "MM": ("缅甸", "Myanmar"),
    "LB": ("黎巴嫩", "Lebanon"),
    "QA": ("卡塔尔", "Qatar"),
    "AE": ("阿联酋", "United Arab Emirates"),
    "SA": ("沙特", "Saudi Arabia"),
    "IL": ("以色列", "Israel"),
    "AU": ("澳洲", "Australia"),
    "NZ": ("新西兰", "New Zealand"),
    "CA": ("加拿大", "Canada"),
    "MX": ("墨西哥", "Mexico"),
    "BR": ("巴西", "Brazil"),
    "PE": ("秘鲁", "Peru"),
    "CH": ("瑞士", "Switzerland"),
    "IE": ("爱尔兰", "Ireland"),
    "NL": ("荷兰", "Netherlands"),
    "BE": ("比利时", "Belgium"),
    "PL": ("波兰", "Poland"),
    "CZ": ("捷克", "Czechia"),
    "SK": ("斯洛伐克", "Slovakia"),
    "HU": ("匈牙利", "Hungary"),
    "RO": ("罗马尼亚", "Romania"),
    "HR": ("克罗地亚", "Croatia"),
    "DE": ("德国", "Germany"),
    "FR": ("法国", "France"),
    "ES": ("西班牙", "Spain"),
    "IT": ("意大利", "Italy"),
    "PT": ("葡萄牙", "Portugal"),
    "AT": ("奥地利", "Austria"),
    "DK": ("丹麦", "Denmark"),
    "SE": ("瑞典", "Sweden"),
    "FI": ("芬兰", "Finland"),
    "NO": ("挪威", "Norway"),
    "GR": ("希腊", "Greece"),
    "EE": ("爱沙尼亚", "Estonia"),
    "LT": ("立陶宛", "Lithuania"),
    "LV": ("拉脱维亚", "Latvia"),
    "BG": ("保加利亚", "Bulgaria"),
    "CY": ("塞浦路斯", "Cyprus"),
    "MT": ("马耳他", "Malta"),
    "TR": ("土耳其", "Türkiye"),
    "EG": ("埃及", "Egypt"),
    "BY": ("白俄罗斯", "Belarus"),
    "CU": ("古巴", "Cuba"),
    "IR": ("伊朗", "Iran"),
    "KP": ("朝鲜", "North Korea"),
    "RU": ("俄罗斯", "Russia"),
    "SD": ("苏丹", "Sudan"),
    "SY": ("叙利亚", "Syria"),
}


def _value(deal: dict, field: str):
    """取字段值；缺失或空值退回默认值。"""
    value = deal.get(field)
    if value in (None, "", []):
        return DEFAULTS[field]
    return value


def _region_name(code: str, is_en: bool) -> str:
    zh, en = REGION_NAMES.get(code, (code, code))
    return en if is_en else zh


def geo_text(geo: list[str], is_en: bool) -> str:
    """把 geo_restriction 渲染成一句人话：全球（不含美国）/ 美国、加拿大。"""
    codes = [str(c) for c in geo]
    excluded = [c[1:] for c in codes if c.startswith("-")]
    included = [c for c in codes if not c.startswith("-")]

    def names(items: list[str]) -> str:
        return ("; " if is_en else "、").join(_region_name(i, is_en) for i in items)

    if "GLOBAL" in included:
        if excluded:
            return (
                f"Global, excluding {names(excluded)}"
                if is_en else f"全球（不含{names(excluded)}）"
            )
        return "Global" if is_en else "全球"
    text = names(included)
    if excluded:
        text += f" (excluding {names(excluded)})" if is_en else f"（不含{names(excluded)}）"
    return text


def platform_items(platforms: list[str], is_en: bool) -> list[tuple[str, str]]:
    """按 ios / android / web 固定顺序给出 [(枚举值, 文案)]，供详情页渲染「图标 + 文字」小徽标。"""
    return [(p, PLATFORM_LABELS[p][1 if is_en else 0]) for p in PLATFORMS if p in platforms]


def platform_text(platforms: list[str], is_en: bool) -> str:
    seps = ", " if is_en else "、"
    return seps.join(text for _, text in platform_items(platforms, is_en))


def eligibility_entries(
    deal: dict, is_en: bool = False
) -> list[tuple[str, str, list[tuple[str, str]] | None]]:
    """详情页「参与资格」区块的 (标签, 值文本, 平台徽标) 列表。

    只返回非默认值，默认值整行不出现；平台那一行的第三项是 [(ios/android/web, 文案)]，
    由渲染端换成图标小徽标，其余行为 None。
    """
    rows: list[tuple[str, str, list[tuple[str, str]] | None]] = []

    identity = deal.get("identity_requirement") or DEFAULTS["identity_requirement"]
    if identity != DEFAULTS["identity_requirement"]:
        zh, en = IDENTITY_LABELS.get(identity, (identity, identity))
        rows.append(("身份验证" if not is_en else "Identity", en if is_en else zh, None))

    residency = deal.get("residency_requirement") or DEFAULTS["residency_requirement"]
    if residency != DEFAULTS["residency_requirement"]:
        zh, en = RESIDENCY_LABELS.get(residency, (residency, residency))
        rows.append(("居住要求" if not is_en else "Residency", en if is_en else zh, None))

    platforms = deal.get("platform_requirement")
    if platforms and sorted(platforms) != sorted(ALL_PLATFORMS):
        # 平台徽标只给「要开银行卡的 App」与 eSIM 这两类；其余分类即便数据里写了
        # platform_requirement 也只出文字，不给装饰性图标。
        icons = platform_items(platforms, is_en) if deal.get("category") in PLATFORM_CATEGORIES else None
        rows.append(
            ("可用平台" if not is_en else "Platform", platform_text(platforms, is_en), icons)
        )

    phone = deal.get("phone_requirement") or DEFAULTS["phone_requirement"]
    if phone != DEFAULTS["phone_requirement"]:
        zh, en = PHONE_LABELS.get(phone, (phone, phone))
        rows.append(("手机号" if not is_en else "Phone number", en if is_en else zh, None))

    funding = deal.get("funding_requirement") or DEFAULTS["funding_requirement"]
    if funding != DEFAULTS["funding_requirement"]:
        zh, en = FUNDING_LABELS.get(funding, (funding, funding))
        rows.append(("入金/消费" if not is_en else "Funding", en if is_en else zh, None))

    geo = deal.get("geo_restriction")
    if geo and [str(g) for g in geo] != DEFAULTS["geo_restriction"]:
        rows.append(("可参与地区" if not is_en else "Availability", geo_text(geo, is_en), None))

    return rows


def eligibility_rows(deal: dict, is_en: bool = False) -> list[tuple[str, str]]:
    """只要 (标签, 值文本) 的旧口径，保留给不需要图标的地方。"""
    return [(label, text) for label, text, _ in eligibility_entries(deal, is_en)]


def geo_ld(deal: dict) -> tuple[list[str], list[str]]:
    """JSON-LD 用：返回 (eligibleRegion, ineligibleRegion) 的代号列表。

    只映射这两项；全球无限制时不输出 eligibleRegion（等于不写地区限制），
    排除项写进 ineligibleRegion。
    """
    geo = deal.get("geo_restriction") or []
    codes = [str(g) for g in geo]
    eligible = [c for c in codes if not c.startswith("-")]
    ineligible = [c[1:] for c in codes if c.startswith("-")]
    if "GLOBAL" in eligible:
        eligible = []
    return eligible, ineligible


# ---------------------------------------------------------------- 与 kyc_level 的一致性
# kyc_level 只描述“实名能不能过”，这里描述“够不够资格”，两者必须说得上话：
# 需要当地证件 / 当地居民 / 非中国大陆的单一市场 → foreign_only；
# 护照 + 人脸能过、无居住地门槛 → cn_ok（大陆护照线上可过）；
# 需要海外号码 / 海外卡 / 海外地址但证件可过 → cn_ok_extra。
LOCAL_IDENTITY = {"local_id", "business"}
OVERSEAS_PHONE = {"local_number", "specific_country"}


def implied_kyc(deal: dict) -> str | None:
    """由六个资格字段反推 kyc_level；信息不足时返回 None（不改动原值）。"""
    identity = deal.get("identity_requirement") or DEFAULTS["identity_requirement"]
    residency = deal.get("residency_requirement") or DEFAULTS["residency_requirement"]
    phone = deal.get("phone_requirement") or DEFAULTS["phone_requirement"]
    geo = [str(g) for g in (deal.get("geo_restriction") or ["GLOBAL"])]
    region_tokens = {"EEA", "EU", "APAC", "ASIA", "SEA"}
    excluded = [g[1:] for g in geo if g.startswith("-")]
    included = [g for g in geo if not g.startswith("-")]
    countries = [g for g in included if g not in region_tokens | {"GLOBAL"}]
    # 全球无限制、或只发中国大陆：大陆证件就在“本地”范围内；
    # 只写区域代号（EEA / 亚太…）而没有全球，仍算海外市场
    domestic_ok = ("GLOBAL" in included and not countries and not excluded) or (
        "GLOBAL" not in included and "CN" in countries
    ) or ("GLOBAL" in included and "CN" in countries)
    overseas_only = not domestic_ok

    if identity in LOCAL_IDENTITY or residency == "citizen_only":
        return "cn_ok" if domestic_ok else "foreign_only"
    if residency in ("local_address", "local_resident") and overseas_only:
        return "foreign_only"
    if identity == "photo_id":
        # 护照 + 人脸这类线上实名，大陆护照本身能过；但只能在当地办的仍要额外条件
        return "cn_ok" if domestic_ok else "cn_ok_extra"
    if overseas_only and phone in OVERSEAS_PHONE:
        return "cn_ok_extra"
    return None


# 资格字段推不出“只收某几国护照”这类限制的条目，kyc_level 以人工标定为准
KYC_KEEP = {
    "true-tat-asean-tourist-sim-8gb",
    # 下面三条的 kyc_level 是人工核过材料门槛的结论，由资格字段反推会把它拉错档：
    # dtcpay 要海外地址证明 + 非 +86 号码（cn_ok_extra，反推会变 cn_ok）；
    # sun-phuquoc 需入境越南到店（foreign_only，反推会变 cn_ok）；
    # norma connect 要德国收货地址（cn_ok_extra，反推会变 cn_ok）。
    "dtcpay-esim-5gb-6m",
    "sun-phuquoc-free-esim-5gb",
    "norma-connect-start-esim",
}


def check_kyc(deal: dict) -> str | None:
    """返回冲突说明；一致或无法判断时返回 None。"""
    if deal.get("id") in KYC_KEEP:
        return None
    implied = implied_kyc(deal)
    current = deal.get("kyc_level")
    if implied is None or current in (None, implied):
        return None
    # cn_ok 与 cn_ok_extra 只差“要不要海外手机号/卡”，实际资格一致时不强行改
    if {implied, current} == {"cn_ok", "cn_ok_extra"}:
        return None
    return f"{deal.get('id')}: kyc_level={current} 与资格字段推出的 {implied} 不一致"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return _SLUG_RE.sub("-", str(text or "").lower()).strip("-")
