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



def patch_libjxl(content):
    # libjxl's dependencies do not provide vendor variants in lineage-24.0.
    return replace_once(
        content,
        '    name: "libjxl",\n    host_supported: true,\n    vendor_available: true,\n',
        '    name: "libjxl",\n    host_supported: true,\n',
        "libjxl unsupported vendor variant",
    )


def patch_dng_sdk(content):
    # DNG SDK's libjxl and xmp_toolkit_sdk dependencies are platform-only.
    return replace_once(
        content,
        '    name: "libdng_sdk",\n    host_supported: true,\n'
        '    defaults: ["libdng_sdk-defaults"],\n    vendor_available: true,\n',
        '    name: "libdng_sdk",\n    host_supported: true,\n'
        '    defaults: ["libdng_sdk-defaults"],\n',
        "libdng_sdk unsupported vendor variant",
    )


def patch_poweroffalarm(content):
    # The generated kernel linux/sched/types.h clashes with Bionic sched.h.
    # The PowerOffAlarm C++ sources only need the normal Bionic UAPI headers.
    return replace_once(
        content,
        '        "libbase_headers",\n        "generated_kernel_headers",\n',
        '        "libbase_headers",\n',
        "PowerOffAlarm duplicate sched_param declaration",
    )


def comment_exact_rule(content, rule, label, pattern=None):
    import re
    lines = content.splitlines(keepends=True)
    hits = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if (re.fullmatch(pattern, stripped) if pattern else stripped == rule):
            hits.append(index)
    if len(hits) > 1:
        raise LayoutError(f"{label}: multiple active rules found")
    if hits:
        index = hits[0]
        lines[index] = "# " + lines[index]
    return "".join(lines)


def patch_genfs_contexts(content):
    content = comment_exact_rule(
        content,
        "genfscon proc /sys/vm/dirty_writeback_centisecs u:object_r:proc_dirty:s0",
        "duplicate proc dirty_writeback_centisecs",
    )
    return comment_exact_rule(
        content,
        "",
        "conflicting sysfs /class/typec label",
        r"genfscon\s+sysfs\s+/class/typec\s+u:object_r:sysfs_usb_nonplat:s0",
    )


def patch_system_server_te(content):
    return comment_exact_rule(
        content,
        "allow system_server self:capability sys_module;",
        "system_server forbidden sys_module capability",
    )



# Compatibility backport: Android 17 used to ship an FCM 6 matrix for
# Android 12-launch devices. This is NOT official support on current QPRs.
FCM_RELATIVE_PATH = "hardware/interfaces/compatibility_matrices/compatibility_matrix.6.android17.xml"
FCM_AOSP_URL = (
    "https://android.googlesource.com/platform/hardware/interfaces/+/"
    "refs/tags/android-16.0.0_r4/compatibility_matrices/"
    "compatibility_matrix.6.android17.xml?format=TEXT"
)


def patch_fcm_bp(content):
    name = "framework_compatibility_matrix.6.android17.xml"
    key = f'    name: "{name}",'
    anchor = "SYSTEM_MATRIX_DEPS_A17 = [\n"
    entry = f'    "{name}",\n'
    if content.count(anchor) != 1:
        raise LayoutError("Android 17 FCM list missing or changed")
    # Only add the missing Android 17 dependency, not Android 18's.
    start = content.index(anchor) + len(anchor)
    end = content.find("]", start)
    if end == -1:
        raise LayoutError("Unterminated Android 17 FCM list")
    list_part = content[start:end]
    if entry not in list_part:
        content = content[:start] + entry + content[start:]
    if content.count(key) > 1:
        raise LayoutError("Duplicate Android 17 FCM 6 module definitions")
    module = (
        'vintf_compatibility_matrix {\n'
        f'{key}\n'
        '    stem: "compatibility_matrix.6.android17.xml",\n'
        '    srcs: ["compatibility_matrix.6.android17.xml"],\n'
        '    kernel_configs: [\n'
        '        "kernel_config_s_4.19",\n'
        '        "kernel_config_s_5.4",\n'
        '        "kernel_config_s_5.10",\n'
        '    ],\n'
        '}\n\n'
    )
    if key not in content:
        # Keep it with the other generated framework compatibility modules.
        next_module = (
            'vintf_compatibility_matrix {\n'
            '    name: "framework_compatibility_matrix.7.xml",'
        )
        if content.count(next_module) != 1:
            raise LayoutError("Cannot locate FCM 7 module insertion point")
        content = content.replace(next_module, module + next_module, 1)
    elif 'stem: "compatibility_matrix.6.android17.xml"' not in content:
        raise LayoutError("FCM 6 Android 17 module has an unexpected definition")
    return content


def fetch_legacy_fcm_xml():
    import base64
    import urllib.request
    import xml.etree.ElementTree as ET

    try:
        with urllib.request.urlopen(FCM_AOSP_URL, timeout=30) as response:
            encoded = response.read(262144)
        data = base64.b64decode(encoded, validate=True)
        root = ET.fromstring(data)
    except Exception as exc:
        raise LayoutError(f"Cannot fetch/parse pinned AOSP FCM 6 matrix: {exc}")
    if root.tag != "compatibility-matrix" or root.get("type") != "framework":
        raise LayoutError("Downloaded AOSP matrix is not a framework matrix")
    if root.get("level") != "6":
        raise LayoutError("Downloaded AOSP matrix does not declare FCM 6")
    return data.decode("utf-8")


FIXES = {
    "hardware/mediatek/Android.bp": patch_hardware,
    "hardware/mediatek/PowerOffAlarm/Android.bp": patch_poweroffalarm,
    "hardware/interfaces/compatibility_matrices/Android.bp": patch_fcm_bp,
    "external/libjxl/Android.bp": patch_libjxl,
    "external/dng_sdk/Android.bp": patch_dng_sdk,
    "device/mediatek/sepolicy_vndr/basic/non_plat/genfs_contexts": patch_genfs_contexts,
    "device/mediatek/sepolicy_vndr/basic/non_plat/system_server.te": patch_system_server_te,
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

    # Preserve fresh-checkout compatibility: the AOSP matrix is intentionally
    # downloaded from a pinned Android source tag rather than reproduced here.
    fcm_file = root / FCM_RELATIVE_PATH
    if fcm_file.is_file():
        import xml.etree.ElementTree as ET
        try:
            xml_root = ET.parse(fcm_file).getroot()
        except ET.ParseError as exc:
            raise LayoutError(f"Invalid existing legacy FCM XML: {exc}")
        if (xml_root.tag != "compatibility-matrix"
                or xml_root.get("type") != "framework"
                or xml_root.get("level") != "6"):
            raise LayoutError("Existing legacy FCM XML has unexpected contents")
        print(f"OK       {FCM_RELATIVE_PATH} (already present)")
    else:
        print(f"FETCH    {FCM_RELATIVE_PATH} (AOSP android-16.0.0_r4)")
        if args.apply:
            changes[FCM_RELATIVE_PATH] = (None, fetch_legacy_fcm_xml())

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
        if (root / name).is_file():
            shutil.copy2(root / name, dest)
    for name, (_, after) in changes.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
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
