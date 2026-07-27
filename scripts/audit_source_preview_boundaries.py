import json
import hashlib
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data/source-preview-boundaries.json"
VERSION_PATH = ROOT / "data/version.json"
PDF_PATH = ROOT / "source/acgf-guarantee-manual-115-04.pdf"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_pdf_sha():
    with open(PDF_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def validate_manifest(manifest, authoritative_inventory):
    if manifest.get("version") != 2:
        raise ValueError(f"Expected manifest version 2, got {manifest.get('version')}")

    # 1. SHA verification
    actual_pdf_sha = get_pdf_sha()
    version_data = load_json(VERSION_PATH)
    if actual_pdf_sha != version_data.get("sha256"):
        raise ValueError("Actual PDF SHA does not match data/version.json")
    if actual_pdf_sha != manifest.get("sourcePdfSha256"):
        raise ValueError("Actual PDF SHA does not match manifest sourcePdfSha256")
    
    # 2. Schema and rule checks
    boundaries = manifest.get("boundaries", [])
    if len(boundaries) != 46:
        raise ValueError(f"Expected 46 boundaries, got {len(boundaries)}")
        
    if len(authoritative_inventory) != 46:
        raise ValueError(f"Expected authoritative_inventory to have 46 items, got {len(authoritative_inventory)}")

    for idx, (b, auth) in enumerate(zip(boundaries, authoritative_inventory)):
        kind = b.get("kind")
        prev = b.get("previous")
        curr = b.get("current")
        prev_start = b.get("previousStartPdfPage")
        prev_end = b.get("previousEndPdfPage")
        curr_start = b.get("currentStartPdfPage")
        state = b.get("state")
        rev_pages = b.get("reviewedPdfPages", [])
        dividers = b.get("dividerPdfPages", [])
        prev_cont = b.get("previousContentContinuesIntoCurrentStartPage")
        curr_cont = b.get("currentContentStartsOnPreviousEndPage")
        method = b.get("reviewMethod")

        if any(x is None for x in [kind, prev, curr, prev_start, prev_end, curr_start, state, method]):
            raise ValueError(f"Missing required fields in boundary {idx}: {b}")
            
        # Verify against authoritative inventory
        if kind != auth.get("kind"):
            raise ValueError(f"Boundary {idx}: kind '{kind}' does not match authoritative '{auth.get('kind')}'")
        if prev != auth.get("previous"):
            raise ValueError(f"Boundary {idx}: previous '{prev}' does not match authoritative '{auth.get('previous')}'")
        if curr != auth.get("current"):
            raise ValueError(f"Boundary {idx}: current '{curr}' does not match authoritative '{auth.get('current')}'")
        if prev_start != auth.get("previousStartPdfPage"):
            raise ValueError(f"Boundary {idx}: previousStartPdfPage '{prev_start}' does not match authoritative '{auth.get('previousStartPdfPage')}'")
        if curr_start != auth.get("currentStartPdfPage"):
            raise ValueError(f"Boundary {idx}: currentStartPdfPage '{curr_start}' does not match authoritative '{auth.get('currentStartPdfPage')}'")
            
        # Case D True End verification if injected for tests
        true_end = auth.get("previousTrueEndPdfPage")
        if true_end is not None and prev_end != true_end:
            raise ValueError(f"Boundary {idx}: Authoritative true end is {true_end}, but manifest claims {prev_end}")

        # D. reviewedPdfPages check
        expected_reviewed = set([prev_end, curr_start] + dividers)
        if not expected_reviewed.issubset(set(rev_pages)):
            raise ValueError(f"Boundary {idx}: reviewedPdfPages must cover prev_end, curr_start, and dividers.")
        
        for p in rev_pages:
            if not (1 <= p <= 203):
                raise ValueError(f"Boundary {idx}: reviewed page {p} out of bounds (1-203).")

        # E. Overlap check (except shared-page)
        if state != "shared-page" and prev_end >= curr_start:
            raise ValueError(f"Boundary {idx}: previousEnd ({prev_end}) >= currentStart ({curr_start}) in state {state}")

        # C. State consistency
        if state == "clean-new-page":
            if prev_end + 1 != curr_start:
                raise ValueError(f"Boundary {idx}: clean-new-page must have prev_end + 1 == curr_start")
            if dividers != []:
                raise ValueError(f"Boundary {idx}: clean-new-page cannot have dividers")
            if prev_cont or curr_cont:
                raise ValueError(f"Boundary {idx}: clean-new-page cannot have ownership booleans true")
                
        elif state == "separated-by-divider":
            if prev_end + 1 >= curr_start:
                raise ValueError(f"Boundary {idx}: separated-by-divider must have prev_end + 1 < curr_start")
            expected_dividers = list(range(prev_end + 1, curr_start))
            if dividers != expected_dividers:
                raise ValueError(f"Boundary {idx}: dividers {dividers} do not match expected {expected_dividers}")
                
        elif state == "shared-page":
            if prev_end != curr_start:
                raise ValueError(f"Boundary {idx}: shared-page must have prev_end == curr_start")
            if not prev_cont and not curr_cont:
                raise ValueError(f"Boundary {idx}: shared-page must have at least one true ownership boolean")
        else:
            raise ValueError(f"Boundary {idx}: unknown state {state}")

    # Verify dividers don't have printed pages
    pages_data = load_json(ROOT / "data/pages.json")
    page_map = {p["pdfPage"]: p.get("printedPage", "") for p in pages_data}
    
    for idx, b in enumerate(boundaries):
        dividers = b.get("dividerPdfPages", [])
        for d in dividers:
            if page_map.get(d) != "":
                raise ValueError(f"Boundary {idx}: divider page {d} has a printedPage, it cannot be a divider!")

def main():
    import sys
    sys.path.insert(0, str(ROOT))
    try:
        from scripts.source_preview_boundaries import get_authoritative_boundaries
        authoritative_inventory = get_authoritative_boundaries()
        manifest = load_json(MANIFEST_PATH)
        validate_manifest(manifest, authoritative_inventory)
        
        # Now print summary
        clean = sum(1 for b in manifest["boundaries"] if b["state"] == "clean-new-page")
        divider = sum(1 for b in manifest["boundaries"] if b["state"] == "separated-by-divider")
        shared = sum(1 for b in manifest["boundaries"] if b["state"] == "shared-page")
        
        print("SOURCE-PREVIEW BOUNDARY AUDIT PASSED:")
        print(f"Total: {len(manifest['boundaries'])}")
        print(f"clean-new-page: {clean}")
        print(f"separated-by-divider: {divider}")
        print(f"shared-page: {shared}")
        sys.exit(0)
    except Exception as e:
        print(f"SOURCE-PREVIEW BOUNDARY AUDIT FAILED: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
