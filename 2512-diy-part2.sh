#!/bin/bash
#
# https://github.com/P3TERX/Actions-OpenWrt
# File name: diy-part2.sh
# Description: OpenWrt DIY script part 2 (After Update feeds)
#
# Copyright (c) 2019-2024 P3TERX <https://p3terx.com>
#
# This is free software, licensed under the MIT License.
# See /LICENSE for more information.
#

set -e
set -o pipefail

SMP_HOTPLUG="target/linux/mediatek/filogic/base-files/etc/hotplug.d/iface/30-ext-devices-rps-setting"
if [ -f "$SMP_HOTPLUG" ]; then
  sed -i '/^NPROCS=/i\
case "$ACTION" in\
  ifup|ifdown) ;;\
  *) exit 0 ;;\
esac\
' "$SMP_HOTPLUG"
fi

# Select official 25.12 Wi-Fi drivers and APK instead of the old MTK Wi-Fi driver.
for pkg in kmod-mt_wifi mtk-smp mtkhqos_util opkg; do
  sed -i "/^CONFIG_PACKAGE_${pkg}=/d; /^# CONFIG_PACKAGE_${pkg} is not set/d" .config
done
for pkg in kmod-mt7915e kmod-mt7981-firmware mt7981-wo-firmware apk-openssl; do
  sed -i "/^CONFIG_PACKAGE_${pkg}=/d; /^# CONFIG_PACKAGE_${pkg} is not set/d" .config
  printf 'CONFIG_PACKAGE_%s=y\n' "$pkg" >> .config
done

# Modify default IP
sed -i 's/192.168.1.1/192.168.10.1/g' package/base-files/files/bin/config_generate

# Modify hostname
BUILD_DATE=$(TZ="America/New_York" date +"%Y%m%d")
sed -i "s/ImmortalWrt/ImmortalWrt-25.12-${BUILD_DATE}/g" package/base-files/files/bin/config_generate

# Modify theme
sed -i 's/luci-theme-material/luci-theme-argon/g' feeds/luci/collections/luci/Makefile


# Modify filename, add date prefix
sed -i 's|IMG_PREFIX:=|IMG_PREFIX:=$(shell TZ="America/New_York" date +"%Y%m%d")-25.12|' include/image.mk

# Use general ImmortalWrt defaults plus a single US locale customization.
# Do not install default-settings-chn: it writes Chinese NTP/mirror settings.
# Use a late sort key (99z) so US settings run after distribution defaults.
OVERRIDE_SCRIPT="files/etc/uci-defaults/99z-default-settings-us"
mkdir -p "$(dirname "$OVERRIDE_SCRIPT")"
cat > "$OVERRIDE_SCRIPT" <<'OVERRIDE_EOF'
#!/bin/sh
# US first-boot locale settings:
# - Timezone: America/New_York (UTC-5/UTC-4 DST)
# - NTP: Cloudflare + NIST (no Chinese servers)
# - apk mirror: restored to official immortalwrt.org

uci -q get system.@imm_init[0] > /dev/null || uci -q add system imm_init > /dev/null || exit 1

uci -q batch <<-EOF
	set system.@system[0].timezone="EST5EDT,M3.2.0,M11.1.0"
	set system.@system[0].zonename="America/New_York"

	delete system.ntp.server
	add_list system.ntp.server="time.cloudflare.com"
	add_list system.ntp.server="time.nist.gov"
	add_list system.ntp.server="pool.ntp.org"
	add_list system.ntp.server="time.google.com"

	set system.@imm_init[0].apk_mirror="https://downloads.immortalwrt.org"
	commit system
EOF
[ "$?" -eq 0 ] || exit 1

# Normalize active feeds directly; a saved mirror list may be stale.
feeds=/etc/apk/repositories.d/distfeeds.list
[ -s "$feeds" ] || exit 1
sed -i -E 's#https?://[^/]+/(openwrt/|immortalwrt/)?#https://downloads.immortalwrt.org/#g; s#mt7981#filogic#g' "$feeds" || exit 1

exit 0
OVERRIDE_EOF
chmod +x "$OVERRIDE_SCRIPT"

# Use the OneNAS LuCI service instead of the feeds LuCI package, whose
# +adguardhome dependency would select a second, official core. Do this
# before feeds install refreshes Kconfig with the explicit user selections.
FEED_ADGUARD_LUCI=package/feeds/luci/luci-app-adguardhome
if [ -L "$FEED_ADGUARD_LUCI" ]; then
  rm "$FEED_ADGUARD_LUCI"
elif [ -e "$FEED_ADGUARD_LUCI" ]; then
  echo "Unexpected non-symlink feed AdGuardHome LuCI package" >&2
  exit 1
