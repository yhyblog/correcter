#!/usr/bin/env python3
"""Copy and verify the sealed reference experiment without changing its bytes."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "ACT-RECAP"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args()
    manifest_path = ROOT / "provenance/reference_archive_manifest.json"
    if options.verify_only:
        data = json.loads(manifest_path.read_text())
        for entry in data["files"]:
            destination = ROOT / entry["destination"]
            assert destination.is_file() and not destination.is_symlink(), str(destination)
            assert destination.stat().st_size == entry["size_bytes"], str(destination)
            assert sha256(destination) == entry["sha256"], str(destination)
        print(json.dumps({"status": "passed", "files": len(data["files"])}))
        return

    copied_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entries = []

    def copy_file(source: Path, destination: Path) -> None:
        before = source.stat()
        expected = sha256(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.is_symlink() or sha256(destination) != expected:
                raise RuntimeError(f"Refusing to overwrite different existing file: {destination}")
        else:
            shutil.copy2(source, destination, follow_symlinks=True)
        after = source.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(source)
        assert destination.stat().st_size == before.st_size and sha256(destination) == expected, str(destination)
        entries.append({"source": str(source), "destination": str(destination.relative_to(ROOT)),
                        "size_bytes": before.st_size, "sha256": expected,
                        "source_mtime_ns": before.st_mtime_ns, "copied_at_utc": copied_at})

    def copy_tree(source: Path, destination: Path) -> None:
        for item in sorted(source.rglob("*")):
            if item.is_file():
                copy_file(item, destination / item.relative_to(source))

    copy_tree(SOURCE / "outputs/act_recap_ogg_flow_20260916", ROOT / "results/reference_flow_20260916")
    for name in ["ACT_RECAP_FLOW_GUIDANCE_RESULTS_20260916.md",
                 "ACT_RECAP_FLOW_GUIDANCE_PROTOCOL_20260916.md",
                 "ACT_RECAP_FLOW_GUIDANCE_EXECUTION_BRIEF_20260916.md",
                 "ACT_RECAP_OGG_V3_FLOW_GUIDANCE_REVIEW_20260916.md",
                 "ACT_RECAP_OGG_V3_RESULTS_20260916.md"]:
        copy_file(SOURCE / name, ROOT / "docs/reference" / name)
    copy_tree(SOURCE / "docs/ogg_flow_20260916", ROOT / "docs/reference/ogg_flow_20260916")

    snapshot = ROOT / "provenance/source_snapshot"
    paths = [*sorted((SOURCE / "src/ac_tmil/ogg_flow").glob("*.py")),
             *[SOURCE / path for path in [
                 "src/ac_tmil/ogg/core.py",
                 "src/ac_tmil/ogg_research_v3/learning.py",
                 "src/ac_tmil/ogg_research/statistics.py",
                 "tests/test_ogg_flow_guidance.py", "tests/test_ogg_flow_matching.py",
                 "scripts/run_recap_ogg_flow.sh",
                 "outputs/act_recap_ogg_20260915/config.json",
                 "outputs/act_recap_ogg_20260915/config_identity.json",
                 "outputs/act_recap_ogg_research_v3_20260916/config.json",
                 "outputs/act_recap_future_aware_20260914/config.json",
                 "outputs/act_recap_future_aware_20260914/audits/frozen_selection.json",
             ]]]
    for path in paths:
        copy_file(path, snapshot / path.relative_to(SOURCE))

    summary = {"created_at_utc": copied_at, "source_repository": str(SOURCE),
               "destination_root": str(ROOT), "copy_semantics": "regular files; no symlinks; byte-identical SHA256 verification",
               "file_count": len(entries), "total_bytes": sum(entry["size_bytes"] for entry in entries),
               "files": entries}
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("file_count", "total_bytes", "copy_semantics")}), flush=True)


if __name__ == "__main__":
    main()
