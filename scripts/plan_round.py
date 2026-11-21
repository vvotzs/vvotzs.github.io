#!/usr/bin/env python3
"""羊毛情报局采集调度器：按轮次挑源、轮转关键词、排重核队列、回写抓取时间。

用法（在仓库根目录）：

    python3 scripts/plan_round.py --dry-run          # 看本轮该抓什么（不写文件）
    python3 scripts/plan_round.py --json             # 同上的机器可读版
    python3 scripts/plan_round.py --status           # 表况、到期数、下一轮时间
    python3 scripts/plan_round.py --validate         # 只校验 data/sources.json

    # 抓到后回写（只有这几个命令会改文件）
    python3 scripts/plan_round.py --mark-done uscardforum,nodeseek
    python3 scripts/plan_round.py --mark-hit  uscardforum,nodeseek
    python3 scripts/plan_round.py --mark-zero topup-game          # 整组零结果，下次自动走 fallback 词
    python3 scripts/plan_round.py --mark-hit  uscardforum --apply-downgrades

规则来自 Hark 第七轮合并定稿 + 第八轮充值平台整合（2026-11-21）：
  · 2.5 小时一轮，北京时间 07:30 / 10:00 / 12:30 / 15:00 / 17:30 / 20:00 / 22:30，01:00–07:30 休眠
  · 每轮 12 个到期源 + 4 条待重核老条目
  · 选源顺序：全部到期 P0 → P1（按逾期倍数）→ P2；P2 每轮保底 1 个，保证每周 49 个 P2 轮完一遍
  · 关键词 6 组按 round_index % 6 轮转，只用于 search 类入口，P0 不用关键词
  · 6 组里 通信资源 / AI 与软件 / 返利羊毛 带英文切片（append_en），只给 lang != zh 的源用，
    切片序号 = (r div 6) mod 切片数，仍只发 1 条查询
  · 数字充值/礼品卡平台已合并成 4 个 search_group + 1 个 rss：整组只发 1 条
    `(site:a OR site:b …) (词集)` 查询，词集来自顶层 term_sets.topup 的 T0/T1（按年日 mod 2 轮换，
    不占 r mod 6），零结果后改用 fallback；二手 key 五家 status=manual，不调度
  · 回写 last_crawled_at / last_hit_at；P0 连续 14 天无产出降 P1、P1 30 天降 P2、P2 90 天暂停

数据契约见 data/sources.json 的 _meta 字段；校验失败一律退出码 2。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "data" / "sources.json"
DEALS_PATH = ROOT / "data" / "deals.json"

TZ = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc

# 每轮固定时刻（北京时间），与 scheduled action 的 7 轮一致
ROUND_TIMES = [(7, 30), (10, 0), (12, 30), (15, 0), (17, 30), (20, 0), (22, 30)]
ROUNDS_PER_DAY = len(ROUND_TIMES)
PER_ROUND_SOURCES = 12
PER_ROUND_RECHECK = 4
P2_RESERVE_PER_ROUND = 1          # P2 每轮保底 1 个 → 每周 49 个 P2 源位
P2_ACTIVE_CAP = 49                # 全库调度中的 P2 上限（避免每周积压）
P1_ACTIVE_CAP = 35                # P1 上限：每轮 12 个源时每日 P1 源位 35 个，正好 24h 轮完
FIRST_LOOKBACK_DAYS = 30          # search_group 首抓回看 30 天
GROUP_TERMS_MAX = 3               # 轮转组每次查询最多 3 个词

TIER_ORDER = ("P0", "P1", "P2")
TIER_PRIORITY = {"P0": 3, "P1": 2, "P2": 1}
TIER_CADENCE = {"P0": 2, "P1": 24, "P2": 168}

ENTRY_TYPES = ("rss", "md", "list", "search")
STATUSES = ("active", "paused", "manual")   # manual：留在表里但完全不进调度（二手 key 五家）
CATEGORIES = ("ai", "bank", "cloud", "crypto", "esim", "software")

# 降频阈值（天）
DOWNGRADE_DAYS = {"P0": 14, "P1": 30, "P2": 90}

# 轮次基准：2026-11-21 07:30（北京时间）为第 0 轮
EPOCH_SLOT = datetime(2026, 11, 21, 7, 30, tzinfo=TZ)


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #

def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def parse_ts(value) -> datetime | None:
    """解析 ISO 8601 时间（允许 Z 结尾 / +08:00），空值返回 None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=TZ)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"无法解析时间：{value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_local(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, doc) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #

