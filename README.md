# vless-all-in-one

## Quick Install

```bash
wget -O vless-server.sh https://raw.githubusercontent.com/afsfge/vless-all-in-one/main/vless-server.sh && chmod +x vless-server.sh && ./vless-server.sh
```

## 服务器初始化

重装系统后，一键完成：系统更新、安装基础工具、设置时区（Asia/Shanghai）、启用 BBR、修改 SSH 端口为 51120。

```bash
bash <(wget -qO- https://raw.githubusercontent.com/afsfge/vless-all-in-one/main/init-server.sh)
```
