import unittest
import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_source_preview_boundaries import validate_manifest, get_pdf_sha

class TestBoundaryAudit(unittest.TestCase):
    def get_valid_authoritative_inventory(self):
        # Create a mock 46-boundary inventory matching the test manifests
        return [{
            "kind": "form",
            "previous": "A",
            "current": "B",
            "previousStartPdfPage": 5 if i % 2 == 0 else 122,
            "currentStartPdfPage": 11 if i % 2 == 0 else 129
        } for i in range(46)]

    def test_case_a_clean_new_page(self):
        manifest = {
            "version": 2,
            "sourcePdfSha256": get_pdf_sha(),
            "boundaries": [{
                "kind": "form", "previous": "A", "current": "B",
                "previousStartPdfPage": 5, "previousEndPdfPage": 10,
                "currentStartPdfPage": 11, "state": "clean-new-page",
                "reviewedPdfPages": [10, 11], "dividerPdfPages": [],
                "previousContentContinuesIntoCurrentStartPage": False,
                "currentContentStartsOnPreviousEndPage": False,
                "reviewMethod": "visual"
            } for i in range(46)]
        }
        # Update starts to match our mock inventory
        for i, b in enumerate(manifest["boundaries"]):
            if i % 2 != 0:
                b["previousStartPdfPage"] = 122
                b["currentStartPdfPage"] = 129
                b["previousEndPdfPage"] = 128
                b["reviewedPdfPages"] = [128, 129]
        
        # Should not raise
        validate_manifest(manifest, self.get_valid_authoritative_inventory())

    def test_case_b_divider(self):
        manifest = {
            "version": 2,
            "sourcePdfSha256": get_pdf_sha(),
            "boundaries": [{
                "kind": "form", "previous": "A", "current": "B",
                "previousStartPdfPage": 122, "previousEndPdfPage": 126,
                "currentStartPdfPage": 129, "state": "separated-by-divider",
                "reviewedPdfPages": [126, 127, 128, 129], "dividerPdfPages": [127, 128],
                "previousContentContinuesIntoCurrentStartPage": False,
                "currentContentStartsOnPreviousEndPage": False,
                "reviewMethod": "visual"
            } for i in range(46)]
        }
        for i, b in enumerate(manifest["boundaries"]):
            if i % 2 == 0:
                b["previousStartPdfPage"] = 5
                b["currentStartPdfPage"] = 11
                b["previousEndPdfPage"] = 10
                b["state"] = "clean-new-page"
                b["reviewedPdfPages"] = [10, 11]
                b["dividerPdfPages"] = []

        validate_manifest(manifest, self.get_valid_authoritative_inventory())

    def test_case_c_shared(self):
        manifest = {
            "version": 2,
            "sourcePdfSha256": get_pdf_sha(),
            "boundaries": [{
                "kind": "form", "previous": "A", "current": "B",
                "previousStartPdfPage": 5, "previousEndPdfPage": 11,
                "currentStartPdfPage": 11, "state": "shared-page",
                "reviewedPdfPages": [11], "dividerPdfPages": [],
                "previousContentContinuesIntoCurrentStartPage": True,
                "currentContentStartsOnPreviousEndPage": False,
                "reviewMethod": "visual"
            } for i in range(46)]
        }
        for i, b in enumerate(manifest["boundaries"]):
            if i % 2 != 0:
                b["previousStartPdfPage"] = 122
                b["currentStartPdfPage"] = 129
                b["previousEndPdfPage"] = 129
                b["reviewedPdfPages"] = [129]

        validate_manifest(manifest, self.get_valid_authoritative_inventory())

    def test_case_d_invalid_推導(self):
        # true start is 5, true next start is 13.
        # true end is 10.
        # manifest falsely claims previousEnd = 12, state = clean-new-page.
        
        manifest = {
            "version": 2,
            "sourcePdfSha256": get_pdf_sha(),
            "boundaries": [{
                "kind": "form", "previous": "A", "current": "B",
                "previousStartPdfPage": 5, "previousEndPdfPage": 12, # Invalid!
                "currentStartPdfPage": 13, "state": "clean-new-page",
                "reviewedPdfPages": [12, 13], "dividerPdfPages": [],
                "previousContentContinuesIntoCurrentStartPage": False,
                "currentContentStartsOnPreviousEndPage": False,
                "reviewMethod": "visual"
            } for i in range(46)]
        }

        # The authoritative inventory says previous item truly ends at 10.
        inventory = [{
            "kind": "form",
            "previous": "A",
            "current": "B",
            "previousStartPdfPage": 5,
            "previousTrueEndPdfPage": 10, # Add true end for this case D
            "currentStartPdfPage": 13
        } for i in range(46)]
        
        with self.assertRaises(ValueError) as context:
            validate_manifest(manifest, inventory)
            
        self.assertIn("Authoritative true end", str(context.exception))

if __name__ == '__main__':
    unittest.main()
