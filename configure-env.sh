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

is_rate_expr() {
    [[ "$1" =~ ^[0-9]+/(sec|min|hour|day)$ ]]
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

ask_yes_no() {
    local prompt="$1"
    local default_bool="$2"
    local suffix="[y/N]"
    local value

    if [ "$default_bool" = "true" ]; then
        suffix="[Y/n]"
    fi

    while true; do
        read -r -p "$prompt $suffix: " value
        value="${value,,}"

        if [ -z "$value" ]; then
            echo "$default_bool"
            return 0
        fi

        case "$value" in
            y|yes|s|si|sí|true)
                echo "true"
                return 0
                ;;
            n|no|false)
                echo "false"
                return 0
                ;;
            *)
                say_warn "Responde y/n"
                ;;
        esac
    done
}

module_default_include() {
    case "$1" in
        ip_loopback|ip_whitelist|ip_allowlist_ports|ip_openvpn|ip_tcp_ssh|ip_http_https_protect)
            echo "true"
            ;;
        ip_tcpfilter_chain|ip_l4d2_udp_base|ip_l4d2_packet_validation|ip_l4d2_a2s_filters)
            echo "false"
            ;;
        *)
            echo "false"
            ;;
    esac
}

module_backend_variants() {
    case "$1" in
        ip_chain_setup) echo "ip_chain_setup nf_chain_setup" ;;
        ip_finalize) echo "ip_finalize nf_finalize" ;;
        ip_whitelist) echo "ip_whitelist nf_whitelist" ;;
        ip_allowlist_ports) echo "ip_allowlist_ports nf_allowlist_ports" ;;
        ip_openvpn) echo "ip_openvpn nf_openvpn" ;;
        ip_tcp_ssh) echo "ip_tcp_ssh nf_tcp_ssh" ;;
        ip_http_https_protect) echo "ip_http_https_protect nf_http_https_protect" ;;
        ip_l4d2_udp_base) echo "ip_l4d2_udp_base nf_l4d2_udp_base" ;;
        ip_l4d2_packet_validation) echo "ip_l4d2_packet_validation nf_l4d2_packet_validation" ;;
        ip_l4d2_a2s_filters) echo "ip_l4d2_a2s_filters nf_l4d2_a2s_filters" ;;
        ip_loopback|ip_tcpfilter_chain) echo "$1" ;;
        *) echo "$1" ;;
    esac
}

append_module_variants() {
    local module_id="$1"
    local __target_array_name="$2"
    local variant

    for variant in $(module_backend_variants "$module_id"); do
        eval "$__target_array_name+=(\"$variant\")"
    done
}

