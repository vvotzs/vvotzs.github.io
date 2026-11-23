# AGENTS.md — 羊毛情报局（公开接手入口）

本仓库是「羊毛情报局」的全部源码与已发布产物：中文站 <https://vvotzs.github.io/>，英文站 `/en/`。
纯静态、零后端，`main` 分支直接由 GitHub Pages 发布。

## 目录

```
index.html / en/index.html          中英首页（由脚本生成，卡片是真 HTML）
d/<id>/ · en/d/<id>/                每条优惠的中英独立详情页（含归档条目）
category/<slug>/ · en/category/<slug>/  6 类目页（ai / crypto / bank / cloud / esim / software）
about|privacy|disclosure/ · en/…    合规页（中英各一份）
data/deals.json                     优惠数据（中文，12 项标准字段 + 资格/通信等扩展字段）
data/deals_en.json                  英文翻译，按 id 一一对应
data/meta.json                      统计与最后更新时间
data/sources.json                   信源分层调度表（P0/P1/P2，含暂停与手动源）
scripts/                            common / i18n / maintain_deals / build_site / check_schema / plan_round 等
docs/                               规则文档：scoring、dedup-key、eligibility-fields、votes-api、apps-script-submit.gs
assets/                             css / js / 本地品牌图标（48×48 WebP）
```

## 构建与发布

```bash
python3 scripts/maintain_deals.py   # 去重、补 added_at、标状态、归档、写 meta 与 sitemap
python3 scripts/build_site.py       # 生成全部页面；任一校验不过就构建失败
```

- `build_site.py` 内含 `validate()`、`check_en_pages()`（英文页不许残留中日文）、`check_descriptions()`（120–156 字）与结构化数据体检，失败即中止。
- 产物（`index.html`、`en/`、`d/`、`en/d/`、`category/`、`en/category/`、合规页、`data/meta.json`、`sitemap.xml`）都提交进仓库，`main` 推送即上线。
- 巡检取本轮计划：`python3 scripts/plan_round.py --json`；结束时用 `--mark-hit` / `--mark-done` / `--mark-zero` 回写 `data/sources.json`。
- **不要删除**根目录 `googleb403ab28aa8c2b3e.html`（Google Search Console 验证）与 `e4ecde03aa1a475c932d455016e9b95b.txt`（IndexNow key）。
- 不要提交 `reports/`（内部回测表）与 `scripts/__pycache__/`。

## 改动规则

- 收录口径、字段、门槛分类、区服区分、eSIM 9 维、SEO 与校验口径**只在 `README.md` 与 `docs/` 维护**；本文件不复写，冲突时以它们为准。
- 改数据后必须重跑构建；英文缺字段会回退中文，构建会打印「缺少英文翻译」清单，请补齐 `data/deals_en.json`。
- **中文 `title` 的空格边界**：中文与英文 / 数字 / 标点之间不加空格（`[美区]Clear Street券商3%现金配比：最高$10,000`）；纯英文单词之间留单个空格（`Google Cloud`、`U.S. Bank`、`Drei eSIM`、`Bill Pay`）；**英文词 / 品牌后接数值时留一个空格**（`eSIM 3–7天`、`Talkmobile 150GB`、`Capital One 360 Checking`、`Verizon 30天`、`AED 400`、`Gemini 3.1 Pro`）。数字 + 单位仍连写不拆（`1GB`、`500MB`、`1USDT`、`24h`、`30+`、`1C2G`），常见型号 / 缩写 / 版本号 / 优惠码不动（`B2B`、`Web3`、`S3`、`v2`、`H100`、`3D`、`4G`、`5G`、`iOS18`、`MI300X`、`IPv4`、`Qwen4-Max`、`GLM-5.3-Flash`、`MAKE400`）。英文站 `data/deals_en.json` 的 `title` 照常使用英文空格。
- 归档条目永久保留，不清理；归档页的替代推荐与 JSON-LD 由构建自动生成。

## 真实性 6 条

1. 已实现与计划分开，未上线的不要写成已上线。
2. 只收录能在官方页面核实的优惠；不确定的字段写「待核实」并放进风险提示。
3. 严禁编造优惠、金额、截止日或链接。
4. 区分区服（美区 / 英区 / 德区等）与币种，不同区服分别核验，不合并。
5. 被否决或已归档的方案不要当成现行做法。
6. 代码与数据现状优先于文档描述；发现矛盾先标记，不擅自选。

## 接手顺序

`AGENTS.md` → `README.md` → 需要的 `docs/` → 核对 `data/` 与 `scripts/`。
先输出：项目理解、当前阶段、不可擅改的规则、文档与代码不一致处、最重要待办、建议下一步。
**在维护者确认理解正确之前，不改代码、不推送。**

## 私有知识层

决策原因、当前进度、交接记录与内部运营信息在私有仓库 `vvotzs/deals-kb`（需被授权才能读取）。
公开仓库只保留公开安全的规则与构建信息。
