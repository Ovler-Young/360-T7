#!/usr/bin/env python3
"""Prepare the public ARM64 AdGuard Home binary package for an OpenWrt build."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPOSITORY = "AdguardTeam/AdGuardHome"
ASSET = "AdGuardHome_linux_arm64.tar.gz"


def curl(url, *args):
    return subprocess.check_output(
        ["curl", "-fsSL", "--retry", "3", "--connect-timeout", "20",
         "--max-time", "300", url, *args],
        text=True,
    )


def prepare(build_root):
    release = json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{REPOSITORY}/releases/latest"], text=True
    ))
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v?\d[\w.-]*", tag):
        raise ValueError("Expected a stable AdGuard Home release tag")
    asset = next(item for item in release["assets"] if item["name"] == ASSET)
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("The release asset has no SHA-256 digest")
    base_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    url = f"{base_url}/{ASSET}"
    if asset["browser_download_url"] != url:
        raise ValueError("Unexpected AdGuard Home release asset URL")

    downloads = build_root / "dl"
    downloads.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="adguardhome-", dir=downloads)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        curl(url, "-o", str(temporary))
        hasher = hashlib.sha256()
        with temporary.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        if f"sha256:{checksum}" != digest:
            raise ValueError("AdGuard Home asset checksum mismatch")
        with tarfile.open(temporary, "r:gz") as archive:
            member = next(item for item in archive.getmembers()
                          if item.name.removeprefix("./") == "AdGuardHome/AdGuardHome")
            if not member.isfile():
                raise ValueError("Expected a regular AdGuardHome executable")
            with archive.extractfile(member) as binary:
                header = binary.read(20)
            if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\xb7\x00":
                raise ValueError("Expected a 64-bit little-endian AArch64 executable")

        version = tag.removeprefix("v")
        temporary.replace(downloads / f"adguardhome-core-{version}-linux-arm64.tar.gz")
        package = build_root / "package" / "adguardhome-core"
        package.mkdir(parents=True, exist_ok=True)
        template = Path(__file__).resolve().parent.parent / "packages/adguardhome-core/Makefile"
        shutil.copyfile(template, package / "Makefile")
        (package / "release.mk").write_text(
            f"PKG_VERSION:={version}\nPKG_HASH:={checksum}\n"
            f"ADGUARDHOME_SOURCE_URL:={base_url}\n"
        )
        print(f"==> AdGuard Home core {version}, ARM64, SHA-256 verified: {checksum}")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        prepare(Path.cwd())
    except (OSError, ValueError, KeyError, StopIteration, tarfile.TarError,
            subprocess.CalledProcessError) as error:
        print(f"Cannot prepare AdGuard Home core: {error}", file=sys.stderr)
        sys.exit(1)
