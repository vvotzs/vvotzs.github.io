# 羊毛情报局 / Deal Hunter

全球优惠情报导航：AI 免费额度、Crypto 奖励、海外银行与跨境汇款邀请、VPS / 云服务额度、eSIM 免费流量、软件学生福利。
每个条目都带价值、门槛与截止时间，点击直达官方活动页。

线上地址：

- 中文：<https://vvotzs.github.io/>
- English：<https://vvotzs.github.io/en/>（`https://vvotzs.github.io/?lang=en` 也可直接进英文版）

## 结构

```
index.html              # 中文静态页面（由脚本生成，卡片全部是真 HTML，利于 SEO）
en/index.html           # 英文静态页面（同一套数据与样式，英文 title / description / OG，方便分享到英文社区）
assets/css/style.css    # 视觉与交互样式（含中英双语 .t-zh / .t-en 切换规则）
assets/js/app.js        # 手风琴 / 搜索筛选 / 移动端分页 / 滑轨高亮 / URL 状态同步 / 语言切换
assets/fav/<domain>.png # 构建时缓存到本地的站点图标（境内直连即可显示，不依赖 google.com）
assets/og-cover.png     # 1200×630 社交分享封面（scripts/make_og_cover.py 生成）
data/deals.json         # 优惠条目（中文 12 项标准字段；抽奖 / 阶梯类另有 value_expected）
data/deals_en.json      # 124 条英文翻译，按 id 对应 deals.json（title / highlight / regions / value / content / conditions / steps / risk / source）
data/meta.json          # 统计与最后更新时间
scripts/common.py          # 共用常量与函数（北京时间、类别、状态、value_expected）
scripts/i18n.py            # 界面文案的中英对照表、类别 / 门槛英文标签、英文日期格式
scripts/maintain_deals.py  # 去重、状态标记、归档、meta 与 sitemap（含 /en/ 与 hreflang）
scripts/build_site.py      # 由 deals.json + deals_en.json 生成中英两个 index.html（含图标下载）
scripts/make_og_cover.py   # 生成分享封面图
docs/workflows-reference/daily-rebuild.yml  # 每日重建工作流模板（不放进 .github/workflows）
robots.txt / sitemap.xml
```

## 投稿（Tally）

右侧滑轨正上方的「投稿 / Submit」按钮打开 Tally 投稿表单：

- 表单：<https://tally.so/r/J1lj1d>（表单 ID `J1lj1d`，写在 `scripts/build_site.py` 的 `TALLY_FORM_ID`，换表单只改这一处再重建）
- 弹窗：`Tally.openPopup(id, { layout: "modal", width: 520, autoClose: 3000 })`，脚本来自 `https://tally.so/widgets/embed.js`
- 兜底：按钮本身就是指向 `https://tally.so/r/<id>` 的链接，embed.js 没加载（境内网络被墙 / 被拦截）时直接在新标签打开表单
- 通知：表单 Settings → Email notifications → Self email notifications，新投稿发到 vvotzs@gmail.com（免费版收件人固定）

## 中英双语

- **切换**：左下角悬浮小胶囊（中文页显示 `EN`，英文页显示 `中文`），不占顶栏任何空间，也不挡右侧滑轨和卡片按钮。
- **显示机制**：每段文案在 HTML 里同时存在 `<span class="t-zh">` 与 `<span class="t-en">`，由 `<html data-lang>` + CSS 决定显示哪一个。语言在 `<head>` 的引导脚本里就定好，所以不会闪一下另一种语言，JS 关掉时默认中文。
- **语言判定顺序**：`/en/` 路径 → `?lang=en` / `?lang=zh` → `localStorage["ydj-lang"]` → 中文。
- **搜索**：搜索索引同时包含两种语言，英文模式用英文关键词、中文模式用中文关键词。
- **新增条目记得补翻译**：英文缺字段时页面会回退中文，但 `build_site.py` 会打印“缺少英文翻译”清单，请补齐 `data/deals_en.json`。

## 「直达」按钮指向哪

主按钮（卡片上的 `Go ↗` / `Open official page`）默认指向条目自己的 `url`（官方活动页）。
如果条目是从社区原帖抓的（NodeSeek、NodeLoc、linux.do、Reddit 等），在 `data/deals.json` 里给它加 `source_url`，按钮就改指原帖；也可以在 `source` 字段里直接写原帖链接，构建时会自动识别。
官方活动链接始终保留在展开详情里，不会丢。

## 日常维护

```bash
python3 scripts/maintain_deals.py   # 先维护数据（去重 / 标记到期 / 归档，过期条目永久保留）
python3 scripts/build_site.py       # 再生成中英两个页面（会顺便把新域名图标下载到 assets/fav/）
```

新增一条优惠：往 `data/deals.json` 里追加一个对象（字段说明见现有条目），再往 `data/deals_en.json` 补同样的英文，两条命令跑一遍即可。
“最高 $2,000”这类抽奖或阶梯奖励，请同时填 `value_expected`（实际到手期望值），排行榜按它排序。

## 规则

- 只收录能在官方页面核实的优惠；不确定的字段写「待核实」，并放进风险提示。
- 参与门槛分五类：真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请条件。
- 过期活动全部保留进归档，不再自动清理：历史条目是 SEO 长尾流量的落地页，也方便对照往年同期活动。
- 英文翻译保留所有优惠码、金额、百分比与限制条件，不做本地化改写（金额仍是原币种）。
