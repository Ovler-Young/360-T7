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

SMP_HOTPLUG="target/linux/mediatek/filogic/base-files/etc/hotplug.d/iface/30-ext-devices-rps-setting"
if [ ! -f "$SMP_HOTPLUG" ]; then
  echo "Missing upstream MediaTek SMP iface hotplug script" >&2
  exit 1
fi
sed -i '/^NPROCS=/i\
case "$ACTION" in\
  ifup|ifdown) ;;\
  *) exit 0 ;;\
esac\
' "$SMP_HOTPLUG"

# Modify default IP
sed -i 's/192.168.6.1/192.168.10.1/g' package/base-files/files/bin/config_generate

# Modify hostname
BUILD_DATE=$(TZ="America/New_York" date +"%Y%m%d")
sed -i "s/ImmortalWrt/ImmortalWrt-24.10-${BUILD_DATE}/g" package/base-files/files/bin/config_generate

# Modify theme
sed -i 's/luci-theme-material/luci-theme-argon/g' feeds/luci/collections/luci/Makefile


# Modify filename, add date prefix
sed -i 's|IMG_PREFIX:=|IMG_PREFIX:=$(shell TZ="America/New_York" date +"%Y%m%d")-24.10|' include/image.mk

# Insert lines before the last line in 99-default-settings-chinese. For Modify opkg url, change mt7981 to filogic
sed -i '\|^exit 0$|i sed -i "s,mt7981,filogic,g" /etc/opkg/distfeeds.conf' \
    package/emortal/default-settings/files/99-default-settings-chinese

# Inject US locale override script that runs after 99-default-settings-chinese on first boot.
# Uses a higher sort key (99z) so it executes last among the 99-* scripts.
OVERRIDE_SCRIPT="package/emortal/default-settings/files/99z-default-settings-us"
mkdir -p "$(dirname "$OVERRIDE_SCRIPT")"
cat > "$OVERRIDE_SCRIPT" <<'OVERRIDE_EOF'
#!/bin/sh
# Override locale settings applied by 99-default-settings-chinese:
# - Timezone: America/New_York (UTC-5/UTC-4 DST)
# - NTP: Cloudflare + NIST (no Chinese servers)
# - opkg mirror: restored to official immortalwrt.org

uci -q get system.@imm_init[0] > /dev/null || uci -q add system imm_init > /dev/null

uci -q batch <<-EOF
	set system.@system[0].timezone="EST5EDT,M3.2.0,M11.1.0"
	set system.@system[0].zonename="America/New_York"

	delete system.ntp.server
	add_list system.ntp.server="time.cloudflare.com"
	add_list system.ntp.server="time.nist.gov"
	add_list system.ntp.server="pool.ntp.org"
	add_list system.ntp.server="time.google.com"

	set system.@imm_init[0].opkg_mirror="https://downloads.immortalwrt.org"
	commit system
EOF

# Restore distfeeds.conf to official upstream (undo any mirror substitution)
if [ -f /etc/opkg/distfeeds.conf.bak ]; then
	cp /etc/opkg/distfeeds.conf.bak /etc/opkg/distfeeds.conf
else
	sed -i "s,https://mirrors.vsean.net/openwrt,https://downloads.immortalwrt.org,g" \
		/etc/opkg/distfeeds.conf
fi

exit 0
OVERRIDE_EOF
chmod +x "$OVERRIDE_SCRIPT"

# Add tailscale-community
git clone https://github.com/tokisaki-galaxy/luci-app-tailscale-community --branch=master --depth=1 /tmp/luci-app-tailscale-community
mkdir -p package/luci-app-tailscale-community
cp -r /tmp/luci-app-tailscale-community/luci-app-tailscale-community package/
# Fix luci-app-tailscale-community recursive dependency (select + depends cycle)
sed -i 's/LUCI_DEPENDS:=+tailscale/LUCI_DEPENDS:=tailscale/' package/luci-app-tailscale-community/Makefile

git clone https://github.com/GuNanOvO/openwrt-tailscale --branch=main --depth=1 /tmp/openwrt-tailscale
mkdir -p package/tailscale-community
cp -r /tmp/openwrt-tailscale/package/tailscale/* package/tailscale-community/

TAILSCALE_MK="package/tailscale-community/Makefile"
sed -i '/^include \$(TOPDIR)\/rules.mk/a DISABLE_UPX:=1' "$TAILSCALE_MK"
sed -i "s/(OpenWrt-UPX)/(OpenWrt)/" "$TAILSCALE_MK"
sed -i 's/Zero config VPN (UPX Compressed)/Zero config VPN/' "$TAILSCALE_MK"
sed -i '/mkdir -p.*bin\/packages.*base/d' "$TAILSCALE_MK"
sed -i '/\$(CP).*base\/tailscaled/d' "$TAILSCALE_MK"

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

update_release_package() {
  local pkg="$1" repo="$2" mk="net/$1/Makefile"
  local tag version archive hash

  if [ ! -f "$mk" ] || ! grep -Fq "https://codeload.github.com/$repo/tar.gz/" "$mk"; then
    echo "Unexpected source URL for $pkg: $mk" >&2
    return 1
  fi

  tag=$(curl -fsSL --retry 3 "https://api.github.com/repos/$repo/releases/latest" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])') || return 1
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
# cloudflared: update to latest release (tag has no 'v' prefix)
update_release_package cloudflared cloudflare/cloudflared || exit 1

popd

if grep -qx 'CONFIG_PACKAGE_adguardhome-core=y' .config; then
  python3 "$GITHUB_WORKSPACE/scripts/prepare-adguardhome-core.py" || exit 1
fi
