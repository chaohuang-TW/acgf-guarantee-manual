#!/usr/bin/env python3
"""Rebuild the exact formal baseline outside the checkout; compare contracts."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "212a9e79a2779296c45e6f6907c90e7d8dc0d4f2"


class PageContract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    node = os.environ.get("NODE_BINARY", "node")
    with tempfile.TemporaryDirectory(prefix="manual-experience-contract-") as directory:
        old = Path(directory)
        archive = subprocess.check_output(["git", "archive", BASELINE], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(old)
        subprocess.run([sys.executable, str(old / "scripts/build_site.py")], check=True)
        immutable = {}
        for prefix in ["data", "source", "assets/page-previews", "site/downloads", "site/assets/data"]:
            for before in (old / prefix).rglob("*"):
                if before.is_file():
                    relative = before.relative_to(old)
                    after = ROOT / relative
                    assert after.is_file() and digest(before) == digest(after), f"Immutable bytes changed: {relative}"
                    immutable[str(relative)] = digest(after)
        routes = []
        for before in (old / "site").rglob("*.html"):
            relative = before.relative_to(old / "site")
            after = ROOT / "site" / relative
            assert after.is_file(), f"Route removed: {relative}"
            original = PageContract(); original.feed(before.read_text())
            candidate = PageContract(); candidate.feed(after.read_text())
            assert set(original.ids) <= set(candidate.ids), f"Old anchor removed: {relative}"
            assert len(candidate.ids) == len(set(candidate.ids)), f"Duplicate ID: {relative}"
            routes.append(str(relative))
        fixture = str(ROOT / "tests/experience_search_contract.cjs")
        before = json.loads(subprocess.check_output([node, fixture, str(old)]))
        after = json.loads(subprocess.check_output([node, fixture, str(ROOT)]))
        assert before == after, "Full search result/order/exactForm/reason/segment/snippet contract changed"
        assert after["recordCount"] == 196
        report = {"baseline": BASELINE, "immutableFiles": immutable, "routesAndAnchors": routes,
                  "searchRecords": 196, "queries": len(after["queries"]), "searchContractSha256": after["sha256"],
                  "result": "PASS"}
        out = Path(os.environ.get("EXPERIENCE_CONTRACT_REPORT", "/tmp/manual-experience-redesign/contracts.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"EXPERIENCE CONTRACT PASS: {len(immutable)} immutable files; {len(routes)} routes/anchors; {report['queries']} full queries; SHA {after['sha256']}")


if __name__ == "__main__":
    main()
