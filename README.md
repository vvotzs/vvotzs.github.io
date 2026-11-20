# 羊毛情报局 / Deal Hunter

全球优惠情报导航：AI 免费额度、Crypto 奖励、海外银行与跨境汇款邀请、VPS / 云服务额度、eSIM 免费流量、软件学生福利。
每个条目都带价值、门槛与截止时间，点击直达官方活动页。

线上地址：

- 中文：<https://vvotzs.github.io/>
- English：<https://vvotzs.github.io/en/>（`https://vvotzs.github.io/?lang=en` 也可直接进英文版）

## 结构

```
index.html              # 中文静态页面（纯中文 DOM，由脚本生成，卡片全部是真 HTML，利于 SEO）
en/index.html           # 英文静态页面（纯英文 DOM，英文 title / description / OG，方便分享到英文社区）
d/<id>/index.html       # 每条优惠的中文独立详情页（含已归档条目，页顶挂归档提示），给外链与搜索长尾一个稳定落脚点
en/d/<id>/index.html    # 每条优惠的英文独立详情页（title / description / canonical / hreflang / og / JSON-LD 各自独立）
category/<slug>/index.html     # 6 大类的中文静态目录页（banner 面包屑 / 导语 / 全部活跃优惠 / 其他分类导航）
en/category/<slug>/index.html  # 同上，纯英文；slug 取 ai / crypto / bank / cloud / esim / software
about|privacy|disclosure/index.html     # 合规页（中英各一份，页脚只有一行「关于 · 隐私 · 披露」文字链接）
en/about|privacy|disclosure/index.html  # 同上，纯英文；给 AdSense 审核与投稿说明用
assets/css/style.css    # 视觉与交互样式
assets/js/app.js        # 手风琴 / 搜索筛选 / 移动端分页 / 滑轨高亮 / URL 状态同步 / 语言跳转
assets/fav/<domain>.webp # 构建时缓存到本地的站点图标（48×48 WebP，境内直连即可显示，不依赖 google.com）
assets/og-cover.png     # 1200×630 中文社交分享封面（scripts/make_og_cover.py 生成）
assets/og-cover-en.png  # 1200×630 英文社交分享封面（/en/ 的 og:image，同一脚本 `en` 参数生成）
data/deals.json         # 优惠条目（中文 12 项标准字段；抽奖 / 阶梯类另有 value_expected）
data/deals_en.json      # 全部条目的英文翻译，按 id 对应 deals.json（title / highlight / regions / value / content / conditions / steps / risk / source）
data/meta.json          # 统计与最后更新时间
scripts/common.py          # 共用常量与函数（北京时间、类别、状态、value_expected）
scripts/i18n.py            # 界面文案的中英对照表、类别 / 门槛英文标签、英文日期格式
scripts/maintain_deals.py  # 去重、状态标记、归档、meta 与 sitemap（含 /en/ 与 hreflang）
scripts/build_site.py      # 由 deals.json + deals_en.json 生成中英两个 index.html、全部 /d/<id>/ 与 /en/d/<id>/ 详情页、12 个分类目录页，并重建 sitemap.xml
scripts/check_schema.py    # 结构化数据体检：每段 ld+json 必须合法 JSON，Offer / HowTo 字段齐全（构建时自动跑，也可单独跑）
scripts/make_og_cover.py   # 生成中英两张分享封面（`python3 scripts/make_og_cover.py` 全出，加 `en` 只出英文）
docs/workflows-reference/daily-rebuild.yml  # 每日重建工作流模板（不放进 .github/workflows）
ads.txt                        # AdSense 发布商授权文件（当前只有注释，拿到 pub-… 后取消注释填 ID）
robots.txt / sitemap.xml
```

## 投稿（原生弹窗 + Apps Script 直邮）

右侧滑轨正上方的「投稿 / Submit」按钮打开**纯原生 `<dialog>` 弹窗**（Gmail 写信式布局：
左上 `←` 关闭、右上「TG 交流群 + 明黄圆发送徽标」、横线分行的名称 / 链接 / 地区 / 亮点说明），
不加载任何第三方脚本，也没有 `Made with …` 水印。

