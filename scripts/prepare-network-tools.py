#!/usr/bin/env python3
"""Restore explicit legacy network-tool selections from verified public upstream sources."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

NDISC_INDEX = "https://www.remlab.net/files/ndisc6/"
WRTBWMON_REPO = "pyrovski/wrtbwmon"


def curl(url):
    return subprocess.check_output(["curl", "-fsSL", "--retry", "3", "--max-time", "50", url])


def verify_tar(payload, prefix, expected_files):
    if not 1024 < len(payload) < 10_000_000:
        raise ValueError("Invalid source archive size")
    with tarfile.open(fileobj=BytesIO(payload), mode="r:*") as archive:
        paths = {member.name.removeprefix("./") for member in archive.getmembers()}
        if any(path.startswith("/") or ".." in Path(path).parts for path in paths):
            raise ValueError("Unsafe source archive paths")
        if not {f"{prefix}/{name}" for name in expected_files} <= paths:
            raise ValueError("Unexpected upstream source layout")
    return hashlib.sha256(payload).hexdigest()


def prepare_ndisc6(root):
    page = curl(NDISC_INDEX).decode("utf-8")
    versions = {tuple(map(int, match)) for match in
                re.findall(r'ndisc6-(\d+)\.(\d+)\.(\d+)\.tar\.bz2', page)}
    if not versions:
        raise ValueError("No official ndisc6 source release found")
    version = ".".join(map(str, max(versions)))
    url = f"{NDISC_INDEX}ndisc6-{version}.tar.bz2"
    digest = verify_tar(
        curl(url), f"ndisc6-{version}",
        ("configure", "COPYING", "src/ndisc.c", "rdnss/rdnssd.c"),
    )
    dest = root / "package/ndisc6"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parent.parent / "packages/ndisc6/Makefile", dest / "Makefile")
    (dest / "release.mk").write_text(f"PKG_VERSION:={version}\nPKG_HASH:={digest}\n")
    print(f"ndisc6 {version}: official source SHA-256 {digest}")


def wrtbwmon_tag(tags):
    available = []
    for entry in tags:
        name = entry.get("name", "")
        match = re.fullmatch(r"(\d+)\.(\d+)(?:_(ipv6))?", name)
        if match:
            available.append((int(match[1]), int(match[2]),
                              bool(match[3]), name))
    if not available:
        raise ValueError("No compatible wrtbwmon source tag found")
    major, minor, _, tag = max(available)
    return f"{major}.{minor}", tag


def prepare_wrtbwmon(root):
    tags = json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{WRTBWMON_REPO}/tags?per_page=100"],
            text=True,
        )
    )
    version, tag = wrtbwmon_tag(tags)
    url = f"https://codeload.github.com/{WRTBWMON_REPO}/tar.gz/refs/tags/{tag}"
    digest = verify_tar(
        curl(url), f"wrtbwmon-{tag}",
        ("wrtbwmon", "readDB.awk", "init/wrtbwmon", "copyright",
         "usage.htm1", "usage.htm2"),
    )
    dest = root / "package/wrtbwmon"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parent.parent / "packages/wrtbwmon/Makefile", dest / "Makefile")
    (dest / "release.mk").write_text(
        f"PKG_VERSION:={version}\nPKG_SOURCE_TAG:={tag}\nPKG_HASH:={digest}\n"
    )
    print(f"wrtbwmon {tag}: GitHub source SHA-256 {digest}")


if __name__ == "__main__":
    try:
        prepare_ndisc6(Path.cwd())
        prepare_wrtbwmon(Path.cwd())
    except (ValueError, OSError, tarfile.TarError, subprocess.CalledProcessError,
            json.JSONDecodeError) as error:
        sys.exit(f"Cannot prepare public network-tool packages: {error}")
