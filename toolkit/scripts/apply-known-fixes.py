#!/usr/bin/env python3
"""Safely replay known yunluo LineageOS 24.0 source fixes.

Dry-run by default. Only use on the matching imported source tree.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys


class LayoutError(Exception):
    pass


def replace_once(content, old, new, label):
    if old in content:
        if content.count(old) != 1:
            raise LayoutError(f"{label}: expected one original match")
        return content.replace(old, new, 1)
    if new in content:
        return content
    raise LayoutError(f"{label}: neither original nor fixed layout found")


def patch_hardware(content):
    anchor = '        "hardware/google/pixel",\n'
    if content.count(anchor) != 1:
        raise LayoutError("hardware/mediatek: unexpected namespace imports")
    for name in ("usb", "pixelstats"):
        item = f'        "hardware/google/pixel/{name}",\n'
        if item not in content:
            content = content.replace(anchor, anchor + item, 1)
    return content


def patch_boardconfig(content):
    slash = chr(92)
    old = ("    hardware/xiaomi/vintf/xiaomi_framework_compatibility_matrix.xml "
           + slash + "\n    vendor/lineage/config/device_framework_matrix.xml")
    new = "    hardware/xiaomi/vintf/xiaomi_framework_compatibility_matrix.xml"
    content = replace_once(content, old, new, "framework compatibility matrix")
    if "vendor/lineage/config/device_framework_matrix.xml" in content:
        raise LayoutError("old framework matrix reference remains")
    return content


def patch_vendor_bp(content):
    obsolete = '        "hardware/lineage/compat",\n'
    if obsolete in content:
        content = content.replace(obsolete, "", 1)
    if '"hardware/mediatek/libmtkperf_client"' not in content:
        raise LayoutError("vendor Soong namespace layout changed")

    content = replace_once(
        content,
        '    name: "libformatter",\n',
        '    name: "libformatter_mtk",\n    stem: "libformatter",\n',
        "proprietary MediaTek libformatter module",
    )
    old_dep = '                "libformatter",\n'
    new_dep = '                "libformatter_mtk",\n'
    if old_dep in content:
        if content.count(old_dep) != 2:
            raise LayoutError("expected two codec2 libformatter dependencies")
        content = content.replace(old_dep, new_dep)
    elif content.count(new_dep) != 2:
        raise LayoutError("expected two corrected codec2 libformatter dependencies")
    return content


def patch_vendor_mk(content):
    slash = chr(92)
    return replace_once(
        content,
        "    libformatter " + slash + "\n",
        "    libformatter_mtk " + slash + "\n",
        "vendor proprietary package list",
    )


def patch_device_mk(content):
    content = replace_once(
        content,
        "$(call soong_config_set,lineage_health,charging_control_supports_bypass,false)",
        "$(call soong_config_set_bool,lineage_health,charging_control_supports_bypass,false)",
        "Lineage health bypass boolean",
    )
    slash = chr(92)
    content = replace_once(
        content,
        "    hardware/google/pixel\n",
        "    hardware/google/pixel " + slash + "\n"
        "    hardware/google/pixel/power-libperfmgr\n",
        "Pixel power HAL product namespace",
    )
    return content


def patch_device_android_mk(content):
    # A real Soong-installed libmnl.so occupies the same output location;
    # do not also generate a platform symlink at that path.
    name = "$(TARGET_OUT_VENDOR)/lib64/libmnl.so"
    rows = content.splitlines(keepends=True)
    matched = [line for line in rows if line.lstrip().startswith(name)]
    if len(matched) > 1:
        raise LayoutError("duplicate libmnl link entries in Android.mk")
    if matched:
        if not any("VENDOR_PLATFORM_LINKS" in line for line in rows):
            raise LayoutError("vendor symlink list missing")
        rows.remove(matched[0])
        return "".join(rows)
    if name in content:
        raise LayoutError("libmnl reference in unexpected location")
    return content


FIXES = {
    "hardware/mediatek/Android.bp": patch_hardware,
    "device/xiaomi/yunluo/BoardConfig.mk": patch_boardconfig,
    "device/xiaomi/yunluo/Android.mk": patch_device_android_mk,
    "device/xiaomi/yunluo/device.mk": patch_device_mk,
    "vendor/xiaomi/yunluo/Android.bp": patch_vendor_bp,
    "vendor/xiaomi/yunluo/yunluo-vendor.mk": patch_vendor_mk,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="LineageOS checkout root")
    ap.add_argument("--apply", action="store_true", help="Back up and apply known edits")
    args = ap.parse_args()
    root = args.root.expanduser().resolve()
    if not (root / ".repo").is_dir() or not (root / "build/envsetup.sh").is_file():
        raise LayoutError("Not a repo-initialized LineageOS source root")

    # Validate every file and compute all changes BEFORE writing any of them.
    changes = {}
    for name, transformer in FIXES.items():
        path = root / name
        if not path.is_file():
            raise LayoutError(f"Missing required file: {name}")
        before = path.read_text(encoding="utf-8")
        after = transformer(before)
        if before == after:
            print(f"OK       {name} (already fixed)")
        else:
            print(f"PATCH    {name}")
            changes[name] = (before, after)

    if not changes:
        print("All known source fixes already present. No files changed.")
        return 0
    if not args.apply:
        print("Dry-run only. Review the list, then add --apply to save fixes.")
        return 0

    backup = root / "out/lineage-source-fix-backups" / datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%S-%f")
    for name in changes:
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, dest)
    for name, (_, after) in changes.items():
        (root / name).write_text(after, encoding="utf-8")
    print(f"Applied {len(changes)} file patches.")
    print(f"Backups: {backup}")
    print("Review changes with git diff; no build or repo sync was started.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LayoutError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
