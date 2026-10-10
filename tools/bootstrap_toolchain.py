"""Bootstrap the pinned Windows x64 spike locally, optionally run verification.

Requires the manifest's Python version. No service, global package or PATH edit.
Downloads are restricted to pinned official/public artifact URLs and hashes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
from uuid import uuid4
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / ".dev-tools"


def digest(path):
    result = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): result.update(block)
    return result.hexdigest()


def owned_path(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root): raise ValueError("Artifact path escapes the owned development root")
    return path


def archive_members(archive, destination):
    chosen = []
    seen = set()
    for item in archive.infolist():
        if item.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
            path = owned_path(destination / item.filename, destination)
            # Reject aliases/symlinks/duplicate filenames before extraction.
            if path in seen or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Ambiguous or symbolic archive member")
            seen.add(path)
            chosen.append((item, path))
    if not chosen or len(chosen) > 20000 or sum(i.file_size for i, _ in chosen) > 2 * 1024 ** 3:
        raise ValueError("Unexpected binary archive scope")
    return chosen


def prepare_postgresql(manifest):
    artifact = manifest["postgresql"]
    url = artifact["url"]
    if url != "https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip":
        raise ValueError("Unexpected PostgreSQL download URL")
    archive_path = owned_path(DEV / "downloads" / url.rsplit("/", 1)[1], DEV)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        temporary = owned_path(archive_path.with_suffix("." + uuid4().hex + ".part"), DEV)
        total = 0
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("xb") as stream:
            if response.geturl() != url: raise ValueError("Unexpected artifact redirect")
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > artifact["bytes"]: raise ValueError("Artifact exceeds its pinned size")
                stream.write(block)
        if total != artifact["bytes"] or digest(temporary) != artifact["sha256"]:
            raise ValueError("Artifact size/digest mismatch; original files preserved")
        # Same owned root, destination absent, no recursive move/delete.
        temporary.rename(archive_path)
    if archive_path.stat().st_size != artifact["bytes"] or digest(archive_path) != artifact["sha256"]:
        raise ValueError("Existing archive does not match its pin")
    destination = owned_path(DEV / "postgresql-18.6", DEV)
    with zipfile.ZipFile(archive_path) as archive:
        chosen = archive_members(archive, destination)
        if destination.exists():
            for item, path in chosen:
                if item.is_dir(): continue
                if not path.is_file() or path.stat().st_size != item.file_size or zlib.crc32(path.read_bytes()) != item.CRC:
                    raise ValueError("Existing extracted binary differs; refusing to overwrite it")
        else:
            destination.mkdir(parents=True)
            for item, path in chosen:
                if item.is_dir(): path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(item))
    return destination / "pgsql"


def run(argv):
    result = subprocess.run([str(a) for a in argv], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.stdout: print(result.stdout, end="", flush=True)
    if result.stderr: print(result.stderr, end="", file=sys.stderr, flush=True)
    result.check_returncode()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Run all offline checks and a new isolated PostgreSQL spike")
    parser.add_argument("--venv-root", type=Path, help="Optional fresh environment under .dev-tools/environments")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "toolchain/manifest.json").read_text(encoding="utf-8"))
    if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64") or platform.python_version() != manifest["python_version"]:
        print("Bootstrap requires Windows x64 and Python " + manifest["python_version"], file=sys.stderr); return 1
    try:
        environment = owned_path(args.venv_root, DEV / "environments") if args.venv_root else ROOT / ".venv"
        interpreter = environment / "Scripts/python.exe"
        if not environment.exists(): run([sys.executable, "-m", "venv", environment])
        if not interpreter.is_file(): raise ValueError("Existing .venv is incomplete; refusing to replace it")
        run([interpreter, "-m", "pip", "install", "--cache-dir", DEV / "pip-cache", "--require-hashes", "--only-binary=:all:", "--index-url", "https://pypi.org/simple", "-r", "requirements-toolchain.lock"])
        run([interpreter, "-m", "pip", "check"])
        postgres_root = prepare_postgresql(manifest)
        print("Pinned local spike environment ready", flush=True)
        if args.verify: run([interpreter, "tools/verify_toolchain.py", "--postgres-root", postgres_root])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(type(error).__name__ + ": " + str(error), file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
