"""Run isolated Snell regressions: python3 tests/test_snell_instances.py (Bash >= 4, jq)."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'vless-server.sh').read_text()
BASH = os.environ.get('BASH_BIN') or shutil.which('bash')


def function(name):
    start = re.search(r'^' + re.escape(name) + r'\(\).*\{', SOURCE, re.M).start()
    for end in re.finditer(r'^}\s*$', SOURCE[start:], re.M):
        block = SOURCE[start:start + end.end()] + '\n'
        check = subprocess.run([BASH, '-n'], input=block, text=True, capture_output=True)
        if check.returncode == 0 and not check.stderr:
            return block
    raise AssertionError(f'Cannot extract {name}')


NAMES = '''init_db _db_touch _db_apply db_add db_get db_get_field db_list_ports
 db_get_port_config db_add_port db_remove_port db_update_port db_del db_exists
 db_list_protocols db_get_all_protocols register_protocol is_protocol_installed get_installed_protocols
 is_snell_protocol snell_instance_names snell_service_names snell_active_services
 _write_snell_instance remove_snell_instance build_config gen_snell_server_config
 gen_snell_v5_server_config gen_snell_v6_server_config create_service svc _svc_one
 _country_flag snell_node_name _country_prefix _sub_proto_label _ip_type_label gen_snell_link gen_surge_sub
 create_server_scripts update_snell_v5_core update_snell_v6_core
 handle_existing_protocol select_port_to_uninstall check_port_conflict'''.split()

with tempfile.TemporaryDirectory(prefix='snell-test-') as directory:
    path = Path(directory)
    library = '\n'.join(function(n) for n in NAMES)
    # Redirect all service artifacts in the extracted functions to the sandbox.
    for target in ('/etc/systemd/system', '/etc/init.d', '/run'):
        library = library.replace(target, directory + target)
        (path / target.lstrip('/')).mkdir(parents=True, exist_ok=True)
    declarations = SOURCE[SOURCE.index('declare -A PROTO_SVC'):SOURCE.index('# 普通 Snell 按端口')]
    script = r'''
set -e
[[ ${BASH_VERSINFO[0]} -ge 4 ]]
CFG="$1/config"; DB_FILE="$CFG/db.json"; DISTRO=debian
mkdir -p "$CFG"
SINGBOX_PROTOCOLS='hy2 tuic anytls'; XRAY_PROTOCOLS='vless'
_err() { echo "$*" >&2; }; _info() { :; }; _ok() { :; }; _warn() { :; }
get_ipv4() { echo 192.0.2.1; }; get_ipv6() { :; }
get_ip_country() { echo US; }
_has_ipv6() { return 1; }; _listen_addr() { echo 0.0.0.0; }
_fmt_hostport() { echo "$1:$2"; }
_save_join_info() { printf 'test join\n' > "$CFG/$1.join"; }
'''
    script += library + '\n' + declarations + r'''
# Fake service manager tracks individual units, without touching the host.
systemctl() {
    echo "$*" >> "$CFG/service.log"
    case "$1" in
        is-active) [[ -f "$CFG/running-${@: -1}" ]] && echo active ;;
        start|restart) touch "$CFG/running-$2" ;;
        stop) rm -f "$CFG/running-$2" ;;
        *) return 0 ;;
    esac
}
rc-service() {
    case "$2" in
        status) [[ -f "$CFG/running-$1" ]] ;;
        start|restart) touch "$CFG/running-$1" ;;
        stop) rm -f "$CFG/running-$1" ;;
    esac
}
rc-update() { :; }
init_db
for proto in snell snell-v5 snell-v6; do
    case "$proto" in
        snell) generator=gen_snell_server_config; version=4 ;;
        snell-v5) generator=gen_snell_v5_server_config; version=5 ;;
        snell-v6) generator=gen_snell_v6_server_config; version=6 ;;
    esac
    # Legacy object + user edits must survive adding another instance.
    db_add xray "$proto" "{\"port\":3000,\"psk\":\"legacy-test-key\",\"version\":$version}"
    echo 'user configuration' > "$CFG/$proto.conf"
    INSTALL_MODE=add
    "$generator" test-key-12345678 3001 "$version"
    [[ $(db_list_ports xray "$proto" | wc -l) -eq 2 ]]
    handle_existing_protocol "$proto" xray <<< '1'
    [[ "$INSTALL_MODE" == add ]]
    handle_existing_protocol "$proto" xray <<< $'2\n1'
    [[ "$INSTALL_MODE" == replace && "$REPLACE_PORT" == 3000 ]]
    select_port_to_uninstall "$proto" <<< '2'
    [[ "$SELECTED_PORT" == 3001 ]]
    select_port_to_uninstall "$proto" <<< '3'
    [[ "$SELECTED_PORT" == all ]]
    unset INSTALL_MODE REPLACE_PORT
    db_add xray vless '{"port":9000}'
    if (check_port_conflict 9000 "$proto" xray); then exit 1; fi
    (check_port_conflict 9001 "$proto" xray)
    db_del xray vless
    [[ $(cat "$CFG/$proto.conf") == 'user configuration' ]]
    grep -q '3001' "$CFG/$proto-3001.conf"
    if "$generator" duplicate-test-key 3001 "$version"; then exit 1; fi
    # Cover a legacy instance with a changed port, preserving its service identity.
    INSTALL_MODE=replace; REPLACE_PORT=3000
    "$generator" replacement-test-key 3002 "$version"
    [[ $(db_get_port_config xray "$proto" 3002 | jq -r .instance) == "$proto" ]]
    # Cover a new instance, then re-add its original port (must not overwrite it).
    INSTALL_MODE=replace; REPLACE_PORT=3001
    "$generator" changed-test-key 3003 "$version"
    INSTALL_MODE=add
    "$generator" additional-test-key 3001 "$version"
    grep -q '3003' "$CFG/$proto-3001.conf"
    grep -q '3001' "$CFG/$proto-3001-1.conf"
    create_service "$proto"
    grep -q "$proto-3001.conf" "$1/etc/systemd/system/vless-$proto-3001.service"
    svc start "vless-$proto"
    svc status "vless-$proto"
    _svc_one stop "vless-$proto-3001"
    if svc status "vless-$proto"; then exit 1; fi
    [[ $(snell_active_services "$proto" | wc -l) -eq 2 ]]
    svc stop "vless-$proto"
    # Failed registration must leave both DB and config unchanged.
    cp "$DB_FILE" "$CFG/before.json"
    original=$(declare -f register_protocol)
    register_protocol() { return 1; }
    INSTALL_MODE=replace; REPLACE_PORT=3003
    if "$generator" failing-test-key 3003 "$version"; then exit 1; fi
    cmp "$DB_FILE" "$CFG/before.json"
    grep -q 'changed-test-key' "$CFG/$proto-3001.conf"
    eval "$original"; unset INSTALL_MODE REPLACE_PORT
    # Names read the actual instance file, including legacy and renamed instances.
    [[ $(snell_node_name 192.0.2.1 3003 "$version" US) == "🇺🇸S$version-3003-v4-off" ]]
    printf '[snell-server]\r\n ipv6 = TRUE # manual edit\r\n[other]\nipv6=false\n' > "$CFG/$proto-3001.conf"
    [[ $(snell_node_name '[2001:db8::1]' 3003 "$version" US) == "🇺🇸S$version-3003-v6-on" ]]
    [[ $(gen_snell_link 192.0.2.1 3003 test "$version" US) == *"#🇺🇸S$version-3003-v4-on" ]]
    printf '[snell-server]\n# ipv6 = true\n' > "$CFG/$proto-3001.conf"
    [[ $(snell_node_name 192.0.2.1 3003 "$version" '') == "S$version-3003-v4-auto" ]]
    printf '[snell-server]\nipv6=invalid\n' > "$CFG/$proto-3001.conf"
    [[ $(snell_node_name 192.0.2.1 3003 "$version" US) == *-unknown ]]
    rm "$CFG/$proto-3001.conf"
    [[ $(snell_node_name 192.0.2.1 3003 "$version" US) == *-unknown ]]
    printf '[snell-server]\nipv6=true\ndns-ip-preference=ipv4-only\n' > "$CFG/$proto-3001.conf"
    [[ $(snell_node_name 192.0.2.1 3003 "$version" US) == *-on ]]
    # Subscriptions must retain every port under distinct names.
    gen_surge_sub > "$CFG/sub.conf"
    grep -q "🇺🇸S$version-3003-v4-on = snell," "$CFG/sub.conf"
    expected="🇺🇸S$version-3003-v4-on, 🇺🇸S$version-3002-v4-off, 🇺🇸S$version-3001-v4-off"
    grep -Fxq "Proxy = select, $expected" "$CFG/sub.conf"
    actual=$(grep ' = snell,' "$CFG/sub.conf" | cut -d' ' -f1 | paste -sd, -)
    [[ "$actual" == "${expected//, /,}" ]]
    # Unknown fields sort last; the same ordering applies independently to IPv6.
    mv "$CFG/$proto.conf" "$CFG/legacy-backup"
    get_ipv6() { echo 2001:db8::1; }
    gen_surge_sub > "$CFG/dual-sub.conf"
    expected="🇺🇸S$version-3003-v4-on, 🇺🇸S$version-3001-v4-off, 🇺🇸S$version-3002-v4-unknown, 🇺🇸S$version-3003-v6-on, 🇺🇸S$version-3001-v6-off, 🇺🇸S$version-3002-v6-unknown"
    grep -Fxq "Proxy = select, $expected" "$CFG/dual-sub.conf"
    get_ipv6() { :; }
    mv "$CFG/legacy-backup" "$CFG/$proto.conf"
    for port in 3001 3002 3003; do grep -q ", $port, psk=" "$CFG/sub.conf"; done
    [[ $(sed -n '/^\[Proxy\]$/,/^\[Proxy Group\]$/p' "$CFG/sub.conf" | grep ' = snell,' | cut -d= -f1 | sort | uniq -d | wc -l) -eq 0 ]]
    DISTRO=alpine
    create_service "$proto"
    grep -q "$proto-3001.conf" "$1/etc/init.d/vless-$proto-3001"
    DISTRO=debian
    remove_snell_instance "$proto" 3003
    [[ ! -f "$CFG/$proto-3001.conf" ]]
    [[ -f "$CFG/$proto-3001-1.conf" && -f "$CFG/$proto.conf" ]]
    [[ $(db_list_ports xray "$proto" | wc -l) -eq 2 ]]
    remove_snell_instance "$proto" 3001
    remove_snell_instance "$proto" 3002
    if db_exists xray "$proto"; then exit 1; fi
done
# A failed final rename must also roll back registration.
original_mv=$(command -v mv)
mv() { [[ "$2" == "$CFG/snell-v6-4000.conf" ]] && return 1; "$original_mv" "$@"; }
if gen_snell_v6_server_config failed-rename-key 4000 6; then exit 1; fi
if db_exists xray snell-v6; then exit 1; fi
unset -f mv
# Upgrade a partially stopped group: restore exactly the previously active instances.
_check_core_update_deps() { :; }; _confirm_core_update() { :; }
check_cmd() { :; }; _get_snell_v5_version() { :; }; _get_snell_v6_version() { :; }
for version in 5 6; do
    proto="snell-v$version"
    "gen_snell_v${version}_server_config" upgrade-test-key 5000 "$version"
    INSTALL_MODE=add
    "gen_snell_v${version}_server_config" upgrade-test-key 5001 "$version"
    _svc_one start "vless-$proto-5000"
    eval "install_snell_v$version() { [[ ! -f \"\$CFG/running-vless-$proto-5000\" ]]; }"
    "update_snell_v${version}_core"
    [[ -f "$CFG/running-vless-$proto-5000" && ! -f "$CFG/running-vless-$proto-5001" ]]
done
create_server_scripts
bash -n "$CFG/watchdog.sh"
# Inspect the generated monitor's own service discovery, without running its loop.
eval "$(sed -n '/^get_all_services() {/,/^log "INFO: Watchdog 启动"/p' "$CFG/watchdog.sh" | sed '$d')"
services=$(get_all_services)
[[ "$services" == *vless-snell-v6-5000:snell-server-v6* ]]
[[ "$services" == *vless-snell-v6-5001:snell-server-v6* ]]
echo 'PASS: Snell v4/v5/v6 legacy/add/replace/delete, isolation, rollback, subscriptions, systemd/OpenRC, upgrades, watchdog'
'''
    runner = path / 'run.sh'
    runner.write_text(script)
    subprocess.run([BASH, str(runner), directory], check=True)
