#!/usr/bin/env python3
"""dedup_key 巡检：缺失 / 格式错误 / 撞键，以及「疑似重复」检查清单。

用法：
  python3 scripts/dedup_audit.py            # 打印摘要 + 疑似重复清单
  python3 scripts/dedup_audit.py --write    # 同时写 docs/dedup-audit.md

判定顺序：
  1. 缺 dedup_key 或四段不全 / 分类不在六类里 / 与大表算出来的键不一致 → 格式错误；
  2. 同一 dedup_key 出现两遍 → 撞键（真重复，maintain_deals 会按标题+区域再判一次）；
  3. 同品牌 + 同分类 + 同市场，且标题相似度高、官方链接相同或价值相同 → 疑似重复，
     仅供人工确认，脚本不删任何条目。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import CAT_META, DATA, dedup_key, market_code  # noqa: E402


def norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(text or "").lower())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="写 docs/dedup-audit.md")
    args = parser.parse_args()

    deals = json.loads(DATA.read_text(encoding="utf-8"))
    problems: list[str] = []
    expected = {}

    for deal in deals:
        expected_key = dedup_key(deal)
        expected[deal["id"]] = expected_key
        current = deal.get("dedup_key")
        parts = (current or "").split("|")
        if not current:
            problems.append(f"{deal['id']}：缺 dedup_key（应为 {expected_key}）")
            continue
        if len(parts) != 4 or any(not p for p in parts):
            problems.append(f"{deal['id']}：dedup_key 段数不对（{current}）")
            continue
        if parts[1] not in CAT_META:
            problems.append(f"{deal['id']}：category 段 {parts[1]!r} 不是六类之一（{current}）")
        if parts[1] != deal.get("category"):
            problems.append(f"{deal['id']}：category 段与条目分类不一致（{current}）")
        if current != expected_key:
            problems.append(f"{deal['id']}：与规范键不一致（现 {current} → 应为 {expected_key}）")

    by_key = defaultdict(list)
    for deal in deals:
        by_key[expected[deal["id"]]].append(deal["id"])
    collisions = {k: v for k, v in by_key.items() if len(v) > 1}

    # 疑似重复：同品牌 + 分类 + 市场，且标题相似 / 官方链接相同 / 价值相同
    buckets = defaultdict(list)
    for deal in deals:
        buckets[
            (str(deal.get("brand") or "").lower(), deal.get("category"), market_code(deal))
        ].append(deal)

    suspects: list[tuple[str, list[tuple[dict, float]]]] = []
    for (brand, category, market), items in buckets.items():
        if len(items) < 2:
            continue
        reported: set[str] = set()
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                pair = (a["id"], b["id"])
                if pair in reported:
                    continue
                ratio = SequenceMatcher(None, norm(a.get("title")), norm(b.get("title"))).ratio()
                same_url = bool(a.get("url")) and str(a.get("url")).rstrip("/").lower() == str(
                    b.get("url")
                ).rstrip("/").lower()
                same_value = (
                    a.get("value_num") is not None
                    and b.get("value_num") is not None
                    and str(a.get("value_num")) == str(b.get("value_num"))
                )
                if ratio >= 0.72 or (same_url and ratio >= 0.4) or (same_url and same_value):
                    reported.add(pair)
                    suspects.append(
                        (
                            f"{brand} / {category} / {market}",
                            [(a, ratio), (b, ratio)],
                        )
                    )

    print(f"条目 {len(deals)} 条 · 唯一 dedup_key {len(by_key)} 个 · 格式问题 {len(problems)} 处")
    for line in problems:
        print("  !", line)
    if collisions:
        print(f"撞键 {len(collisions)} 组：")
        for key, ids in collisions.items():
            print(f"  - {key}: {', '.join(ids)}")
    else:
        print("撞键：无")
    print(f"疑似重复：{len(suspects)} 组")
    for group, items in suspects:
        print(f"  - {group}")
        for deal, ratio in items:
            print(f"      {deal['id']} · {deal.get('value')} · {deal.get('url')} · 相似 {ratio:.2f}")

    if args.write:
        lines = [
            "---",
            "title: dedup_key 巡检与疑似重复清单",
            "kind: note",
            "---",
            "",
            f"- 条目总数：{len(deals)}",
            f"- 唯一 dedup_key：{len(by_key)}",
            f"- 格式问题：{len(problems)}",
            f"- 撞键：{len(collisions)} 组",
            f"- 疑似重复：{len(suspects)} 组",
            "",
            "## 格式问题",
            "",
        ]
        lines += [f"- {p}" for p in problems] or ["（无）"]
        lines += ["", "## 撞键", ""]
        lines += [f"- `{k}`：{', '.join(v)}" for k, v in collisions.items()] or ["（无）"]
        lines += ["", "## 疑似重复（人工确认，脚本不自动删）", ""]
        for group, items in suspects:
            lines.append(f"### {group}")
            for deal, ratio in items:
                lines.append(
                    f"- `{deal['id']}` · {deal.get('value')} · {deal.get('url')} · 标题相似度 {ratio:.2f}"
                )
            lines.append("")
        if not suspects:
            lines.append("（无）")
        out = ROOT / "docs" / "dedup-audit.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写入 {out.relative_to(ROOT)}")

    return 0 if not problems and not collisions else 1


if __name__ == "__main__":
    raise SystemExit(main())
