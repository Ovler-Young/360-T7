include $(TOPDIR)/rules.mk
include $(CURDIR)/release.mk

PKG_NAME:=adguardhome-core
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/AdguardTeam/AdGuardHome/tar.gz/v$(PKG_VERSION)?
PKG_BUILD_DIR:=$(BUILD_DIR)/AdGuardHome-$(PKG_VERSION)

FRONTEND_DEST:=$(PKG_NAME)-frontend-$(PKG_VERSION).tar.gz
FRONTEND_URL:=https://github.com/AdguardTeam/AdGuardHome/releases/download/v$(PKG_VERSION)/

PKG_LICENSE:=GPL-3.0-only
PKG_LICENSE_FILES:=LICENSE.txt
PKG_BUILD_DEPENDS:=golang/host
PKG_BUILD_PARALLEL:=1
PKG_BUILD_FLAGS:=no-mips16

GO_PKG:=github.com/AdguardTeam/AdGuardHome
GO_PKG_BUILD_PKG:=$(GO_PKG)
GO_PKG_LDFLAGS_X:= \
	$(GO_PKG)/internal/version.channel=release \
	$(GO_PKG)/internal/version.version=v$(PKG_VERSION) \
	$(GO_PKG)/internal/version.committime=$(SOURCE_DATE_EPOCH) \
	$(GO_PKG)/internal/version.goarm=$(GO_ARM) \
	$(GO_PKG)/internal/version.gomips=$(GO_MIPS)

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/golang/golang-package.mk

define Package/adguardhome-core
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Source-built AdGuard Home core for the existing LuCI service
  URL:=https://github.com/AdguardTeam/AdGuardHome
  DEPENDS:=$(GO_ARCH_DEPENDS) +ca-bundle
  CONFLICTS:=adguardhome
endef

define Package/adguardhome-core/description
  AdGuard Home built with the supported Go toolchain. The OneNAS LuCI
  package provides configuration and service management; this core does
  not install another init script.
endef

define Download/adguardhome-core-frontend
	URL:=$(FRONTEND_URL)
	URL_FILE:=AdGuardHome_frontend.tar.gz
	FILE:=$(FRONTEND_DEST)
	HASH:=$(FRONTEND_HASH)
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	gzip -dc $(DL_DIR)/$(FRONTEND_DEST) | $(HOST_TAR) -C $(PKG_BUILD_DIR)/ $(TAR_OPTIONS)
endef

define Package/adguardhome-core/install
	$(call GoPackage/Package/Install/Bin,$(1))
endef

$(eval $(call Download,adguardhome-core-frontend))
$(eval $(call GoBinPackage,adguardhome-core))
$(eval $(call BuildPackage,adguardhome-core))
