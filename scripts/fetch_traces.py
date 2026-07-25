#!/usr/bin/env python3
"""Download the standard raw traces into the artifact trace-root layout."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "local_artifact/manifests/trace_sources.json"
CHUNK = 8 * 1024 * 1024
USER_AGENT = "SC26-Provisioning-artifact/1.0"


class DirectoryIndex(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


@dataclass(frozen=True)
class RemoteFile:
    source_id: str
    name: str
    url: str
    size: int
    expected_sha256: str | None
    targets: tuple[Path, ...]


def request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None):
    all_headers = {"User-Agent": USER_AGENT}
    all_headers.update(headers or {})
    return urlopen(Request(url, method=method, headers=all_headers), timeout=60)


def human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("sources"), list):
        raise SystemExit(f"unsupported trace manifest: {path}")
    return data["sources"]


def selected_targets(
    source: dict[str, Any], figures: set[int] | None
) -> tuple[Path, ...]:
    targets: list[Path] = []
    for figure_text, paths in source["targets"].items():
        if figures is None or int(figure_text) in figures:
            targets.extend(Path(path) for path in paths)
    return tuple(targets)


def list_source(source: dict[str, Any], targets: tuple[Path, ...]) -> list[RemoteFile]:
    base_url = source["url"]
    parser = DirectoryIndex()
    with request(base_url) as response:
        parser.feed(response.read().decode("utf-8", errors="replace"))

    entries: list[tuple[str, str]] = []
    for href in parser.links:
        if href.startswith("?") or href == "../" or href.endswith("/"):
            continue
        file_url = urljoin(base_url, href)
        name = unquote(Path(urlparse(file_url).path).name)
        if fnmatch.fnmatch(name, source.get("pattern", "*.nsys-rep")):
            entries.append((name, file_url))
    entries.sort()
    if not entries:
        raise RuntimeError(f"no matching traces listed at {base_url}")

    recorded = source.get("files", {})

    def describe(entry: tuple[str, str]) -> RemoteFile:
        name, file_url = entry
        metadata = recorded.get(name, {})
        size = metadata.get("bytes")
        if size is None:
            with request(file_url, method="HEAD") as response:
                length = response.headers.get("Content-Length")
            if length is None:
                raise RuntimeError(f"server did not report a size for {file_url}")
            size = int(length)
        return RemoteFile(
            source_id=source["id"],
            name=name,
            url=file_url,
            size=int(size),
            expected_sha256=metadata.get("sha256"),
            targets=targets,
        )

    with ThreadPoolExecutor(max_workers=min(16, len(entries))) as pool:
        return list(pool.map(describe, entries))


def existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists():
        if current.parent == current:
            return Path("/")
        current = current.parent
    return current


def download(remote: RemoteFile, destination: Path) -> tuple[Path, str, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == remote.size:
        digest = sha256_file(destination)
        if remote.expected_sha256 and digest != remote.expected_sha256:
            raise RuntimeError(f"checksum mismatch for existing {destination}")
        print(f"[ready] {remote.source_id}/{remote.name}", flush=True)
        return destination, digest, "existing"

    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with request(remote.url, headers=headers) as response:
        append = offset > 0 and getattr(response, "status", None) == 206
        if not append:
            offset = 0
        mode = "ab" if append else "wb"
        with partial.open(mode) as handle:
            while chunk := response.read(CHUNK):
                handle.write(chunk)

    if partial.stat().st_size != remote.size:
        raise RuntimeError(
            f"size mismatch for {remote.url}: "
            f"expected {remote.size}, got {partial.stat().st_size}"
        )
    os.replace(partial, destination)
    digest = sha256_file(destination)
    if remote.expected_sha256 and digest != remote.expected_sha256:
        raise RuntimeError(f"checksum mismatch for downloaded {remote.url}")
    print(f"[done]  {remote.source_id}/{remote.name}", flush=True)
    return destination, digest, "downloaded"


def materialize(source: Path, destination: Path, expected_size: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == expected_size:
        return
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(
            f"existing target has the wrong size: {destination}; "
            "move it aside and rerun"
        )
    try:
        os.link(source, destination)
    except OSError:
        destination.symlink_to(os.path.relpath(source, destination.parent))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Required scratch destination; this becomes --trace-root.",
    )
    parser.add_argument(
        "--figures",
        type=int,
        choices=(3, 4, 5, 6),
        nargs="+",
        help="Optional subset. The default downloads all standard Figures 3-6 traces.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Parallel downloads (default: 4).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve the remote listing and report space without downloading.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered trace sets without accessing the network.",
    )
    args = parser.parse_args()
    if not args.list and args.output is None:
        parser.error("--output is required unless --list is used")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    return args


def main() -> int:
    args = parse_args()
    sources = load_manifest(args.manifest)
    figures = set(args.figures) if args.figures else None
    active = [
        (source, selected_targets(source, figures))
        for source in sources
        if selected_targets(source, figures)
    ]

    if args.list:
        for source, targets in active:
            figure_text = ",".join(str(value) for value in source["figures"])
            print(
                f"{source['id']}: figures {figure_text}; "
                f"{source['selection']}; {source['url']}"
            )
            print("  targets:", ", ".join(str(path) for path in targets))
        return 0

    output = args.output.resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit("--output must be outside the repository; use scratch")

    remote_files: list[RemoteFile] = []
    for source, targets in active:
        marker = " [provisional mapping]" if source["selection"] == "provisional" else ""
        print(f"Resolving {source['id']}{marker}: {source['url']}")
        remote_files.extend(list_source(source, targets))

    total_bytes = sum(remote.size for remote in remote_files)
    cache_root = output / ".trace_downloads"
    missing_bytes = sum(
        remote.size
        for remote in remote_files
        if not (cache_root / remote.source_id / remote.name).is_file()
        or (cache_root / remote.source_id / remote.name).stat().st_size != remote.size
    )
    print(
        f"Selected {len(remote_files)} files from {len(active)} trace sets: "
        f"{human_bytes(total_bytes)} total, {human_bytes(missing_bytes)} to download."
    )
    print("Grok 4K traces are not included in the standard manifest.")
    if args.dry_run:
        return 0

    free_bytes = shutil.disk_usage(existing_ancestor(output)).free
    if free_bytes < missing_bytes:
        raise SystemExit(
            f"insufficient free space: need {human_bytes(missing_bytes)}, "
            f"have {human_bytes(free_bytes)}"
        )
    output.mkdir(parents=True, exist_ok=True)

    def fetch(remote: RemoteFile) -> tuple[RemoteFile, Path, str, str]:
        cache_path = cache_root / remote.source_id / remote.name
        path, digest, state = download(remote, cache_path)
        return remote, path, digest, state

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        fetched = list(pool.map(fetch, remote_files))

    records: list[dict[str, Any]] = []
    for remote, cache_path, digest, state in fetched:
        target_paths: list[str] = []
        for target_dir in remote.targets:
            target = output / target_dir / remote.name
            materialize(cache_path, target, remote.size)
            target_paths.append(str(target.relative_to(output)))
        records.append(
            {
                "source_id": remote.source_id,
                "url": remote.url,
                "bytes": remote.size,
                "sha256": digest,
                "state": state,
                "targets": target_paths,
            }
        )

    run_manifest = {
        "trace_root": str(output),
        "figures": sorted(figures) if figures else [3, 4, 5, 6],
        "grok_4k_included": False,
        "files": records,
    }
    manifest_path = output / "trace_download_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Trace root ready: {output}")
    print(f"Download record: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
