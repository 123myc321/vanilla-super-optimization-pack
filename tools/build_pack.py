#!/usr/bin/env python3
"""Build pack.json and the .mrpack for the Vanilla Super Optimization Pack.

Sources: tools/mod-sources.json (curated list)
Outputs: pack.json, docs/mod-versions.md, <name>-<version>.mrpack

Only metadata and hashes are stored in git; jars are downloaded from the
official Modrinth CDN at install time, which keeps redistribution clean.

Usage:
    python tools/build_pack.py                # metadata only
    python tools/build_pack.py --download     # also download + verify jars
    python tools/build_pack.py --mrpack       # also build the .mrpack
    python tools/build_pack.py --all
"""

import argparse
import concurrent.futures
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

API = "https://api.modrinth.com/v2"
UA = "vanilla-super-optimization-pack/1.0 (pack builder)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PACK_NAME = "Vanilla Super Optimization Pack"
PACK_VERSION = "1.0.0"
PACK_SUMMARY = (
    "面向 Minecraft 26.2 / Fabric 的全面性能整合包：客户端渲染与服务端逻辑双侧优化，"
    "提供 full（极限性能）与 strict（机制安全）两套配置。"
)

CHANNEL_RANK = {"release": 3, "beta": 2, "alpha": 1}

# Required dependencies are pulled in automatically. These ids never need a jar.
IGNORED_DEP_PROJECTS = {
    "minecraft",
    "fabricloader",
    "fabric-loader",
    "java",
    "quilt_loader",
    "quilt-loader",
}


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def project(slug):
    return http_json(f"{API}/project/{urllib.parse.quote(slug)}")


def versions_for(slug, mc, loader="fabric"):
    q = urllib.parse.urlencode(
        {"game_versions": json.dumps([mc]), "loaders": json.dumps([loader])}
    )
    data = http_json(f"{API}/project/{urllib.parse.quote(slug)}/version?{q}")
    return [v for v in data if v.get("files")]


def pick_version(versions):
    """Prefer newest release, then newest beta, then newest alpha."""
    if not versions:
        return None
    return max(
        versions,
        key=lambda v: (
            CHANNEL_RANK.get(v.get("version_type"), 0),
            v.get("date_published", ""),
        ),
    )


def primary_file(version):
    for f in version["files"]:
        if f.get("primary"):
            return f
    return version["files"][0]


def side_map(proj):
    def m(v):
        return "unsupported" if v == "unsupported" else "required"

    return {"client": m(proj["client_side"]), "server": m(proj["server_side"])}


def fetch_entry(slug, profiles, note, mc, force_env=None, pin=None):
    proj = project(slug)
    versions = versions_for(slug, mc)
    if pin:
        versions = [v for v in versions if v["version_number"] == pin]
    ver = pick_version(versions)
    if ver is None:
        raise RuntimeError(f"{slug}: no {mc} fabric version")
    f = primary_file(ver)
    if "sha512" not in f["hashes"]:
        raise RuntimeError(f"{slug}: file has no sha512")
    env = side_map(proj)
    if force_env:
        env.update(force_env)
    return {
        "slug": slug,
        "title": proj["title"],
        "license": proj["license"]["id"],
        "profiles": sorted(profiles),
        "env": env,
        "version": ver["version_number"],
        "channel": ver["version_type"],
        "published": ver["date_published"][:10],
        "filename": f["filename"],
        "url": f["url"],
        "sha1": f["hashes"].get("sha1", ""),
        "sha512": f["hashes"]["sha512"],
        "size": f["size"],
        "dependencies": ver.get("dependencies", []),
        "note": note,
        "dependency_of": [],
    }


def resolve_dependencies(entries, mc):
    """Add required dependencies (e.g. Fabric API) until the list is closed."""
    by_slug = {e["slug"]: e for e in entries}
    queue = list(entries)
    warnings = []

    while queue:
        parent = queue.pop()
        for dep in parent.get("dependencies", []):
            if dep.get("dependency_type") != "required":
                continue
            pid = dep.get("project_id")
            if not pid or pid in IGNORED_DEP_PROJECTS:
                continue
            try:
                proj = http_json(f"{API}/project/{pid}")
            except Exception as exc:  # noqa: BLE001 - reported to the user
                warnings.append(f"{parent['slug']}: cannot resolve dependency {pid}: {exc}")
                continue
            slug = proj["slug"]
            if slug in IGNORED_DEP_PROJECTS:
                continue

            if slug in by_slug:
                existing = by_slug[slug]
                existing["profiles"] = sorted(set(existing["profiles"]) | set(parent["profiles"]))
                for side in ("client", "server"):
                    if parent["env"][side] != "unsupported":
                        existing["env"][side] = "required"
                if parent["slug"] not in existing["dependency_of"]:
                    existing["dependency_of"].append(parent["slug"])
                continue

            try:
                entry = fetch_entry(slug, set(parent["profiles"]), "自动解析的必需前置", mc)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{parent['slug']}: dependency {slug} unusable: {exc}")
                continue
            entry["env"] = {
                "client": "required" if parent["env"]["client"] != "unsupported" else "unsupported",
                "server": "required" if parent["env"]["server"] != "unsupported" else "unsupported",
            }
            entry["dependency_of"] = [parent["slug"]]
            by_slug[slug] = entry
            entries.append(entry)
            queue.append(entry)

    return entries, warnings


