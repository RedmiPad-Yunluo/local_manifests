#!/usr/bin/env python3
"""Read-only preflight for yunluo's vendor symlinks vs generated Soong install targets.

This reports *possible* duplicate installation rules. It never edits source files.
Review matches manually before removing a symlink.
"""
from pathlib import Path
import argparse
import re
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path.cwd())
args = parser.parse_args()
root = args.root.expanduser().resolve()
device = root / "device/xiaomi/yunluo/Android.mk"
soong = root / "out/soong/installs-lineage_yunluo.mk"

for f in (device, soong):
    if not f.is_file():
        sys.exit(f"Missing {f}; run after a Soong bootstrap has generated install rules.")

device_lines = device.read_text(encoding="utf-8").splitlines()
soong_lines = soong.read_text(encoding="utf-8", errors="replace").splitlines()

# Match the device's explicit vendor symlink targets (including all device-side
# lists, without following or modifying any of the symlinks).
symlinks = {}
for n, line in enumerate(device_lines, start=1):
    match = re.search(r"\$\(TARGET_OUT_VENDOR\)/([^\s\\]+)", line)
    if match:
        target = f"out/target/product/yunluo/vendor/{match.group(1)}"
        symlinks[target] = n

# Soong install file usually uses literal build-output targets.
# Limit matching to make rule left-hand sides, not arbitrary prerequisites.
rules = {}
for n, line in enumerate(soong_lines, start=1):
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        continue
    lhs = stripped.split(":", 1)[0].strip()
    if lhs in symlinks:
        rules.setdefault(lhs, []).append(n)

print(f"Device explicit vendor symlink entries: {len(symlinks)}")
print(f"Potential conflicts with Soong installed targets: {len(rules)}")
for path, mk_lines in sorted(rules.items()):
    print(f"  {path}   [device Android.mk:{symlinks[path]}, Soong installs:{','.join(map(str, mk_lines))}]")
if rules:
    print("\nReview every conflict. Do not automatically delete library files or symlink rules.")
else:
    print("No literal-target collisions detected. This is not proof of a clean Kati build.")
