#!/usr/bin/env python3
"""
build.py — PyInstaller build script for Dodol.

Usage:
    python build.py            # build with default settings
    python build.py --onefile  # single executable
    python build.py --clean    # clean build dirs first

Requires:  pip install pyinstaller
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def clean():
    """Remove PyInstaller build artifacts."""
    for d in ("build", "dist"):
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)
            print(f"Removed {p}/")
    for spec in ROOT.glob("*.spec"):
        spec.unlink()
        print(f"Removed {spec}")


def build(onefile: bool = False):
    """Run PyInstaller with the right flags."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name=Dodol",
        "--windowed",  # no console window on Windows/macOS
        "--add-data=actions:actions",
        "--add-data=core:core",
        "--add-data=memory:memory",
        "--add-data=plugins:plugins",
        "--add-data=dashboard:dashboard",
        "--add-data=config:config",
        "--hidden-import=google.genai",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtMultimedia",
        "--hidden-import=PyQt6.QtSvg",
        "--hidden-import=uvicorn",
        "--hidden-import=fastapi",
        "--hidden-import=websockets",
        "--hidden-import=PIL",
        "--hidden-import=pyautogui",
        "--hidden-import=psutil",
        "--hidden-import=pyaudio",
        "--hidden-import=speech_recognition",
        "--hidden-import=pyttsx3",
        "--hidden-import=pystray",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Entry point
    cmd.append("main.py")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print("\n✓ Build complete!")
        if onefile:
            out = ROOT / "dist" / "Dodol"
            if sys.platform == "win32":
                out = out.with_suffix(".exe")
            print(f"  Output: {out}")
        else:
            print(f"  Output: {ROOT / 'dist' / 'Dodol'}/")
    else:
        print("\n✗ Build failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Build Dodol with PyInstaller")
    parser.add_argument("--onefile", action="store_true", help="Build as single executable")
    parser.add_argument("--clean", action="store_true", help="Clean build dirs first")
    args = parser.parse_args()

    if args.clean:
        clean()

    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