def download_all(entries, mc):
    out = os.path.join(ROOT, "build", "mods")
    os.makedirs(out, exist_ok=True)
    import hashlib

    results = []

    def one(e):
        path = os.path.join(out, e["filename"])
        if os.path.exists(path):
            h = hashlib.sha512(open(path, "rb").read()).hexdigest()
            if h == e["sha512"]:
                return e["filename"], "cached", e["size"]
        last = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(e["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = r.read()
                h = hashlib.sha512(data).hexdigest()
                if h != e["sha512"]:
                    return e["filename"], "HASH MISMATCH", len(data)
                with open(path, "wb") as fh:
                    fh.write(data)
                return e["filename"], "downloaded", len(data)
            except Exception as exc:  # noqa: BLE001 - retried below
                last = exc
                import time

                time.sleep(1.5 * (attempt + 1))
        return e["filename"], f"FAILED: {last}", 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name, status, size in pool.map(one, entries):
            results.append((name, status, size))

    ok = all(s in ("cached", "downloaded") for _, s, _ in results)
    for name, status, size in sorted(results):
        print(f"  {status:12s} {size:>9,d}  {name}")
    return ok, out


def build_mrpack(entries, mc, loader, out_path):
    overrides_root = os.path.join(ROOT, "configs", "full")
    index = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": PACK_VERSION,
        "name": PACK_NAME,
        "summary": PACK_SUMMARY,
        "files": [],
        "dependencies": {"minecraft": mc, "fabric-loader": loader},
    }
    for e in entries:
        index["files"].append(
            {
                "path": f"mods/{e['filename']}",
                "hashes": {"sha1": e["sha1"], "sha512": e["sha512"]},
                "env": e["env"],
                "downloads": [e["url"]],
                "fileSize": e["size"],
            }
        )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("modrinth.index.json", json.dumps(index, ensure_ascii=False, indent=2))
        for sub in ("common", "client", "server"):
            base_dir = os.path.join(overrides_root, sub)
            for base, _, files in os.walk(base_dir):
                for fn in files:
                    full = os.path.join(base, fn)
                    rel = os.path.relpath(full, base_dir).replace("\\", "/")
                    z.write(full, "overrides/" + rel)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="download and verify every jar")
    ap.add_argument("--mrpack", action="store_true", help="build the .mrpack")
    ap.add_argument("--all", action="store_true", help="download + mrpack")
    args = ap.parse_args()

    src_path = os.path.join(ROOT, "tools", "mod-sources.json")
    with open(src_path, encoding="utf-8") as fh:
        src = json.load(fh)
    mc = src["minecraft"]

    entries = []
    warnings = []
    for item in src["mods"]:
        entry = fetch_entry(
            item["slug"], set(item["profiles"]), item.get("note", ""), mc,
            force_env=item.get("force_env"), pin=item.get("version"),
        )
        entries.append(entry)

    entries, dep_warnings = resolve_dependencies(entries, mc)
    warnings.extend(dep_warnings)
    entries.sort(key=lambda e: (e["title"].lower(), e["slug"]))

    pack = {
        "name": PACK_NAME,
        "version": PACK_VERSION,
        "minecraft": mc,
        "fabricLoader": src["fabricLoader"],
        "java": src["java"],
        "summary": PACK_SUMMARY,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profiles": {
            "full": "极限性能：包含会改变原版机制的优化项（激活范围、TT20、出生点区块、树叶衰减等）。",
            "strict": "机制安全：只保留不改变红石/流体/刷怪/爆炸/tick 顺序的优化项。",
        },
        "mods": entries,
    }

    with open(os.path.join(ROOT, "pack.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    lines = [
        "# 版本清单",
        "",
        f"由 `tools/build_pack.py` 自动生成，对应 Minecraft {mc} / Fabric {src['fabricLoader']} / Java {src['java']}。",
        "",
        "| Mod | 版本 | 通道 | 侧 | 配置 | 许可证 | 文件 |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        side = "/".join(
            s for s in ("client", "server") if e["env"][s] != "unsupported"
        ) or "-"
        lines.append(
            f"| [{e['title']}](https://modrinth.com/mod/{e['slug']}) | {e['version']} "
            f"| {e['channel']} | {side} | {'/'.join(e['profiles'])} | {e['license']} | `{e['filename']}` |"
        )
    lines.append("")
    if warnings:
        lines.append("## 依赖警告")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    with open(os.path.join(ROOT, "docs", "mod-versions.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))

    print(f"pack.json: {len(entries)} mods")
    for e in entries:
        req = f" (前置: {', '.join(e['dependency_of'])})" if e["dependency_of"] else ""
        print(f"  {e['slug']:22s} {e['version']:28s} {e['channel']:7s} "
              f"{e['env']['client'][:3]}/{e['env']['server'][:3]}  {'/'.join(e['profiles'])}{req}")
    for w in warnings:
        print("WARN:", w, file=sys.stderr)

    ok = True
    if args.download or args.all:
        print("downloading jars ...")
        ok, _ = download_all(entries, mc)
        if not ok:
            print("ERROR: some jars failed verification", file=sys.stderr)

    if args.mrpack or args.all:
        out = os.path.join(ROOT, f"vanilla-super-optimization-{PACK_VERSION}-fabric{mc}.mrpack")
        build_mrpack(entries, mc, src["fabricLoader"], out)
        print("mrpack:", out)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
