# Redmi Pad (yunluo) — LineageOS 24.0 build fixes

Bundled in the organization's `local_manifests/toolkit/` directory because there is not yet a standalone organization toolkit repository.

Reusable notes and opt-in helpers for the **unofficial Android 17 / LineageOS 24.0** bring-up on Xiaomi Redmi Pad (yunluo).

**Status:** work in progress, not a boot-tested ROM or a guarantee that the build will finish.

## Source of truth

The actual fixes have already been committed to these repositories on branch main:

- [Device tree](https://github.com/RedmiPad-Yunluo/android_device_xiaomi_yunluo)
- [Vendor blobs](https://github.com/RedmiPad-Yunluo/android_vendor_xiaomi_yunluo)
- [MediaTek hardware](https://github.com/RedmiPad-Yunluo/android_hardware_mediatek)
- [Manifest](https://github.com/RedmiPad-Yunluo/local_manifests)

This toolkit directory is a **reproducible backup/checklist** of the fixes, not a separate replacement for those upstream trees.

## Fixes recorded

1. Remove missing hardware/lineage/compat Soong namespace from vendor Android.bp.
2. Expose hardware/google/pixel/usb and hardware/google/pixel/pixelstats to MediaTek Soong.
3. Rename MediaTek proprietary libformatter module to libformatter_mtk (preserve installed filename with stem: "libformatter"); update codec2 dependencies and vendor package list.
4. Remove absent vendor/lineage/config/device_framework_matrix.xml from the device framework matrix list.
5. Declare lineage_health.charging_control_supports_bypass using soong_config_set_bool, not a string setter.
6. Export hardware/google/pixel/power-libperfmgr through PRODUCT_SOONG_NAMESPACES so the existing Pixel power HAL resolves.
7. Avoid the vendor/lib64/libmnl.so duplicate install rule by removing its VENDOR_PLATFORM_LINKS symlink entry in device/xiaomi/yunluo/Android.mk. Keep the actual Soong-installed module.
8. Use a local manifest pointing to RedmiPad-Yunluo sources on main and LineageOS hardware/xiaomi on lineage-24.0.

See [fix history](docs/fix-history.md) for failures, locations, and scope.

## Use on a future fresh checkout

For a source directory such as ~/android/lineage, first sync the [organization manifest](https://github.com/RedmiPad-Yunluo/local_manifests/blob/main/mt6789.xml). The organization device/vendor/MediaTek repositories include the previously committed fixes. External-project edits are handled by the fix script.

Clone the organization manifest repository to a separate helper directory (without changing a running build), then inspect what (if anything) needs patching:

~~~bash
git clone https://github.com/RedmiPad-Yunluo/local_manifests.git ~/yunluo_manifests_toolkit
python3 ~/yunluo_manifests_toolkit/toolkit/scripts/apply-known-fixes.py --root ~/android/lineage
~~~

To apply only if the dry-run explicitly reports expected older source patterns:

~~~bash
python3 ~/yunluo_manifests_toolkit/toolkit/scripts/apply-known-fixes.py --root ~/android/lineage --apply
~~~

The helper validates all targeted files before changing any; it refuses unexpected layouts and backs up modified files under out/lineage-source-fix-backups/. It does **not** edit build/soong or run repo sync, make clean, or the build itself.

Newer repo clients support the manifest's optional `post-sync` hook, which invokes this helper automatically after user approval. Older repo clients such as the previously reported 2.36 require running the command above explicitly. **Do not sync or apply fixes while a build is running.**

## Host memory

See [memory and swap](docs/memory-and-swap.md). Our wattOS R13 test system has 16 GiB-class physical RAM, 8 GiB ZRAM (zstd, priority 100), and two 32 GiB NVMe swapfiles (priorities -2 and -3). This has shown severe memory stalls in Soong. Trying 16 GiB ZRAM is a **test**, not a confirmed fix. Never run swapoff -a while building or under high swap usage.

## Experimental or unproven changes

- Local build/soong/cmd/soong_build/main.go tweak: runtime/debug.SetGCPercent(40) and SetMemoryLimit(12 << 30). **Not a validated optimization; not applied by this helper**. It may increase garbage-collection overhead and slow a memory-heavy build. Prefer stock Soong for reliable A/B testing.
- External `libjxl` and `libdng_sdk` `vendor_available` removals are now included in the guarded helper because the November 7 local build passed Soong after those edits. The helper also handles `PowerOffAlarm` headers and the three MediaTek SELinux rules. This is not yet a complete-build or runtime validation, so reconfirm on future Android updates.
- Compilation passed Soong Android.bp analysis and then exposed Make/module errors. Passing bootstrap does not imply the ROM boots.

## Safety

Never apply this helper to a different device, release branch, or changed source layout without reviewing diffs. Do not flash an untested build solely because compilation succeeds.