def validate(doc) -> list[str]:
    """返回错误列表；空列表表示通过。"""
    errors: list[str] = []

    if not isinstance(doc, dict):
        return ["sources.json 顶层必须是对象"]
    if doc.get("schema") != 1:
        errors.append(f"schema 必须为 1，当前 {doc.get('schema')!r}")

    sources = doc.get("sources")
    paused = doc.get("paused_sources", [])
    if not isinstance(sources, list) or not sources:
        return errors + ["sources 必须是非空数组"]
    if not isinstance(paused, list):
        errors.append("paused_sources 必须是数组")

    seen: set[str] = set()
    tier_count = {t: 0 for t in TIER_ORDER}   # 只统计 status=active 的源
    manual_count = 0

    term_sets = doc.get("term_sets")
    if not isinstance(term_sets, dict) or not term_sets:
        errors.append("term_sets 必须是非空对象（如 topup: {T0, T1, fallback}）")
        term_sets = {}
    else:
        for name, spec in term_sets.items():
            if not isinstance(spec, dict):
                errors.append(f"term_sets[{name!r}] 必须是对象")
                continue
            for key in ("T0", "T1"):
                vals = spec.get(key)
                if not isinstance(vals, list) or not vals:
                    errors.append(f"term_sets[{name!r}].{key} 必须是非空数组")
                elif any(not isinstance(v, str) or not v.strip() for v in vals):
                    errors.append(f"term_sets[{name!r}].{key} 只能是非空字符串")
            fb = spec.get("fallback")
            if fb is not None and (not isinstance(fb, list) or not fb):
                errors.append(f"term_sets[{name!r}].fallback 必须是非空数组")

    for idx, src in enumerate(sources):
        where = f"sources[{idx}]"
        if not isinstance(src, dict):
            errors.append(f"{where} 必须是对象")
            continue
        sid = src.get("id")
        if not sid or not isinstance(sid, str):
            errors.append(f"{where} 缺少 id")
            continue
        where = f"sources[{idx}]({sid})"
        if sid in seen:
            errors.append(f"{where} id 重复")
        seen.add(sid)
        for key in ("name", "url", "tier", "entry_type", "cadence_h", "categories", "lang", "status"):
            if key not in src:
                errors.append(f"{where} 缺少字段 {key}")
        tier = src.get("tier")
        status = src.get("status")
        if tier not in TIER_ORDER:
            errors.append(f"{where} tier 非法：{tier!r}")
        elif status == "active":
            tier_count[tier] += 1
        elif status == "manual":
            manual_count += 1
            if not (src.get("manual_note") or src.get("note")):
                errors.append(f"{where} status=manual 必须写 manual_note 说明为什么不自动巡检")
        if src.get("entry_type") not in ENTRY_TYPES:
            errors.append(f"{where} entry_type 非法：{src.get('entry_type')!r}")
        if src.get("status") not in STATUSES:
            errors.append(f"{where} status 非法：{src.get('status')!r}")
        cad = src.get("cadence_h")
        if not isinstance(cad, int) or cad <= 0:
            errors.append(f"{where} cadence_h 必须是正整数")
        elif status == "active" and tier in TIER_CADENCE and cad != TIER_CADENCE[tier]:
            errors.append(
                f"{where} cadence_h={cad} 与 {tier} 默认 {TIER_CADENCE[tier]} 不一致"
                "（如需覆盖请显式加 cadence_override=true）"
            )
        cats = src.get("categories")
        if not isinstance(cats, list) or not cats:
            errors.append(f"{where} categories 必须是非空数组")
        else:
            bad = [c for c in cats if c not in CATEGORIES]
            if bad:
                errors.append(f"{where} categories 含未知分类：{bad}")
        if src.get("keyword_pool") not in (None, "group") and src.get("keyword_pool") not in term_sets:
            errors.append(
                f"{where} keyword_pool={src.get('keyword_pool')!r} 非法"
                f"（只能是 group 或 term_sets 里的键：{', '.join(term_sets) or '无'}）"
            )
        for key in ("last_crawled_at", "last_hit_at", "added_at"):
            if src.get(key) is not None:
                try:
                    parse_ts(src.get(key))
                except ValueError as exc:
                    errors.append(f"{where} {key} {exc}")
        if src.get("entry_type") == "search":
            domains = src.get("search_domains")
            if domains is not None and (not isinstance(domains, list) or not domains):
                errors.append(f"{where} search_domains 必须是非空数组")
            entries = src.get("entries")
            if entries is not None:
                if not isinstance(entries, list) or not entries:
                    errors.append(f"{where} entries 必须是非空数组")
                else:
                    for ei, ent in enumerate(entries):
                        ewhere = f"{where} entries[{ei}]"
                        if not isinstance(ent, dict):
                            errors.append(f"{ewhere} 必须是对象")
                            continue
                        if ent.get("kind") != "search_group":
                            errors.append(f"{ewhere} kind 目前只支持 search_group，当前 {ent.get('kind')!r}")
                        doms = ent.get("domains")
                        if not isinstance(doms, list) or not doms:
                            errors.append(f"{ewhere} domains 必须是非空数组")
                        elif len(doms) > 4:
                            errors.append(
                                f"{ewhere} domains 最多 4 个，当前 {len(doms)} 个"
                                "（一次查询只发 1 条 site: 组合，超了要拆组）"
                            )
                        elif any(not isinstance(d, str) or not d.strip() for d in doms):
                            errors.append(f"{ewhere} domains 只能是非空字符串")
                        ts = ent.get("term_set")
                        if not ts:
                            errors.append(f"{ewhere} 缺少 term_set")
                        elif ts not in term_sets:
                            errors.append(f"{ewhere} term_set={ts!r} 不在 term_sets 里")
            blocked = src.get("blocked")
            if blocked is not None and (
                not isinstance(blocked, list) or any(not isinstance(b, str) for b in blocked)
            ):
                errors.append(f"{where} blocked 必须是字符串数组（直连 403/429 的域名）")
            vurls = src.get("verify_urls")
            if vurls is not None and (
                not isinstance(vurls, dict) or any(not isinstance(v, str) for v in vurls.values())
            ):
                errors.append(f"{where} verify_urls 必须是 {{域名: URL}} 对象")
        zero_streak = src.get("zero_streak")
        if zero_streak is not None and (not isinstance(zero_streak, int) or zero_streak < 0):
            errors.append(f"{where} zero_streak 必须是非负整数")

    for idx, src in enumerate(paused):
        where = f"paused_sources[{idx}]"
        if not isinstance(src, dict):
            errors.append(f"{where} 必须是对象")
            continue
        sid = src.get("id")
        if not sid:
            errors.append(f"{where} 缺少 id")
        elif sid in seen:
            errors.append(f"{where} id 与 sources 重复：{sid}")
        seen.add(sid)
        if src.get("status") != "paused":
            errors.append(f"{where} status 必须为 paused")
        if not src.get("paused_reason"):
            errors.append(f"{where} 缺少 paused_reason")
        try:
            parse_ts(src.get("paused_at"))
        except ValueError as exc:
            errors.append(f"{where} paused_at {exc}")

    if tier_count["P2"] > P2_ACTIVE_CAP:
        errors.append(
            f"调度中的 P2 有 {tier_count['P2']} 个，超过上限 {P2_ACTIVE_CAP}"
            "（每周 7 天 × 每天 7 个 P2 源位）；请把多余的移入 paused_sources"
        )

    groups = doc.get("keyword_groups")
    if not isinstance(groups, list) or len(groups) != 6:
        errors.append("keyword_groups 必须正好 6 组（round_index % 6 轮转）")
    else:
        keys = [g.get("key") for g in groups if isinstance(g, dict)]
        if len(set(keys)) != 6:
            errors.append("keyword_groups 的 key 必须唯一")
        for g in groups:
            if not isinstance(g, dict):
                errors.append("keyword_groups 每项必须是对象")
                continue
            if not g.get("terms"):
                errors.append(f"关键词组 {g.get('key')!r} 没有 terms")
            if not g.get("categories"):
                errors.append(f"关键词组 {g.get('key')!r} 没有 categories")
            slices = g.get("append_en")
            if slices is not None:
                if not isinstance(slices, list):
                    errors.append(f"关键词组 {g.get('key')!r} 的 append_en 必须是切片数组")
                else:
                    for si, sl in enumerate(slices):
                        if not isinstance(sl, list) or not sl:
                            errors.append(f"关键词组 {g.get('key')!r} append_en[{si}] 必须是非空数组")
                        elif len(sl) > GROUP_TERMS_MAX:
                            errors.append(
                                f"关键词组 {g.get('key')!r} append_en[{si}] 最多 {GROUP_TERMS_MAX} 个词，"
                                f"当前 {len(sl)}"
                            )
                        elif any(not isinstance(v, str) or not v.strip() for v in sl):
                            errors.append(f"关键词组 {g.get('key')!r} append_en[{si}] 只能是非空字符串")

    return errors