- 接口：Google Apps Script Web App（项目 `Deal Hunter Submit`，账号 `vvotzs@gmail.com`），
  地址写在 `scripts/build_site.py` 的 `SUBMIT_ENDPOINT`，换接口只改这一处再重建；
  前端从弹窗的 `data-endpoint` 读取，用 `fetch(..., { method: "POST", mode: "no-cors" })`
  提交 `URLSearchParams`（name / url / region / notes / lang / hp_x7 / elapsed_ms）。
- 邮件：脚本里 `MailApp.sendEmail("vvotzs@gmail.com", "[羊毛情报投稿] …", …)`，
  免费额度每天 100 封（个人 Gmail），不占第三方表单名额。
- 必填：名称、链接（链接只要求非空，`http(s)://` 前缀与域名格式都不校验）；地区与亮点选填。
- 防刷：表单里有一个移出屏幕、不占布局、读屏与 Tab 都碰不到的蜜罐字段（`app.js` 读它的 `.value` 当作 `hp_x7`，
  故意不用 `website` / `email` 这类名字，免得密码管理器自动填写把真人误判成机器人），被填入就静默走回执、不发请求；
  提交同时带上 `elapsed_ms`（弹窗打开到点提交的毫秒数）。同一份表单 5 秒内重复提交只发第一次
  （`app.js` 的 `COOLDOWN_MS`），起点存在 `sessionStorage` 的 `ydj_last_sent`，刷新页面或点「再投一条」后仍然生效，
  只有请求失败才清零。
- 服务端参考实现：`docs/apps-script-submit.gs`（蜜罐、`elapsed_ms < 1500`、`CacheService` 每分钟限流、
  `MailApp.getRemainingDailyQuota()` 检查与同链接去重）。线上 Web App 仍是旧版参数，未重新部署，避免中断现有直邮。
- 没有 `<form>`：弹窗内容用 `<div class="sd-form">` 承载，发送按钮（`type="button"`）与单行字段的 Enter
  在 `app.js` 里触发同一段提交逻辑（校验、蜜罐、5 秒冷却、提交中态、回执都不变），多行说明框的 Enter 仍是换行。
  原因：安卓 Chrome 的 Autofill 启发式会忽略 `autocomplete="off"`，只要检测到 `<form>` 加带 `name` / `region`
  这类关键词的输入框，就会在 Gboard 上方弹出钥匙 / 银行卡 / 地址填充条；因此输入框用中性 `id`（`sd-f1`～`sd-f4`）、
  不设 `name` 属性，并带 `autocomplete="nope"` + `data-lpignore` / `data-1p-ignore` / `data-bwignore` / `data-form-type="other"`。
- 三个单行字段（名称 / 链接 / 地区）是 `<textarea rows="1" wrap="off">` 而不是 `<input>`：真机实测那条 🔑💳📍 辅助栏
  只按控件类型判断，对 `<textarea>` 完全不弹（`<input>` 无论换什么 `autocomplete` 值都照弹）。视觉由 `.sd-field-single`
  压成 46px 单行（行高=高度垂直居中、`nowrap`、`overflow:hidden`、`resize:none`），`app.js` 里：`keydown` 拦 Enter 发送，
  `beforeinput` 兜底拦 `insertLineBreak` / `insertParagraph`（Gboard 常常只给 `beforeinput`），输入法组字中与
  `compositionend` 后 200ms 内不发送（拼音选词的回车只算上屏），`input` 事件把粘贴进来的换行折成空格并复位光标。
  多行说明框（`sd-f4`）不受影响，仍是正常换行。
- 蜜罐 `#sd-hp` 同样是 `<textarea rows="1">`，所以 `<dialog id="submit-dialog">` 里**没有任何 `<input>`**：
  `<dialog>.showModal()` 打开时 Chrome 会扫到弹窗内的文本 `<input>` 并聚焦它，那一瞬间就会闪出键盘上方的
  🔑💳📍 辅助栏（点进任一字段、焦点转走后它又消失）。另给 `<dialog>` 加 `tabindex="-1"`（CSS `.submit-dialog:focus{outline:none}`），
  并在 `app.js` 的 `openDialog()` 里手机端（`max-width:680px`）`showModal()` 后显式
  `submitDialog.focus({preventScroll:true})`，让打开时的焦点落在弹窗自己身上、不落到任何表单控件上；
  桌面端维持自动聚焦名称框。
- 兜底：禁用 JS / 不支持 `showModal()` 时，按钮本身就是 TG 群链接
  （<https://t.me/+aAqP0DbW_YMxMmNh>），不会走进死路。
