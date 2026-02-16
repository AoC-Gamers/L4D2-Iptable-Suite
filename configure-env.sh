#!/bin/bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_file="${1:-$project_root/.env}"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RESET='\033[0m'
    C_BOLD='\033[1m'
    C_CYAN='\033[36m'
    C_GREEN='\033[32m'
    C_YELLOW='\033[33m'
else
    C_RESET=''
    C_BOLD=''
    C_CYAN=''
    C_GREEN=''
    C_YELLOW=''
fi

say_section() {
    echo >&2
    echo -e "${C_BOLD}${C_CYAN}== $1 ==${C_RESET}" >&2
}

say_info() {
    echo -e "${C_GREEN}INFO:${C_RESET} $1" >&2
}

say_hint() {
    echo -e "${C_YELLOW}Hint:${C_RESET} $1" >&2
}

say_warn() {
    echo -e "${C_YELLOW}WARNING:${C_RESET} $1" >&2
}

is_typechain() {
    case "$1" in
        0|1|2) return 0 ;;
        *) return 1 ;;
    esac
}

is_bool() {
    case "${1,,}" in
        true|false) return 0 ;;
        *) return 1 ;;
    esac
}

is_required_ports_expr() {
    [[ "$1" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]
}

is_optional_ports_expr() {
    [ -z "$1" ] && return 0
    is_required_ports_expr "$1"
}

is_cmd_limit() {
    [[ "$1" =~ ^[0-9]+$ ]] || return 1
    [ "$1" -ge 10 ] && [ "$1" -le 10000 ]
}

is_port_number() {
    [[ "$1" =~ ^[0-9]+$ ]] || return 1
    [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

is_ipv4_cidr() {
    local cidr="$1"
    local ip prefix
    local a b c d

    [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] || return 1
    ip="${cidr%/*}"
    prefix="${cidr#*/}"

    IFS='.' read -r a b c d <<< "$ip"
    for octet in "$a" "$b" "$c" "$d"; do
        [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
    done

    [ "$prefix" -ge 0 ] && [ "$prefix" -le 32 ]
}

is_interface_name() {
    [[ "$1" =~ ^[a-zA-Z0-9._:+-]+$ ]]
}

ask() {
    local prompt="$1"
    local default="$2"
    local value
    read -r -p "$prompt [$default]: " value
    if [ -z "$value" ]; then
        value="$default"
    fi
    echo "$value"
}

ask_validated() {
    local prompt="$1"
    local default="$2"
    local validator="$3"
    local error_text="$4"
    local value

    while true; do
        value="$(ask "$prompt" "$default")"
        if "$validator" "$value"; then
            echo "$value"
            return 0
        fi
        say_warn "$error_text"
    done
}

ask_with_context() {
    local title="$1"
    local context="$2"
    local source_doc="$3"
    local prompt="$4"
    local default="$5"
    local validator="$6"
    local error_text="$7"

    echo >&2
    echo -e "${C_BOLD}$title${C_RESET}" >&2
    say_hint "$context"
    say_hint "Fuente: $source_doc"
    ask_validated "$prompt" "$default" "$validator" "$error_text"
}

echo -e "${C_BOLD}${C_CYAN}=== L4D2 Env Wizard (MVP) ===${C_RESET}" >&2
say_info "Este asistente genera .env usando el contexto documentado en docs/modules/*.md"

say_section "Backend y alcance"
typechain="$(ask_with_context \
    "TYPECHAIN" \
    "0=input host, 1=docker-user (contenedores), 2=ambos." \
    "docs/modules/12_ip_00_chain_setup.md" \
    "TYPECHAIN (0=input, 1=docker-user, 2=both)" \
    "0" \
    "is_typechain" \
    "TYPECHAIN debe ser 0, 1 o 2.")"

say_section "Servicios de juego (UDP base)"
game_ports="$(ask_with_context \
    "GAMESERVERPORTS" \
    "Puertos UDP principales del GameServer." \
    "docs/modules/19_ip_50_udp_base.md" \
    "GAMESERVERPORTS (ej: 27015 o 27015:27020)" \
    "27015" \
    "is_required_ports_expr" \
    "Formato inválido. Usa puertos/rangos separados por coma (ej: 27015 o 27015:27020).")"

tv_ports="$(ask_with_context \
    "TVSERVERPORTS" \
    "Puertos SourceTV/separados para espectadores." \
    "docs/modules/19_ip_50_udp_base.md" \
    "TVSERVERPORTS (ej: 27020 o 27115:27120)" \
    "27020" \
    "is_required_ports_expr" \
    "Formato inválido. Usa puertos/rangos separados por coma (ej: 27020 o 27115:27120).")"

cmd_limit="$(ask_with_context \
    "CMD_LIMIT" \
    "Controla los límites dinámicos de UDP; recomendado según tickrate." \
    "docs/modules/19_ip_50_udp_base.md" \
    "CMD_LIMIT" \
    "100" \
    "is_cmd_limit" \
    "CMD_LIMIT debe ser numérico entre 10 y 10000.")"

say_section "Acceso y protección TCP"
ssh_ports="$(ask_with_context \
    "SSH_PORT" \
    "Puertos SSH permitidos; admite lista/rango." \
    "docs/modules/18_ip_40_tcp_ssh.md" \
    "SSH_PORT (ej: 22 o 423,4230:4239)" \
    "22" \
    "is_required_ports_expr" \
    "Formato inválido para SSH_PORT.")"

whitelist="$(ask_with_context \
    "WHITELISTED_IPS" \
    "IPs de confianza (separadas por espacio), sin rate limits." \
    "docs/modules/14_ip_10_whitelist.md" \
    "WHITELISTED_IPS (espacio separado)" \
    "" \
    "true" \
    "")"

udp_allow="$(ask_with_context \
    "UDP_ALLOW_PORTS" \
    "Excepciones UDP adicionales (opcional)." \
    "docs/modules/15_ip_20_allowlist_ports.md" \
    "UDP_ALLOW_PORTS (comma/range, optional)" \
    "" \
    "is_optional_ports_expr" \
    "Formato inválido para UDP_ALLOW_PORTS.")"

tcp_allow="$(ask_with_context \
    "TCP_ALLOW_PORTS" \
    "Excepciones TCP adicionales (opcional)." \
    "docs/modules/15_ip_20_allowlist_ports.md" \
    "TCP_ALLOW_PORTS (comma/range, optional)" \
    "" \
    "is_optional_ports_expr" \
    "Formato inválido para TCP_ALLOW_PORTS.")"

enable_tcp_protect_raw="$(ask_with_context \
    "ENABLE_TCP_PROTECT" \
    "Activa bloqueo/protección anti-spam TCP (RCON)." \
    "docs/modules/18_ip_40_tcp_ssh.md" \
    "ENABLE_TCP_PROTECT (true/false)" \
    "true" \
    "is_bool" \
    "ENABLE_TCP_PROTECT debe ser true o false.")"
enable_tcp_protect="${enable_tcp_protect_raw,,}"

say_section "OpenVPN"
vpn_enabled_raw="$(ask_with_context \
    "VPN_ENABLED" \
    "Habilita reglas OpenVPN (host/gateway)." \
    "docs/modules/16_ip_30_openvpn.md" \
    "VPN_ENABLED (true/false)" \
    "false" \
    "is_bool" \
    "VPN_ENABLED debe ser true o false.")"
vpn_enabled="${vpn_enabled_raw,,}"

vpn_port="1194"
vpn_subnet="10.8.0.0/24"
vpn_interface="tun0"

if [ "$vpn_enabled" = "true" ]; then
    vpn_port="$(ask_with_context \
        "VPN_PORT" \
        "Puerto de escucha de OpenVPN (1-65535)." \
        "docs/modules/16_ip_30_openvpn.md" \
        "VPN_PORT" \
        "1194" \
        "is_port_number" \
        "VPN_PORT debe ser numérico entre 1 y 65535.")"

    vpn_subnet="$(ask_with_context \
        "VPN_SUBNET" \
        "Subred del túnel en formato CIDR IPv4 (ej: 10.8.0.0/24)." \
        "docs/modules/16_ip_30_openvpn.md" \
        "VPN_SUBNET" \
        "10.8.0.0/24" \
        "is_ipv4_cidr" \
        "VPN_SUBNET debe tener formato CIDR IPv4 válido (ej: 10.8.0.0/24).")"

    vpn_interface="$(ask_with_context \
        "VPN_INTERFACE" \
        "Interfaz del túnel OpenVPN (ej: tun0)." \
        "docs/modules/16_ip_30_openvpn.md" \
        "VPN_INTERFACE" \
        "tun0" \
        "is_interface_name" \
        "VPN_INTERFACE contiene caracteres no válidos.")"
else
    say_info "VPN deshabilitada: se usarán defaults para variables VPN en .env"
fi

say_section "Compatibilidad Docker"
docker_input_compat_raw="$(ask_with_context \
    "DOCKER_INPUT_COMPAT" \
    "Si TYPECHAIN=0, preserva flujo Docker sin romper FORWARD/NAT." \
    "docs/modules/12_ip_00_chain_setup.md" \
    "DOCKER_INPUT_COMPAT (true/false)" \
    "false" \
    "is_bool" \
    "DOCKER_INPUT_COMPAT debe ser true o false.")"
docker_input_compat="${docker_input_compat_raw,,}"

docker_chain_autorecover_raw="$(ask_with_context \
    "DOCKER_CHAIN_AUTORECOVER" \
    "Intenta recuperar cadenas Docker si faltan." \
    "docs/modules/12_ip_00_chain_setup.md" \
    "DOCKER_CHAIN_AUTORECOVER (true/false)" \
    "true" \
    "is_bool" \
    "DOCKER_CHAIN_AUTORECOVER debe ser true o false.")"
docker_chain_autorecover="${docker_chain_autorecover_raw,,}"

if [ "$typechain" = "0" ]; then
    say_warn "TYPECHAIN=0 protege INPUT host. Para servidores dockerizados usa 1 o 2."
fi

cat > "$output_file" <<EOF
# Generated by configure-env.sh
MODULES_ROOT_DIR=""
MODULES_IP_DIR=""
MODULES_NF_DIR=""
MODULES_ONLY=""
MODULES_EXCLUDE=""

TYPECHAIN=${typechain}
DOCKER_INPUT_COMPAT=${docker_input_compat}
DOCKER_CHAIN_AUTORECOVER=${docker_chain_autorecover}
ENABLE_TCP_PROTECT=${enable_tcp_protect}

GAMESERVERPORTS="${game_ports}"
TVSERVERPORTS="${tv_ports}"
CMD_LIMIT=${cmd_limit}
SSH_PORT="${ssh_ports}"
WHITELISTED_IPS="${whitelist}"

UDP_ALLOW_PORTS="${udp_allow}"
TCP_ALLOW_PORTS="${tcp_allow}"

VPN_ENABLED=${vpn_enabled}
VPN_PROTO="udp"
VPN_PORT=${vpn_port}
VPN_SUBNET="${vpn_subnet}"
VPN_INTERFACE="${vpn_interface}"
VPN_DOCKER_INTERFACE=""
VPN_LAN_SUBNET="192.168.1.0/24"
VPN_LAN_INTERFACE=""
VPN_ENABLE_NAT=false
VPN_ROUTER_REAL_IP=""
VPN_ROUTER_ALIAS_IP=""
VPN_LOG_ENABLED=false
VPN_LOG_PREFIX="VPN_TRAFFIC: "

LOG_PREFIX_INVALID_SIZE="INVALID_SIZE: "
LOG_PREFIX_MALFORMED="MALFORMED: "
LOG_PREFIX_A2S_INFO="A2S_INFO_FLOOD: "
LOG_PREFIX_A2S_PLAYERS="A2S_PLAYERS_FLOOD: "
LOG_PREFIX_A2S_RULES="A2S_RULES_FLOOD: "
LOG_PREFIX_STEAM_GROUP="STEAM_GROUP_FLOOD: "
LOG_PREFIX_L4D2_CONNECT="L4D2_CONNECT_FLOOD: "
LOG_PREFIX_L4D2_RESERVE="L4D2_RESERVE_FLOOD: "
LOG_PREFIX_UDP_NEW_LIMIT="UDP_NEW_LIMIT: "
LOG_PREFIX_UDP_EST_LIMIT="UDP_EST_LIMIT: "
LOG_PREFIX_TCP_RCON_BLOCK="TCP_RCON_BLOCK: "
LOG_PREFIX_ICMP_FLOOD="ICMP_FLOOD: "

LOGFILE=/var/log/l4d2-iptables.log
RSYSLOG_CONF=/etc/rsyslog.d/l4d2-iptables.conf
EOF

echo "OK: .env generated at $output_file" >&2

echo >&2
echo -e "${C_BOLD}${C_GREEN}Resumen rápido:${C_RESET}" >&2
echo "  TYPECHAIN=$typechain" >&2
echo "  GAMESERVERPORTS=$game_ports" >&2
echo "  TVSERVERPORTS=$tv_ports" >&2
echo "  CMD_LIMIT=$cmd_limit" >&2
echo "  SSH_PORT=$ssh_ports" >&2
echo "  ENABLE_TCP_PROTECT=$enable_tcp_protect" >&2
echo "  VPN_ENABLED=$vpn_enabled" >&2
echo "  VPN_PORT=$vpn_port" >&2
echo "  VPN_SUBNET=$vpn_subnet" >&2
echo "  VPN_INTERFACE=$vpn_interface" >&2
echo "  DOCKER_INPUT_COMPAT=$docker_input_compat" >&2
echo "  DOCKER_CHAIN_AUTORECOVER=$docker_chain_autorecover" >&2
