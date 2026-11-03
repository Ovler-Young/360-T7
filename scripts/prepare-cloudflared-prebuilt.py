#!/usr/bin/env python3
"""Stage the fork's matching stable ARM64 cloudflared release for OpenWrt."""

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

REPOSITORY = "xiexiaopeng2002/cloudflared"
ASSET = "cloudflared-linux-arm64"


def select_release(fork, upstream):
    for release in (fork, upstream):
        if (release.get("draft") or release.get("prerelease")
                or not re.fullmatch(r"\d{4}\.\d+\.\d+", release["tag_name"])):
            raise ValueError("Expected a stable cloudflared release")
    tag = fork["tag_name"]
    if tag != upstream["tag_name"]:
        raise ValueError(f"Fork release {tag} does not match upstream {upstream['tag_name']}")
    assets = [asset for asset in fork["assets"] if asset["name"] == ASSET]
    if len(assets) != 1:
        raise ValueError("Expected exactly one ARM64 release asset")
    asset = assets[0]
    base = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    if (asset["browser_download_url"] != f"{base}/{ASSET}"
            or type(asset["size"]) is not int or asset["size"] <= 0
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest", ""))):
        raise ValueError("Invalid release asset URL, size or SHA-256 digest")
    return tag, base, asset


def verify_binary(data, asset):
    if len(data) != asset["size"] or "sha256:" + hashlib.sha256(data).hexdigest() != asset["digest"]:
        raise ValueError("cloudflared size or SHA-256 mismatch")
    if (len(data) < 64 or data[:7] != b"\x7fELF\x02\x01\x01"
            or struct.unpack_from("<HH", data, 16) not in ((2, 183), (3, 183))):
        raise ValueError("Expected an ELF64 little-endian AArch64 executable")
    offset = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    if entry_size != 56 or not count or offset < 64 or offset + count * entry_size > len(data):
        raise ValueError("Invalid ELF program headers")
    types = [struct.unpack_from("<I", data, offset + i * entry_size)[0] for i in range(count)]
    if 3 in types or 1 not in types:
        raise ValueError("Expected a static executable without PT_INTERP")


def prepare(root):
    def release(repo):
        return json.loads(subprocess.check_output(
            ["gh", "api", f"repos/{repo}/releases/latest"], text=True))
    tag, base, asset = select_release(release(REPOSITORY), release("cloudflare/cloudflared"))
    package = root / "feeds/packages/net/cloudflared"
    for name in ("sample_config.yml", "cloudflared.config", "cloudflared.init"):
        if not (package / "files" / name).is_file():
            raise ValueError(f"Missing feed service file: {name}")
    template = Path(__file__).resolve().parent.parent / "packages/cloudflared-prebuilt/Makefile"
    recipe = template.read_text()
    downloads = root / "dl"
    downloads.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloudflared-", dir=downloads) as directory:
        binary = Path(directory) / ASSET
        subprocess.run(["curl", "-fsSL", "--retry", "3", "--connect-timeout", "20",
                        "--max-time", "300", asset["browser_download_url"], "-o", str(binary)], check=True)
        verify_binary(binary.read_bytes(), asset)
        binary.replace(downloads / f"cloudflared-prebuilt-{tag}-linux-arm64")
    (package / "release.mk").write_text(
        f"PKG_VERSION:={tag}\nPKG_HASH:={asset['digest'][7:]}\n"
        f"CLOUDFLARED_SOURCE_URL:={base}\nCLOUDFLARED_SOURCE_FILE:={ASSET}\n")
    (package / "Makefile").write_text(recipe)
    print(f"==> cloudflared {tag}: fork ARM64 binary verified")


if __name__ == "__main__":
    try:
        prepare(Path.cwd())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f"Cannot prepare cloudflared: {error}")