- 关闭：左上 `←`、ESC、点遮罩都可以；提交成功后同一张卡片就地换成紧凑回执
  （薄荷绿对勾 + 「已收到！核验后会尽快收录 ✨」+ 关闭 / 再投一条），此时表单与右上角发送按钮隐藏。
- 手机端位置自适应：平时垂直居中；输入法弹起时加 `.kb-open` 贴到可视区域顶部，
  位置与最大高度由 `visualViewport.offsetTop` / `.height` 写成的 CSS 变量 `--vv-top` / `--vv-max-h` 决定
  （iOS 布局视口不缩、可视区域会平移，只按布局视口定位会被顶出屏幕；Android Chrome 两个高度一起缩，
  所以用「打开弹窗时的 `visualViewport.height`」做基准判断），收起键盘或进入成功页就移除，260ms 缓动平滑回正。

## 中英双语

- **切换**：右下角悬浮小胶囊（中文页显示 `EN`，英文页显示 `中文`），点一下整页跳到另一语言版本，保留当前 `#hash` 与 `?q=` 等筛选参数。
- **渲染方式**：两页各自只输出一种语言。文案仍以 `(中文, English)` 成对维护在 `scripts/i18n.py`，`build_site.py` 渲染 `/` 时取中文、渲染 `/en/` 时取英文，HTML 里不再有 `<span class="t-zh"> / <span class="t-en">` 双份节点。
- **老链接兼容**：`<head>` 最前面有一段极短脚本，`/?lang=en` 立即 `location.replace` 到 `/en/`（`/en/?lang=zh` 跳回 `/`），此前发到 X / Dev.to / Hashnode / Medium 的外链照旧直达。
- **SEO**：两页都带 `hreflang="zh-CN" / "en" / "x-default"`，`x-default` 指向中文首页；`og:image` 各用自己的封面（中文 `og-cover.png` / 英文 `og-cover-en.png`），并用 `og:locale:alternate` 互相声明另一种语言。
- **搜索**：每页只带自己语言的搜索索引（体积减半），中文页用中文关键词、英文页用英文关键词。
- **新增条目记得补翻译**：英文缺字段时页面会回退中文，但 `build_site.py` 会打印“缺少英文翻译”清单，请补齐 `data/deals_en.json`。

## 热榜 tab：右上角计数角标 + 迷你日历

- 四个分区（新收录 / 高价值榜 / 即将截止 / 抽奖）的数量不再写在文字后面，而是绝对定位到 tab 自己的右上角
  （`.hot-tab b`）：数字不占行内宽度，360px 上四个 tab 也不会再出现「高价值榜 1」这种被挤掉末位的裁切。
  选中态是暖橙实心角标，未选中是白底细描边；角标靠 `.hot-tablist` / `.hot-tabs-mobile` 的 `padding-top`
  留出上浮余量，父容器不会裁到它。
- 「即将截止」文字右侧只留一颗 15×16 的内联 SVG 迷你日历（`scripts/build_site.py` 的 `calendar_badge()`），
  日历里直接印这批用到的窗口天数：全部落在 `EXPIRING_DAYS` 天内 → 暖橙 `7`；用到 `CLOSING_WINDOW_DAYS`
  窗口补足 → 薄荷绿 `30`。它本身就是按钮（`button.closing-cal`），点一下弹口径吐司，不再额外写
  「30天 / 30d」或单独一颗 ⓘ。中文英文都是同一个数字写法，不带单位。
- 两个断点只调字号与留白：≤768px 手机四个 tab 一行均分，≤379px 再收半号；行内不换行、不产生横向滚动。

## 首屏 TG 徽标 + 右侧滑轨的一个发现锚点

