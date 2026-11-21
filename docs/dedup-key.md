# 去重键 dedup_key：格式与生成规则

每条优惠在 `data/deals.json` 上带一个 `dedup_key`，用来在巡检、投稿、二手信源
之间判断「这是不是同一个活动」。格式固定四段，全小写：

```
brand|category|market|offer_type
```

例：

```
tastytrade|bank|us|sweetbonus-2000
hsbc|bank|gb|premier-switch-500
openai|ai|multi|academic-researchers-plus-2026
legend-vps|cloud|sg|2c2g-secondhand
```

## 四段怎么来

| 段 | 取值 | 说明 |
|---|---|---|
| `brand` | 品牌规范 slug | 中文名 / 带符号的名字在 `common.BRAND_SLUGS` 定死（中信 → `citic`、中国银行 → `boc`、E*TRADE → `etrade`），其余取品牌名前两个 ASCII 词 |
| `category` | ai / crypto / bank / cloud / esim / software | **必须保留分类**：同一家银行的存款奖与同一家交易所的空投不会因为品牌相同撞成一条 |
| `market` | 国家代号 | ISO 3166-1 alpha-2 小写（`gb`、`us`、`ae`）；多市场按字母序 `-` 连接（`ca-us`）；全球 `global`、多区不定 `multi`，另有 `eea`、`apac`、`asia`、`sea` |
| `offer_type` | 活动 slug | 条目 id 去掉开头的品牌 / 来源站（nodeseek 等）/ 市场标记 / 通用词后的剩余部分 |

两个口径要点：

1. **子区域一律收到国家**。`us-la`、`jp-tyo`、`cn-4837` 都只算 `us`、`jp`、`cn`，
   城市 / 机房差异留在 `offer_type`。否则同一个活动换个城市就绕过了判重。
2. **`market` 来自标题开头的 `[区域]` 标签**（全站 339 条都有），标签写法到代号的
   映射在 `common.MARKET_TAGS`；新标签写法要先补进这张表，否则会退成 `multi`。

## 在哪生成、怎么维护

- `common.dedup_key(deal)` 是唯一实现；
- `maintain_deals.py` 每轮巡检重算全部条目的键，手工追加的条目不用记着填；
- `dedup_audit.py` 体检：缺键 / 段数不对 / category 段不是六类之一 / 与大表算出的
  键不一致 / 撞键，并输出「疑似重复」清单（同品牌 + 同分类 + 同市场，标题相似度
  ≥0.72、或官方链接相同且价值相同）。清单只供人工确认，脚本不删任何条目。

```bash
python3 scripts/dedup_audit.py           # 摘要 + 疑似重复清单
python3 scripts/dedup_audit.py --write   # 同时写 docs/dedup-audit.md
```

## 2026-11-21 全库统一

- 339 条全部重新生成，原来缺键 240 条；旧键里 `uk` 统一成 `gb`、`us-la` 这类
  子区域收到国家级；
- 格式错误 `kite|bitrefill|global|campaign-1124` 修正为 `kite|crypto|global|bitrefill-3pct-kite`
  （把信源站当成了 category，条目真实分类是 crypto）；
- 唯一键 339 个、撞键 0 组；疑似重复 1 组（`starryblu-60sgd-signup` 与
  `starryblu-free-virtual-card`，同品牌同官网但一个是消费券、一个是免费虚拟卡，
  人工确认不是重复）。
