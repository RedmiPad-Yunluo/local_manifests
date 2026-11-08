# Redmi Pad (yunluo) — LineageOS 24.0 local manifest

Canonical source manifest for the unofficial Android 17 / LineageOS 24.0 project under **RedmiPad-Yunluo**.

- `mt6789.xml` syncs organization device/vendor/MediaTek source on `main`, with LineageOS hardware/xiaomi on `lineage-24.0`.
- `post-sync.py` and `toolkit/scripts/apply-known-fixes.py` maintain known build fixes.
- Fixes include vendor SELinux genfscon/neverallow issues, PowerOffAlarm's generated kernel header conflict, and the external libjxl / dng_sdk vendor-variant Soong issues, plus prior device/vendor bring-up fixes.
- The helper also backports the earlier AOSP Android 17 FCM 6 compatibility matrix into `hardware/interfaces/compatibility_matrices` for the legacy `5.10-android12` kernel (using a pinned AOSP Android tag). This is an experimental compatibility backport, not current official support, and still requires a successful VINTF check.

## Fresh builds

Use the manifest by copying `mt6789.xml` into `.repo/local_manifests/` **before** syncing. On repo versions with `post-sync` hook support (introduced in 2025, newer than the 2.36 launcher), `repo sync` can run the fix script automatically after you explicitly approve the hook once. Older versions ignore this hook; do not assume a clean checkout is patched just because sync succeeded.

The same script can be run explicitly before building on any version:

```bash
python3 tools/yunluo-build-fixes/toolkit/scripts/apply-known-fixes.py --root . --apply
```

The helper is idempotent for its supported source layouts: already-fixed inputs are left unchanged, backups are written beneath `out/lineage-source-fix-backups/`, and unexpected source layouts cause an error. Review `git diff` after a patch. The automatic hook's failures are warnings from repo, so verify the output.

**Do not run repo sync or apply patches during an ongoing build.** These source changes have passed Soong in one local build, which does not prove the complete ROM builds, boots, or is ready for release.

See [toolkit documentation](toolkit/README.md) for details.
