include $(TOPDIR)/rules.mk
include $(CURDIR)/release.mk

PKG_NAME:=wrtbwmon
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/pyrovski/wrtbwmon/tar.gz/refs/tags/$(PKG_SOURCE_TAG)?
PKG_BUILD_DIR:=$(BUILD_DIR)/wrtbwmon-$(PKG_SOURCE_TAG)
PKG_LICENSE:=GPL-2.0-or-later
PKG_LICENSE_FILES:=copyright
PKG_ARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/wrtbwmon
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Per-host bandwidth monitoring (iptables compatibility)
  URL:=https://github.com/pyrovski/wrtbwmon
  DEPENDS:=+iptables-nft
endef

define Build/Compile
endef

define Package/wrtbwmon/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/usr/share/wrtbwmon $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/wrtbwmon $(1)/usr/sbin/
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/readDB.awk $(1)/usr/sbin/
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/usage.htm1 $(1)/usr/share/wrtbwmon/
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/usage.htm2 $(1)/usr/share/wrtbwmon/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/init/wrtbwmon $(1)/etc/init.d/
endef

$(eval $(call BuildPackage,wrtbwmon))
