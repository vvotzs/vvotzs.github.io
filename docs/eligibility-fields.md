# 参与资格字段（Eligibility）：口径与渲染

Bank（94 条）与 eSIM（98 条）全量在 `data/deals.json` 上各带 6 个资格字段，用来回答
详情页最常被追问的那句「我到底够不够格」。字段值一律是英文 code（枚举），
页面文案由 `scripts/eligibility.py` 的标签表按语言取，所以英文页天然零 CJK。

- 标定（每条填什么）：`scripts/label_eligibility.py`，幂等，漏标直接报错；
- 口径与标签（能填什么）：`scripts/eligibility.py`；
- 渲染：`scripts/build_site.py` → 详情页正文「参与资格 / Eligibility」`<dl>`；
- 结构化数据：同一个 Offer 里只映射 `eligibleRegion` / `ineligibleRegion`；
- 体检：`scripts/check_schema.py` 会检查两个 region 字段只能是 ISO 3166-1
  alpha-2 或 EEA / EU / APAC / ASIA / SEA，且两者不重叠。

## 六个字段

| 字段 | 取值 | 默认（= 不渲染） | 含义 |
|---|---|---|---|
| `identity_requirement` | none / email / phone / photo_id / local_id / student / business | email | 要交什么身份资料 |
| `residency_requirement` | none / local_address / local_resident / citizen_only | none | 要不要当地地址 / 居留 / 国籍 |
| `platform_requirement` | `["ios"]` / `["android"]` / `["web"]` 的自由组合 | 三端全可 | 只能在哪个端参与 |
| `phone_requirement` | none / any_number / local_number / specific_country | none | 手机号门槛 |
| `funding_requirement` | none / min_deposit / direct_deposit / purchase / paid_plan / existing_card | none | 要不要先入金 / 直存 / 消费 / 持卡 |
| `geo_restriction` | ISO 3166-1 alpha-2 数组，另有 GLOBAL / EEA / EU / APAC / ASIA / SEA；`"-XX"` 表示排除 | `["GLOBAL"]` | 可参与的国家 / 地区 |

细则：

- `platform_requirement` 只写平台，不写「both」。设备型号、系统版本、必须
  Google Wallet 这类更细的限制写 `conditions` / `risk`，这里只保留三端事实。
- `phone_requirement` 的 `specific_country` 只表示「必须是指定国家的号码」，
  具体是哪一国写在 `conditions` 或由 `geo_restriction` 收窄。
- `funding_requirement` 的 `existing_card` 指「领奖前必须已经持有某张卡 / 某个
  账户 / 某份保单」，不是入金；单纯要充钱的一律用 `min_deposit`。
- `geo_restriction` 记的是**活动可参与地**，不是流量可用地。eSIM 的漫游覆盖国
  已经在 `regions` 里，不重复塞进这里。

## 页面怎么显示

只显示非默认值：默认值（邮箱注册 / 无居住要求 / 三端都能用 / 无需手机号 /
无需入金 / 全球）对应的那一行不出现，所以一屏最多 6 行，常见 3–5 行。
192 条 Bank + eSIM（Bank 94 + eSIM 98）里有 191 条渲染 1–6 行：4 行最多（73 条），其次
5 行（43）、1 行（23）、3 行（21）、2 行（16）、6 行（15）。

唯一的 0 行例外是已归档的 `ubigi-cnet-free-500mb`：它只写了默认值（`email` + `GLOBAL`），
所以不渲染这一块——不是「空区块」，而是「没有区块」（构建只在有非默认行时才插 `<dl>`）。

除了 Bank / eSIM，另有 13 条 AI / 云 / 软件条目也带了这组字段（如
`google-antigravity-science-free`、`claude-max-monthly-api-credits`、`aws-quick-free-plus-trial`、
`tencent-lightvela-free-month`）；其中 12 条会显示，`urnetwork-free-tier-30gib` 只写了默认的
三端平台，同样不出区块。合计全站 203 个中文详情页、203 个英文详情页渲染
「参与资格 / Eligibility」。

```
身份验证   当地证件/税号
居住要求   需当地地址
入金/消费  需入金/存款
可参与地区 美国
```

英文页同一份数据渲染成 `Identity / Residency / Platform / Phone number /
Funding / Availability`，取值也是英文（`Local ID or tax number` 等）。

## 与 kyc_level 的关系

`kyc_level` 只回答「实名能不能过」，这六项回答「够不够资格」。两者冲突时以
实际资格为准，脚本会把 `kyc_level` 改成对得上的值并打印出来。2026-11-21 首次标定
资格字段时，因此改了 5 条：

| 条目 | 原 kyc_level | 改为 | 依据 |
|---|---|---|---|
| `ktm-mobi-japan-esim-1plus1-zero` | foreign_only | cn_ok_extra | 护照/证件不是卡点，卡点是韩国手机号 + 直营店 |
| `umobile-ultra5g-tourist-esim-my` | foreign_only | cn_ok_extra | 外国护照均可，但必须本人到马来西亚机场扫码 |
| `du-uae-free-tourist-esim` | foreign_only | cn_ok_extra | 同上：护照可过，须入境阿联酋 |
| `eand-uae-free-visitor-line-esim` | foreign_only | cn_ok_extra | 同上 |
| `klook-data-bank-gift` | cn_ok_extra | foreign_only | 账户居住地必须是台 / 泰 / 马 / 越，大陆账号不符合 |

`true-tat-asean-tourist-sim-8gb` 属于「只收东盟与印度护照」，六项字段推不出
护照国籍限制，`kyc_level` 保留人工标定（`eligibility.KYC_KEEP`）。

## 新增条目时

1. 在 `scripts/label_eligibility.py` 的 `ELIG` 里补一条（只写非默认值）；
2. `python3 scripts/label_eligibility.py`；
3. `python3 scripts/build_site.py && python3 scripts/check_schema.py`。

Bank / eSIM 新条目漏标会直接报错（`Bank / eSIM 漏标：…`），不会静默生成空区块；
其他分类是可选填，写了就渲染。
