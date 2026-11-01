#!/bin/sh
set -eu

[ "$(uci -q get AdGuardHome.AdGuardHome || :)" = 'AdGuardHome' ] || exit 0
[ "$(uci -q get adguardhome.config.legacy_migrated || :)" != '1' ] || exit 0
[ "$(uci -q get adguardhome.config.enabled || :)" != '1' ] || exit 0

source=$(uci -q get AdGuardHome.AdGuardHome.configpath || :)
source=${source:-/etc/AdGuardHome.yaml}
[ -f "$source" ] || exit 1
target=/etc/adguardhome/adguardhome.yaml

umask 077
mkdir -p /etc/adguardhome
if [ "$source" != "$target" ]; then
    if [ -e "$target" ] && ! cmp -s "$source" "$target"; then
        logger -t adguardhome 'Legacy migration stopped: destination configuration already exists'
        exit 1
    fi
    cp -p "$source" "$target"
fi

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
uci set adguardhome.config.legacy_migrated=1
uci commit adguardhome
/etc/init.d/adguardhome enable

exit 0
