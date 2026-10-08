#!/usr/bin/env python3
"""Freeze/verify an experimental configuration and its local evidence hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "adapters", "policy", "eval", "examples", "scripts", "tests")
EXTENSIONS = {".py", ".ts", ".json", ".jsonl", ".md", ".xml", ".sh", ".toml"}
EXCLUDED = {"node_modules", "__pycache__"}


def local_file(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or any(part.startswith(".") for part in path.parts):
        raise ValueError("snapshot inputs must be visible project-relative paths")
    target = root / path
    if not target.is_file() or any((root / Path(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts)+1)):
        raise ValueError(f"missing or symlinked snapshot input: {relative}")
    return target


def build_snapshot(root, profile_path):
    root = Path(root).resolve()
    profile_path = Path(profile_path)
    profile_bytes = local_file(root, profile_path).read_bytes()
    profile = json.loads(profile_bytes)
    if (not isinstance(profile, dict) or type(profile.get("schema_version")) is not int or profile["schema_version"] != 1
            or profile.get("status") != "experimental" or profile.get("release_ready") is not False
            or not isinstance(profile.get("id"), str) or not profile["id"].strip()):
        raise ValueError("profile must declare schema 1, experimental status and release_ready=false")
    version = tomllib.loads(local_file(root, "pyproject.toml").read_text())["project"]["version"]
    if profile.get("package_version") != version:
        raise ValueError("profile package version does not match pyproject.toml")
    evidence = profile.get("evidence")
    if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, dict) or not isinstance(item.get("path"), str)
            or not isinstance(item.get("scope"), str) or not item["scope"].strip() for item in evidence):
        raise ValueError("profile requires evidence paths with explicit scopes")
    if any((Path(item["path"]).parts[:1] != ("docs",) or Path(item["path"]).suffix not in {".md", ".json", ".jsonl", ".txt"})
           and item["path"] != "README.md" for item in evidence):
        raise ValueError("evidence must be explicit docs artifacts or README.md, never runtime databases")
    paths = {str(profile_path), "pyproject.toml", "uv.lock", "corpus/seed.jsonl", "corpus/units.db"}
    paths.update(item["path"] for item in evidence)
    for directory in SOURCE_DIRS:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root)
            if any(part in EXCLUDED or part.startswith(".") for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"symlinked snapshot source: {relative}")
            if path.is_file() and path.suffix in EXTENSIONS:
                paths.add(relative.as_posix())
    files = {}
    for path in sorted(paths):
        raw = local_file(root, path).read_bytes()
        files[path] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return dict(schema_version=1, status="experimental", release_ready=False,
                profile_path=str(profile_path), profile=profile,
                inputs_sha256=fingerprint, files=files,
                integrity_scope="local file integrity and declared settings; not proof of host/model enforcement or release acceptance")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="project-relative configuration JSON")
    parser.add_argument("--output", help="new snapshot path; existing files are preserved")
    parser.add_argument("--verify", help="verify an existing snapshot instead of freezing")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.profile or args.output:
                raise ValueError("--verify cannot be combined with --profile/--output")
            saved = json.loads(Path(args.verify).read_bytes())
            if (not isinstance(saved, dict) or not isinstance(saved.get("profile_path"), str)
                    or not isinstance(saved.get("files"), dict)):
                raise ValueError("snapshot has no profile path")
            current = build_snapshot(ROOT, saved["profile_path"])
            if saved != current:
                old = saved.get("files", {})
                changed = sorted(path for path in set(old) | set(current["files"]) if old.get(path) != current["files"].get(path))
                raise ValueError("snapshot differs: " + (", ".join(changed[:10]) or "manifest metadata") )
            print(f"Verified {len(saved['files'])} files; status remains experimental, not release-ready.")
        else:
            if not args.profile or not args.output:
                raise ValueError("--profile and --output are required to freeze")
            snapshot = build_snapshot(ROOT, args.profile)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            # Never rewrite an existing evidence snapshot or an input alias.
            with output.open("x", encoding="utf-8") as file:
                file.write(json.dumps(snapshot, ensure_ascii=False, indent=2)+"\n")
            print(f"Saved {len(snapshot['files'])} file hashes to {output}; experimental, not release-ready.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
