#!/bin/sh
set -eu

[ "$(uci -q get AdGuardHome.AdGuardHome || :)" = 'AdGuardHome' ] || exit 0
[ "$(uci -q get adguardhome.config.legacy_migrated || :)" != '1' ] || exit 0

source=$(uci -q get AdGuardHome.AdGuardHome.configpath || :)
source=${source:-/etc/AdGuardHome.yaml}
[ -f "$source" ] || exit 1
target=/etc/adguardhome/adguardhome.yaml

# Stop the legacy service before copying its live configuration.
if [ -x /etc/init.d/AdGuardHome ]; then
    /etc/init.d/AdGuardHome stop
    /etc/init.d/AdGuardHome disable
fi

umask 077
mkdir -p /etc/adguardhome
if [ "$source" != "$target" ]; then
    if [ -e "$target" ] && ! cmp -s "$source" "$target"; then
        logger -t adguardhome 'Legacy migration stopped: destination configuration already exists'
        exit 1
    fi
    cp "$source" "$target"
fi

chmod 600 "$target"

uci set adguardhome.config=adguardhome
uci set "adguardhome.config.config_file=$target"
workdir=$(uci -q get AdGuardHome.AdGuardHome.workdir || :)
uci set "adguardhome.config.work_dir=${workdir:-/tmp/AdGuardHome}"
uci set adguardhome.config.user=root
uci set adguardhome.config.group=root
for option in enabled redirect verbose crontab gc maxprocs memlimit; do
    value=$(uci -q get "AdGuardHome.AdGuardHome.$option" || :)
    [ -z "$value" ] || uci set "adguardhome.config.$option=$value"
done
uci -q delete adguardhome.config.config || :
uci -q delete adguardhome.config.workdir || :
uci commit adguardhome
/etc/init.d/adguardhome enable
# Remove the superseded service only after its replacement is configured.
rm -f /etc/init.d/AdGuardHome
uci set adguardhome.config.legacy_migrated=1
uci commit adguardhome

exit 0
