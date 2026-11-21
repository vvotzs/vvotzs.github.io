# 分类排序：一期打分规则（2026-11-21 上线）

本站的分类列表顺序只在构建时计算，前端永不重排。分数不对外显示，只在
`python3 scripts/build_site.py --explain` 与 `build/score_debug.csv` 里可见。
来源：Hark 五轮定稿 + 318 条真实数据标定（原始评估见 `hark-scoring/打分与赞踩-评估结论.md`，
契约见 `docs/votes-api.md`）。

## 公式

```
S = (20 + V + 15·U) × max(0.2, A × E × G × H × T × L) × R_t + Vote + Fresh

V = 40 · min(1, ln(1+v)/ln(501))        v = value_expected，<=0 取 0
U = 1 人工标定（utility 字段）
A = eSIM：全球 / 大陆漫游 / 中国大陆区 1.0；港台日韩新马 0.9；其他 0.8
    其余分类一律 1.0
E = 真正免费 1.00 / 免费试用 0.85 / 需要充值 0.85 / 需要邀请条件 0.80 / 需要交易量 0.75
G = none 1.00 / cn_ok 0.95 / cn_ok_extra 0.80 / foreign_only 0.50 / 未标定 0.90（告警）
H = 低通过率或长期积压（is_backlogged_deal）0.40；否则 1.00
T = verified == true 1.00；否则 0.85
L = 距 last_verified ≤30 天 1.00；≤60 天 0.90；更久 0.75
R_t = 有 end 且 8–30 天内到期，同时 E≥0.85、G=1.00、H=1.00 时 1.10；否则 1.00
Vote = [全站有效票 ≥100] · 40 · (u − 0.7·n)/(n + 5)   n = u + d（同一 vid 只算最后一票）
Fresh = 未过期且 age(added_at) < 60 天时 10 · 2^(−age/7)；否则 0
```

排序键：`(-round(S,1), -value_expected, -added_at, id)`。

**多样性护栏**：每个分类前 10 条里，同一服务商（`provider` 字段优先，否则归一化域名）
最多 2 条；超出的顺延到第 11 位起。这样「冷门外语免费 eSIM」不会独占榜首。

顶部四个聚合分区保持原规则：最新收录=added_at 降序、高价值榜=value_expected、
即将截止=end 升序、抽奖=上限金额；它们不受本公式影响，也不带赞/踩按钮。

## 数据标定口径

### kyc_level（谁能办）

| 值 | G | 含义 |
|---|---|---|
| `none` | 1.00 | 免 KYC，邮箱 / App 注册即可 |
| `cn_ok` | 0.95 | 大陆身份证或护照线上可过（含香港 / 澳门数字银行、iFAST 英国、Starryblu、UUPAY） |
| `cn_ok_extra` | 0.80 | 大陆证件可过，但另需海外手机号 / 海外 IP / 学生认证 / 海外卡 / 特定市场 App |
| `foreign_only` | 0.50 | 需 SSN / ITIN / 当地税号（Steuer-ID、TIN）/ 英国 eVisa·BRP / 当地居留、地址证明、长期居住，或只能线下入境办理 |

Jun 补充的三条口径：

1. 德国税号、菲律宾 TIN、UK eVisa / BRP 等大陆普通用户很难拿到的证件 → `foreign_only`；
   马来西亚税号这类低门槛可线上办的 → `cn_ok_extra`（无需其他海外条件时可 `cn_ok`）。
2. 需要「线下入境办理、当地长期居住 / 地址证明、或长居后才能拿到」的本地证件 / 税号
   → `foreign_only`。
3. 条款要求当地居留、或正文 / 风险里写了「可能抽查居留许可证 / 地址证明」的银行与卡片
   → `foreign_only`。2026-10 起外区 Wise（护照国与注册居住国不一致时抽查居留许可、
   ≥90 天长签、UK eVisa）、Revolut（要求当地合法居留证明）、N26（清退无 EEA 居留的云开
   用户）都按此处理，risk 里已补一句提示。

