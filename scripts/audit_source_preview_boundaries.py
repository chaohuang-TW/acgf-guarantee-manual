import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    manifest_path = ROOT / "data" / "source-preview-boundaries.json"
    if not manifest_path.is_file():
        print(f"ERROR: Missing {manifest_path.relative_to(ROOT)}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    with open(ROOT / "data" / "version.json", "r", encoding="utf-8") as f:
        version = json.load(f)

    if manifest.get("version") != 1:
        print("ERROR: Invalid manifest version")
        sys.exit(1)

    if manifest.get("sourcePdfSha256") != version["sha256"]:
        print("ERROR: sourcePdfSha256 in manifest does not match version.json! The PDF has changed and boundaries must be re-verified.")
        sys.exit(1)

    with open(ROOT / "data" / "toc.json", "r", encoding="utf-8") as f:
        toc = json.load(f)

    with open(ROOT / "data" / "pages.json", "r", encoding="utf-8") as f:
        pages = json.load(f)

    pdf_by_printed = {int(p["printedPage"]): p["pdfPage"] for p in pages if p["printedPage"]}

    expected_boundaries = []

    def add_expected(prev_id, curr_id, curr_printed):
        curr_pdf = pdf_by_printed[int(curr_printed)]
        expected_boundaries.append({
            "previous": prev_id,
            "current": curr_id,
            "previousEndPdfPage": curr_pdf - 1,
            "currentStartPdfPage": curr_pdf
        })

    def process_group(items):
        for i in range(len(items) - 1):
            curr_item = items[i]
            next_item = items[i+1]
            add_expected(
                curr_item.get("title") or curr_item.get("id"),
                next_item.get("title") or next_item.get("id"),
                next_item["printedPage"]
            )

    # Appendices 16->17, 17->18
    add_expected(toc["appendices"][15]["id"], toc["appendices"][16]["id"], toc["appendices"][16]["printedPage"])
    add_expected(toc["appendices"][16]["id"], toc["appendices"][17]["id"], toc["appendices"][17]["printedPage"])

    # App18 -> Form 1A
    add_expected(toc["appendices"][17]["id"], toc["forms"][0]["title"], toc["forms"][0]["printedPage"])

    # Forms
    process_group(toc["forms"])

    # Form 31 -> Special Form 3A
    add_expected(toc["forms"][-1]["title"], toc["specialForms"][0]["title"], toc["specialForms"][0]["printedPage"])

    # Special Forms
    process_group(toc["specialForms"])

    actual_boundaries = manifest.get("boundaries", [])
    
    if len(expected_boundaries) != len(actual_boundaries):
        print(f"ERROR: Expected {len(expected_boundaries)} boundaries in manifest, but found {len(actual_boundaries)}.")
        sys.exit(1)

    for i, expected in enumerate(expected_boundaries):
        actual = actual_boundaries[i]
        
        if expected["previous"] != actual["previous"] or expected["current"] != actual["current"]:
            print(f"ERROR: Boundary mismatch at index {i}. Expected {expected['previous']}->{expected['current']}, got {actual['previous']}->{actual['current']}")
            sys.exit(1)
            
        if expected["previousEndPdfPage"] != actual["previousEndPdfPage"]:
            print(f"ERROR: previousEndPdfPage mismatch for {actual['previous']}->{actual['current']}.")
            sys.exit(1)
            
        if expected["currentStartPdfPage"] != actual["currentStartPdfPage"]:
            print(f"ERROR: currentStartPdfPage mismatch for {actual['previous']}->{actual['current']}.")
            sys.exit(1)
            
        if "state" not in actual or actual["state"] not in ["clean-new-page", "shared-page", "separated-by-divider"]:
            print(f"ERROR: Invalid or missing state for {actual['previous']}->{actual['current']}.")
            sys.exit(1)

    print(f"SOURCE-PREVIEW BOUNDARY AUDIT PASSED: {len(actual_boundaries)} visual boundaries verified.")

if __name__ == "__main__":
    main()
