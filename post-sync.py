#!/usr/bin/env python3
"""Apply the Redmi Pad LineageOS 24.0 source compatibility fixes after repo sync.

Repo asks users for hook approval. This runs only after successful syncs on
repo versions that support post-sync (introduced after repo 2.36).
"""
from pathlib import Path
import subprocess
import sys


def main(repo_topdir=None, **kwargs):
    if not repo_topdir:
        raise RuntimeError("Missing repository root; cannot apply yunluo fixes")
    root = Path(repo_topdir).resolve()
    script = Path(__file__).resolve().parent / "toolkit/scripts/apply-known-fixes.py"
    if not script.is_file():
        raise RuntimeError(f"Missing yunluo fix script: {script}")
    print("RedmiPad-Yunluo: validating and applying build fixes after sync")
    subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--apply"],
        check=True,
    )