- `.hero` 行内（标语与更新时间之间的空档）加了一颗 Telegram 群徽标 `a.hero-tg`，指向与投稿弹窗同一个群
  `https://t.me/+aAqP0DbW_YMxMmNh`（`target="_blank" rel="noopener noreferrer"`）。
  徽标是纯 SVG、没有可见文字（`hero_tg_badge()`）：Jun 发来的群聊图形原样复刻（`viewBox="0 0 12 12"`），
  两个 `#191919` 实心圆角气泡，右下那枚带一个小尾巴点出「群聊」，没有底色、没有刻度线；
  原文件的 `<clipPath id="clip0">` 改成页面里唯一的 `id="hero-tg-clip"`（clipPath 的 id 是全文档作用域，
  撞名会把其中一枚裁没）；语义走 `aria-label` + `title`
  （中英各自输出，复用 `submit_tg_aria`）。桌面 20×20px、≤768px 18×18px，盒子只占标语行高
  （18.2px / 15.9px）并让图形绝对居中溢出约 1px，所以 `.hero` 行高与改动前逐像素一致，不撑行、不换行。
  徽标与 `.hero-meta` 两个 `margin-left:auto` 平分空档，图形正好落在空位中间；另挂一圈透明点击热区。
- 右侧滑轨里「新收录 / 高价值榜 / 即将截止」本来就同属页面顶部的一块聚合看板，三格锚点合成一格
  「发现 / Discover」（`href="#hot"`，即 `.hot-board` 的 `id`），位置就是原来「新收录」那一格；
  点它平滑回到看板顶部，看板里当前看的哪块板保持不变。滑轨高亮只要停在看板内任一块板就点亮这一格。
  这一格的图标是 Google Trends 风格的四色上升折线箭头（`i-trends`：蓝 `#4285F4` 上升 → 红 `#EA4335` 下折 →
  黄 `#FBBC05` 上升 → 绿 `#34A853` 实心箭头，颜色走 `--tr-1…--tr-4`）；选中态在实心薄荷绿底上整枚切成纯白。
  最底部的「顶部 / Top」原位置、原文案不变。

## 手绘小徽标（3D 蓝盾 / 3D 沙漏 / AI 芯片 / 明黄发送）

这四枚都是 Jun 给的参考图手绘 / 原样落地，全部是内联矢量，没多一个请求。

- **3D 蓝盾白勾**（`<symbol id="i-verified-shield">`，24×24）：厚盾面 `vs-face` 渐变（`#8FBEFF` → `#6399FF` →`#4C7DF2`），
  右下方一块 `vs-side` 深蓝厚边（就是把盾面路径整条 `translate(1.35 .95)` 垫在后面），
  内凹浅描边槽两道 + 居中纯白对勾（自带蓝调投影与上缘高光）。取代了原来的「✓ 已核验」文字勾号：
  展开卡片的 `.dcheck`、独立详情页「核验状态」、搜索弹窗「已核验」筛选 chip。
- **3D 倾斜沙漏**（`<symbol id="i-hourglass">`，24×24）：整体 `rotate(12…)`，上下陶土橙圆角盘 + 两根立柱（`hg-wood` /
  `hg-wood-dark` 渐变），中间玻璃腔（`hg-glass`）里上是未流完的沙、中间细沙流、下是沙堆（`hg-sand`）。
  入位：顶栏「即将截止」胶囊（桌面 12.5px / 手机 11px）、搜索弹窗「最近截止」排序 chip、
  展开卡片行内的截止提示（`.card.open .deadline .dl-hg`，收起态 `display:none`）、详情页「截止时间」。
- **AI 芯片**（`<symbol id="i-ai">`，512×512）：方芯 + 四则引脚 + 芯内「A」「I」，填充色 `var(--ai-ic, #3292FF)`；
  右侧滑轨「AI」一格在 `.active`（薄荷绿实心胶囊）时由 CSS 把 `--ai-ic` 切成纯白。
  `#ai` 分区标题里那枚同 ID 图标没有设 `--ai-ic`，所以一直是默认蓝。
- **明黄发送徽标**（`send_badge()`，40×40）：`#FEE500` 正圆 + `#191919` 折角纸飞机，路径原样保留。
  它就是 `#sd-send` 按钮的脸：按钮仍 34×34、`background:none`，SVG 30×30 居中，禁用态靠 `opacity`/`grayscale`，点击热区与提交中态不变。

**渐变必须放在 `.vdefs`**：蓝盾与沙漏的 symbol 在 `display:none` 的精灵里，Chrome/Android 下
`<use>` 的 `url(#id)` 会失效（跟页头精灵那张白脸同源）。所以渐变单独放一个 `position:absolute;width:0;height:0`
的可见 `<svg class="vdefs">`（`vector_defs()`，每页一次），既不复重复也不占位、不影响 CLS。

## 「直达」按钮指向哪

