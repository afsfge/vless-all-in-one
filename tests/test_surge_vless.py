"""Isolated Surge VLESS rendering regression; no services or network calls."""
import json
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
        r = subprocess.run([BASH, '-n'], input=block, text=True, capture_output=True)
        if r.returncode == 0 and not r.stderr:
            return block
    raise AssertionError(name)

base = dict(uuid='00000000-0000-4000-8000-000000000001', sni='example.com')
fixture = {
    'vless': [dict(base, port=443, public_key='test-public-key', short_id='abcd'),
              dict(base, port=444, security_mode='encryption', encryption='mlkem-test'),
              dict(base, port=445, public_key='test-public-key', short_id=''),
              dict(base, port=446)],
    'vless-vision': dict(base, port=8443),
    'vless-ws': dict(base, port=10000, path='/ws'),
    'vless-ws-notls': dict(base, port=10001, path='/plain', host='cdn.example.com'),
    'vless-xhttp': dict(base, port=10002, path='/xhttp'),
}
lib = '\n'.join(function(n) for n in ['gen_surge_sub', '_get_master_port', '_sub_proto_label', '_ip_type_label', '_country_flag'])
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'db.json'
    path.write_text(json.dumps(fixture))
    setup = '''
set -e
get_installed_protocols() { jq -r 'keys[]' "$DB"; }
get_ipv4() { echo 192.0.2.1; }
get_ipv6() { echo 2001:db8::1; }
get_ip_country() { echo US; }
is_snell_protocol() { return 1; }
db_exists() { [[ "$1" == xray ]] && jq -e --arg p "$2" 'has($p)' "$DB" >/dev/null; }
db_get() { jq -c --arg p "$2" '.[$p]' "$DB"; }
db_get_field() { jq -r --arg p "$2" --arg f "$3" '.[$p][$f]' "$DB"; }
'''
    def render(no6=False):
        r = subprocess.run([BASH, '-c', setup + lib + '\ngen_surge_sub '+('no_ipv6' if no6 else '')],
                           env=dict(os.environ, DB=str(path)), text=True, capture_output=True)
        assert r.returncode == 0, r.stderr
        assert not r.stderr, r.stderr
        lines = [l for l in r.stdout.splitlines() if ' = vless,' in l]
        group = next(l for l in r.stdout.splitlines() if l.startswith('Proxy = select,'))
        assert group.split(', ')[1:] == [l.split(' = ')[0] for l in lines]
        assert len(set(l.split(' = ')[0] for l in lines)) == len(lines)
        return lines
    lines = render()
    assert len(lines) == 10, lines
    assert all(re.match(r'^🇺🇸Vless(?:-WS)?-\d+-v[46] = ', l) for l in lines)
    assert any(l.startswith('🇺🇸Vless-443-v4 = ') for l in lines)
    assert any(l.startswith('🇺🇸Vless-443-v6 = ') for l in lines)
    v4 = render(True)
    assert len(v4) == 5 and all('2001:db8' not in l for l in v4)
    assert all('username='+base['uuid'] in l for l in lines)
    assert not any(', 444,' in l or ', 446,' in l or 'xhttp' in l.lower() for l in lines)
    reality = next(l for l in v4 if ', 443,' in l)
    assert 'reality-public-key=test-public-key, reality-short-id=abcd' in reality
    assert 'flow=xtls-rprx-vision' in reality and 'skip-cert-verify' not in reality
    ws = next(l for l in v4 if 'ws-path=/ws' in l)
    assert ', 8443,' in ws and 'ws-headers=Host:example.com' in ws and 'flow=' not in ws
    plain = next(l for l in v4 if 'ws-path=/plain' in l)
    assert 'tls=true' not in plain and 'ws-headers=Host:cdn.example.com' in plain
    fixture.pop('vless-vision')
    path.write_text(json.dumps(fixture))
    assert ', 10000,' in next(l for l in render(True) if 'ws-path=/ws' in l)
print('Surge VLESS regressions passed')
