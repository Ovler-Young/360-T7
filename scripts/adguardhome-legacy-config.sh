#!/bin/sh
set -eu

[ "$(uci -q get AdGuardHome.AdGuardHome || :)" = 'AdGuardHome' ] || exit 0
[ "$(uci -q get adguardhome.config.legacy_migrated || :)" != '1' ] || exit 0

source=$(uci -q get AdGuardHome.AdGuardHome.configpath || :)
source=${source:-/etc/AdGuardHome.yaml}
[ -f "$source" ] || exit 1
target=/etc/adguardhome/adguardhome.yaml

# Reject conflicts before changing either service.
[ -r "$source" ] || exit 1
[ -x /etc/init.d/adguardhome ] || exit 1
if [ "$source" != "$target" ] && [ -e "$target" ] && ! cmp -s "$source" "$target"; then
    logger -t adguardhome 'Legacy migration stopped: destination configuration already exists'
    exit 1
fi

umask 077
mkdir -p /etc/adguardhome
legacy_enabled=0
legacy_running=0
replacement_enabled=0
legacy_stopped=0
success=0
/etc/init.d/adguardhome enabled && replacement_enabled=1
if [ -x /etc/init.d/AdGuardHome ]; then
    /etc/init.d/AdGuardHome enabled && legacy_enabled=1
    /etc/init.d/AdGuardHome running && legacy_running=1
fi
rollback() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$success" != 1 ]; then
        /etc/init.d/adguardhome stop || :
        if [ "$replacement_enabled" = 0 ]; then
            /etc/init.d/adguardhome disable || :
        fi
        uci -q delete adguardhome.config.legacy_migrated || :
        uci commit adguardhome || :
        if [ "$legacy_stopped" = 1 ]; then
            if [ "$legacy_enabled" = 1 ]; then
                /etc/init.d/AdGuardHome enable || :
            fi
            if [ "$legacy_running" = 1 ]; then
                /etc/init.d/AdGuardHome start || :
            fi
        fi
    fi
    exit "$status"
}
trap rollback EXIT
trap 'exit 1' HUP INT TERM
# Check that the replacement can be enabled before interrupting legacy DNS.
/etc/init.d/adguardhome enable
if [ -x /etc/init.d/AdGuardHome ]; then
    legacy_stopped=1
    /etc/init.d/AdGuardHome stop
    /etc/init.d/AdGuardHome disable
fi

if [ "$source" != "$target" ]; then
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
/etc/init.d/adguardhome start
/etc/init.d/adguardhome running
# Keep the disabled legacy service and its configuration available for recovery.
uci set adguardhome.config.legacy_migrated=1
uci commit adguardhome
success=1

exit 0
