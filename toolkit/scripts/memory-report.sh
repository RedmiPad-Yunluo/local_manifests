#!/usr/bin/env bash
# Read-only host memory diagnostic for wattOS/Debian LineageOS builds.
set -u

printf '\n=== DATE / HOST ===\n'
date -Is
uname -srmo
printf '\n=== MEMORY ===\n'
free -h
printf '\n=== SWAP DEVICES AND PRIORITY ===\n'
/usr/sbin/swapon --show || true
printf '\n=== ZRAM COMPRESSION ===\n'
if command -v zramctl >/dev/null 2>&1; then
    zramctl
elif [ -x /usr/sbin/zramctl ]; then
    /usr/sbin/zramctl
fi
printf '\n=== KERNEL MEMORY SETTINGS ===\n'
for key in vm.swappiness vm.page-cluster vm.overcommit_memory; do
    printf '%s=' "$key"
    sysctl -n "$key" 2>/dev/null || printf 'unavailable\n'
done
printf '\n=== MEMORY PRESSURE ===\n'
if [ -r /proc/pressure/memory ]; then
    cat /proc/pressure/memory
else
    printf 'Not available on this kernel\n'
fi
printf '\n=== SOONG PROCESS ===\n'
ps -C soong_build -o pid,ppid,stat,rss,vsz,%cpu,etime || true
printf '\n=== DISK FREE ===\n'
df -h / "$HOME"
