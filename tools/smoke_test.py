#!/usr/bin/env python3
"""End-to-end smoke test for the server side of the pack.

Copies a Fabric server's launcher + libraries into a scratch directory,
installs the selected profile, boots the server on a fresh world, waits for
"Done", sends `stop` over RCON and checks for a clean exit.

Requirements: Java 25 on PATH (or --java), a Fabric server directory that
already has server.jar + libraries.

Usage:
    python tools/smoke_test.py --server-src "D:\\servers\\mc-src" --profile full
    python tools/smoke_test.py --server-src . --profile strict --java "C:\\Java\\bin\\java.exe"

The source directory is never modified.
"""

import argparse
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RCON_PORT = 25575
RCON_PASS = "smoketest"


def prepare(src, test, pack, profile):
    os.makedirs(os.path.join(test, "mods"), exist_ok=True)
    shutil.copy2(os.path.join(src, "server.jar"), test)
    shutil.copytree(os.path.join(src, "libraries"), os.path.join(test, "libraries"))
    with open(os.path.join(test, "eula.txt"), "w") as fh:
        fh.write("eula=true\n")
    with open(os.path.join(test, "server.properties"), "w") as fh:
        fh.write(
            "level-name=world\n"
            "level-seed=424242\n"
            "online-mode=false\n"
            "view-distance=6\n"
            "simulation-distance=4\n"
            "max-players=2\n"
            "enable-rcon=true\n"
            f"rcon.port={RCON_PORT}\n"
            f"rcon.password={RCON_PASS}\n"
            "sync-chunk-writes=false\n"
            "max-auto-save-chunks-per-tick=8\n"
            "spawn-protection=0\n"
            "motd=pack smoke test\n"
            "enforce-secure-profile=false\n"
        )
    cache = os.path.join(ROOT, "build", "mods")
    for entry in pack["mods"]:
        if entry["env"]["server"] == "unsupported" or profile not in entry["profiles"]:
            continue
        cached = os.path.join(cache, entry["filename"])
        if os.path.exists(cached):
            shutil.copy2(cached, os.path.join(test, "mods", entry["filename"]))


def rcon(command):
    with socket.create_connection(("127.0.0.1", RCON_PORT), timeout=15) as s:
        def send(rid, typ, body):
            payload = struct.pack("<ii", rid, typ) + body.encode("utf8") + b"\x00\x00"
            s.sendall(struct.pack("<i", len(payload)) + payload)

        def recv():
            raw = s.recv(4)
            if len(raw) < 4:
                return None, None, ""
            (length,) = struct.unpack("<i", raw)
            data = b""
            while len(data) < length:
                data += s.recv(length - len(data))
            rid, typ = struct.unpack("<ii", data[:8])
            return rid, typ, data[8:-2].decode("utf8", "replace")

        send(1, 3, RCON_PASS)
        recv()
        send(2, 2, command)
        return recv()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-src", required=True,
                    help="Fabric server directory containing server.jar and libraries/")
    ap.add_argument("--profile", choices=["full", "strict"], default="full")
    ap.add_argument("--dir", default=os.path.join(tempfile.gettempdir(), "vsop-smoke"))
    ap.add_argument("--java", default="java")
    ap.add_argument("--memory", default="2G")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    src = os.path.abspath(args.server_src)
    for required in ("server.jar", "libraries"):
        if not os.path.exists(os.path.join(src, required)):
            print(f"error: {required} not found under {src}", file=sys.stderr)
            return 2

    test = os.path.abspath(args.dir)
    if os.path.exists(test):
        shutil.rmtree(test)
    os.makedirs(test)

    with open(os.path.join(ROOT, "pack.json"), encoding="utf-8") as fh:
        pack = json.load(fh)
    prepare(src, test, pack, args.profile)

    subprocess.run(
        [sys.executable, os.path.join(ROOT, "install.py"), "--side", "server",
         "--profile", args.profile, "--dir", test],
        check=True,
    )

    log_path = os.path.join(test, "console.log")
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(
            [args.java, f"-Xms{args.memory}", f"-Xmx{args.memory}",
             "-XX:+UseG1GC", "-Djava.awt.headless=true", "-jar", "server.jar", "nogui"],
            cwd=test, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        done = threading.Event()

        def pump():
            for line in proc.stdout:
                log.write(line)
                log.flush()
                if "Done (" in line:
                    done.set()

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()

        started = done.wait(timeout=args.timeout)
        print("reached Done:", started)
        if started:
            time.sleep(3)
            try:
                print("rcon stop:", rcon("stop"))
            except Exception as exc:  # noqa: BLE001
                print("rcon failed:", exc)
        else:
            proc.kill()
        try:
            proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        reader.join(timeout=10)

    lines = open(log_path, encoding="utf-8", errors="replace").read().splitlines()
    fatal = [ln for ln in lines if any(k in ln for k in (
        "Mod resolution failed", "Incompatible mods", "Missing or unsupported",
        "A potential solution", "[main/ERROR]",
    ))]
    print("\n--- last 20 lines ---")
    for ln in lines[-20:]:
        print(ln)
    if fatal:
        print("\n--- fatal ---")
        for ln in fatal[-30:]:
            print(ln)
    print("\nexit code:", proc.returncode)
    ok = started and proc.returncode == 0 and not fatal
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
