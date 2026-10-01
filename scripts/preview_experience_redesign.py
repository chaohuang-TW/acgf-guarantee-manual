#!/usr/bin/env python3
"""Preserve the fresh build plus review evidence before restoring tracked site/."""
import argparse
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new output directory; existing work is never removed")
    shutil.copytree(ROOT / "site", args.output)
    shutil.copytree(ROOT / "docs/experience-redesign", args.output / "design/experience-redesign")
    review = args.output / "review"
    review.mkdir()
    comparisons = []
    for width in [390, 1440]:
        for family, label in [("home", "首頁"), ("search-exact", "搜尋25a"), ("reading-overdue", "連續閱讀"), ("form25a-preview", "格式25A原頁")]:
            images = []
            for stage, folder in [("before", args.before), ("after", args.after)]:
                source = folder / f"{family}-{width}.png" if folder else None
                if source and source.is_file():
                    destination = review / f"{stage}-{family}-{width}.png"
                    shutil.copy2(source, destination)
                    images.append(f'<figure><figcaption>{"改版前" if stage == "before" else "候選版"} · {width}px</figcaption><img src="{html.escape(destination.name)}" alt="{label} {stage} {width}px"></figure>')
            comparisons.append(f'<section><h2>{label} · {width}px</h2><div class="comparison">{"".join(images)}</div></section>')
    page = '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Experience Redesign 1.0 前後比較</title><link rel="stylesheet" href="../assets/css/site.css"><style>.comparison{display:grid;grid-template-columns:1fr 1fr;gap:24px}.comparison figure{margin:0}.comparison img{display:block;width:100%;height:auto;border:1px solid var(--line)}.comparison figcaption{margin:16px 0;font-weight:600}section{margin-bottom:64px}@media(max-width:700px){.comparison{grid-template-columns:1fr}}</style></head><body><main class="shell content-shell"><p class="eyebrow">本機設計驗收候選版 · 未發布</p><h1>相同內容，不同閱讀秩序。</h1><p><a href="../">操作候選版</a> · <a href="../design/experience-redesign/components.html">元件展示</a></p><p>所有畫面來自實際瀏覽器。相同寬度並排；書表圖保持完整比例。模擬視窗不代表實體手機驗收。</p>'''
    (review / "index.html").write_text(page + "".join(comparisons) + "</main></body></html>")
    print(f"Candidate preserved: {args.output}")
    print(f"Serve: {shutil.which('python3') or 'python3'} -m http.server 8765 --bind 127.0.0.1 --directory {args.output}")


if __name__ == "__main__":
    main()
