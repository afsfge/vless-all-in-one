# vless-all-in-one

## 快速安装

```bash
wget -O vless-server.sh https://raw.githubusercontent.com/afsfge/vless-all-in-one/main/vless-server.sh && chmod +x vless-server.sh && ./vless-server.sh
```

## Snell 多实例

普通 Snell v4/v5/v6 支持同版本部署多个独立端口。再次选择已安装的 Snell 版本时，选择「添加新端口实例」或「覆盖现有端口」；卸载时可以选择单个端口或全部端口。ShadowTLS 组合协议仍沿用原来的单实例管理。

- 每个实例有独立配置、PSK、服务和分享信息，同版本共享二进制。
- 新实例文件通常为 `/etc/vless-reality/snell-v6-<端口>.conf`，对应 `vless-snell-v6-<端口>.service`（v4/v5 同理）。覆盖实例时保留原文件名；名称冲突时添加数字后缀。实际名称记录在 `db.json` 的 `instance` 字段中。
- 旧配置无需迁移：无 `instance` 字段的记录继续使用原配置和服务名。新增节点不会重写旧节点配置。
- 服务状态和日志支持区分实例；普通 Snell 节点名格式为 `🇺🇸S6-21279-v4-off`：国旗、协议版本、端口、入口地址类型、配置中的 `ipv6` 值（true 为 on，false 为 off，未配置为 auto，文件缺失或值异常为 unknown）。生成订阅时读取各实例实际配置；手动修改后需要重新生成订阅，再让客户端刷新。末尾只表示配置值，`dns-ip-preference` 可能覆盖其实际行为。更新订阅后，按名称引用旧节点的客户端规则需同步调整。
- 内核升级处理该版本所有运行中的实例；IP 地址选择逻辑保持原样。

本地回归测试（Python 3、Bash 4+、jq）：

```bash
python3 tests/test_snell_instances.py
# macOS 若 PATH 中仍是系统 Bash，可指定：
BASH_BIN=/usr/local/bin/bash python3 tests/test_snell_instances.py
```

测试使用临时目录和模拟服务管理命令，不安装服务或连接生产服务器。

Surge 订阅按 IPv4 入口、IPv6 入口分组，各组内 Snell v6/v5/v4 优先；同一普通 Snell 协议内按 `on → off → auto/unknown` 排列，相同状态保留实例原顺序。节点定义与策略组使用相同顺序。
