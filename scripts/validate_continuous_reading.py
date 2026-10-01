#!/usr/bin/env python3
"""Validate all configured continuous-reading units against source data."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import (  # noqa: E402
    CONTINUOUS_READING_UNIT_IDS,
    VERSION_ROOT,
    map_fragment_boundaries,
    rel_from,
)
from display_text import non_whitespace_characters, normalize_display_text  # noqa: E402
from reading_units import load_resolved_units  # noqa: E402


class Node:
    def __init__(self, tag: str, attrs: list[tuple[str, str | None]], parent: "Node | None" = None):
        self.tag = tag
        self.attrs = {key: value or "" for key, value in attrs}
        self.parent = parent
        self.children: list[Node | str] = []

    @property
    def text(self) -> str:
        return "".join(child.text if isinstance(child, Node) else child for child in self.children)

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()

    def descendants(self, *, tag: str | None = None, class_name: str | None = None) -> list["Node"]:
        result: list[Node] = []
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and (class_name is None or child.has_class(class_name)):
                result.append(child)
            result.extend(child.descendants(tag=tag, class_name=class_name))
        return result


class TreeParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", [])
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(Node(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _html_tree(path: Path) -> tuple[str, Node]:
    source = path.read_text(encoding="utf-8")
    parser = TreeParser()
    parser.feed(source)
    return source, parser.root


def _first(nodes: list[Node]) -> Node | None:
    return nodes[0] if nodes else None


def _unique_by_id(nodes: list[Node], element_id: str) -> list[Node]:
    return [node for node in nodes if node.attrs.get("id") == element_id]


def _relative_target(site_path: Path, page_path: Path, href: str) -> tuple[Path | None, str | None]:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or parsed.query:
        return None, None
    target_path = (page_path.parent / unquote(parsed.path)).resolve()
    try:
        target_path.relative_to(site_path.resolve())
    except ValueError:
        return None, None
    return target_path, unquote(parsed.fragment)


def _expected_related_forms(unit_id: str, relations: list[dict]) -> list[dict]:
    by_number: dict[str, tuple[int, dict]] = {}
    for relation in relations:
        if relation["contentRef"]["id"] != unit_id:
            continue
        form = relation["form"]
        number = form["number"]
        if number not in by_number:
            first_page = min((item["pdfPage"] for item in relation.get("evidence", [])), default=9999)
            by_number[number] = (first_page, relation)
    ordered = sorted(by_number.values(), key=lambda item: item[0])
    return [item[1]["form"] for item in ordered]


def validate_continuous_reading() -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    metrics: list[dict] = []
    units = load_resolved_units()
    units_by_id = {unit["id"]: unit for unit in units}
    configured = set(CONTINUOUS_READING_UNIT_IDS)
    if configured != {"excluded-guarantee", "credit-deterioration", "pre-negotiation", "overdue-guarantee"}:
        errors.append(f"Continuous rendering configuration unexpectedly changed: {sorted(configured)}")
    if not configured.issubset(units_by_id):
        errors.append(f"Configured units missing from reading-units.json: {sorted(configured - set(units_by_id))}")

    page_data = _load_json(ROOT / "data/pages.json")
    pages_by_pdf = {int(page["pdfPage"]): page for page in page_data}
    relations = _load_json(ROOT / "data/related-forms.json")["relations"]
    generated_html: dict[str, tuple[str, Node, Path]] = {}

    # Per-unit gates derive all titles and page boundaries from reading-units.json.
    for unit_id in sorted(configured):
        unit = units_by_id.get(unit_id)
        if not unit:
            continue
        relative = unit["readingUrl"]
        path = SITE / relative
        if not path.is_file():
            errors.append(f"{unit_id}: canonical generated file missing: {relative}")
            continue
        content, document = _html_tree(path)
        generated_html[unit_id] = (content, document, path)
        all_nodes = document.descendants()
        h1s = [node for node in all_nodes if node.tag == "h1"]
        if len(h1s) != 1:
            errors.append(f"{unit_id}: expected exactly one H1, found {len(h1s)}")
        elif h1s[0].text.strip() != unit["title"]:
            errors.append(f"{unit_id}: H1/title mismatch: {h1s[0].text.strip()!r} != {unit['title']!r}")

        article = _first([node for node in all_nodes if node.tag == "article" and node.has_class("continuous-reading")])
        continuous_articles = [node for node in all_nodes if node.tag == "article" and node.has_class("continuous-reading")]
        if len(continuous_articles) != 1:
            errors.append(f"{unit_id}: expected one .continuous-reading article, found {len(continuous_articles)}")
        page_cards = [node for node in all_nodes if node.has_class("page-card")]
        if page_cards:
            errors.append(f"{unit_id}: continuous logical page contains {len(page_cards)} .page-card element(s)")
        if not article:
            continue

        source_headings = [node for node in article.descendants(tag="h1", class_name="continuous-source-heading")]
        source_bodies = [node for node in article.descendants(tag="div", class_name="continuous-source-text")]
        heading = _first(source_headings)
        body = _first(source_bodies)
        if len(source_headings) != 1 or len(source_bodies) != 1 or not heading or not body:
            errors.append(f"{unit_id}: expected exactly one source heading and source body")
            continue

        fragments = unit["fragments"]
        raw_stream = "\n".join(fragment["text"] for fragment in fragments)
        paragraphs = normalize_display_text(raw_stream)
        if not paragraphs or paragraphs[0] != unit["title"]:
            errors.append(f"{unit_id}: source title gate failed; first normalized paragraph must exactly equal unit title")
            continue

        raw_text = "".join(fragment["text"] for fragment in fragments)
        source_text = heading.text + body.text
        raw_sequence = non_whitespace_characters(raw_text)
        rendered_sequence = non_whitespace_characters(source_text)
        fidelity = raw_sequence == rendered_sequence
        if not fidelity:
            errors.append(f"{unit_id}: source text sequence mismatch (raw {len(raw_sequence)} NW, rendered {len(rendered_sequence)} NW)")
        if heading.text.strip() != unit["title"]:
            errors.append(f"{unit_id}: rendered continuous heading differs from authoritative title")

        # Physical-page anchors are each unique, correctly ordered, zero-text spans.
        expected_pages = [int(fragment["pdfPage"]) for fragment in fragments]
        anchor_nodes = [node for node in all_nodes if node.tag == "span" and node.has_class("source-page-anchor")]
        anchor_pages = [int(node.attrs.get("data-pdf-page", "-1")) for node in anchor_nodes]
        if anchor_pages != expected_pages:
            errors.append(f"{unit_id}: source-page anchors/order mismatch; expected {expected_pages}, got {anchor_pages}")
        ids = [node.attrs.get("id", "") for node in all_nodes if node.attrs.get("id")]
        for pdf_page in expected_pages:
            anchor_id = f"pdf-page-{pdf_page}"
            count = ids.count(anchor_id)
            if count != 1:
                errors.append(f"{unit_id}: {anchor_id} must exist exactly once, found {count}")
            matches = _unique_by_id(all_nodes, anchor_id)
            if matches and (matches[0].tag != "span" or not matches[0].has_class("source-page-anchor") or matches[0].text):
                errors.append(f"{unit_id}: {anchor_id} is not a zero-text source-page span")
        if any(node.tag == "hr" or "page-divider" in node.attrs.get("class", "").split() for node in all_nodes):
            errors.append(f"{unit_id}: visible physical page divider found")

        # Check boundary placement against the same normalized source paragraph mapping.
        from build_site import map_fragment_boundaries
        mappings = map_fragment_boundaries(paragraphs, fragments)
        body_paragraphs = [node for node in body.descendants(tag="p")]
        if [node.text for node in body_paragraphs] != paragraphs[1:]:
            errors.append(f"{unit_id}: rendered body paragraphs differ from normalized source paragraphs")
        for mapping in mappings:
            pdf_page = mapping["pdfPage"]
            anchor = _first(_unique_by_id(all_nodes, f"pdf-page-{pdf_page}"))
            if not anchor:
                continue
            paragraph_index = mapping["paragraphIndex"]
            char_offset = mapping["characterOffset"]
            if paragraph_index == 0:
                header = anchor.parent
                heading_parent = heading.parent
                if header is None or header is not heading_parent or header.children.index(anchor) >= header.children.index(heading):
                    errors.append(f"{unit_id}: first-page anchor {pdf_page} must precede source H1 in its header")
                continue
            if paragraph_index - 1 >= len(body_paragraphs):
                errors.append(f"{unit_id}: boundary paragraph index out of range for PDF {pdf_page}")
                continue
            paragraph = body_paragraphs[paragraph_index - 1]
            if mapping["is_mid_paragraph"]:
                if anchor.parent is not paragraph:
                    errors.append(f"{unit_id}: mid-paragraph anchor {pdf_page} is not inline in its paragraph")
                    continue
                before: list[str] = []
                for child in paragraph.children:
                    if child is anchor:
                        break
                    before.append(child.text if isinstance(child, Node) else child)
                if "".join(before) != paragraphs[paragraph_index][:char_offset]:
                    errors.append(f"{unit_id}: mid-paragraph anchor {pdf_page} character offset mismatch")
            else:
                parent = anchor.parent
                if parent is not body or paragraph.parent is not body:
                    errors.append(f"{unit_id}: paragraph-start anchor {pdf_page} must be a body sibling before its paragraph")
                    continue
                siblings = [child for child in body.children if isinstance(child, Node) or (isinstance(child, str) and child.strip())]
                if anchor not in siblings or paragraph not in siblings or siblings.index(anchor) + 1 != siblings.index(paragraph):
                    errors.append(f"{unit_id}: paragraph-start anchor {pdf_page} must immediately precede its paragraph")

        # Provenance is data-derived, uses rel_from(), and must resolve to physical HTML anchors.
        links = [node for node in all_nodes if node.tag == "a" and node.has_class("source-page-link")]
        if len(links) != len(fragments):
            errors.append(f"{unit_id}: expected {len(fragments)} provenance links, found {len(links)}")
        for fragment, link in zip(fragments, links):
            pdf_page = int(fragment["pdfPage"])
            target_rel = f"{VERSION_ROOT}/pages/page-{pdf_page:03d}.html"
            expected_href = rel_from(relative, target_rel) + f"#pdf-page-{pdf_page}"
            if link.attrs.get("href") != expected_href:
                errors.append(f"{unit_id}: PDF {pdf_page} provenance href mismatch: {link.attrs.get('href')!r} != {expected_href!r}")
            printed = fragment.get("printedPage")
            printed_label = f"手冊頁 {printed} " if printed else ""
            expected_label = printed_label + f"(PDF {pdf_page})"
            if link.text.strip() != expected_label:
                errors.append(f"{unit_id}: PDF {pdf_page} provenance visible label mismatch")
            accessible_label = link.attrs.get("aria-label") or link.text.strip()
            if accessible_label != expected_label:
                errors.append(f"{unit_id}: PDF {pdf_page} provenance accessible/visible label mismatch")
            target_file, target_anchor = _relative_target(SITE, path, link.attrs.get("href", ""))
            if not target_file or not target_file.is_file():
                errors.append(f"{unit_id}: provenance destination missing/outside site for PDF {pdf_page}")
            elif not target_anchor:
                errors.append(f"{unit_id}: provenance destination has no anchor for PDF {pdf_page}")
            else:
                _, target_document = _html_tree(target_file)
                target_nodes = target_document.descendants()
                if len(_unique_by_id(target_nodes, target_anchor)) != 1:
                    errors.append(f"{unit_id}: provenance destination #{target_anchor} is missing/duplicated")
                target_card = _first([node for node in target_nodes if node.attrs.get("id") == target_anchor])
                if not target_card or not target_card.has_class("page-card"):
                    errors.append(f"{unit_id}: physical target #{target_anchor} must retain .page-card")

        # TOC text must be exact source paragraph text; an empty TOC is omitted entirely.
        toc_nodes = [node for node in all_nodes if node.tag == "nav" and node.has_class("topic-toc")]
        source_clause_nodes = [node for node in body_paragraphs if re.match(r"^[一二三四五六七八九十]+、", node.text)]
        if source_clause_nodes:
            if len(toc_nodes) != 1:
                errors.append(f"{unit_id}: expected one source-derived topic TOC, found {len(toc_nodes)}")
            else:
                toc_links = [node for node in toc_nodes[0].descendants(tag="a")]
                if len(toc_links) != len(source_clause_nodes):
                    errors.append(f"{unit_id}: TOC link count {len(toc_links)} != source clause count {len(source_clause_nodes)}")
                for link in toc_links:
                    target_id = link.attrs.get("href", "").removeprefix("#")
                    targets = _unique_by_id(all_nodes, target_id)
                    if not target_id or len(targets) != 1 or targets[0].tag != "p":
                        errors.append(f"{unit_id}: TOC link target is missing/ambiguous/not a paragraph: {target_id!r}")
                    elif link.text != targets[0].text:
                        errors.append(f"{unit_id}: TOC text is not an exact source paragraph excerpt for {target_id}")
        elif toc_nodes:
            errors.append(f"{unit_id}: empty topic TOC should be omitted")

        # Related Forms are compared to explicit relations, deduplicated by form number as in renderer.
        expected_forms = _expected_related_forms(unit_id, relations)
        form_sections = [node for node in all_nodes if node.tag == "section" and node.has_class("related-forms")]
        expected_form_links = [(form["title"], rel_from(relative, form["url"])) for form in expected_forms]
        actual_form_links: list[tuple[str, str]] = []
        if form_sections:
            for link in form_sections[0].descendants(tag="a", class_name="related-form-card"):
                title = _first(link.descendants(class_name="related-form-title"))
                actual_form_links.append((title.text.strip() if title else "", link.attrs.get("href", "")))
        if len(form_sections) != (1 if expected_forms else 0):
            errors.append(f"{unit_id}: related-forms section count mismatch; expected {1 if expected_forms else 0}, got {len(form_sections)}")
        if actual_form_links != expected_form_links:
            errors.append(f"{unit_id}: related-form title/href mismatch; expected {expected_form_links!r}, got {actual_form_links!r}")

        pagination = [node for node in all_nodes if node.tag == "nav" and node.has_class("reading-pagination")]
        if len(pagination) != 1 or not pagination[0].descendants(tag="a"):
            errors.append(f"{unit_id}: Reading Pagination is missing or has no navigation links")

        if unit_id == "overdue-guarantee":
            contamination = sum(body.text.count(marker) for marker in ("陸、解除保證責任", "保證案件有下列情事之一者，本基金得解除保證責任"))
            if contamination:
                errors.append(f"{unit_id}: release-liability contamination found {contamination} occurrence(s)")

        metrics.append({
            "unitId": unit_id,
            "sourceNonWhitespaceCharacters": len(raw_sequence),
            "renderedNonWhitespaceCharacters": len(rendered_sequence),
            "sourceFidelity": fidelity,
            "anchors": anchor_pages,
            "tocItems": len(source_clause_nodes),
            "relatedForms": len(expected_forms),
            "provenanceLinks": len(links),
            "paragraphs": len(body_paragraphs),
            "htmlBytes": len(content.encode("utf-8")),
            "contaminationCount": 0 if unit_id == "overdue-guarantee" else None,
        })

    # All remaining logical units stay on the legacy physical-card architecture.
    legacy_units = [unit for unit in units if unit["id"] not in configured]
    unexpected_logical_changes = 0
    for unit in legacy_units:
        path = SITE / unit["readingUrl"]
        if not path.is_file():
            errors.append(f"Legacy logical unit file missing: {unit['readingUrl']}")
            unexpected_logical_changes += 1
            continue
        _, document = _html_tree(path)
        nodes = document.descendants()
        cards = [node for node in nodes if node.has_class("page-card")]
        continuous = [node for node in nodes if node.tag == "article" and node.has_class("continuous-reading")]
        if continuous or len(cards) != len(unit["fragments"]):
            errors.append(f"Legacy logical unit changed unexpectedly: {unit['id']} (cards {len(cards)}/{len(unit['fragments'])}, continuous {len(continuous)})")
            unexpected_logical_changes += 1

    # The existing 203 physical pages retain their physical .page-card architecture.
    physical_changes = 0
    for page in page_data:
        pdf_page = int(page["pdfPage"])
        path = SITE / f"{VERSION_ROOT}/pages/page-{pdf_page:03d}.html"
        if not path.is_file():
            errors.append(f"Physical page missing: {path.relative_to(SITE)}")
            physical_changes += 1
            continue
        _, document = _html_tree(path)
        nodes = document.descendants()
        cards = [node for node in nodes if node.tag == "section" and node.has_class("page-card")]
        anchors = _unique_by_id(nodes, f"pdf-page-{pdf_page}")
        if len(cards) != 1 or len(anchors) != 1 or not anchors[0].has_class("page-card"):
            errors.append(f"Physical page {pdf_page} DOM changed: page-cards={len(cards)}, anchor-count={len(anchors)}")
            physical_changes += 1

    if len(page_data) != 203:
        errors.append(f"Expected exactly 203 physical page records, found {len(page_data)}")
    if unexpected_logical_changes != 0:
        errors.append(f"UNEXPECTED_LOGICAL_PAGE_CHANGES={unexpected_logical_changes}")
    if physical_changes != 0:
        errors.append(f"PHYSICAL_PAGE_DOM_CHANGES={physical_changes}")

    # Generic empty-TOC behavior: no invented text and no empty navigation frame.
    from build_site import render_continuous_reading_unit
    empty_toc_unit = {
        "id": "synthetic-no-toc",
        "title": "測試無目錄標題",
        "fragments": [{"pdfPage": 999, "printedPage": 1, "text": "測試無目錄標題\n\n這是一段沒有正式條款標號的原文。"}],
    }
    empty_toc_html = render_continuous_reading_unit(empty_toc_unit, "versions/115-04/chapters/part-1/synthetic.html")
    if 'class="topic-toc"' in empty_toc_html:
        errors.append("Generic empty-TOC behavior emitted an empty .topic-toc")

    return errors, metrics


def main() -> None:
    errors, metrics = validate_continuous_reading()
    if errors:
        print(f"CONTINUOUS READING VALIDATION FAILED with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    for item in metrics:
        print(
            f"PASS {item['unitId']}: source NW={item['sourceNonWhitespaceCharacters']}, "
            f"rendered NW={item['renderedNonWhitespaceCharacters']}, fidelity={item['sourceFidelity']}, "
            f"anchors={item['anchors']}, TOC={item['tocItems']}, Related Forms={item['relatedForms']}, "
            f"provenance={item['provenanceLinks']}, paragraphs={item['paragraphs']}, HTML bytes={item['htmlBytes']}"
        )
    print("UNEXPECTED_LOGICAL_PAGE_CHANGES=0")
    print("PHYSICAL_PAGE_DOM_CHANGES=0 (203 pages)")
    print("CONTINUOUS READING VALIDATION PASSED")


if __name__ == "__main__":
    main()
