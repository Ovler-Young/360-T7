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

# Insert lines before the last line in 99-default-settings-chinese. For Modify apk url, change mt7981 to filogic
sed -i '\|^exit 0$|i sed -i "s,mt7981,filogic,g" /etc/apk/repositories.d/distfeeds.list' \
    package/emortal/default-settings/files/99-default-settings-chinese

# Inject US locale override script that runs after 99-default-settings-chinese on first boot.
# Uses a higher sort key (99z) so it executes last among the 99-* scripts.
OVERRIDE_SCRIPT="files/etc/uci-defaults/99z-default-settings-us"
mkdir -p "$(dirname "$OVERRIDE_SCRIPT")"
cat > "$OVERRIDE_SCRIPT" <<'OVERRIDE_EOF'
#!/bin/sh
# Override locale settings applied by 99-default-settings-chinese:
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

# Add tailscale-community
git clone https://github.com/tokisaki-galaxy/luci-app-tailscale-community --branch=master --depth=1 /tmp/luci-app-tailscale-community
mkdir -p package/luci-app-tailscale-community
cp -r /tmp/luci-app-tailscale-community/luci-app-tailscale-community package/
# Use the official source-built core with its matching Go toolchain.
# Its service supports the same state, port, nftables and logging settings.
./scripts/feeds install tailscale

# Add luci-app-adguardhome (nft version, downloads AdGuardHome binary on first run)
# Note: do NOT install the feeds adguardhome package alongside this to avoid dual procd services
git clone https://github.com/OneNAS-space/luci-app-adguardhome --branch=main --depth=1 package/luci-app-adguardhome || exit 1
rm -rf package/luci-app-adguardhome/patches
# Fix luci-app-adguardhome recursive dependency (tar + xz cycle)
sed -i 's/+wget-ssl +tar +xz/+wget-ssl +tar/' package/luci-app-adguardhome/Makefile
install -Dm755 "$GITHUB_WORKSPACE/scripts/adguardhome-legacy-config.sh" \
  package/luci-app-adguardhome/root/etc/uci-defaults/90-adguardhome-legacy-config || exit 1

# Update sing-box and cloudflared in feeds
pushd feeds/packages

# sing-box: remove tailscale tag and update to latest release
# sing-box: remove tailscale support
sed -i 's/,with_tailscale//g' net/sing-box/Makefile
sed -i '/CONFIG_SING_BOX_TINY_BUILD_TAILSCALE/d' net/sing-box/Makefile

# Add only the official versioned compiler; retain the release's default Go and feeds.
go_ref=$(gh api repos/immortalwrt/packages/commits/openwrt-25.12 --jq .sha) || exit 1
[[ "$go_ref" =~ ^[0-9a-f]{40}$ ]] || exit 1
go_recipe=$(mktemp) || exit 1
if ! gh api "repos/immortalwrt/packages/contents/lang/golang/golang1.27/Makefile?ref=$go_ref" \
    -H 'Accept: application/vnd.github.raw+json' > "$go_recipe"; then
  rm -f "$go_recipe"
  exit 1
fi
# Refuse unexpected recipe layouts or compiler sources before installing the overlay.
GO_COMPILER_VERSION=$(python3 - "$go_recipe" <<'PY_GO'
import pathlib
import re
import sys

recipe = pathlib.Path(sys.argv[1]).read_text()
def value(name):
    matches = re.findall(r"^" + re.escape(name) + r":=(.*)$", recipe, re.M)
    if len(matches) != 1:
        sys.exit(f"Missing or ambiguous Go recipe field: {name}")
    return matches[0].strip()

if (value("PKG_NAME") != "golang1.27"
        or value("GO_VERSION_MAJOR_MINOR") != "1.27"
        or not re.fullmatch(r"[0-9]+", value("GO_VERSION_PATCH"))
        or value("GO_VERSION_RC")
        or value("PKG_SOURCE") != "go$(PKG_FILE_VERSION).src.tar.gz"
        or not value("GO_SOURCE_URLS").startswith("https://go.dev/dl/")
        or not re.fullmatch(r"[0-9a-f]{64}", value("PKG_HASH"))):
    sys.exit("Unexpected official Go source recipe")
print("1.27." + value("GO_VERSION_PATCH"))
PY_GO
) || { rm -f "$go_recipe"; exit 1; }
mkdir -p lang/golang/golang1.27
mv "$go_recipe" lang/golang/golang1.27/Makefile
printf '==> Official golang%s from immortalwrt/packages %s\n' "$GO_COMPILER_VERSION" "$go_ref"

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
    -e "s/^PKG_HASH:=.*/PKG_HASH:=$hash/" \
    -e '/^PKG_BUILD_DEPENDS/s/golang[0-9.]*/golang1.27/g' "$mk" || return 1
  grep -qx "PKG_VERSION:=$version" "$mk" && \
    grep -qx "PKG_HASH:=$hash" "$mk" || return 1
  echo "==> $pkg updated to $version (SHA-256: $hash)"
}

update_release_package sing-box SagerNet/sing-box || exit 1
# cloudflared: update to latest release (tag has no 'v' prefix)
update_release_package cloudflared cloudflare/cloudflared || exit 1

popd

# Register the added compiler recipe after the pinned feed was initially indexed.
./scripts/feeds update -i packages
./scripts/feeds install golang1.27

if grep -qx 'CONFIG_PACKAGE_adguardhome-core=y' .config; then
  python3 "$GITHUB_WORKSPACE/scripts/prepare-adguardhome-core.py" || exit 1
fi
