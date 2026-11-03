include $(TOPDIR)/rules.mk

# Generated from the current public release during firmware preparation.
include $(CURDIR)/release.mk

PKG_NAME:=adguardhome-core
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION)-linux-arm64.tar.gz
PKG_SOURCE_URL:=$(ADGUARDHOME_SOURCE_URL)
PKG_SOURCE_URL_FILE:=AdGuardHome_linux_arm64.tar.gz
PKG_LICENSE:=GPL-3.0-only
PKG_LICENSE_FILES:=AdGuardHome/LICENSE.txt

include $(INCLUDE_DIR)/package.mk

define Package/adguardhome-core
  SECTION:=net
  CATEGORY:=Network
  TITLE:=AdGuard Home binary for the existing LuCI service
  URL:=https://github.com/AdguardTeam/AdGuardHome
  DEPENDS:=@aarch64 +ca-bundle
  CONFLICTS:=adguardhome
endef

define Package/adguardhome-core/description
  The upstream ARM64 binary only. Configuration and service management are
  provided by luci-app-adguardhome; no second init script is installed.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(TAR) -xzf $(DL_DIR)/$(PKG_SOURCE) -C $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/adguardhome-core/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/AdGuardHome/AdGuardHome $(1)/usr/bin/AdGuardHome
endef

$(eval $(call BuildPackage,adguardhome-core))
