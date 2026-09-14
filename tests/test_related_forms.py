#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "related-forms.json"

class TestRelatedForms(unittest.TestCase):
    def setUp(self):
        with open(DATA, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_schema_and_version(self):
        self.assertEqual(self.data["version"], "115-04")
        self.assertEqual(self.data["source"], "authoritative-manual-explicit-relations")
        self.assertIn("relations", self.data)

    def test_29_verified_relations(self):
        # We need exact 29 verified relations
        self.assertEqual(len(self.data["relations"]), 29)

    def test_duplicate_relations(self):
        seen = set()
        for r in self.data["relations"]:
            key = (r["contentRef"]["id"], r["form"]["number"])
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_evidence_presence(self):
        evidence_count = 0
        for r in self.data["relations"]:
            self.assertTrue(len(r.get("evidence", [])) > 0)
            evidence_count += len(r["evidence"])
        self.assertEqual(evidence_count, 48)

    def test_subrogation_form_26(self):
        # Form 26 should not be in subrogation-documents
        for r in self.data["relations"]:
            if r["contentRef"]["id"] == "subrogation-documents":
                self.assertNotEqual(r["form"]["number"], "26")

    def test_subrogation_form_26_1(self):
        # Form 26-1 should be in subrogation-documents
        found = False
        for r in self.data["relations"]:
            if r["contentRef"]["id"] == "subrogation-documents" and r["form"]["number"] == "26-1":
                found = True
                break
        self.assertTrue(found)

if __name__ == "__main__":
    unittest.main()
