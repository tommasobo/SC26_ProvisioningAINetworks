#!/usr/bin/env python3
"""Read-only verification for the compact SC26 artifact data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ARTIFACT = Path(__file__).resolve().parent
MANIFESTS = ARTIFACT / "manifests"
CHUNK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_committed_hashes() -> tuple[int, int]:
    manifest = ARTIFACT / "committed_sha256.txt"
    checked = 0
    failed = 0
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, relative = raw.split(maxsplit=1)
        path = REPO / relative
        if not path.is_file():
            print(f"[FAIL] missing committed file: {relative}")
            failed += 1
            continue
        actual = sha256_file(path)
        if actual != expected:
            print(f"[FAIL] SHA-256 {relative}: expected {expected}, got {actual}")
            failed += 1
            continue
        checked += 1
    return checked, failed


def verify_llama_metadata() -> tuple[int, int]:
    rows = read_csv(MANIFESTS / "llama_figure6_local_metadata.csv")
    checked = 0
    failed = 0
    for row in rows:
        path = REPO / row["path"]
        if not path.is_file():
            print(f"[FAIL] missing Llama metadata: {row['path']}")
            failed += 1
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != int(row["bytes"]) or actual_hash != row["sha256"]:
            print(
                f"[FAIL] Llama metadata {row['path']}: "
                f"size={actual_size}, sha256={actual_hash}"
            )
            failed += 1
            continue
        checked += 1
    return checked, failed


def verify_llama_public_manifest() -> tuple[int, int]:
    rows = read_csv(MANIFESTS / "llama_figure6_public_nsys.csv")
    failed = 0
    if len(rows) != 32:
        print(f"[FAIL] expected 32 public Llama NSYS rows, found {len(rows)}")
        failed += 1
    total = sum(int(row["bytes"]) for row in rows)
    if total != 1_732_200_457:
        print(f"[FAIL] public Llama NSYS byte total is {total}, expected 1732200457")
        failed += 1
    if any(row["sha256"] != "not_computed" for row in rows):
        print("[FAIL] public Llama manifest unexpectedly claims unverified SHA-256 values")
        failed += 1
    return len(rows), failed


def main() -> int:
    argparse.ArgumentParser().parse_args()

    total_checked = 0
    total_failed = 0
    for verifier in (
        verify_committed_hashes,
        verify_llama_metadata,
        verify_llama_public_manifest,
    ):
        checked, failed = verifier()
        total_checked += checked
        total_failed += failed

    if total_failed:
        print(f"[FAIL] {total_failed} verification problem(s); {total_checked} checks passed")
        return 1
    print(f"[OK] {total_checked} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
