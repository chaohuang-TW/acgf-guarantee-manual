import unittest

from scripts.display_text import normalize_display_text


class DisplayTextTests(unittest.TestCase):
    def one(self, value):
        return "\n".join(normalize_display_text(value))

    def test_debt_ratio(self):
        self.assertEqual(self.one("（九） 使 用 統 一 發 票 之 企 業 戶 最 近 年 度 期 末 負 債 比 率\n（負 債 ／ 淨 值） 超\n過 四 ○ ○ ％ 者 。 但 有 下 列 情 事 者 ， 不 在 此 限\n："), "（九）使用統一發票之企業戶最近年度期末負債比率（負債／淨值）超過四○○％者。但有下列情事者，不在此限：")

    def test_first_fullwidth_item(self):
        self.assertEqual(self.one("１ 、 其 後 已 辦 理 增 資 ， 而 期 中 財 務 報 表 已\n無 上 開 情 事 者 。"), "１、其後已辦理增資，而期中財務報表已無上開情事者。")

    def test_second_fullwidth_item(self):
        self.assertEqual(self.one("２ 、 有 特 殊 情 形 ， 經 受 託 機 構 評 估 認 為 不\n影 響 償 債 能 力 ， 並 經\n本 基 金 同 意 者 。"), "２、有特殊情形，經受託機構評估認為不影響償債能力，並經本基金同意者。")

    def test_english_spaces_remain(self):
        self.assertEqual(self.one("OpenAI API 與 GitHub Pages"), "OpenAI API 與 GitHub Pages")

    def test_number_unit_space_remains(self):
        self.assertEqual(self.one("貸款金額 300 萬元，年利率 5%。"), "貸款金額 300 萬元，年利率 5%。")

    def test_items_do_not_merge(self):
        self.assertEqual(normalize_display_text("一、第一項內容。\n二、第二項內容。\n（一）子項內容。\n（二）子項內容。"), ["一、第一項內容。", "二、第二項內容。", "（一）子項內容。", "（二）子項內容。"])

    def test_idempotent(self):
        value = "（九） 使 用 統 一 發 票\n超 過 四 ○ ○ ％。"
        once = normalize_display_text(value)
        self.assertEqual(normalize_display_text("\n".join(once)), once)

    def test_empty(self):
        self.assertEqual(normalize_display_text(""), [])

    def test_whitespace_only(self):
        self.assertEqual(normalize_display_text(" \n　\t"), [])

    def test_non_whitespace_characters_are_preserved(self):
        raw = "格式 3-1A、B33、B36、B66、K33、Z13、1,500 萬元、四 ○ ○ ％"
        rendered = "".join(normalize_display_text(raw))
        self.assertEqual("".join(raw.split()), "".join(rendered.split()))


if __name__ == "__main__":
    unittest.main()