### vowifi（仅 esim）

`true` 运营商官方确认这张卡 / 这个套餐支持 Wi-Fi Calling；`false` 官方明确不支持；
`unknown` 含号但未确认（计分按 false）；`n/a` 纯流量、无号码（不显示标签）。
App 内 VoIP（Saily 等）标 `false`，不给 U；社区说法只算 `unknown`。
只在详情页显示事实标签，收起态卡片不显示。

### eSIM 9 维通信参数（`deals.json` 字段）

2026-11-21 起，含号 eSIM 在 `deals.json` 里逐条写齐 8 项，详情页事实区直接由字段渲染
（`esim_comm_facts()`），不再只靠正文叙述：

| 字段 | 取值 | 口径 |
|---|---|---|
| `has_number` / `phone_number` | bool / `"+852"` | 运营商原生号码（不是 App 内 VoIP 号）与号段国码 |
| `cn_roaming` | true / false / `"unknown"` | 能否在中国大陆接入漫游网络（语音/短信） |
| `free_sms_roam` | 同上 | 在大陆收短信是否免费（含 VoWiFi 通道） |
| `vowifi` | `"true"` / `"false"` / `"unknown"` / `"n/a"` | 仅官网或实测明确时给 true/false |
| `long_term_keep` | bool / `"unknown"` | 号码能否长期保留（试用号、游客卡为 false） |
| `annual_keep_cost` / `_en` | 字符串 | 每年最低维护成本，带货币、周期与充值档位 |
| `online_activation` | `cloud` / `partial` / `on_site` / `on_arrival` | 云开 / 部分线上 / 需到店 / 需落地 |
| `local_kyc` | bool / `"unknown"` | 是否必须当地证件或实名 |
| `euicc_compat` | `works` / `partial` / `blocked` / `whitelist` / `"unknown"` | 第三方实体 eUICC（eSTK / 9eSIM 等）能否写入：`whitelist` 是运营商走 EID 白名单，`blocked` 是明确屏蔽或写不进 |

`comm_note` / `comm_note_en` 写明该条的关键限制（如「VoWiFi 只限本国」），`comm_source`
留证据页面，`comm_verified` 是核对日期。没有官网依据的项一律 `unknown`，不靠推断。

第 9 维（2026-11-21 应 Jun 要求补）专记第三方可插拔 eUICC：`euicc_compat` 取值同上，
`euicc_note` / `euicc_note_en` 写清楚是哪类卡能写、哪类会被拒，`euicc_source` 留社区实测帖。
EID 号段决定兼容性：eSTK 为 G+D（89049032），9eSIM V3 为 Kigen（89044045），
9eSIM V0 / V0 Max / B1 与多数小白卡是东信和平 ECP（89086030），部分运营商专门拉黑国产号段；
美系与日系运营商普遍做 EID 白名单，中国大陆运营商因 China CI 与机卡锁定也写不进。
同一条只写「有实测」或「有明确限制」，没实测就 `unknown`。

### utility（U，+15）

`U=1` 只给两类：

1. 真正免费且高普惠刚需、可长期白拿的基础设施：免费域名、免费主机 / 容器 / VPS / 云电脑；
2. eSIM **B 案**：含号 + 可线上开通 + 年保号成本 ≤¥100 + 有官方或实测依据能在陆收短信
   （VoWiFi 或漫游收短信都算，App 内 VoIP 不算）。

## 与旧规则的差异

- 旧 `order_category_deals()` 的 if/else（AI 全球优先、银行按 `is_local_id_bank()` 分两段、
  `is_backlogged_deal()` 沉底）全部由本公式替代；`is_local_id_bank()` 降级为标定参考，
  不再直接参与排序。
- 旧规则只按 value_expected 排，免费小羊毛会被 $100 条目压住；新公式把无价值条目的
  基础分压到 20 分档。