# --------------------------------------------------------------------------- #
# 轮次与到期
# --------------------------------------------------------------------------- #

def slot_for(now: datetime) -> dict:
    """返回 now 所处的（或最近一个已开始的）轮次信息。"""
    local = now.astimezone(TZ)
    idx_today = None
    for i, (h, m) in enumerate(ROUND_TIMES):
        if (local.hour, local.minute) >= (h, m):
            idx_today = i
    if idx_today is None:
        slot_day = local.date() - timedelta(days=1)
        idx_today = ROUNDS_PER_DAY - 1
    else:
        slot_day = local.date()
    h, m = ROUND_TIMES[idx_today]
    slot_dt = datetime(slot_day.year, slot_day.month, slot_day.day, h, m, tzinfo=TZ)
    days = (slot_dt.date() - EPOCH_SLOT.date()).days
    r = days * ROUNDS_PER_DAY + idx_today
    nxt_day = slot_day
    nxt_idx = idx_today + 1
    if nxt_idx >= ROUNDS_PER_DAY:
        nxt_day = slot_day + timedelta(days=1)
        nxt_idx = 0
        # 跨天时跳过 01:00–07:30 休眠：下一轮就是次日 07:30
    nh, nm = ROUND_TIMES[nxt_idx]
    next_slot = datetime(nxt_day.year, nxt_day.month, nxt_day.day, nh, nm, tzinfo=TZ)
    in_sleep = local.hour < 7 or (local.hour == 7 and local.minute < 30)
    return {
        "round_index": r,
        "slot_at": slot_dt,
        "slot_at_local": fmt_local(slot_dt),
        "next_slot_at_local": fmt_local(next_slot),
        "in_sleep_window": in_sleep,
        "keyword_group_index": r % 6,
    }


def last_crawled(src: dict) -> datetime | None:
    return parse_ts(src.get("last_crawled_at"))


def due_at(src: dict) -> datetime | None:
    lc = last_crawled(src)
    if lc is None:
        return None
    return lc + timedelta(hours=int(src.get("cadence_h") or TIER_CADENCE[src["tier"]]))


def is_due(src: dict, now: datetime) -> bool:
    d = due_at(src)
    return True if d is None else now >= d


def overdue_hours(src: dict, now: datetime) -> float:
    d = due_at(src)
    if d is None:
        return 1e9
    return (now - d).total_seconds() / 3600.0


def overdue_ratio(src: dict, now: datetime) -> float:
    cad = int(src.get("cadence_h") or TIER_CADENCE[src["tier"]])
    return overdue_hours(src, now) / cad


# --------------------------------------------------------------------------- #
# 关键词
# --------------------------------------------------------------------------- #

def group_for_categories(doc: dict, start: int, cats: list[str]) -> dict:
    """从第 start 组开始，找第一个与源分类匹配的组；都不中则用 start 组。"""
    groups = doc["keyword_groups"]
    base = groups[start % len(groups)]
    if "*" in base.get("categories", []):
        return base
    for step in range(len(groups)):
        g = groups[(start + step) % len(groups)]
        gcats = set(g.get("categories", []))
        if "*" in gcats or gcats & set(cats):
            return g
    return base


def pick_terms(terms: list[str], offset: int, count: int = 3) -> list[str]:
    if not terms:
        return []
    count = min(count, len(terms))
    start = offset % len(terms)
    return [terms[(start + i) % len(terms)] for i in range(count)]


def search_group_domains(src: dict) -> list[str]:
    """取 entries 里 search_group 的域名（最多 4 个），没有则空。"""
    for entry in src.get("entries") or []:
        if isinstance(entry, dict) and entry.get("kind") == "search_group":
            return [str(d) for d in entry.get("domains") or []]
    return []


