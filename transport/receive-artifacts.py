#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path
import requests

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()

def main():
    if len(sys.argv) != 3:
        print("Usage: receive-artifacts.py <base-url> <output-dir>", file=sys.stderr)
        sys.exit(2)
    base_url = sys.argv[1].rstrip("/")
    out_root = Path(sys.argv[2]).resolve()
    if not out_root.is_dir():
        print(f"Output not a directory: {out_root}", file=sys.stderr)
        sys.exit(1)
    manifest_url = f"{base_url}/manifest.json"
    try:
        r = requests.get(manifest_url, timeout=30)
        r.raise_for_status()
        manifest = r.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        print(f"Manifest fetch/parse failed: {e}", file=sys.stderr)
        sys.exit(3)
    if not isinstance(manifest, dict):
        print("Manifest is not a dict", file=sys.stderr)
        sys.exit(4)
    for rel, expected_digest in manifest.items():
        file_url = f"{base_url}/{rel}"
        target_path = out_root / rel
        try:
            r = requests.get(file_url, timeout=30, stream=True)
            r.raise_for_status()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            actual_digest = sha256_file(target_path)
            if actual_digest != expected_digest:
                print(f"Hash mismatch for {rel}: expected {expected_digest}, got {actual_digest}", file=sys.stderr)
                target_path.unlink(missing_ok=True)
                sys.exit(5)
        except requests.RequestException as e:
            print(f"Fetch failed for {rel}: {e}", file=sys.stderr)
            sys.exit(6)
        except OSError as e:
            print(f"Write/OS error for {rel}: {e}", file=sys.stderr)
            sys.exit(7)
    sys.exit(0)

if __name__ == "__main__":
    main()