fi
git clone https://github.com/OneNAS-space/luci-app-adguardhome --branch=main --depth=1 package/luci-app-adguardhome || exit 1
rm -rf package/luci-app-adguardhome/patches
# Fix luci-app-adguardhome recursive dependency (tar + xz cycle)
sed -i 's/+wget-ssl +tar +xz/+wget-ssl +tar/' package/luci-app-adguardhome/Makefile
# fw4 loads /etc/nftables.d snippets inside its inet fw4 table. OneNAS
# declares a complete 'table inet adguardhome', which belongs at ruleset level.
install -Dm644 package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft \
  package/luci-app-adguardhome/root/usr/share/nftables.d/ruleset-post/99-adguardhome.nft || exit 1
rm package/luci-app-adguardhome/root/etc/nftables.d/99-adguardhome.nft || exit 1

# Upgrade the pinned feed's default compiler with matching official 25.12 files.
GO_REF=$(gh api repos/immortalwrt/packages/commits/openwrt-25.12 --jq .sha)
[[ "$GO_REF" =~ ^[0-9a-f]{40}$ ]] || exit 1
GO_RECIPE=$(mktemp)
GO_HELPER=$(mktemp)
gh api "repos/immortalwrt/packages/contents/lang/golang/golang1.27/Makefile?ref=$GO_REF" \
  -H 'Accept: application/vnd.github.raw+json' > "$GO_RECIPE"
gh api "repos/immortalwrt/packages/contents/lang/golang/golang-version.mk?ref=$GO_REF" \
  -H 'Accept: application/vnd.github.raw+json' > "$GO_HELPER"
python3 - "$GO_RECIPE" "$GO_HELPER" <<'PY_TOOLCHAIN'
import pathlib
import re
import sys

recipe = pathlib.Path(sys.argv[1]).read_text()
helper = pathlib.Path(sys.argv[2]).read_text()
def assignment(text, name, pattern):
    values = re.findall(r"^" + re.escape(name) + r":=(" + pattern + r")$", text, re.M)
    if len(values) != 1:
        sys.exit(f"Invalid Go recipe assignment: {name}")
    return values[0]

assignment(recipe, "PKG_NAME", r"golang1\.27")
assignment(recipe, "PKG_HASH", r"[0-9a-f]{64}")
minor = assignment(recipe, "GO_VERSION_MAJOR_MINOR", r"1\.27")
patch = int(assignment(recipe, "GO_VERSION_PATCH", r"[0-9]+"))
if patch < 3:
    sys.exit("Official Go recipe must provide Go >= 1.27.3")
if "include ../golang-values.mk" not in helper or "$(if $(PKG_HOST_ONLY),BUILDONLY:=1)" not in helper:
    sys.exit("Unexpected official Go build helper")
root = pathlib.Path("feeds/packages/lang/golang")
values_path = root / "golang-values.mk"
values = values_path.read_text()
assignment(values, "GO_DEFAULT_VERSION", r"1\.(?:26|27)")
values = re.sub(r"^GO_DEFAULT_VERSION:=1\.(?:26|27)$",
                "GO_DEFAULT_VERSION:=1.27", values, flags=re.M)
for package in ("tailscale", "sing-box"):
    content = pathlib.Path(f"feeds/packages/net/{package}/Makefile").read_text()
    if not re.search(r"^PKG_BUILD_DEPENDS[:+]?=.*(?<![\w/])golang/host(?:\s|$)", content, re.M):
        sys.exit(f"{package} must use the default golang/host toolchain")
(root / "golang1.27").mkdir(exist_ok=True)
(root / "golang1.27/Makefile").write_text(recipe)
(root / "golang-version.mk").write_text(helper)
values_path.write_text(values)
print(f"==> Default Go compiler: {minor}.{patch}")
PY_TOOLCHAIN
rm -f "$GO_RECIPE" "$GO_HELPER"
# Register the source-built AdGuardHome core before package metadata is
# regenerated; otherwise its explicit Kconfig selection gets discarded.
if grep -qx 'CONFIG_PACKAGE_adguardhome-core=y' .config; then
  python3 "$GITHUB_WORKSPACE/scripts/prepare-adguardhome-core.py" || exit 1
fi
# 25.12 feeds no longer provide these explicitly selected legacy utilities.
# Prepare upstream HTTPS source archives with build-time SHA-256 before reindexing.
if grep -Eq '^CONFIG_PACKAGE_(ndisc6|rdisc6|rdnssd|traceroute6|wrtbwmon)=y$' .config; then
  python3 "$GITHUB_WORKSPACE/scripts/prepare-network-tools.py" || exit 1
fi
# Reindex local changes without moving the pinned feed revision.
./scripts/feeds update -i packages
./scripts/feeds install -p packages golang golang1.27

# Add tailscale-community
git clone https://github.com/tokisaki-galaxy/luci-app-tailscale-community --branch=master --depth=1 /tmp/luci-app-tailscale-community
mkdir -p package/luci-app-tailscale-community
cp -r /tmp/luci-app-tailscale-community/luci-app-tailscale-community package/
# Use the official source-built core with its matching Go toolchain.
# Its service supports the same state, port, nftables and logging settings.
./scripts/feeds install tailscale

