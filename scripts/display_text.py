"""Deterministic, display-only cleanup for the PDF's existing text layer."""

from __future__ import annotations

import re

HAN = r"\u3400-\u9fff"
CJK_PUNCTUATION = "，。；：！？、】【（）「」『』【】《》〈〉／/%％﹪、○"
ITEM_START = re.compile(
    r"^(?:[壹貳參肆伍陸柒捌玖拾][、．.]|[一二三四五六七八九十][、．.]|"
    r"[（(][一二三四五六七八九十0-9０-９]+[）)]|[０-９0-9]+[、.．]|※|備註：|附註：|"
    r"第[一二三四五六七八九十0-9０-９]+[篇章節])"
)


def _is_han(char: str) -> bool:
    return bool(char) and bool(re.fullmatch(f"[{HAN}]", char))


def _is_layout_character(char: str) -> bool:
    return _is_han(char) or char in CJK_PUNCTUATION or "０" <= char <= "９"


def _normalize_spaces(text: str) -> str:
    """Remove only PDF layout whitespace where adjacent characters prove it is decorative."""
    chunks = re.split(r"([ \t\u3000]+)", text)
    result: list[str] = []
    for index, chunk in enumerate(chunks):
        if not chunk or not re.fullmatch(r"[ \t\u3000]+", chunk):
            result.append(chunk)
            continue
        left = result[-1][-1] if result and result[-1] else ""
        right = ""
        for following in chunks[index + 1 :]:
            if following and not re.fullmatch(r"[ \t\u3000]+", following):
                right = following[0]
                break
        remove = _is_layout_character(left) and _is_layout_character(right)
        remove = remove or (left.isdigit() and right in "％﹪%")
        result.append("" if remove else " ")
    return "".join(result).strip()


def _join(left: str, right: str) -> str:
    if not left:
        return right
    if left[-1].isascii() and left[-1].isalnum() and right[:1].isascii() and right[:1].isalnum():
        return left + " " + right
    return left + right


def normalize_display_text(raw_text: str) -> list[str]:
    """Return logical paragraphs without changing any non-whitespace character."""
    if not raw_text or not raw_text.strip():
        return []
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragraphs: list[str] = []
    current = ""
    for original in lines:
        line = _normalize_spaces(original.rstrip())
        if not line:
            if current:
                paragraphs.append(current)
                current = ""
            continue
        starts_new = bool(ITEM_START.match(line))
        previous_complete = current.endswith(("。", "！", "？"))
        if current and (starts_new or previous_complete):
            paragraphs.append(current)
            current = line
        else:
            current = _join(current, line)
    if current:
        paragraphs.append(current)
    return paragraphs


def non_whitespace_characters(text: str) -> str:
    return re.sub(r"\s+", "", text)
