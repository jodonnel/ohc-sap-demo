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
    if len(sys.argv) < 3:
        print("Usage: send-artifacts.py <target-url> <file1> [<file2> ...]", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    files = [Path(f) for f in sys.argv[2:]]
    manifest = {}
    payload = {}
    try:
        for p in files:
            if not p.is_file():
                print(f"Not a file: {p}", file=sys.stderr)
                sys.exit(1)
            digest = sha256_file(p)
            manifest[p.name] = digest
            payload[p.name] = p.open("rb")
        payload["manifest.json"] = json.dumps(manifest, sort_keys=True).encode("utf-8")
        r = requests.post(url, files=payload, timeout=30)
        r.raise_for_status()
    except (requests.RequestException, OSError) as e:
        print(f"Transport failed: {e}", file=sys.stderr)
        sys.exit(3)
    sys.exit(0)

if __name__ == "__main__":
    main()
