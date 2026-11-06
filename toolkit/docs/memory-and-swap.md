# wattOS R13 (Debian 12): memory and swap notes

Host used for tests: i3-12100, ~15.4 GiB available physical RAM, 1 TB ext4 SATA SSD mounted as /home, 240 GB NVMe system volume, 32 GiB + 32 GiB NVMe swapfiles, and 8 GiB zram (zstd, priority 100).

This is for troubleshooting, **not** a guarantee that a 16 GB PC can reliably finish Android 17/LineageOS 24.0.

## What the observed numbers mean

- ZRAM's DISKSIZE is logical swap capacity, **not** additional RAM or preallocated physical RAM.
- A screenshot showed approximately 8 GiB of data compressed to <1 GiB of physical ZRAM storage, which makes a 16 GiB ZRAM test reasonable for *this* workload.
- Heavy memory stalls, high io-wait and growing NVMe swap indicate thrashing. Adding disk swap can prevent immediate out-of-memory failures, but cannot make a 16 GB machine as fast as one with more RAM.
- The combined swap *capacity* (e.g., 71 GiB shown by free -h) does not need to fill. A lower usage value is normal and generally desirable.
- Do **not** use sudo swapoff -a while a build is active or memory is under pressure. Do **not** run make clean to troubleshoot swapping.

## Before touching swap or ZRAM

**Do this only after a build has stopped**, when you can confirm you have sufficient available RAM for any pages moved out of ZRAM:

~~~bash
free -h
/usr/sbin/swapon --show
/usr/sbin/zramctl
ps -C soong_build -o pid,stat,rss,etime
~~~

Do not restart the zram service while Soong is running. Restarting zram can cause long stalls or an OOM if pages cannot be moved safely.

## Optional test: change 8 GiB ZRAM to 16 GiB

Only when idle, with adequate free RAM:

~~~bash
sudo cp -a /etc/default/zramswap /etc/default/zramswap.backup-before-16g
printf 'ALGO=zstd\nSIZE=16384\nPRIORITY=100\n' | sudo tee /etc/default/zramswap
sudo systemctl restart zramswap.service
/usr/sbin/zramctl
/usr/sbin/swapon --show
~~~

Expected: /dev/zram0 has 16G logical size, uses zstd, and priority 100. If restart fails, check systemctl status zramswap.service and revert from the backup. Keep disk swap as overflow. 16 GiB ZRAM may improve swap behavior, but it still uses physical RAM to store compressed pages.

## NVMe swap: why 32 GiB is a reasonable starting point

The system already has:

- /swapfile: 32 GiB, enabled persistently from /etc/fstab
- /swapfile2: 32 GiB, created as *temporary* extra capacity and normally not listed in /etc/fstab

You can test just **32 GiB NVMe disk swap plus 16 GiB ZRAM** if no build is active and /swapfile2 has zero used pages.

First inspect (read-only):

~~~bash
/usr/sbin/swapon --show
grep -n -E 'swapfile' /etc/fstab
df -h /
~~~

If /swapfile2 still has 0 used, no build is active, and you explicitly want to retire that temporary swapfile, it can be disabled independently:

~~~bash
sudo /usr/sbin/swapoff /swapfile2
~~~

After verifying that /swapfile2 is no longer shown by swapon --show, optionally remove that *specific* unused file to reclaim space:

~~~bash
sudo rm -- /swapfile2
~~~

**Never delete an active swapfile.** If /swapfile2 is listed in fstab, remove only that corresponding line before reboot; leave /swapfile intact. If swapoff fails, do not remove it. The persistent /swapfile is left untouched.

An arbitrary 36 GiB swapfile offers no clear advantage over the existing 32 GiB swapfile. Avoid replacing an active one just to achieve a round number.

## Swappiness and build settings

- Current persistent setting: /etc/sysctl.d/99-lineageos-swap.conf with vm.swappiness=80.
- Keep 80 for a controlled A/B test of ZRAM sizes. Once measured, 100-120 can be tested; none is universally optimal.
- Ninja -j1/-j2 limits parallel compile jobs but does not cap a single Soong process.
- GOMEMLIMIT/GOGC exported in the shell were **not visible** in the active soong_build process (it was started with env -i). A temporary source-level runtime/debug experiment was not proven effective.
- Stock Soong source + monitoring is preferable as a baseline when testing ZRAM changes.

Run this read-only report before and during future builds:

~~~bash
bash ~/yunluo_manifests_toolkit/toolkit/scripts/memory-report.sh
~~~
