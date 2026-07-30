import unittest
import json
import urllib.parse
import re
from pathlib import Path

class TestReadingNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.site_dir = cls.root / "site/versions/115-04"
        with open(cls.root / "data/toc.json") as f:
            cls.toc = json.load(f)
            
        cls.chapters = []
        for p in cls.toc["parts"]:
            cls.chapters.extend(p["sections"])
            
        cls.appendices = cls.toc["appendices"]
        
        combined_forms = [("forms", f) for f in cls.toc["forms"]] + [("specialForms", f) for f in cls.toc["specialForms"]]
        def form_sort_key(entry):
            idx, (category, item) = entry
            page = item.get("printedPage")
            if page is None:
                return (float('inf'), idx)
            try:
                if isinstance(page, int):
                    return (float(page), idx)
                return (float(str(page).replace("頁", "").strip()), idx)
            except ValueError:
                return (float('inf'), idx)
        
        cls.forms = [x[1] for x in sorted(enumerate(combined_forms), key=form_sort_key)]

    def get_links(self, path: str):
        with open(self.site_dir / path, "r", encoding="utf-8") as f:
            content = f.read()
        
        nav_prev = re.search(r'<a[^>]*class="[^"]*nav-prev[^"]*"[^>]*href="([^"]+)"', content)
        nav_next = re.search(r'<a[^>]*class="[^"]*nav-next[^"]*"[^>]*href="([^"]+)"', content)
        
        return {
            "prev": nav_prev.group(1) if nav_prev else None,
            "next": nav_next.group(1) if nav_next else None
        }

    def test_chapter_edges(self):
        first = self.chapters[0]
        links = self.get_links(f"chapters/part-1/{first['id']}.html")
        self.assertIsNone(links["prev"])
        self.assertIsNotNone(links["next"])
        
        mid = self.chapters[1]
        links = self.get_links(f"chapters/part-1/{mid['id']}.html")
        self.assertIsNotNone(links["prev"])
        self.assertIsNotNone(links["next"])
        
        last = self.chapters[-1]
        links = self.get_links(f"chapters/part-4/{last['id']}.html")
        self.assertIsNotNone(links["prev"])
        self.assertIsNone(links["next"])

        p1_last = self.chapters[3]
        links = self.get_links(f"chapters/part-1/{p1_last['id']}.html")
        self.assertIn("guarantee-changes", links["next"])

    def test_appendix_edges(self):
        links = self.get_links("appendices/appendix-02.html")
        self.assertIn("appendix-01", links["prev"])
        self.assertIn("appendix-03", links["next"])
        
        links = self.get_links("appendices/appendix-10.html")
        self.assertIn("appendix-09", links["prev"])
        self.assertIn("appendix-11", links["next"])
        
        links = self.get_links("appendices/appendix-18.html")
        self.assertIsNotNone(links["prev"])
        self.assertIsNone(links["next"])
        
        idx2 = next(i for i, a in enumerate(self.appendices) if a["id"] == "appendix-02")
        idx10 = next(i for i, a in enumerate(self.appendices) if a["id"] == "appendix-10")
        self.assertLess(idx2, idx10)

    def test_forms_order(self):
        codes = [f[1]["code"] for f in self.forms]
        self.assertLess(codes.index("格式 1A"), codes.index("格式 1B"))
        self.assertLess(codes.index("格式 1B"), codes.index("格式 1C"))
        
        self.assertLess(codes.index("格式 11"), codes.index("格式 11A"))
        
        self.assertLess(codes.index("格式 25"), codes.index("格式 25A"))
        self.assertLess(codes.index("格式 25A"), codes.index("格式 25B"))
        self.assertLess(codes.index("格式 25B"), codes.index("格式 25C"))
        
        self.assertLess(codes.index("格式 33"), codes.index("格式 33-1"))
        self.assertLess(codes.index("格式 33-1"), codes.index("格式 34"))
        self.assertLess(codes.index("格式 34"), codes.index("格式 34-1"))
        
        idx31 = codes.index("格式 31")
        self.assertEqual(codes[idx31+1], "格式 3A")
        
        idx33_1 = codes.index("格式 33-1")
        self.assertEqual(codes[idx33_1+1], "格式 12")
        
    def test_form_edges(self):
        def get_slug(code):
            return re.sub(r"[^a-z0-9]+", "-", code.lower().replace("格式", "form")).strip("-")
            
        first = self.forms[0]
        dir_first = "forms/special" if first[0] == "specialForms" else "forms"
        file_first = get_slug(first[1]["code"])
        links = self.get_links(f"{dir_first}/{file_first}.html")
        self.assertIsNone(links["prev"])
        
        last = self.forms[-1]
        dir_last = "forms/special" if last[0] == "specialForms" else "forms"
        file_last = get_slug(last[1]["code"])
        links = self.get_links(f"{dir_last}/{file_last}.html")
        self.assertIsNone(links["next"])

    def test_all_pages(self):
        pages = list(self.site_dir.rglob("*.html"))
        for p in pages:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                
            nav_matches = re.finditer(r'<a[^>]*class="[^"]*nav-(prev|next)[^"]*"[^>]*href="([^"]+)"', content)
            
            nav_links = list(nav_matches)
            self.assertLessEqual(len(nav_links), 2)
            
            for match in nav_links:
                href = match.group(2)
                self.assertIsNotNone(href)
                
                parsed = urllib.parse.urlparse(href)
                self.assertFalse(parsed.query, f"Query params found in {href}")
                self.assertFalse(parsed.fragment, f"Fragment found in {href}")
                
                target_path = (p.parent / href).resolve()
                self.assertTrue(target_path.exists(), f"404 target in {p}: {href}")
                self.assertNotEqual(target_path, p, "Self link found")
                
                rel_p = p.relative_to(self.site_dir)
                rel_target = target_path.relative_to(self.site_dir)
                
                if rel_p.parts[0] == "forms":
                    self.assertEqual(rel_target.parts[0], "forms")
                elif rel_p.parts[0] == "chapters":
                    self.assertEqual(rel_target.parts[0], "chapters")
                elif rel_p.parts[0] == "appendices":
                    self.assertEqual(rel_target.parts[0], "appendices")
