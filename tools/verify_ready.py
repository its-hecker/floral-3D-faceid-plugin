#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail the product configuration early when prepared inputs have changed."""
import hashlib
import json
from pathlib import Path
import sys
from fetch_prebuilts import ROOT, verify_all


def verify(root=ROOT):
    verify_all(root)
    profile = json.loads((root / "generated/profile.json").read_text())
    for item in profile.get("input_files", []):
        data = Path(item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Prepared source changed; rerun tools/prepare.py: " + item["path"])
    for item in profile.get("output_files", []):
        data = (root / item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Generated configuration changed; rerun tools/prepare.py: " + item["path"])


def main():
    try:
        verify()
        from apply_framework_fixes import apply
        status, _ = apply(Path.cwd(), write=False)
        if status != "already applied":
            raise ValueError("Apply tools/apply_framework_fixes.py --apply before building")
        print("ready")
    except (OSError, ValueError) as error:
        print("Floral setup:", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
