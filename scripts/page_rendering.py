#!/usr/bin/env python3
"""Resolve declarative page rendering rules against the manual page map."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_MODES = {"text", "source-preview", "blank-page"}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def printed_page_map(pages: list[dict]) -> dict[int, int]:
    mapping = {int(page["printedPage"]): int(page["pdfPage"]) for page in pages if page["printedPage"]}
    # The source page is an image-only continuation of appendix 18. Its printed
    # page number is established by the adjacent pages and the formal TOC.
    mapping[116] = 126
    return mapping


def expand_rule(rule: dict, pages: list[dict]) -> list[int]:
    result = [int(value) for value in rule.get("pdfPages", [])]
    has_start = "printedPageStart" in rule
    has_end = "printedPageEnd" in rule
    if has_start != has_end:
        raise ValueError(f"rule {rule.get('id')} must define both printed page bounds")
    if has_start:
        mapping = printed_page_map(pages)
        start = int(rule["printedPageStart"])
        end = int(rule["printedPageEnd"])
        if start > end:
            raise ValueError(f"rule {rule.get('id')} has reversed printed page bounds")
        missing = [number for number in range(start, end + 1) if number not in mapping]
        if missing:
            raise ValueError(f"rule {rule.get('id')} cannot map printed pages {missing}")
        result.extend(mapping[number] for number in range(start, end + 1))
    return sorted(set(result))


def resolve_all(config: dict, pages: list[dict]) -> dict[int, dict]:
    default_mode = config.get("defaultMode")
    if default_mode not in ALLOWED_MODES:
        raise ValueError(f"invalid default mode: {default_mode}")
    page_by_number = {int(page["pdfPage"]): page for page in pages}
    resolved = {
        number: {
            "mode": default_mode,
            "label": "一般文字頁",
            "reason": "保留PDF既有文字層",
            "ruleIds": [],
        }
        for number in page_by_number
    }
    for rule in config.get("rules", []):
        mode = rule.get("mode")
        if mode not in ALLOWED_MODES:
            raise ValueError(f"invalid mode in rule {rule.get('id')}: {mode}")
        for number in expand_rule(rule, pages):
            if number not in page_by_number:
                raise ValueError(f"rule {rule.get('id')} PDF page out of range: {number}")
            existing = resolved[number]
            if existing["ruleIds"] and existing["mode"] != mode:
                raise ValueError(
                    f"conflicting modes for PDF page {number}: {existing['mode']} and {mode}"
                )
            if not existing["ruleIds"]:
                existing.update(
                    mode=mode,
                    label=str(rule.get("label", "")),
                    reason=str(rule.get("reason", "")),
                )
            existing["ruleIds"].append(str(rule.get("id", "")))
    return resolved


def load_page_rendering(root: Path = ROOT) -> tuple[dict, list[dict], dict[int, dict]]:
    config = load_json(root / "data" / "page-rendering.json")
    pages = load_json(root / "data" / "pages.json")
    if not isinstance(config, dict) or not isinstance(pages, list):
        raise ValueError("invalid page rendering data")
    return config, pages, resolve_all(config, pages)