主按钮默认指向条目自己的 `url`（官方活动页）。
如果条目是从社区原帖抓的（NodeSeek、NodeLoc、linux.do、Reddit、美卡论坛、Doctor of Credit、官方博客公告等），在 `data/deals.json` 里给它加 `source_url`，按钮就改指原帖；也可以在 `source` 字段里直接写原帖链接，构建时会自动识别。
官方活动链接始终保留在展开详情里，不会丢。

按钮文案跟着去向变：`source_url` 与 `url` 不同时写「原文 ↗ / Source ↗」；确实只有官方活动页可点（包括 `url` 本身就是第三方报道或论坛帖的情形）时写「官网 ↗ / Official ↗」，不再让官方页冒充原帖。构建结束会打印「原文 / 官网」各多少条。

## 日常维护

```bash
python3 scripts/maintain_deals.py   # 先维护数据（去重 / 标记到期 / 归档，过期条目永久保留）
python3 scripts/build_site.py       # 再生成中英两个页面（会顺便把新域名图标下载成 assets/fav/*.webp）
```

新增一条优惠：往 `data/deals.json` 里追加一个对象（字段说明见现有条目），再往 `data/deals_en.json` 补同样的英文，两条命令跑一遍即可。
“最高 $2,000”这类抽奖或阶梯奖励，请同时填 `value_expected`（实际到手期望值），排行榜按它排序。

## 规则

- 只收录能在官方页面核实的优惠；不确定的字段写「待核实」，并放进风险提示。
- 参与门槛分五类：真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请条件。
- 过期活动全部保留进归档，不再自动清理：历史条目是 SEO 长尾流量的落地页，也方便对照往年同期活动。
- 英文翻译保留所有优惠码、金额、百分比与限制条件，不做本地化改写（金额仍是原币种）。
  英文页不允许中日文残留：构建结束会扫一遍 `/en/` 与 `/en/d/**`（去掉注释 / script / svg / `data-*` 后的可见文字），
  命中就让构建失败；语言切换徽标「中文」是唯一白名单（`check_en_pages()`）。品牌中文名仍留在 JSON-LD 的 `seller.name` 与搜索索引里，那是数据不是漏翻。
- 详情页底部内链固定「同类相邻 4 条 + 同地区 2 条」，按条目 id 轮转（`related_deals()`），让每个页面都有入链；
  首页 220+ 个「详情页 ↗」的可见文字保持一致，`aria-label` 带条目标题，读屏与搜索能分清指向哪一条。

## 分类目录页 / 替代优惠 / HowTo 结构化数据

- **分类目录页**（`/category/<slug>/`、`/en/category/<slug>/`，共 12 页）：分类标题、导语与独立 meta description
  收在 `scripts/i18n.py` 的 `CATEGORY_PAGE`（中英成对，中文 description ≥120 字）；列表只收当前活跃条目
  （`status != expired`），按可预期价值降序、同价值新收录在前，每条带图标、价值、门槛、截止、地区与直达详情页的内链；
  页底是其余 5 个分类的横向切换条。详情页面包屑、JSON-LD `BreadcrumbList` 与页底「查看全部优惠」都指向这里，
  `sitemap.xml` 也写入 12 个 URL（`<lastmod>` 取该分类最新核验日）。
- **已归档详情页的「替代优惠」**：仅 `status == "expired"` 时渲染（`alternative_deals()`），放在标题 / 状态提示之后、
  参与步骤之前，最多 3 条同分类活跃优惠 + 一个直达分类目录页的按钮，避免过期页把人直接送走。
- **HowTo JSON-LD**：有参与步骤（`steps` 非空）的详情页在 `Offer` 之外多输出一份 `HowTo`（`name` / `description` /
  `step[]` 为 `HowToStep`，每步带 `text`），整段 JSON 统一把 `</` 转义成 `<\/`，不会提前结束 `<script>`。
- **构建时体检**：`scripts/check_schema.py` 扫全部产物（首页、详情页、分类页），每段 `ld+json` 必须是合法 JSON，
  详情页必须有 `Offer` + `BreadcrumbList`、有步骤的还必须有字段完整的 `HowTo`，不通过就让构建失败（`check_jsonld()`）。
  单独体检：`python3 scripts/check_schema.py`（加 `--list` 顺便列出各页结构化数据类型）。
