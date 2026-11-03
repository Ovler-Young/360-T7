include $(TOPDIR)/rules.mk
include $(CURDIR)/release.mk

PKG_NAME:=ndisc6
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.bz2
PKG_SOURCE_URL:=https://www.remlab.net/files/ndisc6/
PKG_LICENSE:=GPL-2.0-or-later
PKG_LICENSE_FILES:=COPYING
PKG_INSTALL:=1

include $(INCLUDE_DIR)/package.mk

CONFIGURE_ARGS+=--disable-nls

define Package/ndisc6/Default
  SECTION:=net
  CATEGORY:=Network
  URL:=https://www.remlab.net/ndisc6/
endef

define Package/ndisc6
  $(call Package/ndisc6/Default)
  TITLE:=IPv6 neighbor discovery diagnostics
endef

define Package/rdisc6
  $(call Package/ndisc6/Default)
  TITLE:=IPv6 router discovery diagnostics
endef

define Package/rdnssd
  $(call Package/ndisc6/Default)
  TITLE:=IPv6 recursive DNS server discovery daemon (not auto-enabled)
endef

define Package/traceroute6
  $(call Package/ndisc6/Default)
  TITLE:=IPv6 traceroute diagnostic utilities
endef

define Package/ndisc6/install
  $(INSTALL_DIR) $(1)/usr/bin
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/ndisc6 $(1)/usr/bin/
endef

define Package/rdisc6/install
  $(INSTALL_DIR) $(1)/usr/bin
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/rdisc6 $(1)/usr/bin/
endef

define Package/rdnssd/install
  $(INSTALL_DIR) $(1)/usr/sbin
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/sbin/rdnssd $(1)/usr/sbin/
endef

define Package/traceroute6/install
  $(INSTALL_DIR) $(1)/usr/bin
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/rltraceroute6 $(1)/usr/bin/
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/tracert6 $(1)/usr/bin/
  $(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/tcptraceroute6 $(1)/usr/bin/
endef

$(eval $(call BuildPackage,ndisc6))
$(eval $(call BuildPackage,rdisc6))
$(eval $(call BuildPackage,rdnssd))
$(eval $(call BuildPackage,traceroute6))
