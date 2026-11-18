# 羊毛情报局

面向中文用户的全球优惠情报导航：AI 免费额度、Crypto 奖励、海外银行与跨境汇款邀请、VPS / 云服务额度、eSIM 免费流量、软件学生福利。

线上地址：<https://vvotzs.github.io/>

## 结构

```
index.html              # 静态页面（由脚本生成，卡片全部是真 HTML，利于 SEO）
assets/css/style.css    # 视觉与交互样式
assets/js/app.js        # 手风琴 / 搜索筛选 / 移动端分页 / 滑轨高亮
data/deals.json         # 优惠条目（12 项标准字段）
data/meta.json          # 统计与最后更新时间
scripts/maintain_deals.py  # 去重、状态标记、过期清理、meta 与 sitemap
scripts/build_site.py      # 由 deals.json 生成 index.html
robots.txt / sitemap.xml
```

## 日常维护

```bash
python3 scripts/maintain_deals.py   # 先维护数据（去重 / 标记到期 / 清理 30 天前的过期条目）
python3 scripts/build_site.py       # 再生成页面
```

新增一条优惠：往 `data/deals.json` 里追加一个对象（字段说明见现有条目），两条命令跑一遍即可。

## 规则

- 只收录能在官方页面核实的优惠；不确定的字段写「待核实」，并放进风险提示。
- 参与门槛分五类：真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请条件。
- 过期活动保留 30 天后自动清理，避免陈旧信息堆积。