# Update sing-box in feeds
pushd feeds/packages

# sing-box: remove tailscale tag and update to latest release
# sing-box: remove tailscale support
sed -i 's/,with_tailscale//g' net/sing-box/Makefile
sed -i '/CONFIG_SING_BOX_TINY_BUILD_TAILSCALE/d' net/sing-box/Makefile

# Resolve the distribution's actual default Go compiler for the sing-box go.mod check.
GO_COMPILER_VERSION=$(python3 - <<'PY_VERSION'
import pathlib
import re

def value(content, name, pattern):
    matches = re.findall(r"^" + name + r":=(" + pattern + r")$", content, re.M)
    if len(matches) != 1:
        raise SystemExit("Cannot determine default Go compiler version")
    return matches[0]

default = pathlib.Path("lang/golang/golang-values.mk").read_text()
minor = value(default, "GO_DEFAULT_VERSION", r"[0-9]+\.[0-9]+")
recipe = pathlib.Path(f"lang/golang/golang{minor}/Makefile").read_text()
if value(recipe, "GO_VERSION_MAJOR_MINOR", r"[0-9]+\.[0-9]+") != minor:
    raise SystemExit("Unexpected default Go compiler recipe")
patch = value(recipe, "GO_VERSION_PATCH", r"[0-9]+")
print(f"{minor}.{patch}")
PY_VERSION
) || exit 1

update_release_package() {
  local pkg="$1" repo="$2" mk="net/$1/Makefile"
  local tag version archive hash

  if [ ! -f "$mk" ] || ! grep -Fq "https://codeload.github.com/$repo/tar.gz/" "$mk"; then
    echo "Unexpected source URL for $pkg: $mk" >&2
    return 1
  fi

  tag=$(gh api "repos/$repo/releases/latest" --jq .tag_name) || return 1
  if [[ ! "$tag" =~ ^v?[0-9][0-9A-Za-z._-]*$ ]]; then
    echo "Invalid release tag for $pkg: $tag" >&2
    return 1
  fi
  version="${tag#v}"

  archive=$(mktemp) || return 1
  if ! curl -fsSL --retry 3 "https://codeload.github.com/$repo/tar.gz/$tag?" -o "$archive"; then
    rm -f "$archive"
    return 1
  fi
  if ! tar -tzf "$archive" >/dev/null; then
    rm -f "$archive"
    return 1
  fi
  # Check the actual hashed source, before updating either version or dependency.
  if ! python3 - "$archive" "$GO_COMPILER_VERSION" <<'PY_GO'
import re
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as source:
    modules = [m for m in source.getmembers()
               if re.fullmatch(r"[^/]+/go\.mod", m.name) and m.isfile()]
    if len(modules) != 1:
        sys.exit("Expected one root go.mod in release source")
    module = source.extractfile(modules[0]).read().decode()
requirements = re.findall(r"^go\s+(\d+\.\d+(?:\.\d+)?)\s*(?://.*)?$", module, re.M)
if len(requirements) != 1:
    sys.exit("Missing or unsupported go.mod version requirement")
def version(text):
    parts = tuple(map(int, text.split(".")))
    return parts + (0,) * (3 - len(parts))
if version(requirements[0]) > version(sys.argv[2]):
    sys.exit(f"Release requires Go {requirements[0]}; official compiler is {sys.argv[2]}")
print(f"==> go.mod requires Go {requirements[0]}; compiler {sys.argv[2]}")
PY_GO
  then
    rm -f "$archive"
    return 1
  fi
  grep -Eq '^PKG_BUILD_DEPENDS[:+]?=.*golang([0-9]+\.[0-9]+)?/host' "$mk" || {
    echo "Missing Go host dependency in $mk" >&2
    rm -f "$archive"
    return 1
  }
  hash=$(sha256sum "$archive") || { rm -f "$archive"; return 1; }
  hash="${hash%% *}"
  rm -f "$archive"
  if [[ ! "$hash" =~ ^[0-9a-f]{64}$ ]]; then
    echo "Invalid source hash for $pkg" >&2
    return 1
  fi

  sed -i \
    -e "s/^PKG_VERSION:=.*/PKG_VERSION:=$version/" \
    -e "s/^PKG_HASH:=.*/PKG_HASH:=$hash/" "$mk" || return 1
  grep -qx "PKG_VERSION:=$version" "$mk" && \
    grep -qx "PKG_HASH:=$hash" "$mk" || return 1
  echo "==> $pkg updated to $version (SHA-256: $hash)"
}

update_release_package sing-box SagerNet/sing-box || exit 1
# The pinned Tailscale 1.98.3 uses an old go-json-experiment alias that
# references json/v2 APIs removed in Go 1.27. Upgrade to a release whose
# go.mod explicitly supports the selected official compiler.
update_release_package tailscale tailscale/tailscale || exit 1


popd

python3 "$GITHUB_WORKSPACE/scripts/prepare-cloudflared-prebuilt.py" || exit 1
