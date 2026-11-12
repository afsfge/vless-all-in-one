# vless-all-in-one

## Quick Install

```bash
wget -O vless-server.sh https://raw.githubusercontent.com/afsfge/vless-all-in-one/main/vless-server.sh && chmod +x vless-server.sh && ./vless-server.sh
```

## 服务器初始化

重装系统后，一键完成：系统更新、安装基础工具、设置时区（Asia/Shanghai）、启用 BBR、修改 SSH 端口

```bash
bash <(wget -qO- https://raw.githubusercontent.com/afsfge/vless-all-in-one/main/init-server.sh)
```

## Surge VLESS subscriptions

Requires Surge iOS 6.0.0+ or Mac 6.12.0+. Generated subscriptions now include
REALITY + Vision, TLS + Vision, WebSocket + TLS (including the public fallback
port), and plain WebSocket VLESS nodes. Surge names use flag + protocol + configured port + v4/v6, e.g.
`🇺🇸Vless-47018-v4`; ordinary Snell nodes retain their IPv6 setting suffix. XHTTP and VLESS Encryption remain excluded. TLS nodes retain
the existing share-link certificate-verification behavior; REALITY uses its
public key and short ID. Regenerate server subscriptions after updating the
script, then refresh Surge.

Specification: https://manual.nssurge.com/policies/vless.html

Test: `python3 tests/test_surge_vless.py` (Bash 4+, jq).
