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

# Modify default IP
sed -i 's/192.168.6.1/192.168.10.1/g' package/base-files/files/bin/config_generate

# Modify hostname
sed -i 's/ImmortalWrt/ImmortalWrt-24.10-$(shell TZ="America/New_York" date +"%Y%m%d")/g' package/base-files/files/bin/config_generate

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
git -C package clone https://github.com/tokisaki-galaxy/luci-app-tailscale-community package/luci-app-tailscale-community 