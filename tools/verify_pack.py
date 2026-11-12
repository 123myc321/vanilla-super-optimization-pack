#!/usr/bin/env python3
"""Static sanity checks for a built pack.

Checks every jar in build/mods (or --dir):
  * zip integrity
  * fabric.mod.json present and parseable
  * unique mod id
  * declared Minecraft version range plausibly covers the pack version
  * every required mod dependency resolves inside the same mods folder
  * client-only / server-only entries have the environment flag they claim
"""

import argparse
import io
import json
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORED = {"minecraft", "fabricloader", "fabric", "java", "quilt_loader", "forge"}


def _cmp(a, b):
    """Compare dotted numeric versions, padding missing segments with zeros."""
    pa = [int(x) for x in re.findall(r"\d+", a)[:3]]
    pb = [int(x) for x in re.findall(r"\d+", b)[:3]]
    while len(pa) < 3:
        pa.append(0)
    while len(pb) < 3:
        pb.append(0)
    return (pa > pb) - (pa < pb)


def covers_mc(spec, mc):
    if not spec:
        return True
    spec = spec.strip()
    if spec in ("*", "any"):
        return True
    # Fabric convention: a trailing '-' widens the range to include pre-releases.
    spec = re.sub(r"(?<=[0-9A-Za-z])-(?=$|\s)", "", spec)
    for part in [p for p in re.split(r"[\s,]+", spec) if p]:
        if part in ("*", "any"):
            continue
        if part.endswith(".x"):
            base = part[:-2]
            if not (mc == base or mc.startswith(base + ".")):
                return False
            continue
        m = re.match(r"^(>=|<=|>|<|=|~|\^)?\s*([0-9][0-9a-zA-Z.\-+]*)$", part)
        if not m:
            continue
        op, ver = m.group(1) or "=", m.group(2)
        c = _cmp(mc, ver)
        if op == "=" and not (c == 0 or mc.startswith(ver + ".")):
            return False
        if op == ">=" and c < 0:
            return False
        if op == ">" and c <= 0:
            return False
        if op == "<=" and c > 0:
            return False
        if op == "<" and c >= 0:
            return False
        if op == "~" and not (c == 0 or mc.startswith(ver.rsplit(".", 1)[0] + ".")):
            return False
    return True


def nested_ids(z):
    """Mod ids provided by jars nested inside a jar (JiJ)."""
    out = set()
    for name in z.namelist():
        if not name.endswith(".jar"):
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                raw = inner.read("fabric.mod.json")
            out.add(json.loads(raw.decode("utf-8-sig")).get("id", ""))
        except Exception:  # noqa: BLE001 - non-mod nested jars exist
            continue
    return {i for i in out if i}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, "build", "mods"))
    ap.add_argument("--pack", default=os.path.join(ROOT, "pack.json"))
    args = ap.parse_args()

    with open(args.pack, encoding="utf-8") as fh:
        pack = json.load(fh)
    mc = pack["minecraft"]

    meta = {}
    problems = []
    ids = {}
    provided = set()
    for entry in pack["mods"]:
        path = os.path.join(args.dir, entry["filename"])
        if not os.path.exists(path):
            problems.append(f"missing file: {entry['filename']}")
            continue
        try:
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()
                if bad:
                    problems.append(f"{entry['filename']}: corrupt entry {bad}")
                raw = z.read("fabric.mod.json")
                provided |= nested_ids(z)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{entry['filename']}: {exc}")
            continue
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{entry['filename']}: bad fabric.mod.json: {exc}")
            continue
        mid = data.get("id", "?")
        meta[mid] = data
        provided.add(mid)
        if mid in ids:
            problems.append(f"duplicate mod id {mid}: {ids[mid]} + {entry['filename']}")
        ids[mid] = entry["filename"]
        dep = data.get("depends", {})
        if "minecraft" in dep and not covers_mc(dep["minecraft"], mc):
            problems.append(f"{mid}: declares minecraft {dep['minecraft']!r}, pack is {mc}")
        if data.get("environment") == "client" and entry["env"]["server"] != "unsupported":
            problems.append(f"{mid}: client-only jar but env.server={entry['env']['server']}")
        if data.get("environment") == "server" and entry["env"]["client"] != "unsupported":
            problems.append(f"{mid}: server-only jar but env.client={entry['env']['client']}")

    for mid, data in meta.items():
        for dep_name in data.get("depends", {}):
            if dep_name in IGNORED:
                continue
            if dep_name not in provided:
                problems.append(f"{mid}: required dependency '{dep_name}' is not in the pack")

    print(f"checked {len(meta)} mods / {len(pack['mods'])} files for Minecraft {mc}")
    for mid in sorted(meta):
        d = meta[mid]
        print(f"  {mid:24s} {d.get('version','?'):28s} env={d.get('environment','*'):7s} "
              f"mc={d.get('depends',{}).get('minecraft','*')}")
    if problems:
        print("\nPROBLEMS")
        for p in problems:
            print(" -", p)
        return 1
    print("\nOK: no problems found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