def term_set_name(src: dict) -> str | None:
    """取 search_group 的 term_set（如 topup）；没有则 None。"""
    for entry in src.get("entries") or []:
        if isinstance(entry, dict) and entry.get("kind") == "search_group":
            ts = entry.get("term_set")
            return str(ts) if ts else None
    return None


def search_domains(src: dict) -> list[str]:
    domains = search_group_domains(src) or src.get("search_domains")
    if domains:
        return list(domains)
    host = str(src.get("url", ""))
    host = host.split("://", 1)[-1].split("/", 1)[0]
    return [host] if host else []


def quote_term(term: str) -> str:
    """英文多词短语加引号（如 "top up bonus"）；中文/混排不加，避免切词后零召回。"""
    t = str(term).strip()
    if not t:
        return t
    if '"' in t:
        return t
    return f'"{t}"' if (" " in t and t.isascii()) else t


def build_query(src: dict, terms: list[str]) -> str:
    domains = search_domains(src)
    site = " OR ".join(f"site:{d}" for d in domains)
    if not terms:
        return f"({site})"
    return f"({site}) ({' OR '.join(quote_term(t) for t in terms)})"


def topup_variant(now: datetime) -> str:
    """充值词集按「一年第几天 mod 2」轮换 T0 / T1，不占 r mod 6。"""
    return "T0" if now.astimezone(TZ).timetuple().tm_yday % 2 == 0 else "T1"


