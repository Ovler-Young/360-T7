#!/usr/bin/env python3
"""Prepare the latest public AdGuard Home source build using the supported Go toolchain."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPOSITORY = "AdguardTeam/AdGuardHome"
FRONTEND = "AdGuardHome_frontend.tar.gz"
FEED_REPOSITORY = "immortalwrt/packages"
FEED_REF = "openwrt-25.12"


def github_json(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def github_raw(path):
    return subprocess.check_output(
        ["gh", "api", path, "-H", "Accept: application/vnd.github.raw+json"],
        text=True,
    )


def assignment(recipe, field, pattern):
    matches = re.findall(r"^" + re.escape(field) + r":=(" + pattern + r")$", recipe, re.M)
    if len(matches) != 1:
        raise ValueError(f"Invalid official AdGuard Home recipe field: {field}")
    return matches[0]


def go_version(value):
    parts = tuple(int(part) for part in value.split("."))
    if len(parts) not in (2, 3):
        raise ValueError("Invalid Go version")
    return parts + (0,) * (3 - len(parts))


def select_release(release, recipe, module, compiler_recipe):
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Expected a stable AdGuard Home release")
    version = tag.removeprefix("v")
    if assignment(recipe, "PKG_NAME", "adguardhome") != "adguardhome":
        raise ValueError("Unexpected upstream package")
    if assignment(recipe, "PKG_VERSION", r"[0-9.]+") != version:
        raise ValueError("Official 25.12 source recipe is older than the latest stable release")
    source_hash = assignment(recipe, "PKG_HASH", r"[0-9a-f]{64}")
    frontend_hash = assignment(recipe, "FRONTEND_HASH", r"[0-9a-f]{64}")
    if "https://codeload.github.com/AdguardTeam/AdGuardHome/tar.gz/" not in recipe:
        raise ValueError("Unexpected AdGuard Home source URL")
    assets = [asset for asset in release["assets"] if asset["name"] == FRONTEND]
    if len(assets) != 1:
        raise ValueError("Expected one official frontend asset")
    asset = assets[0]
    expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{FRONTEND}"
    if (asset["browser_download_url"] != expected_url or type(asset["size"]) is not int
            or asset["size"] <= 0 or asset["digest"] != f"sha256:{frontend_hash}"):
        raise ValueError("AdGuard Home frontend release SHA-256 or URL mismatch")
    requirements = re.findall(r"^go\s+(\d+\.\d+(?:\.\d+)?)\s*$", module, re.M)
    if len(requirements) != 1:
        raise ValueError("Missing or ambiguous go.mod requirement")
    minor = assignment(compiler_recipe, "GO_VERSION_MAJOR_MINOR", r"1\.27")
    patch = assignment(compiler_recipe, "GO_VERSION_PATCH", r"[0-9]+")
    compiler_version = f"{minor}.{patch}"
    if go_version(compiler_version) < go_version("1.27.3") or go_version(requirements[0]) > go_version(compiler_version):
        raise ValueError(f"AdGuard Home requires Go {requirements[0]}; selected compiler is {compiler_version}")
    return version, source_hash, frontend_hash, compiler_version


def prepare(build_root):
    release = github_json(f"repos/{REPOSITORY}/releases/latest")
    recipe = github_raw(
        f"repos/{FEED_REPOSITORY}/contents/net/adguardhome/Makefile?ref={FEED_REF}"
    )
    module = github_raw(f"repos/{REPOSITORY}/contents/go.mod?ref={release['tag_name']}")
    compiler = (build_root / "feeds/packages/lang/golang/golang1.27/Makefile").read_text()
    version, source_hash, frontend_hash, go = select_release(release, recipe, module, compiler)

    package = build_root / "package/adguardhome-core"
    package.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).resolve().parent.parent / "packages/adguardhome-core/Makefile"
    shutil.copyfile(template, package / "Makefile")
    (package / "release.mk").write_text(
        f"PKG_VERSION:={version}\n"
        f"PKG_HASH:={source_hash}\n"
        f"FRONTEND_HASH:={frontend_hash}\n"
    )
    print(f"==> AdGuard Home source {version} with Go {go}; "
          "source/frontend SHA-256 supplied by official ImmortalWrt recipe")


if __name__ == "__main__":
    try:
        prepare(Path.cwd())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f"Cannot prepare AdGuard Home source package: {error}")