module_id_to_file() {
    local module_id="$1"
    local search_dir candidate

    case "$module_id" in
        ip_chain_setup|nf_chain_setup|ip_finalize|nf_finalize)
            echo "$project_root/modules/${module_id}.sh"
            ;;
        ip_*)
            search_dir="$project_root/modules/ip"
            ;;
        nf_*)
            search_dir="$project_root/modules/nf"
            ;;
        *)
            echo ""
            return 0
            ;;
    esac

    if [ -n "${search_dir:-}" ] && [ -d "$search_dir" ]; then
        for candidate in "$search_dir"/*.sh; do
            [ -f "$candidate" ] || continue
            if grep -q "^ID=${module_id}$" "$candidate" 2>/dev/null; then
                echo "$candidate"
                return 0
            fi
        done
    fi

    echo ""
}

collect_required_vars_for_module() {
    local module_id="$1"
    local target_assoc_name="$2"
    local module_file required_raw var

    module_file="$(module_id_to_file "$module_id")"
    [ -n "$module_file" ] || return 0
    [ -f "$module_file" ] || return 0

    required_raw="$(grep -m1 '^REQUIRED_VARS=' "$module_file" | cut -d= -f2- || true)"
    [ -n "$required_raw" ] || return 0

    for var in $required_raw; do
        [ -n "$var" ] || continue
        eval "$target_assoc_name[\"$var\"]=true"
    done
}

needs_var() {
    local var_name="$1"
    [ "${selected_required_vars[$var_name]:-false}" = "true" ]
}

build_csv() {
    local sep=""
    local out=""
    local item
    for item in "$@"; do
        [ -z "$item" ] && continue
        out+="${sep}${item}"
        sep=","
    done
    echo "$out"
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

declare -A module_enabled=()

say_section "Backend y alcance"
typechain="$(ask_with_context \
    "TYPECHAIN" \
    "0=input host, 1=docker-user (contenedores), 2=ambos." \
    "docs/modules/03_chain_setup.md" \
    "TYPECHAIN (0=input, 1=docker-user, 2=both)" \
    "0" \
    "is_typechain" \
    "TYPECHAIN debe ser 0, 1 o 2.")"

say_section "Selección de módulos"
module_mode="whitelist"
say_info "Modo fijo: whitelist (solo módulos incluidos)."

module_enabled[ip_chain_setup]="true"
module_enabled[ip_finalize]="true"

declare -a selectable_modules=(
    "ip_loopback|Loopback local"
    "ip_whitelist|Whitelist por IP/dominio"
    "ip_allowlist_ports|Allowlist de puertos manual"
    "ip_openvpn|Reglas OpenVPN"
    "ip_tcp_ssh|Acceso SSH y TCP"
    "ip_http_https_protect|Protección HTTP/HTTPS"
    "ip_tcpfilter_chain|Cadena TCPfilter"
    "ip_l4d2_udp_base|Base UDP GameServer"
    "ip_l4d2_packet_validation|Validación de paquetes UDP"
    "ip_l4d2_a2s_filters|Filtros A2S/Steam"
)

declare -a selected_only=()
append_module_variants "ip_chain_setup" selected_only

say_info "Módulos fijos: chain_setup/finalize siempre incluidos (ip y nf)"

for module_info in "${selectable_modules[@]}"; do
    module_id="${module_info%%|*}"
    module_desc="${module_info#*|}"
    default_include="$(module_default_include "$module_id")"

    answer="$(ask_yes_no "¿Incluir $module_id ($module_desc)?" "$default_include")"
    module_enabled[$module_id]="$answer"

    if [ "${module_enabled[$module_id]}" = "true" ]; then
        say_info "$module_id => incluido"
        append_module_variants "$module_id" selected_only
    else
        say_warn "$module_id => excluido"
    fi
done

append_module_variants "ip_finalize" selected_only

modules_only=""
modules_exclude=""
modules_only="$(build_csv "${selected_only[@]}")"
say_info "MODULES_ONLY=$modules_only"

declare -A selected_required_vars=()
for selected_module in "${selected_only[@]}"; do
    collect_required_vars_for_module "$selected_module" selected_required_vars
done

l4d2_game_ports="27015"
l4d2_tv_ports="27020"
l4d2_cmd_limit="100"
ssh_ports="22"
ssh_require_whitelist="false"
whitelist=""
whitelist_domains=""
udp_allow=""
tcp_allow=""
enable_l4d2_tcp_protect="false"
enable_l4d2_udp_base="false"
enable_l4d2_packet_validation="false"
enable_l4d2_a2s_filters="false"
enable_http_protect="false"
http_https_ports="80,443"
http_https_docker="80,443"
http_https_rate="180/min"
http_https_burst="360"
vpn_port="1195"
vpn_subnet="10.8.0.0/24"
vpn_interface="tun0"
vpn_proto="udp"
l4d2_tcp_protection=""

if needs_var "SSH_PORT" || needs_var "ENABLE_L4D2_TCP_PROTECT"; then
    say_section "SSH/TCP"
    if needs_var "SSH_PORT"; then
        ssh_ports="$(ask_with_context \
            "SSH_PORT" \
            "Puertos SSH permitidos; admite lista/rango." \
            "docs/modules/07_tcp_ssh.md" \
            "SSH_PORT (ej: 22 o 423,4230:4239)" \
            "22" \
            "is_required_ports_expr" \
            "Formato inválido para SSH_PORT.")"
    fi

    if needs_var "SSH_REQUIRE_WHITELIST"; then
        ssh_require_whitelist_raw="$(ask_with_context \
            "SSH_REQUIRE_WHITELIST" \
            "Si es true, SSH_PORT no se abre públicamente y solo entra vía whitelist." \
            "docs/modules/07_tcp_ssh.md" \
            "SSH_REQUIRE_WHITELIST (true/false)" \
            "true" \
            "is_bool" \
            "SSH_REQUIRE_WHITELIST debe ser true o false.")"
        ssh_require_whitelist="${ssh_require_whitelist_raw,,}"
    fi

    if needs_var "ENABLE_L4D2_TCP_PROTECT"; then
        enable_l4d2_tcp_protect_raw="$(ask_with_context \
            "ENABLE_L4D2_TCP_PROTECT" \
            "Activa bloqueo/protección anti-spam TCP (RCON/juego)." \
            "docs/modules/07_tcp_ssh.md" \
            "ENABLE_L4D2_TCP_PROTECT (true/false)" \
            "false" \
            "is_bool" \
            "ENABLE_L4D2_TCP_PROTECT debe ser true o false.")"
        enable_l4d2_tcp_protect="${enable_l4d2_tcp_protect_raw,,}"
    fi

    if [ "$enable_l4d2_tcp_protect" = "true" ] && needs_var "L4D2_GAMESERVER_PORTS"; then
        l4d2_game_ports="$(ask_with_context \
            "L4D2_GAMESERVER_PORTS" \
            "Puertos usados para protección TCP de juego/RCON." \
            "docs/modules/07_tcp_ssh.md" \
            "L4D2_GAMESERVER_PORTS (ej: 27015 o 27015:27020)" \
            "27015" \
            "is_required_ports_expr" \
            "Formato inválido. Usa puertos/rangos separados por coma.")"
    fi
fi

if [ "${module_enabled[ip_whitelist]:-false}" = "true" ] || [ "$ssh_require_whitelist" = "true" ]; then
    say_section "Whitelist"
    whitelist="$(ask_with_context \
        "WHITELISTED_IPS" \
        "IPs de confianza (separadas por espacio), sin rate limits." \
        "docs/modules/04_whitelist.md" \
        "WHITELISTED_IPS (espacio separado)" \
        "" \
        "true" \
        "")"

    whitelist_domains="$(ask_with_context \
        "WHITELISTED_DOMAINS" \
        "Dominios de confianza (separados por espacio), se resuelven a IPv4 al aplicar reglas." \
        "docs/modules/04_whitelist.md" \
        "WHITELISTED_DOMAINS (espacio separado, optional)" \
        "" \
        "true" \
        "")"
fi

if [ "$ssh_require_whitelist" = "true" ] && [ -z "$whitelist" ] && [ -z "$whitelist_domains" ]; then
    say_warn "SSH_REQUIRE_WHITELIST=true requiere WHITELISTED_IPS o WHITELISTED_DOMAINS. Se fuerza false."
    ssh_require_whitelist="false"
fi

if needs_var "UDP_ALLOW_PORTS" || needs_var "TCP_ALLOW_PORTS"; then
    say_section "Allowlist de puertos"
    udp_allow="$(ask_with_context \
        "UDP_ALLOW_PORTS" \
        "Excepciones UDP adicionales (opcional)." \
        "docs/modules/05_allowlist_ports.md" \
        "UDP_ALLOW_PORTS (comma/range, optional)" \
        "" \
        "is_optional_ports_expr" \
        "Formato inválido para UDP_ALLOW_PORTS.")"

    tcp_allow="$(ask_with_context \
        "TCP_ALLOW_PORTS" \
        "Excepciones TCP adicionales (opcional)." \
        "docs/modules/05_allowlist_ports.md" \
        "TCP_ALLOW_PORTS (comma/range, optional)" \
        "" \
        "is_optional_ports_expr" \
        "Formato inválido para TCP_ALLOW_PORTS.")"
fi

if needs_var "ENABLE_HTTP_PROTECT"; then
    say_section "Web HTTP/HTTPS"
    enable_http_protect_raw="$(ask_with_context \
        "ENABLE_HTTP_PROTECT" \
        "Activa protección anti-abuso para puertos web." \
        "docs/modules/08_http_https_protect.md" \
        "ENABLE_HTTP_PROTECT (true/false)" \
        "true" \
        "is_bool" \
        "ENABLE_HTTP_PROTECT debe ser true o false.")"
    enable_http_protect="${enable_http_protect_raw,,}"

    if [ "$enable_http_protect" = "true" ]; then
        http_https_ports="$(ask_with_context \
            "HTTP_HTTPS_PORTS" \
            "Puertos web en INPUT (host)." \
            "docs/modules/08_http_https_protect.md" \
            "HTTP_HTTPS_PORTS (ej: 80,443)" \
            "80,443" \
            "is_required_ports_expr" \
            "Formato inválido para HTTP_HTTPS_PORTS.")"

        http_https_docker="$(ask_with_context \
            "HTTP_HTTPS_DOCKER" \
            "Puertos web en DOCKER-USER (opcional)." \
            "docs/modules/08_http_https_protect.md" \
            "HTTP_HTTPS_DOCKER (ej: 80,443)" \
            "80,443" \
            "is_required_ports_expr" \
            "Formato inválido para HTTP_HTTPS_DOCKER.")"

        http_https_rate="$(ask_with_context \
            "HTTP_HTTPS_RATE" \
            "Límite de conexiones nuevas por origen (formato num/unidad)." \
            "docs/modules/08_http_https_protect.md" \
            "HTTP_HTTPS_RATE (ej: 180/min)" \
            "180/min" \
            "is_rate_expr" \
            "Formato inválido. Usa <num>/(sec|min|hour|day).")"

        http_https_burst="$(ask_with_context \
            "HTTP_HTTPS_BURST" \
            "Ráfaga permitida antes de bloquear." \
            "docs/modules/08_http_https_protect.md" \
            "HTTP_HTTPS_BURST" \
            "360" \
            "is_cmd_limit" \
            "HTTP_HTTPS_BURST debe ser numérico.")"
    fi
fi

if needs_var "VPN_PORT" || needs_var "VPN_SUBNET" || needs_var "VPN_INTERFACE"; then
    say_section "OpenVPN"
    vpn_port="$(ask_with_context \
        "VPN_PORT" \
        "Puerto de escucha de OpenVPN (1-65535)." \
        "docs/modules/06_openvpn.md" \
        "VPN_PORT" \
        "1195" \
        "is_port_number" \
        "VPN_PORT debe ser numérico entre 1 y 65535.")"

    vpn_subnet="$(ask_with_context \
        "VPN_SUBNET" \
        "Subred del túnel en formato CIDR IPv4 (ej: 10.8.0.0/24)." \
        "docs/modules/06_openvpn.md" \
        "VPN_SUBNET" \
        "10.8.0.0/24" \
        "is_ipv4_cidr" \
        "VPN_SUBNET debe tener formato CIDR IPv4 válido (ej: 10.8.0.0/24).")"

    vpn_interface="$(ask_with_context \
        "VPN_INTERFACE" \
        "Interfaz del túnel OpenVPN (ej: tun0)." \
        "docs/modules/06_openvpn.md" \
        "VPN_INTERFACE" \
        "tun0" \
        "is_interface_name" \
        "VPN_INTERFACE contiene caracteres no válidos.")"
fi

if needs_var "ENABLE_L4D2_UDP_BASE" || needs_var "ENABLE_L4D2_PACKET_VALIDATION" || needs_var "ENABLE_L4D2_A2S_FILTERS" || needs_var "L4D2_TV_PORTS" || needs_var "L4D2_CMD_LIMIT"; then
    if [ "${module_enabled[ip_l4d2_udp_base]:-false}" = "true" ]; then
        enable_l4d2_udp_base="true"
    fi
    if [ "${module_enabled[ip_l4d2_packet_validation]:-false}" = "true" ]; then
        enable_l4d2_packet_validation="true"
    fi
    if [ "${module_enabled[ip_l4d2_a2s_filters]:-false}" = "true" ]; then
        enable_l4d2_a2s_filters="true"
    fi

    say_section "Servicios de juego (UDP)"
    l4d2_game_ports="$(ask_with_context \
        "L4D2_GAMESERVER_PORTS" \
        "Puertos UDP principales del GameServer." \
        "docs/modules/09_l4d2_udp_base.md" \
        "L4D2_GAMESERVER_PORTS (ej: 27015 o 27015:27020)" \
        "$l4d2_game_ports" \
        "is_required_ports_expr" \
        "Formato inválido. Usa puertos/rangos separados por coma (ej: 27015 o 27015:27020).")"

    l4d2_tv_ports="$(ask_with_context \
        "L4D2_TV_PORTS" \
        "Puertos SourceTV/separados para espectadores." \
        "docs/modules/09_l4d2_udp_base.md" \
        "L4D2_TV_PORTS (ej: 27020 o 27115:27120)" \
        "27020" \
        "is_required_ports_expr" \
        "Formato inválido. Usa puertos/rangos separados por coma (ej: 27020 o 27115:27120).")"

    l4d2_cmd_limit="$(ask_with_context \
        "L4D2_CMD_LIMIT" \
        "Controla los límites dinámicos de UDP; recomendado según tickrate." \
        "docs/modules/09_l4d2_udp_base.md" \
        "L4D2_CMD_LIMIT" \
        "100" \
        "is_cmd_limit" \
        "L4D2_CMD_LIMIT debe ser numérico entre 10 y 10000.")"
else
    say_info "Módulos de juego no incluidos: se mantienen defaults mínimos (sin activar protección de juego)."
fi

say_section "Compatibilidad Docker"
docker_input_compat_raw="$(ask_with_context \
    "DOCKER_INPUT_COMPAT" \
    "Si TYPECHAIN=0, preserva flujo Docker sin romper FORWARD/NAT." \
    "docs/modules/03_chain_setup.md" \
    "DOCKER_INPUT_COMPAT (true/false)" \
    "false" \
    "is_bool" \
    "DOCKER_INPUT_COMPAT debe ser true o false.")"
docker_input_compat="${docker_input_compat_raw,,}"

docker_chain_autorecover_raw="$(ask_with_context \
    "DOCKER_CHAIN_AUTORECOVER" \
    "Intenta recuperar cadenas Docker si faltan." \
    "docs/modules/03_chain_setup.md" \
    "DOCKER_CHAIN_AUTORECOVER (true/false)" \
    "true" \
    "is_bool" \
    "DOCKER_CHAIN_AUTORECOVER debe ser true o false.")"
docker_chain_autorecover="${docker_chain_autorecover_raw,,}"

if [ "$typechain" = "0" ]; then
    say_warn "TYPECHAIN=0 protege INPUT host. Para servidores dockerizados usa 1 o 2."
fi

has_l4d2_udp_modules="false"
if needs_var "ENABLE_L4D2_UDP_BASE" || needs_var "ENABLE_L4D2_PACKET_VALIDATION" || needs_var "ENABLE_L4D2_A2S_FILTERS"; then
    has_l4d2_udp_modules="true"
fi

has_l4d2_tcp_modules="false"
if needs_var "ENABLE_L4D2_TCP_PROTECT" || needs_var "L4D2_TCP_PROTECTION"; then
    has_l4d2_tcp_modules="true"
fi

has_l4d2_ports_needed="false"
if needs_var "L4D2_GAMESERVER_PORTS"; then
    has_l4d2_ports_needed="true"
fi

has_openvpn_module="false"
if needs_var "VPN_PORT" || needs_var "VPN_SUBNET" || needs_var "VPN_INTERFACE"; then
    has_openvpn_module="true"
fi

cat > "$output_file" <<EOF
# Generated by configure-env.sh
MODULES_ROOT_DIR=""
MODULES_IP_DIR=""
MODULES_NF_DIR=""
MODULES_ONLY="${modules_only}"
MODULES_EXCLUDE="${modules_exclude}"

TYPECHAIN=${typechain}
DOCKER_INPUT_COMPAT=${docker_input_compat}
DOCKER_CHAIN_AUTORECOVER=${docker_chain_autorecover}
ENABLE_HTTP_PROTECT=${enable_http_protect}

SSH_PORT="${ssh_ports}"
SSH_REQUIRE_WHITELIST=${ssh_require_whitelist}
WHITELISTED_IPS="${whitelist}"
WHITELISTED_DOMAINS="${whitelist_domains}"

UDP_ALLOW_PORTS="${udp_allow}"
TCP_ALLOW_PORTS="${tcp_allow}"
HTTP_HTTPS_PORTS="${http_https_ports}"
HTTP_HTTPS_DOCKER="${http_https_docker}"
HTTP_HTTPS_RATE="${http_https_rate}"
HTTP_HTTPS_BURST=${http_https_burst}
LOG_PREFIX_HTTP_HTTPS_ABUSE="HTTP_HTTPS_ABUSE: "
EOF

if [ "$has_l4d2_tcp_modules" = "true" ]; then
cat >> "$output_file" <<EOF
ENABLE_L4D2_TCP_PROTECT=${enable_l4d2_tcp_protect}
L4D2_TCP_PROTECTION="${l4d2_tcp_protection}"
EOF
fi

if [ "$has_l4d2_ports_needed" = "true" ]; then
cat >> "$output_file" <<EOF
L4D2_GAMESERVER_PORTS="${l4d2_game_ports}"
EOF
fi

if [ "$has_l4d2_udp_modules" = "true" ]; then
cat >> "$output_file" <<EOF
ENABLE_L4D2_UDP_BASE=${enable_l4d2_udp_base}
ENABLE_L4D2_PACKET_VALIDATION=${enable_l4d2_packet_validation}
ENABLE_L4D2_A2S_FILTERS=${enable_l4d2_a2s_filters}
L4D2_TV_PORTS="${l4d2_tv_ports}"
L4D2_CMD_LIMIT=${l4d2_cmd_limit}
EOF
fi

cat >> "$output_file" <<EOF

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
EOF

if [ "$has_openvpn_module" = "true" ]; then
cat >> "$output_file" <<EOF

VPN_PROTO="${vpn_proto}"
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
EOF
fi

cat >> "$output_file" <<EOF

LOGFILE=/var/log/l4d2-iptables.log
RSYSLOG_CONF=/etc/rsyslog.d/l4d2-iptables.conf
EOF

echo "OK: .env generated at $output_file" >&2

echo >&2
echo -e "${C_BOLD}${C_GREEN}Resumen rápido:${C_RESET}" >&2
echo "  MODULE_MODE=$module_mode" >&2
echo "  MODULES_ONLY=$modules_only" >&2
echo "  MODULES_EXCLUDE=$modules_exclude" >&2
echo "  TYPECHAIN=$typechain" >&2
echo "  SSH_PORT=$ssh_ports" >&2
echo "  SSH_REQUIRE_WHITELIST=$ssh_require_whitelist" >&2
echo "  ENABLE_HTTP_PROTECT=$enable_http_protect" >&2
echo "  WHITELISTED_DOMAINS=$whitelist_domains" >&2
echo "  DOCKER_INPUT_COMPAT=$docker_input_compat" >&2
echo "  DOCKER_CHAIN_AUTORECOVER=$docker_chain_autorecover" >&2

if [ "$has_openvpn_module" = "true" ]; then
echo "  VPN_PORT=$vpn_port" >&2
echo "  VPN_SUBNET=$vpn_subnet" >&2
echo "  VPN_INTERFACE=$vpn_interface" >&2
fi

if [ "$has_l4d2_ports_needed" = "true" ]; then
echo "  L4D2_GAMESERVER_PORTS=$l4d2_game_ports" >&2
fi

if [ "$has_l4d2_tcp_modules" = "true" ]; then
echo "  ENABLE_L4D2_TCP_PROTECT=$enable_l4d2_tcp_protect" >&2
fi

if [ "$has_l4d2_udp_modules" = "true" ]; then
echo "  L4D2_TV_PORTS=$l4d2_tv_ports" >&2
echo "  L4D2_CMD_LIMIT=$l4d2_cmd_limit" >&2
echo "  ENABLE_L4D2_UDP_BASE=$enable_l4d2_udp_base" >&2
echo "  ENABLE_L4D2_PACKET_VALIDATION=$enable_l4d2_packet_validation" >&2
echo "  ENABLE_L4D2_A2S_FILTERS=$enable_l4d2_a2s_filters" >&2
fi
