#!/usr/bin/env bash
# ============================================================
#  服务器重装后初始化脚本
#  用法: bash init-server.sh
# ============================================================
set -euo pipefail

# ---------- 颜色 / 工具函数 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }
section() { echo -e "\n${YELLOW}══════════════════════════════════════${NC}"; \
            echo -e "${YELLOW}  $*${NC}"; \
            echo -e "${YELLOW}══════════════════════════════════════${NC}"; }

# ---------- 需要 root / sudo ----------
[[ $EUID -eq 0 ]] || die "请以 root 身份运行，或在命令前加 sudo"

# ============================================================
# 阶段 1：更新系统软件包
# ============================================================
section "阶段 1/5：更新系统软件包"
info "执行 apt update ..."
apt update -y
info "执行 apt upgrade ..."
apt upgrade -y
success "系统软件包更新完成"

# ============================================================
# 阶段 2：安装基础工具
# ============================================================
section "阶段 2/5：安装基础工具"
PACKAGES="sudo curl wget nano vim"
info "安装: $PACKAGES"
apt install $PACKAGES -y
success "基础工具安装完成"

# ============================================================
# 阶段 3：设置时区
# ============================================================
section "阶段 3/5：设置时区为 Asia/Shanghai"
timedatectl set-timezone Asia/Shanghai
CURRENT_TZ=$(timedatectl show -p Timezone --value)
success "时区已设置为: $CURRENT_TZ"

# ============================================================
# 阶段 4：启用 BBR 拥塞控制
# ============================================================
section "阶段 4/5：启用 BBR TCP 拥塞控制"
BBR_CONF="/etc/sysctl.d/yuju-bbr.conf"
info "写入 sysctl 配置: $BBR_CONF"
cat > "$BBR_CONF" << 'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
sysctl -p "$BBR_CONF"
# 验证是否生效
CC=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || true)
if [[ "$CC" == "bbr" ]]; then
    success "BBR 已启用 (tcp_congestion_control=$CC)"
else
    warn "BBR 配置已写入，但当前内核可能需要重启后生效 (当前: $CC)"
fi

# ============================================================
# 阶段 5：修改 SSH 监听端口
# ============================================================
section "阶段 5/5：修改 SSH 端口为 51120"
SSH_CFG="/etc/ssh/sshd_config"
info "备份 sshd_config -> ${SSH_CFG}.bak"
cp "$SSH_CFG" "${SSH_CFG}.bak"
sed -i 's/^#\?Port 22.*/Port 51120/g' "$SSH_CFG"
# 验证修改结果
ACTUAL_PORT=$(grep -E '^Port ' "$SSH_CFG" | awk '{print $2}')
info "配置文件中的 Port 值: $ACTUAL_PORT"
info "重启 sshd 服务 ..."
systemctl restart sshd
success "SSH 端口已更改为 51120，sshd 已重启"

# ============================================================
# 完成
# ============================================================
section "初始化完成 🎉"
echo -e "  时区    : $(timedatectl show -p Timezone --value)"
echo -e "  BBR     : $(sysctl -n net.ipv4.tcp_congestion_control)"
echo -e "  SSH端口 : $(grep -E '^Port ' /etc/ssh/sshd_config | awk '{print $2}')"
echo ""
warn "⚠️  请确保防火墙/安全组已放行 TCP 51120，再关闭当前 SSH 会话！"
