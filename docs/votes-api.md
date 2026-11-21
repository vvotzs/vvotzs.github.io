# 赞 / 踩接口契约（schema 1，2026-11-21 冻结）

本站的票数由 Google Apps Script（GAS）Web App 记录，前端只读一次票数、只做本卡乐观更新；
**页面顺序只在构建时决定，前端永不重排**。二期迁到自购 VPS 时只换 `base`，其余不动。

- `base`：`https://script.google.com/macros/s/AKfycbytBigdTS4LTwtRh6K_jiTPXHOf-6MvljhVuYFDZ9VLfUuTmzgNqNATK_oX2UELJzCJTg/exec`
  （与投稿弹窗同一个 `/exec`；GAS 只有一个地址，用 `?r=` 与 body 里的 `type` 区分。）

## 1. 读票数

```
GET {base}?r=votes
```

```json
{
  "schema": 1,
  "generated_at": "2026-11-21T09:12:33.123Z",
  "items": { "dito-esim-cloud-number-63": [12, 1], "<id>": [up, down] }
}
```

- `items` 只包含已经有票的条目；没有票的 id 不出现，前端按 `0` 处理。
- `generated_at` 一律 UTC ISO 8601。
- 中英文共用同一份票数（`lang` 只记录，不拆分计数）。
- 允许滞后：GAS 的 Properties 读取不保证强一致，前端显示的是快照。

## 2. 投票 / 改票 / 撤销

```
POST {base}
Content-Type: text/plain;charset=utf-8
```

```json
{"schema":1,"type":"vote","id":"dito-esim-cloud-number-63","vid":"9f2c…（32 位小写 hex）","v":1,"reason":"none","lang":"zh"}
```

| 字段 | 取值 |
|---|---|
| `schema` | 固定 `1` |
| `type` | 固定 `"vote"`（投稿走原来的 form-urlencoded，不带这个字段） |
| `id` | 优惠 id，`^[a-z0-9][a-z0-9-]{0,63}$` |
| `vid` | 随机浏览器 ID，32 位小写 hex，不含任何个人信息 |
| `v` | `1` 赞 / `-1` 踩 / `0` 撤销本机此前的投票 |
| `reason` | `none` / `claimed`（已领到）/ `useless`（没用）/ `expired`（已失效）/ `inaccurate`（信息不准） |
| `lang` | `zh` 或 `en`，只记录来源语言 |

成功返回：

```json
{"ok": true, "up": 12, "down": 1}
```

失败返回：`{"ok": false, "error": "code"}`，`code` 为 `bad_body` / `bad_id` / `bad_vid` /
`bad_vote` / `bad_reason` / `rate_limited` / `busy` / `write_failed`。

规则：

- 一个 `(id, vid)` 只有最后一票有效；改票只改计数，不重复累加。
- 点踩后不选原因也已经算一票踩（`reason: "none"`）；选了原因就是同一票换 reason。
- 点「已领到」是赞的 reason，不单独计数。
- 服务端对单个 `vid` 限流（10 分钟最多 30 次投票），不信任前端。
- **原因字段叫 `reason`，不叫 `type`**——`type` 已用于区分投稿 / 投票。

## 3. 导出（给定时任务用，不公开）

```
GET {base}?r=export&token=<EXPORT_TOKEN>
```

返回纯文本，一行一个事件，字段顺序固定：

```
[ts_utc_iso, id, vid, v, reason, lang, schema]
```

例：`["2026-11-21T09:12:33.123Z","dito-esim-cloud-number-63","9f2c…","1","none","zh",1]`

`EXPORT_TOKEN` 只存在 GAS 脚本属性里，不写进仓库；构建任务把导出结果去重后写入
`data/votes_snapshot.json`，构建只读这份快照。

## 4. 存储（GAS 侧）

- `PropertiesService.getScriptProperties()`，零新增授权。
- 单值上限 9 KB：**每条优惠一个 `v:<id>` 键**（值 `{"u":12,"d":1}`），绝不把全站塞进一个键。
- `(id, vid)` 上一票存 `p:<id>:<vid>`（值 `1` / `-1`），撤销时删除。
- 事件日志按块追加 `log_0`、`log_1`…，每块 ≤ 8 KB，只追加不改写。
- 计数在 `LockService` 锁内读改写；限流用 `CacheService`。

## 5. 两期之间不能改的约定

1. `deal id` 永不改名（票数、详情页 URL、内链都以它为键）。
2. 日志是只追加的事件流，计数只是缓存。
3. `vid` 是随机浏览器 ID，不含个人信息。
4. `reason` 是封闭枚举 + schema 版本号，只能新增、不能改旧值含义。
5. 中英文共享同一份票数。
6. `GET` 从第一天就带 `schema` 与 `generated_at`。
7. 排序只在构建时做。
8. 时间一律 UTC ISO。
