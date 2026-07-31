import sys
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Load the search JS
        with open("assets/js/search.js", "r", encoding="utf-8") as f:
            js = f.read()
            
        page.add_script_tag(content=js)

        def eval_highlight(text, terms):
            # Evaluate highlightText and return its outerHTML wrapper
            return page.evaluate(f"""
                (() => {{
                    const frag = window.ManualSearch.highlightText({repr(text)}, {repr(terms)});
                    const div = document.createElement('div');
                    div.appendChild(frag);
                    return {{ html: div.innerHTML, textContent: div.textContent }};
                }})()
            """)

        def check(case_name, text, terms, expected_marks, textContent_should_match=True):
            res = eval_highlight(text, terms)
            html = res['html']
            tc = res['textContent']
            
            # count <mark> tags
            mark_count = html.count('<mark class="search-hit">')
            assert mark_count == expected_marks, f"{case_name}: Expected {expected_marks} marks, got {mark_count}. HTML: {html}"
            
            if textContent_should_match:
                assert tc == text, f"{case_name}: Text content mismatch. Original: '{text}', Got: '{tc}'"
            print(f"PASS: {case_name}")

        # 1. 單一中文詞
        check("單一中文詞", "逾期本金、代償利息及相關費用", ["代償利息"], 1)

        # 2. 重複命中
        check("重複命中", "代償利息及其他代償利息", ["代償利息"], 2)

        # 3. 多關鍵詞
        check("多關鍵詞", "信用保證申請", ["信用", "保證"], 2)

        # 4. 英文大小寫
        check("英文大小寫", "pdf page PDF", ["PDF"], 2)

        # 5. 長詞優先
        check("長詞優先", "代償利息", ["代償利息", "代償"], 1)

        # 6. 特殊符號 (XSS protection is ensured by textContent and DocumentFragment, but let's check it doesn't break)
        check("特殊符號1", "alert(1)", ["<", ">", "&", '"', "'", "[", "(", "\\", ".", "*"], 1) 
        
        html = eval_highlight("<script>alert(1)</script>", ["script"])["html"]
        assert "&lt;script&gt;" in html or "<mark" in html
        assert "<script>" not in html

        # 7. 空query
        check("空query", "代償利息", [], 0)
        check("空白query", "代償利息", ["  "], 0)

        # 8. 無命中
        check("無命中", "完全無關的文字", ["代償"], 0)

        # 9. Unicode中文
        check("Unicode中文", "𠀋𠀋", ["𠀋"], 2)

        print("All highlight logic unit tests passed!")
        browser.close()

if __name__ == "__main__":
    main()
