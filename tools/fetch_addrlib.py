#!/usr/bin/env python3
"""Fetch the pinned AMD addrlib source used by the optional xg_swizzle_select test.

addrlib is MIT-licensed. Mesa carries it under src/amd/addrlib, with a 64-bit type definition for MSVC
(_WIN32) that the GPUOpen PAL copy lacks. This script makes a shallow, sparse, blob-filtered fetch of that
one directory at the Mesa 25.1.0 commit under out/deps/mesa (gitignored) and prints the path to pass as
XBOX2WINDOWS_ADDRLIB_DIR. Nothing is vendored into this repository.

    python tools/fetch_addrlib.py            # fetch out/deps/mesa at the pinned commit
    python tools/fetch_addrlib.py --dest DIR # another location
"""
import argparse
import pathlib
import subprocess
import sys

URL = "https://gitlab.freedesktop.org/mesa/mesa.git"
COMMIT = "5c142e46f3f6e752ed745fd48912ebb8fad67145"  # tag mesa-25.1.0
SUBDIR = "src/amd/addrlib"


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=pathlib.Path, default=root / "out" / "deps" / "mesa")
    args = parser.parse_args()
    dest = args.dest.resolve()

    if not (dest / ".git").exists():
        dest.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=dest)
        git("remote", "add", "origin", URL, cwd=dest)
    git("sparse-checkout", "set", "--cone", SUBDIR, cwd=dest)
    git("fetch", "--depth", "1", "--filter=blob:none", "origin", COMMIT, cwd=dest)
    # Discard any local edit in the dependency checkout so the pinned tree is what gets built.
    git("checkout", "-q", "--force", "--detach", COMMIT, cwd=dest)
    git("clean", "-ffdxq", cwd=dest)
    dirty = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=dest, check=True,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        sys.exit(f"{dest} still differs from {COMMIT}: {dirty}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, check=True, capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        sys.exit(f"checked out {head}, expected {COMMIT}")
    addrlib = dest / SUBDIR
    if not (addrlib / "inc" / "addrinterface.h").is_file():
        sys.exit(f"{addrlib} has no inc/addrinterface.h")
    print(f"addrlib {COMMIT} at {addrlib}")
    print(f"configure with -DXBOX2WINDOWS_ADDRLIB_DIR={addrlib.as_posix()}")


if __name__ == "__main__":
    main()
