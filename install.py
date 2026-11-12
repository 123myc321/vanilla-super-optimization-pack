#!/usr/bin/env python3
"""Install the Vanilla Super Optimization Pack into a Minecraft/Fabric directory.

Examples:
    python install.py --side client --dir "C:\\Users\\<you>\\AppData\\Roaming\\.minecraft"
    python install.py --side server --dir "D:\\servers\\mc" --profile strict
    python install.py --side server --dir . --dry-run

Only jars for the selected side are installed. Every download is verified
against the SHA-512 recorded in pack.json. Existing config files are never
overwritten silently: a `.pack-new` copy is written next to them instead.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = "vanilla-super-optimization-pack/1.0 (installer)"


def load_pack():
    with open(os.path.join(ROOT, "pack.json"), encoding="utf-8") as fh:
        return json.load(fh)


def wanted(entry, side, profile):
    return entry["env"][side] != "unsupported" and profile in entry["profiles"]


def download(entry, dest_dir):
    path = os.path.join(dest_dir, entry["filename"])
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if hashlib.sha512(fh.read()).hexdigest() == entry["sha512"]:
                return "ok", 0
        os.remove(path)

    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(entry["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if hashlib.sha512(data).hexdigest() != entry["sha512"]:
                return "hash mismatch", 0
            with open(path, "wb") as fh:
                fh.write(data)
            return "downloaded", len(data)
        except Exception as exc:  # noqa: BLE001 - retried
            last = exc
            time.sleep(1.5 * (attempt + 1))
    return f"failed: {last}", 0


def copy_configs(profile, side, target_dir, force):
    roots = [
        os.path.join(ROOT, "configs", profile, "common"),
        os.path.join(ROOT, "configs", profile, side),
    ]
    written, unchanged, conflicts = [], [], []
    for src in roots:
        for base, _, files in os.walk(src):
            for fn in files:
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, src)
                dst = os.path.join(target_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.exists(dst) or force:
                    shutil.copy2(full, dst)
                    written.append(rel)
                elif open(dst, "rb").read() == open(full, "rb").read():
                    unchanged.append(rel)
                else:
                    shutil.copy2(full, dst + ".pack-new")
                    conflicts.append(rel + " -> .pack-new")
    return written, unchanged, conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", choices=["client", "server", "both"], default="server")
    ap.add_argument("--profile", choices=["full", "strict"], default="full")
    ap.add_argument("--dir", default=".", help="game or server directory")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-config", action="store_true",
                    help="overwrite existing config files instead of writing .pack-new")
    args = ap.parse_args()

    pack = load_pack()
    if args.side == "both":
        print("error: install client and server separately (their mod sets differ)", file=sys.stderr)
        return 2

    target = os.path.abspath(args.dir)
    mods_dir = os.path.join(target, "mods")
    os.makedirs(mods_dir, exist_ok=True)

    entries = [e for e in pack["mods"] if wanted(e, args.side, args.profile)]
    total = sum(e["size"] for e in entries)
    print(f"pack {pack['version']} | MC {pack['minecraft']} | profile {args.profile} | side {args.side}")
    print(f"target: {target}")
    print(f"{len(entries)} mods, {total / 1048576:.1f} MiB, Java {pack['java']} required\n")

    if args.dry_run:
        for e in sorted(entries, key=lambda x: x["title"].lower()):
            print(f"  would install {e['filename']}")
        print("\ndry run only; nothing changed")
        return 0

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(download, e, mods_dir): e for e in entries}
        for fut in concurrent.futures.as_completed(futures):
            entry = futures[fut]
            status, size = fut.result()
            results.append((entry, status, size))
            print(f"  {status:12s} {entry['filename']}")

    failed = [e for e, s, _ in results if s not in ("ok", "downloaded")]
    print()
    print(f"mods installed: {len(entries) - len(failed)}/{len(entries)}")
    if failed:
        print("failed:", ", ".join(e["filename"] for e in failed), file=sys.stderr)
        print("fix the network and run the same command again; verified files are kept.",
              file=sys.stderr)

    written, unchanged, conflicts = copy_configs(args.profile, args.side, target, args.force_config)
    if written:
        print("configs written:", ", ".join(written))
    if unchanged:
        print(f"configs unchanged: {len(unchanged)}")
    if conflicts:
        print("configs kept (existing file differs, new copy written):")
        for k in conflicts:
            print("  ", k)

    print("\ndone. next:")
    if args.side == "server":
        print("  1. start once, confirm the log has no missing dependency errors")
        print("  2. apply the JVM args from docs/tuning.md")
        print("  3. read docs/mod-selection.md before using full profile on a technical server")
    else:
        print("  1. launch with Fabric " + pack["fabricLoader"] + " and Java " + pack["java"])
        print("  2. set render distance/simulation distance in-game, not by editing jars")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
