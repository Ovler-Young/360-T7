include $(TOPDIR)/rules.mk
include $(CURDIR)/release.mk

PKG_NAME:=cloudflared
PKG_RELEASE:=1
PKG_SOURCE:=cloudflared-prebuilt-$(PKG_VERSION)-linux-arm64
PKG_SOURCE_URL:=$(CLOUDFLARED_SOURCE_URL)
PKG_SOURCE_URL_FILE:=$(CLOUDFLARED_SOURCE_FILE)
PKG_LICENSE:=Apache-2.0

include $(INCLUDE_DIR)/package.mk

define Package/cloudflared
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=Web Servers/Proxies
  TITLE:=Cloudflare Tunnel client
  URL:=https://github.com/cloudflare/cloudflared
  DEPENDS:=@aarch64 +ca-bundle
endef

define Package/cloudflared/conffiles
/etc/config/cloudflared
/etc/cloudflared/
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) $(DL_DIR)/$(PKG_SOURCE) $(PKG_BUILD_DIR)/cloudflared
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/cloudflared/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/cloudflared $(1)/usr/bin/cloudflared
	$(INSTALL_DIR) $(1)/etc/cloudflared/
	$(INSTALL_CONF) $(CURDIR)/files/sample_config.yml $(1)/etc/cloudflared/config.yml
	$(INSTALL_DIR) $(1)/etc/config/
	$(INSTALL_CONF) $(CURDIR)/files/cloudflared.config $(1)/etc/config/cloudflared
	$(INSTALL_DIR) $(1)/etc/init.d/
	$(INSTALL_BIN) $(CURDIR)/files/cloudflared.init $(1)/etc/init.d/cloudflared
endef

$(eval $(call BuildPackage,cloudflared))
