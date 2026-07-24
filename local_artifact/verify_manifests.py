#!/usr/bin/env python3
"""Read-only verification for the local SC26 reproduction handoff."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import zipfile
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


def sha256_stream(handle) -> str:
    digest = hashlib.sha256()
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


def verify_vllm_archive(path: Path) -> tuple[int, int]:
    rows = read_csv(MANIFESTS / "vllm_figure6_files.csv")
    archive_row = next(row for row in rows if row["role"] == "source_archive")
    failed = 0
    checked = 0

    if path.stat().st_size != int(archive_row["bytes"]):
        print(
            f"[FAIL] archive size {path.stat().st_size}, "
            f"expected {archive_row['bytes']}"
        )
        failed += 1
    archive_hash = sha256_file(path)
    if archive_hash != archive_row["sha256"]:
        print(
            f"[FAIL] archive SHA-256 {archive_hash}, "
            f"expected {archive_row['sha256']}"
        )
        failed += 1
    else:
        checked += 1

    with zipfile.ZipFile(path) as archive:
        for row in rows:
            member = row["archive_member"]
            if not member:
                continue
            try:
                info = archive.getinfo(member)
            except KeyError:
                print(f"[FAIL] missing archive member: {member}")
                failed += 1
                continue
            if info.file_size != int(row["bytes"]):
                print(
                    f"[FAIL] member size {member}: {info.file_size}, "
                    f"expected {row['bytes']}"
                )
                failed += 1
                continue
            with archive.open(info) as handle:
                actual_hash = sha256_stream(handle)
            if actual_hash != row["sha256"]:
                print(
                    f"[FAIL] member SHA-256 {member}: {actual_hash}, "
                    f"expected {row['sha256']}"
                )
                failed += 1
                continue
            checked += 1
    return checked, failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vllm-archive",
        type=Path,
        help="Optional path to vllm_recent_runs_20260407.zip for streaming verification",
    )
    args = parser.parse_args()

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

    if args.vllm_archive:
        if not args.vllm_archive.is_file():
            print(f"[FAIL] vLLM archive not found: {args.vllm_archive}")
            total_failed += 1
        else:
            checked, failed = verify_vllm_archive(args.vllm_archive)
            total_checked += checked
            total_failed += failed
    else:
        print("[SKIP] large vLLM archive; pass --vllm-archive to verify it")

    if total_failed:
        print(f"[FAIL] {total_failed} verification problem(s); {total_checked} checks passed")
        return 1
    print(f"[OK] {total_checked} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