def plan_keywords(doc: dict, src: dict, r: int, ordinal: int, now: datetime) -> dict:
    """给本轮这个源分配关键词。ordinal 用于错开同轮不同源的取词位置。"""
    cats = src.get("categories", [])
    tset = term_set_name(src) or (
        src.get("keyword_pool") if src.get("keyword_pool") not in (None, "group") else None
    )
    if tset:
        spec = (doc.get("term_sets") or {}).get(tset) or {}
        variant = topup_variant(now)
        streak = int(src.get("zero_streak") or 0)
        if streak > 0 and spec.get("fallback"):
            variant = "fallback"
        terms = [str(t) for t in (spec.get(variant) or spec.get("fallback") or [])]
        return {
            "pool": "term_set",
            "group": spec.get("label") or f"独立词集 {tset}",
            "group_key": tset,
            "variant": variant,
            "terms": terms,
            "fallback_terms": [str(t) for t in spec.get("fallback") or []],
            "zero_streak": streak,
            "query": build_query(src, terms),
        }
    group = group_for_categories(doc, r % 6, cats)
    slices = group.get("append_en") or []
    if slices and str(src.get("lang") or "") != "zh":
        idx = (r // 6) % len(slices)
        picked = [str(t) for t in slices[idx]][:GROUP_TERMS_MAX]
        return {
            "pool": "group_en",
            "group": group.get("name") or group.get("key"),
            "group_key": group.get("key"),
            "slice": idx,
            "terms": picked,
            "query": build_query(src, picked),
        }
    picked = pick_terms(group["terms"], r // 6 + ordinal)
    return {
        "pool": "group",
        "group": group.get("name") or group.get("key"),
        "group_key": group.get("key"),
        "terms": picked,
        "query": build_query(src, picked),
    }


# --------------------------------------------------------------------------- #
# 选源
# --------------------------------------------------------------------------- #

def after_date_for(src: dict, now: datetime) -> str:
    """search_group 的时间窗：已抓过用 last_crawled_at − 1 天，首抓用今天 − 30 天。"""
    lc = last_crawled(src)
    base = (lc - timedelta(days=1)) if lc else (now - timedelta(days=FIRST_LOOKBACK_DAYS))
    return base.astimezone(TZ).strftime("%Y-%m-%d")


def select_sources(doc: dict, now: datetime, r: int) -> dict:
    active = [s for s in doc["sources"] if s.get("status") == "active"]
    due = [s for s in active if is_due(s, now)]
    by_tier = {t: [s for s in due if s["tier"] == t] for t in TIER_ORDER}
    for t in TIER_ORDER:
        by_tier[t].sort(key=lambda s: (-overdue_ratio(s, now), s["id"]))

    selected: list[dict] = []
    selected.extend(by_tier["P0"][:PER_ROUND_SOURCES])
    remaining = PER_ROUND_SOURCES - len(selected)

    p2_reserved = min(P2_RESERVE_PER_ROUND, len(by_tier["P2"]), remaining)
    p1_take = min(len(by_tier["P1"]), remaining - p2_reserved)
    selected.extend(by_tier["P1"][:p1_take])
    remaining = PER_ROUND_SOURCES - len(selected)

    # 保底 P2
    p2_taken = 0
    for src in by_tier["P2"][:p2_reserved]:
        if remaining <= 0:
            break
        selected.append(src)
        p2_taken += 1
        remaining -= 1

    # 还有空位：先补 P1，再补 P2
    for src in by_tier["P1"][p1_take:]:
        if remaining <= 0:
            break
        selected.append(src)
        remaining -= 1
    for src in by_tier["P2"][p2_taken:]:
        if remaining <= 0:
            break
        selected.append(src)
        remaining -= 1

    rows = []
    for ordinal, src in enumerate(selected):
        od = overdue_hours(src, now)
        first_crawl = od >= 1e8      # last_crawled_at 为空：新源首抓
        row = {
            "id": src["id"],
            "name": src["name"],
            "tier": src["tier"],
            "priority": TIER_PRIORITY[src["tier"]],
            "entry_type": src["entry_type"],
            "url": src["url"],
            "fetch_url": src.get("entry_url") or src["url"],
            "categories": src["categories"],
            "lang": src["lang"],
            "cadence_h": src["cadence_h"],
            "overdue_h": None if first_crawl else round(od, 1),
            "first_crawl": first_crawl,
            "last_crawled_at": src.get("last_crawled_at"),
            "tool": src.get("tool") or ("web_search" if src["entry_type"] == "search" else "web_fetch"),
        }
        if src.get("tool") and src.get("tool") == "gog-gmail":
            row["command"] = (
                "gog --readonly --account vvotzs@gmail.com gmail search "
                f"'{src.get('query')}'"
            )
            row["query"] = src.get("query")
        elif src["entry_type"] == "search":
            kw = plan_keywords(doc, src, r, ordinal, now)
            row["keyword_pool"] = kw["pool"]
            row["keyword_group"] = kw["group"]
            row["keywords"] = kw["terms"]
            row["query"] = src.get("query") or kw["query"]
            if kw.get("variant"):
                row["term_set"] = kw["group_key"]
                row["term_variant"] = kw["variant"]
                row["fallback_terms"] = kw.get("fallback_terms") or []
                row["zero_streak"] = kw.get("zero_streak", 0)
            if kw.get("slice") is not None:
                row["lang_slice"] = kw["slice"]
            group_domains = search_group_domains(src)
            if group_domains:
                row["search_group"] = {
                    "domains": group_domains,
                    "blocked": list(src.get("blocked") or []),
                    "verify_urls": dict(src.get("verify_urls") or {}),
                    "after_date": after_date_for(src, now),
                    "discovered_from_hint": f"{src['id']}:{group_domains[0]}（或组内实际命中的域名）",
                    "hit_rule": "结果 URL 落在组内域名、url 与 dedup_key 都不在 deals/candidates，"
                                "且按 Q4(e) 写成候选/条目，才 --mark-hit；零结果用 --mark-zero 下次走 fallback",
                }
            if src.get("tool") == "x-search":
                row["query"] = " OR ".join(kw["terms"])
                row["command"] = f"x-search {row['query']}"
        rows.append(row)

    deferred = {
        t: max(0, len(by_tier[t]) - sum(1 for s in selected if s["tier"] == t)) for t in TIER_ORDER
    }
    return {"sources": rows, "due_counts": {t: len(by_tier[t]) for t in TIER_ORDER}, "deferred": deferred}


# --------------------------------------------------------------------------- #
# 重核队列
# --------------------------------------------------------------------------- #

def days_until(date_str, today) -> int | None:
    if not date_str:
        return None
    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - today).days


def select_rechecks(doc: dict, now: datetime, r: int, count: int = PER_ROUND_RECHECK) -> list[dict]:
    """按 Hark 的次序挑待重核老条目；不足时按 last_verified 最旧轮转补足。"""
    try:
        deals = load_json(DEALS_PATH)
    except FileNotFoundError:
        return []
    if isinstance(deals, dict):
        deals = deals.get("deals", [])
    if not isinstance(deals, list):
        return []

    today = now.astimezone(TZ).date()

    # 规则 1：被 ≥2 个不同 vid 标为 expired / inaccurate
    flags: dict[str, set[str]] = {}
    try:
        votes = load_json(ROOT / "data" / "votes_snapshot.json")
        for deal_id, val in (votes.get("items") or {}).items():
            if isinstance(val, dict):
                for f in val.get("flags") or []:
                    reason = (f or {}).get("reason")
                    vid = (f or {}).get("vid")
                    if reason in ("expired", "inaccurate") and vid:
                        flags.setdefault(deal_id, set()).add(vid)
    except (FileNotFoundError, ValueError):
        pass

    ranked: list[tuple[int, int, dict, str]] = []
    for d in deals:
        if not isinstance(d, dict) or d.get("status") == "expired":
            continue
        did = d.get("id")
        if not did:
            continue
        lv = parse_ts(d.get("last_verified"))
        age = (now - lv).days if lv else 10_000
        end_days = days_until(d.get("end"), today)
        priority = None
        reason = None
        if len(flags.get(did, set())) >= 2:
            priority, reason = 0, f"社区标记失效/不准（{len(flags[did])} 个 vid）"
        elif end_days is not None and 0 <= end_days <= 7 and age >= 1:
            priority, reason = 1, f"{end_days} 天内到期（fixed）"
        elif end_days is None and age > 14:
            priority, reason = 2, f"无截止日且 {age} 天未核（unstated）"
        elif end_days is not None and end_days > 7 and age > 30:
            priority, reason = 3, f"长期活动且 {age} 天未核（ongoing）"
        if priority is None:
            continue
        ranked.append((priority, age, d, reason))

    ranked.sort(key=lambda t: (t[0], -t[1], zlib.crc32(f"{t[2].get('id')}:{r}".encode())))

    picked: list[tuple[int, int, dict, str]] = []
    cat_count: dict[str, int] = {}
    for item in ranked:
        cat = item[2].get("category") or "?"
        if cat_count.get(cat, 0) >= 2 and len(ranked) > count:
            continue
        picked.append(item)
        cat_count[cat] = cat_count.get(cat, 0) + 1
        if len(picked) >= count:
            break

    # 兜底：按最旧核验时间轮转补足
    if len(picked) < count:
        chosen = {p[2].get("id") for p in picked}
        pool = []
        for d in deals:
            if not isinstance(d, dict) or d.get("status") == "expired" or d.get("id") in chosen:
                continue
            lv = parse_ts(d.get("last_verified"))
            if lv is not None and (now - lv).days == 0:
                continue   # 今天已重核过，不再排
            pool.append((lv or datetime(1970, 1, 1, tzinfo=UTC), str(d.get("id"))))
        pool.sort()
        if pool:
            start = (r * count) % len(pool)
            by_id = {d.get("id"): d for d in deals if isinstance(d, dict)}
            for i in range(len(pool)):
                if len(picked) >= count:
                    break
                did = pool[(start + i) % len(pool)][1]
                d = by_id.get(did)
                if not d:
                    continue
                lv = parse_ts(d.get("last_verified"))
                age = (now - lv).days if lv else 10_000
                picked.append((9, age, d, f"轮转补足（{age} 天未核）"))

    out = []
    for priority, age, d, reason in picked:
        out.append({
            "id": d.get("id"),
            "title": (d.get("title") or "")[:60],
            "category": d.get("category"),
            "end": d.get("end") or None,
            "last_verified": d.get("last_verified"),
            "age_days": None if age >= 10_000 else age,
            "reason": reason,
            "url": d.get("url"),
            "source_url": d.get("source_url"),
        })
    return out


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #

def build_plan(doc: dict, now: datetime) -> dict:
    info = slot_for(now)
    r = info["round_index"]
    sel = select_sources(doc, now, r)
    groups = doc["keyword_groups"]
    g = groups[r % len(groups)]
    slices = g.get("append_en") or []
    slice_idx = (r // len(groups)) % len(slices) if slices else None
    topup_spec = (doc.get("term_sets") or {}).get("topup") or {}
    variant = topup_variant(now)
    plan = {
        "schema": 1,
        "generated_at": fmt_ts(now),
        "round": {
            "index": r,
            "slot_at": fmt_local(info["slot_at"]),
            "next_slot_at": info["next_slot_at_local"],
            "in_sleep_window": info["in_sleep_window"],
            "keyword_group": {
                "key": g.get("key"),
                "name": g.get("name"),
                "terms": g["terms"],
                "en_slice": slices[slice_idx] if slice_idx is not None else [],
                "en_slice_index": slice_idx,
                "en_slice_note": "只用于 lang != zh 的源；中文论坛仍用中文 terms" if slices else None,
            },
            "term_set": {
                "name": "topup",
                "variant": variant,
                "terms": topup_spec.get(variant, []),
                "fallback": topup_spec.get("fallback", []),
                "rule": "按一年第几天 mod 2 轮换 T0/T1，不占 r mod 6；零结果下次走 fallback",
            },
        },
        "sources": sel["sources"],
        "recheck": select_rechecks(doc, now, r),
        "due_counts": sel["due_counts"],
        "deferred": sel["deferred"],
        "totals": {
            "active_sources": sum(1 for s in doc["sources"] if s.get("status") == "active"),
            "paused_sources": len(doc.get("paused_sources", [])),
            "manual_sources": sum(1 for s in doc["sources"] if s.get("status") == "manual"),
            **{
                f"tier_{t}": sum(
                    1 for s in doc["sources"] if s["tier"] == t and s.get("status") == "active"
                )
                for t in TIER_ORDER
            },
        },
    }
    return plan


def print_plan_text(plan: dict) -> None:
    rnd = plan["round"]
    print(f"轮次 #{rnd['index']}  槽位 {rnd['slot_at']}（下一轮 {rnd['next_slot_at']}）")
    if rnd["in_sleep_window"]:
        print("！当前处于 01:00–07:30 休眠窗口，不应开跑；下一轮请等 07:30")
    print(f"关键词组：{rnd['keyword_group']['name']}（{rnd['keyword_group']['key']}）")
    print(f"本组词：{' / '.join(rnd['keyword_group']['terms'])}")
    if rnd["keyword_group"].get("en_slice"):
        print(f"英文切片（只给 lang≠zh 的源）：{' / '.join(rnd['keyword_group']['en_slice'])}")
    ts = rnd["term_set"]
    print(f"充值词集：{ts['name']} · {ts['variant']}：{' / '.join(ts['terms'])}")
    print(f"  零结果时下次走 fallback：{' / '.join(ts['fallback'])}")
    print()
    print(f"本轮 {len(plan['sources'])} 个源（到期 P0 {plan['due_counts']['P0']} / P1 {plan['due_counts']['P1']}"
          f" / P2 {plan['due_counts']['P2']}，未排上 P1 {plan['deferred']['P1']}、P2 {plan['deferred']['P2']}）")
    for i, s in enumerate(plan["sources"], 1):
        od = "首抓（回看 30 天）" if s.get("first_crawl") else f"逾期 {s['overdue_h']}h"
        head = f"{i:>2}. [{s['tier']}·P{s['priority']}] {s['name']}（{s['entry_type']}，{od}）"
        print(head)
        if s["entry_type"] == "search":
            print(f"     查询：{s.get('query')}")
            if s.get("search_group"):
                grp = s["search_group"]
                print(f"     整组 1 条查询｜域名 {', '.join(grp['domains'])}｜after_date {grp['after_date']}")
                if grp.get("blocked"):
                    print(f"     直连 blocked（只核验不抓取）：{', '.join(grp['blocked'])}")
                if grp.get("verify_urls"):
                    print(f"     核验页：{grp['verify_urls']}")
                print(f"     记录：discovered_from 写 {grp['discovered_from_hint']}；{grp['hit_rule']}")
            if s.get("command"):
                print(f"     命令：{s['command']}")
        else:
            print(f"     抓取：{s['fetch_url']}")
    print()
    print(f"待重核 {len(plan['recheck'])} 条：")
    for i, d in enumerate(plan["recheck"], 1):
        print(f"{i:>2}. {d['id']}｜{d['title']}｜{d['reason']}｜last_verified {d['last_verified']}")
    print()
    t = plan["totals"]
    print(f"表况：调度中 {t['active_sources']}（P0 {t['tier_P0']} / P1 {t['tier_P1']} / P2 {t['tier_P2']}）"
          f"，手动不调度 {t['manual_sources']}，暂停留档 {t['paused_sources']}")


# --------------------------------------------------------------------------- #
# 回写与降频
# --------------------------------------------------------------------------- #

def find_source(doc: dict, sid: str) -> dict | None:
    for s in doc["sources"]:
        if s.get("id") == sid:
            return s
    return None


def cmd_mark(doc: dict, ids: list[str], now: datetime, hit: bool) -> int:
    ok, missing = 0, []
    for sid in ids:
        src = find_source(doc, sid)
        if not src:
            missing.append(sid)
            continue
        stamp = fmt_ts(now)
        src["last_crawled_at"] = stamp
        if hit:
            src["last_hit_at"] = stamp
            src["zero_streak"] = 0
        ok += 1
    if missing:
        print(f"未找到这些 id：{', '.join(missing)}", file=sys.stderr)
    print(f"已回写 {ok} 个源的 last_crawled_at{' 与 last_hit_at' if hit else ''} → {fmt_local(now)}")
    return 0 if not missing else 1


def cmd_mark_zero(doc: dict, ids: list[str], now: datetime) -> int:
    """整组零结果：记 zero_streak，下次自动改用 fallback 词集。"""
    ok, missing = 0, []
    for sid in ids:
        src = find_source(doc, sid)
        if not src:
            missing.append(sid)
            continue
        stamp = fmt_ts(now)
        src["last_crawled_at"] = stamp
        src["zero_streak"] = int(src.get("zero_streak") or 0) + 1
        src["last_zero_at"] = stamp
        ok += 1
        print(f"  {sid}: zero_streak={src['zero_streak']}，下次用 fallback 词集")
    if missing:
        print(f"未找到这些 id：{', '.join(missing)}", file=sys.stderr)
    print(f"已记 {ok} 个源零结果 → {fmt_local(now)}")
    return 0 if not missing else 1


def cmd_downgrades(doc: dict, now: datetime, write: bool) -> int:
    changes = []
    for src in list(doc["sources"]):
        if src.get("status") != "active":
            continue          # manual 源不调度，也不参与降频
        tier = src["tier"]
        ref = parse_ts(src.get("last_hit_at")) or parse_ts(src.get("last_crawled_at")) or parse_ts(src.get("added_at"))
        if ref is None:
            continue
        idle_days = (now - ref).days
        threshold = DOWNGRADE_DAYS[tier]
        if idle_days < threshold:
            continue
        if tier == "P0":
            src["tier"] = "P1"
            src["cadence_h"] = TIER_CADENCE["P1"]
            changes.append((src["id"], "P0→P1", idle_days))
        elif tier == "P1":
            p2_count = sum(1 for s in doc["sources"] if s["tier"] == "P2")
            if p2_count < P2_ACTIVE_CAP:
                src["tier"] = "P2"
                src["cadence_h"] = TIER_CADENCE["P2"]
                changes.append((src["id"], "P1→P2", idle_days))
            else:
                doc["sources"].remove(src)
                doc.setdefault("paused_sources", []).append({
                    **src,
                    "status": "paused",
                    "tier_before_pause": "P1",
                    "paused_at": fmt_ts(now),
                    "paused_reason": f"P1 连续 {idle_days} 天无产出且 P2 配额已满",
                })
                changes.append((src["id"], "P1→paused", idle_days))
        elif tier == "P2":
            doc["sources"].remove(src)
            doc.setdefault("paused_sources", []).append({
                **src,
                "status": "paused",
                "tier_before_pause": "P2",
                "paused_at": fmt_ts(now),
                "paused_reason": f"P2 连续 {idle_days} 天无产出",
            })
            changes.append((src["id"], "P2→paused", idle_days))
    if not changes:
        print("没有触发降频的源（阈值：P0 14 天 / P1 30 天 / P2 90 天无产出）")
        return 0
    print(f"{'已应用' if write else '预览（未写盘，加 --write 才落盘）'} {len(changes)} 处降频：")
    for sid, what, days in changes:
        print(f"  {sid}: {what}（{days} 天无产出）")
    return 0


def cmd_pause(doc: dict, ids: list[str], reason: str, now: datetime) -> int:
    moved = 0
    for sid in ids:
        src = find_source(doc, sid)
        if not src:
            print(f"未找到调度中的源：{sid}", file=sys.stderr)
            continue
        doc["sources"].remove(src)
        doc.setdefault("paused_sources", []).append({
            **src,
            "status": "paused",
            "tier_before_pause": src["tier"],
            "paused_at": fmt_ts(now),
            "paused_reason": reason or "人工暂停",
        })
        moved += 1
    print(f"已暂停 {moved} 个源（移入 paused_sources，不占 P2 配额）")
    return 0


def cmd_activate(doc: dict, ids: list[str], now: datetime, write: bool) -> int:
    ok = 0
    for sid in ids:
        src = next((s for s in doc.get("paused_sources", []) if s.get("id") == sid), None)
        if not src:
            print(f"paused_sources 里没有：{sid}", file=sys.stderr)
            continue
        tier = src.get("tier_before_pause") or src.get("tier") or "P2"
        if tier == "P2" and sum(1 for s in doc["sources"] if s["tier"] == "P2") >= P2_ACTIVE_CAP:
            print(f"无法恢复 {sid}：P2 已满 {P2_ACTIVE_CAP} 个，请先暂停另一个 P2", file=sys.stderr)
            continue
        row = {k: v for k, v in src.items()
               if k not in ("paused_at", "paused_reason", "tier_before_pause")}
        row["tier"] = tier
        row["cadence_h"] = TIER_CADENCE[tier]
        row["status"] = "active"
        row["last_crawled_at"] = row.get("last_crawled_at") or fmt_ts(now)
        doc["paused_sources"].remove(src)
        doc["sources"].append(row)
        ok += 1
    print(f"{'已恢复' if write else '预览（加 --write 落盘）：可恢复'} {ok} 个源")
    return 0


def cmd_status(doc: dict, now: datetime) -> int:
    info = slot_for(now)
    active = [s for s in doc["sources"] if s.get("status") == "active"]
    print(f"现在 {fmt_local(now)}｜本轮槽位 {info['slot_at_local']}｜"
          f"下一轮 {info['next_slot_at_local']}{'（休眠中）' if info['in_sleep_window'] else ''}")
    for t in TIER_ORDER:
        rows = [s for s in active if s["tier"] == t]
        due = [s for s in rows if is_due(s, now)]
        print(f"  {t}（priority {TIER_PRIORITY[t]}，{TIER_CADENCE[t]}h）：{len(rows)} 个，到期 {len(due)}")
    p1 = sum(1 for s in active if s["tier"] == "P1")
    p0 = sum(1 for s in active if s["tier"] == "P0")
    manual = sum(1 for s in doc["sources"] if s.get("status") == "manual")
    p1_slots = PER_ROUND_SOURCES * ROUNDS_PER_DAY - p0 * ROUNDS_PER_DAY - P2_RESERVE_PER_ROUND * ROUNDS_PER_DAY
    print(f"  手动不调度（status=manual）：{manual} 个")
    print(f"  暂停留档：{len(doc.get('paused_sources', []))} 个")
    print(f"  每日源位 {PER_ROUND_SOURCES * ROUNDS_PER_DAY} = P0 {p0 * ROUNDS_PER_DAY} + P1 {p1_slots} + P2 {P2_RESERVE_PER_ROUND * ROUNDS_PER_DAY}"
          f"；P1 现有 {p1} 个（上限 {P1_ACTIVE_CAP}）→ 实际轮询周期约 {p1 / max(1, p1_slots) * 24:.1f}h")
    print(f"  P2 上限 {P2_ACTIVE_CAP}，当前 {sum(1 for s in active if s['tier'] == 'P2')}")
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="羊毛情报局采集调度器")
    ap.add_argument("--sources", default=str(SOURCES_PATH), help="sources.json 路径")
    ap.add_argument("--now", help="假装现在是这个时间（ISO 8601，默认取系统时间）")
    ap.add_argument("--dry-run", action="store_true", help="只出计划，不写文件（默认行为）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--status", action="store_true", help="只看表况与到期数")
    ap.add_argument("--validate", action="store_true", help="只校验 schema 与配额")
    ap.add_argument("--mark-done", metavar="IDS", help="确认这些源已抓（写 last_crawled_at）")
    ap.add_argument("--mark-hit", metavar="IDS", help="这些源本轮有新产出（写 last_crawled_at + last_hit_at）")
    ap.add_argument("--mark-zero", metavar="IDS", help="这些 search_group 本轮零结果（记 zero_streak，下次改用 fallback 词集）")
    ap.add_argument("--apply-downgrades", action="store_true", help="按无产出天数自动降频/暂停")
    ap.add_argument("--pause", metavar="IDS", help="人工把这些源移入 paused_sources")
    ap.add_argument("--activate", metavar="IDS", help="把 paused_sources 里的源恢复到调度")
    ap.add_argument("--reason", default="", help="与 --pause 搭配的暂停原因")
    ap.add_argument("--write", action="store_true", help="与 --apply-downgrades / --pause / --activate 搭配，才真正落盘")
    args = ap.parse_args(argv)

    now = parse_ts(args.now) if args.now else now_utc()
    if now is None:
        now = now_utc()
    path = Path(args.sources)
    try:
        doc = load_json(path)
    except FileNotFoundError:
        print(f"找不到 {path}", file=sys.stderr)
        return 2

    errors = validate(doc)
    if errors:
        print("sources.json 校验失败：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    if args.validate:
        tiers = {t: sum(1 for s in doc["sources"] if s["tier"] == t and s.get("status") == "active")
                 for t in TIER_ORDER}
        manual = sum(1 for s in doc["sources"] if s.get("status") == "manual")
        print(f"校验通过：调度中 {tiers['P0'] + tiers['P1'] + tiers['P2']} 个"
              f"（P0 {tiers['P0']} / P1 {tiers['P1']} / P2 {tiers['P2']}，P2 上限 {P2_ACTIVE_CAP}），"
              f"手动不调度 {manual} 个，暂停留档 {len(doc.get('paused_sources', []))} 个")
        if tiers["P1"] > P1_ACTIVE_CAP:
            print(f"  提醒：P1 现有 {tiers['P1']} 个 > 上限 {P1_ACTIVE_CAP}，每轮 12 个源时轮不到 24h；"
                  "把 last_hit 最旧的降到 P2 或移入 paused_sources")
        return 0

    if args.status:
        return cmd_status(doc, now)

    changed = False
    if args.pause:
        ids = [x.strip() for x in args.pause.split(",") if x.strip()]
        if not args.write:
            print(f"预览（加 --write 落盘）：将暂停 {', '.join(ids)}")
        else:
            cmd_pause(doc, ids, args.reason, now)
            changed = True
    if args.activate:
        ids = [x.strip() for x in args.activate.split(",") if x.strip()]
        cmd_activate(doc, ids, now, write=args.write)
        changed = changed or args.write
    if args.mark_done or args.mark_hit:
        ids = [x.strip() for x in (args.mark_done or args.mark_hit).split(",") if x.strip()]
        hit = bool(args.mark_hit)
        rc = cmd_mark(doc, ids, now, hit)
        changed = changed or rc == 0
        if rc != 0:
            return rc
    if args.mark_zero:
        ids = [x.strip() for x in args.mark_zero.split(",") if x.strip()]
        rc = cmd_mark_zero(doc, ids, now)
        changed = changed or rc == 0
        if rc != 0:
            return rc
    if args.apply_downgrades:
        target = doc if args.write else copy.deepcopy(doc)
        cmd_downgrades(target, now, write=args.write)
        changed = changed or args.write
    if changed:
        save_json(path, doc)

    if args.mark_done or args.mark_hit or args.mark_zero or args.apply_downgrades or args.pause or args.activate:
        return 0

    plan = build_plan(doc, now)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_plan_text(plan)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
