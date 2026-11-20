#!/usr/bin/env python3
"""羊毛情报局 — 结构化数据体检（JSON-LD）。

构建产物里每一段 `<script type="application/ld+json">` 都必须是合法 JSON，
而且关键类型的字段要齐：

  · 详情页（`d/<id>/`、`en/d/<id>/`）：必须有 Offer（name / description / url / availability），
    有参与步骤的页面还必须有 HowTo（name / description / step[] 每步为 HowToStep + text）；
  · 分类目录页（`category/<slug>/`、`en/category/<slug>/`）：CollectionPage + ItemList；
  · 首页（`/`、`/en/`）：WebSite + ItemList。

为什么单独一个脚本：手写模板里少一个逗号、某个字段拼出了 `</script>`、
或者 HowTo 只在部分页面生成，肉眼看不出来，Google 那边却是静默不收录。
build_site.py 每次构建都会调用 `check_jsonld()`，不通过直接拒绝发布；
也可以单独跑：

    python3 scripts/check_schema.py          # 体检现有产物
    python3 scripts/check_schema.py --list   # 顺便列出每页的结构化数据类型
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

_LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)


def ld_blocks(page_html: str) -> list[str]:
    return _LD_RE.findall(page_html)


def _types(node: object) -> set[str]:
    """递归收集一段 JSON-LD 里出现的所有 @type。"""
    found: set[str] = set()
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            found.add(t)
        elif isinstance(t, list):
            found.update(str(x) for x in t)
        for value in node.values():
            found |= _types(value)
    elif isinstance(node, list):
        for value in node:
            found |= _types(value)
    return found


def _offer_errors(node: dict) -> list[str]:
    errs: list[str] = []
    for key in ("name", "description", "url", "availability"):
        if not str(node.get(key) or "").strip():
            errs.append(f"Offer 缺字段 {key}")
    return errs


def _howto_errors(node: dict) -> list[str]:
    errs: list[str] = []
    for key in ("name", "description"):
        if not str(node.get(key) or "").strip():
            errs.append(f"HowTo 缺字段 {key}")
    steps = node.get("step")
    if not isinstance(steps, list) or not steps:
        return errs + ["HowTo 没有 step 数组"]
    for i, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            errs.append(f"HowTo 第 {i} 步不是对象")
            continue
        if step.get("@type") != "HowToStep":
            errs.append(f"HowTo 第 {i} 步 @type 不是 HowToStep")
        if not str(step.get("text") or "").strip():
            errs.append(f"HowTo 第 {i} 步缺 text")
    return errs


def _walk_type(node: object, wanted: str) -> list[dict]:
    """从一段 JSON-LD 里找出所有 @type == wanted 的对象。"""
    out: list[dict] = []
    if isinstance(node, dict):
        t = node.get("@type")
        if t == wanted or (isinstance(t, list) and wanted in t):
            out.append(node)
        for value in node.values():
            out += _walk_type(value, wanted)
    elif isinstance(node, list):
        for value in node:
            out += _walk_type(value, wanted)
    return out


def check_jsonld(root: Path = ROOT, expected_howto: dict[str, bool] | None = None) -> list[str]:
    """扫全部生成的 HTML，返回错误列表（空列表 = 全部通过）。"""
    expected = expected_howto or {}
    errors: list[str] = []

    pages: list[Path] = []
    for rel in ("index.html", "en/index.html"):
        p = root / rel
        if p.exists():
            pages.append(p)
    for pattern in ("d/*/index.html", "en/d/*/index.html", "category/*/index.html", "en/category/*/index.html"):
        pages += sorted(root.glob(pattern))

    if not pages:
        return ["没有找到任何 HTML 产物（先跑 build_site.py）"]

    for page in pages:
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8")
        blocks = ld_blocks(text)
        if not blocks:
            errors.append(f"{rel}：没有任何 application/ld+json")
            continue
        objects: list[dict] = []
        for i, raw in enumerate(blocks, start=1):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel} 第 {i} 段 JSON-LD 不是合法 JSON：{exc}")
                continue
            for node in parsed if isinstance(parsed, list) else [parsed]:
                if isinstance(node, dict) and "schema.org" not in str(node.get("@context", "")):
                    errors.append(f"{rel} 第 {i} 段 JSON-LD 缺 schema.org 的 @context")
                objects.append(node)

        types: set[str] = set()
        for node in objects:
            types |= _types(node)

        if rel.startswith(("d/", "en/d/")):
            offers = [n for node in objects for n in _walk_type(node, "Offer")]
            if not offers:
                errors.append(f"{rel}：缺 Offer 结构化数据")
            for offer in offers:
                errors += [f"{rel}：{msg}" for msg in _offer_errors(offer)]
            howtos = [n for node in objects for n in _walk_type(node, "HowTo")]
            if expected.get(rel) and not howtos:
                errors.append(f"{rel}：有参与步骤但没有 HowTo 结构化数据")
            for howto in howtos:
                errors += [f"{rel}：{msg}" for msg in _howto_errors(howto)]
            if "BreadcrumbList" not in types:
                errors.append(f"{rel}：缺 BreadcrumbList")
        elif "/category/" in rel or rel.startswith("category/"):
            for wanted in ("CollectionPage", "ItemList", "BreadcrumbList"):
                if wanted not in types:
                    errors.append(f"{rel}：缺 {wanted}")
            lists = [n for node in objects for n in _walk_type(node, "ItemList")]
            for lst in lists:
                if not isinstance(lst.get("itemListElement"), list) or not lst["itemListElement"]:
                    errors.append(f"{rel}：ItemList 的 itemListElement 为空")
        else:
            for wanted in ("WebSite", "ItemList"):
                if wanted not in types:
                    errors.append(f"{rel}：缺 {wanted}")

    return errors


def expected_howto(deals: list[dict], en_map: dict) -> dict[str, bool]:
    """哪些详情页应当带 HowTo：中文看 steps，英文看翻译（缺翻译时回退中文）。"""
    out: dict[str, bool] = {}
    for deal in deals:
        deal_id = deal["id"]
        out[f"d/{deal_id}/index.html"] = bool(deal.get("steps"))
        en_steps = en_map.get(deal_id, {}).get("steps") or deal.get("steps")
        out[f"en/d/{deal_id}/index.html"] = bool(en_steps)
    return out


def main() -> None:
    list_mode = "--list" in sys.argv
    deals = json.loads((ROOT / "data" / "deals.json").read_text(encoding="utf-8"))
    en_map = json.loads((ROOT / "data" / "deals_en.json").read_text(encoding="utf-8")) \
        if (ROOT / "data" / "deals_en.json").exists() else {}
    errors = check_jsonld(ROOT, expected_howto(deals, en_map))
    if list_mode:
        for page in sorted(ROOT.glob("d/*/index.html"))[:1] + sorted(ROOT.glob("category/*/index.html"))[:1]:
            text = page.read_text(encoding="utf-8")
            kinds: set[str] = set()
            for raw in ld_blocks(text):
                try:
                    kinds |= _types(json.loads(raw))
                except json.JSONDecodeError:
                    kinds.add("（解析失败）")
            print(f"  {page.relative_to(ROOT).as_posix()}：{', '.join(sorted(kinds))}")
    if errors:
        print(f"结构化数据体检未通过：{len(errors)} 个问题", file=sys.stderr)
        for line in errors[:40]:
            print("  · " + line, file=sys.stderr)
        raise SystemExit(1)
    total = len(list(ROOT.glob("d/*/index.html"))) + len(list(ROOT.glob("en/d/*/index.html")))
    cats = len(list(ROOT.glob("category/*/index.html"))) + len(list(ROOT.glob("en/category/*/index.html")))
    print(f"JSON-LD 全部合法：{total} 个详情页（Offer + HowTo）、{cats} 个分类目录页、2 个首页")


if __name__ == "__main__":
    main()
