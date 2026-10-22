"""Maintainer tool: refresh source integrity and release inventories after review."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    files = set()
    for folder, patterns in {"src": ["*.py"], "scripts/a100": ["*.py", "*.sh"], "config": ["*.yaml"]}.items():
        for pattern in patterns:
            files.update(p for p in (ROOT / folder).rglob(pattern) if "__pycache__" not in p.parts)
    files.update(ROOT / name for name in ["pyproject.toml", "uv.lock", "model.lock.json", "benchmark-release.json", ".python-version"])
    return sorted(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    manifest = {p.relative_to(ROOT).as_posix(): digest(p) for p in source_files()}
    path = ROOT / "benchmark-source-manifest.json"
    if args.write:
        path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    elif json.loads(path.read_text()) != manifest:
        raise SystemExit("Source manifest stale; review changes then refresh with --write")
    if args.write:
        names = subprocess.check_output(["git", "ls-files", "--cached"], cwd=ROOT, text=True).splitlines()
        # Hash the staged Git bytes, including normalization, to describe the actual source archive.
        staged = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT,
            input="".join(f":{name}\n" for name in names).encode(), capture_output=True, check=True).stdout
        blob_hashes = {}
        cursor = 0
        for name in names:
            end = staged.index(b"\n", cursor)
            header = staged[cursor:end].split()
            length = int(header[2])
            cursor = end + 1
            blob_hashes[name] = hashlib.sha256(staged[cursor:cursor + length]).hexdigest()
            cursor += length + 1
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["path", "sha256", "purpose", "required_for_execution", "required_for_scientific_evidence"])
        for name in sorted(names):
            p = ROOT / name
            if not p.is_file() or name == "reviewer_analysis/a100_release_manifest.csv":
                continue
            runtime = name in manifest or name == "benchmark-source-manifest.json"
            evidence = name.startswith(("results/", "generated/", "reviewer_analysis/", "fixtures/"))
            writer.writerow([name, blob_hashes[name], "runtime" if runtime else "evidence/provenance" if evidence else "documentation/project", str(runtime).lower(), str(evidence).lower()])
        (ROOT / "reviewer_analysis/a100_release_manifest.csv").write_bytes(stream.getvalue().encode())
    print(f"Source integrity: {len(manifest)} files PASS")


if __name__ == "__main__":
    main()
