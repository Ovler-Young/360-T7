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
sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile


# Modify filename, add date prefix
sed -i 's|IMG_PREFIX:=|IMG_PREFIX:=$(shell TZ="America/New_York" date +"%Y%m%d")-24.10|' include/image.mk

# Insert lines before the last line in 99-default-settings-chinese. For Modify opkg url, change mt7981 to filogic
sed -i '\|^exit 0$|i sed -i "s,mt7981,filogic,g" /etc/opkg/distfeeds.conf' \
    package/emortal/default-settings/files/99-default-settings-chinese