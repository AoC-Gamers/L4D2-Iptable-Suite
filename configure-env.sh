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
        ip_l4d2_tcpfilter_chain|ip_l4d2_tcp_protect|ip_l4d2_udp_base|ip_l4d2_packet_validation|ip_l4d2_a2s_filters)
            echo "false"
            ;;
        *)
            echo "false"
            ;;
    esac
}

module_generic_token() {
    case "$1" in
        ip_chain_setup|nf_chain_setup) echo "chain_setup" ;;
        ip_finalize|nf_finalize) echo "finalize" ;;
        ip_*) echo "${1#ip_}" ;;
        nf_*) echo "${1#nf_}" ;;
        *) echo "$1" ;;
    esac
}

module_token_to_module_ids() {
    local token="$1"

    case "$token" in
        chain_setup) echo "ip_chain_setup nf_chain_setup" ;;
        finalize) echo "ip_finalize nf_finalize" ;;
        whitelist) echo "ip_whitelist nf_whitelist" ;;
        allowlist_ports) echo "ip_allowlist_ports nf_allowlist_ports" ;;
        openvpn) echo "ip_openvpn nf_openvpn" ;;
        tcp_ssh) echo "ip_tcp_ssh nf_tcp_ssh" ;;
        l4d2_tcp_protect) echo "ip_l4d2_tcp_protect nf_l4d2_tcp_protect" ;;
        http_https_protect) echo "ip_http_https_protect nf_http_https_protect" ;;
        l4d2_udp_base) echo "ip_l4d2_udp_base nf_l4d2_udp_base" ;;
        l4d2_packet_validation) echo "ip_l4d2_packet_validation nf_l4d2_packet_validation" ;;
        l4d2_a2s_filters) echo "ip_l4d2_a2s_filters nf_l4d2_a2s_filters" ;;
        loopback) echo "ip_loopback" ;;
        l4d2_tcpfilter_chain|tcpfilter_chain) echo "ip_l4d2_tcpfilter_chain nf_l4d2_tcpfilter_chain" ;;
        ip_*|nf_*) echo "$token" ;;
        *) echo "$token" ;;
    esac
}

append_module_token() {
    local module_id="$1"
    local __target_array_name="$2"
    local token

    token="$(module_generic_token "$module_id")"
    eval "$__target_array_name+=(\"$token\")"
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
    local module_file required_raw optional_raw var

    module_file="$(module_id_to_file "$module_id")"
    [ -n "$module_file" ] || return 0
    [ -f "$module_file" ] || return 0

    required_raw="$(grep -m1 '^REQUIRED_VARS=' "$module_file" | cut -d= -f2- || true)"
    for var in $required_raw; do
        [ -n "$var" ] || continue
        eval "$target_assoc_name[\"$var\"]=true"
    done

    optional_raw="$(grep -m1 '^OPTIONAL_VARS=' "$module_file" | cut -d= -f2- || true)"
    for var in $optional_raw; do
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
    "ip_tcp_ssh|Acceso SSH base"
    "ip_l4d2_tcp_protect|Protección TCP L4D2"
    "ip_http_https_protect|Protección HTTP/HTTPS"
    "ip_l4d2_tcpfilter_chain|Cadena TCPfilter L4D2"
    "ip_l4d2_udp_base|Base UDP GameServer"
    "ip_l4d2_packet_validation|Validación de paquetes UDP"
    "ip_l4d2_a2s_filters|Filtros A2S/Steam"
)

declare -a selected_only=()
append_module_token "ip_chain_setup" selected_only

say_info "Módulos fijos: chain_setup/finalize siempre incluidos (ip y nf)"

for module_info in "${selectable_modules[@]}"; do
    module_id="${module_info%%|*}"
    module_desc="${module_info#*|}"
    default_include="$(module_default_include "$module_id")"

    answer="$(ask_yes_no "¿Incluir $module_id ($module_desc)?" "$default_include")"
    module_enabled[$module_id]="$answer"

    if [ "${module_enabled[$module_id]}" = "true" ]; then
        say_info "$module_id => incluido"
        append_module_token "$module_id" selected_only
    else
        say_warn "$module_id => excluido"
    fi
done

append_module_token "ip_finalize" selected_only

modules_only=""
modules_only="$(build_csv "${selected_only[@]}")"

say_info "MODULES_ONLY=$modules_only"

declare -A selected_required_vars=()
for selected_module in "${selected_only[@]}"; do
    for module_id in $(module_token_to_module_ids "$selected_module"); do
        collect_required_vars_for_module "$module_id" selected_required_vars
    done
done

l4d2_game_ports="27015"
l4d2_tv_ports="27020"
l4d2_cmd_limit="100"
ssh_ports="22"
ssh_docker=""
ssh_rate="60/min"
ssh_burst="20"
whitelist=""
whitelist_domains=""
udp_allow=""
tcp_allow=""
http_https_ports="80,443"
http_https_rate="180/min"
http_https_burst="360"
vpn_port="1195"
vpn_subnet="10.8.0.0/24"
vpn_interface="tun0"
vpn_proto="udp"
l4d2_tcp_protection=""

if needs_var "SSH_PORT"; then
    say_section "SSH"
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

    if needs_var "SSH_DOCKER"; then
        ssh_docker="$(ask_with_context \
            "SSH_DOCKER" \
            "Puertos SSH expuestos por contenedores (DOCKER-USER), opcional." \
            "docs/modules/07_tcp_ssh.md" \
            "SSH_DOCKER (optional, ej: 2222 o 2222,22220:22229)" \
            "" \
            "is_optional_ports_expr" \
            "Formato inválido para SSH_DOCKER.")"
    fi

fi

if needs_var "L4D2_TCP_PROTECTION" || needs_var "L4D2_GAMESERVER_PORTS"; then
    say_section "TCP L4D2"

    if needs_var "L4D2_TCP_PROTECTION"; then
        l4d2_tcp_protection="$(ask_with_context \
            "L4D2_TCP_PROTECTION" \
            "Puertos TCP específicos a proteger (opcional). Vacío=usa L4D2_GAMESERVER_PORTS." \
            "docs/modules/15_l4d2_tcp_protect.md" \
            "L4D2_TCP_PROTECTION (optional, ej: 27015 o 27015:27020)" \
            "" \
            "is_optional_ports_expr" \
            "Formato inválido. Usa puertos/rangos separados por coma.")"
    fi

    if [ -z "$l4d2_tcp_protection" ] && needs_var "L4D2_GAMESERVER_PORTS"; then
        l4d2_game_ports="$(ask_with_context \
            "L4D2_GAMESERVER_PORTS" \
            "Puertos usados para protección TCP de juego/RCON." \
            "docs/modules/15_l4d2_tcp_protect.md" \
            "L4D2_GAMESERVER_PORTS (ej: 27015 o 27015:27020)" \
            "27015" \
            "is_required_ports_expr" \
            "Formato inválido. Usa puertos/rangos separados por coma.")"
    fi
fi

if [ "${module_enabled[ip_whitelist]:-false}" = "true" ]; then
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

if needs_var "HTTP_HTTPS_PORTS" || needs_var "HTTP_HTTPS_RATE" || needs_var "HTTP_HTTPS_BURST"; then
    say_section "Web HTTP/HTTPS"
    http_https_ports="$(ask_with_context \
        "HTTP_HTTPS_PORTS" \
        "Puertos web en INPUT (host)." \
        "docs/modules/08_http_https_protect.md" \
        "HTTP_HTTPS_PORTS (ej: 80,443)" \
        "80,443" \
        "is_required_ports_expr" \
        "Formato inválido para HTTP_HTTPS_PORTS.")"

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

if [ "${module_enabled[ip_l4d2_udp_base]:-false}" = "true" ] || [ "${module_enabled[ip_l4d2_packet_validation]:-false}" = "true" ] || [ "${module_enabled[ip_l4d2_a2s_filters]:-false}" = "true" ]; then
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
if [ "${module_enabled[ip_l4d2_udp_base]:-false}" = "true" ] || [ "${module_enabled[ip_l4d2_packet_validation]:-false}" = "true" ] || [ "${module_enabled[ip_l4d2_a2s_filters]:-false}" = "true" ]; then
    has_l4d2_udp_modules="true"
fi

has_l4d2_tcp_modules="false"
if [ "${module_enabled[ip_l4d2_tcp_protect]:-false}" = "true" ] || [ "${module_enabled[ip_l4d2_tcpfilter_chain]:-false}" = "true" ]; then
    has_l4d2_tcp_modules="true"
fi

has_l4d2_ports_needed="false"
if [ "$has_l4d2_udp_modules" = "true" ]; then
    has_l4d2_ports_needed="true"
elif [ "$has_l4d2_tcp_modules" = "true" ] && [ -z "$l4d2_tcp_protection" ] && needs_var "L4D2_GAMESERVER_PORTS"; then
    has_l4d2_ports_needed="true"
fi

has_openvpn_module="false"
if needs_var "VPN_PORT" || needs_var "VPN_SUBNET" || needs_var "VPN_INTERFACE"; then
    has_openvpn_module="true"
fi

has_ssh_module="false"
if [ "${module_enabled[ip_tcp_ssh]:-false}" = "true" ]; then
    has_ssh_module="true"
fi

cat > "$output_file" <<EOF
# Generated by configure-env.sh
MODULES_ONLY="${modules_only}"

TYPECHAIN=${typechain}
DOCKER_INPUT_COMPAT=${docker_input_compat}
DOCKER_CHAIN_AUTORECOVER=${docker_chain_autorecover}
WHITELISTED_IPS="${whitelist}"
WHITELISTED_DOMAINS="${whitelist_domains}"

UDP_ALLOW_PORTS="${udp_allow}"
TCP_ALLOW_PORTS="${tcp_allow}"
HTTP_HTTPS_PORTS="${http_https_ports}"
HTTP_HTTPS_RATE="${http_https_rate}"
HTTP_HTTPS_BURST=${http_https_burst}
EOF

if [ "$has_ssh_module" = "true" ]; then
cat >> "$output_file" <<EOF
SSH_PORT="${ssh_ports}"
SSH_DOCKER="${ssh_docker}"
SSH_RATE="${ssh_rate}"
SSH_BURST=${ssh_burst}
EOF
fi

if [ "$has_l4d2_tcp_modules" = "true" ]; then
cat >> "$output_file" <<EOF
EOF
    if [ -n "$l4d2_tcp_protection" ]; then
cat >> "$output_file" <<EOF
L4D2_TCP_PROTECTION="${l4d2_tcp_protection}"
EOF
    fi
fi

if [ "$has_l4d2_ports_needed" = "true" ]; then
cat >> "$output_file" <<EOF
L4D2_GAMESERVER_PORTS="${l4d2_game_ports}"
EOF
fi

if [ "$has_l4d2_udp_modules" = "true" ]; then
cat >> "$output_file" <<EOF
L4D2_TV_PORTS="${l4d2_tv_ports}"
L4D2_CMD_LIMIT=${l4d2_cmd_limit}
EOF
fi

if needs_var "LOG_PREFIX_HTTP_HTTPS_ABUSE"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_HTTP_HTTPS_ABUSE="HTTP_HTTPS_ABUSE: "
EOF
fi

if needs_var "LOG_PREFIX_INVALID_SIZE"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_INVALID_SIZE="INVALID_SIZE: "
EOF
fi

if needs_var "LOG_PREFIX_MALFORMED"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_MALFORMED="MALFORMED: "
EOF
fi

if needs_var "LOG_PREFIX_A2S_INFO"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_A2S_INFO="A2S_INFO_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_A2S_PLAYERS"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_A2S_PLAYERS="A2S_PLAYERS_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_A2S_RULES"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_A2S_RULES="A2S_RULES_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_STEAM_GROUP"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_STEAM_GROUP="STEAM_GROUP_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_L4D2_CONNECT"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_L4D2_CONNECT="L4D2_CONNECT_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_L4D2_RESERVE"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_L4D2_RESERVE="L4D2_RESERVE_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_UDP_NEW_LIMIT"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_UDP_NEW_LIMIT="UDP_NEW_LIMIT: "
EOF
fi

if needs_var "LOG_PREFIX_UDP_EST_LIMIT"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_UDP_EST_LIMIT="UDP_EST_LIMIT: "
EOF
fi

if needs_var "LOG_PREFIX_TCP_RCON_BLOCK"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_TCP_RCON_BLOCK="TCP_RCON_BLOCK: "
EOF
fi

if needs_var "LOG_PREFIX_ICMP_FLOOD"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_ICMP_FLOOD="ICMP_FLOOD: "
EOF
fi

if needs_var "LOG_PREFIX_SSH_ABUSE"; then
cat >> "$output_file" <<EOF
LOG_PREFIX_SSH_ABUSE="SSH_ABUSE: "
EOF
fi

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

LOGFILE=/var/log/firewall-suite.log
RSYSLOG_CONF=/etc/rsyslog.d/firewall-suite.conf
EOF

echo "OK: .env generated at $output_file" >&2

echo >&2
echo -e "${C_BOLD}${C_GREEN}Resumen rápido:${C_RESET}" >&2
echo "  MODULE_MODE=$module_mode" >&2
echo "  MODULES_ONLY=$modules_only" >&2
echo "  TYPECHAIN=$typechain" >&2
echo "  WHITELISTED_DOMAINS=$whitelist_domains" >&2
echo "  DOCKER_INPUT_COMPAT=$docker_input_compat" >&2
echo "  DOCKER_CHAIN_AUTORECOVER=$docker_chain_autorecover" >&2

if [ "$has_ssh_module" = "true" ]; then
echo "  SSH_PORT=$ssh_ports" >&2
echo "  SSH_DOCKER=$ssh_docker" >&2
echo "  SSH_RATE=$ssh_rate" >&2
echo "  SSH_BURST=$ssh_burst" >&2
fi

if [ "$has_openvpn_module" = "true" ]; then
echo "  VPN_PORT=$vpn_port" >&2
echo "  VPN_SUBNET=$vpn_subnet" >&2
echo "  VPN_INTERFACE=$vpn_interface" >&2
fi

if [ "$has_l4d2_ports_needed" = "true" ]; then
echo "  L4D2_GAMESERVER_PORTS=$l4d2_game_ports" >&2
fi

if [ "$has_l4d2_udp_modules" = "true" ]; then
echo "  L4D2_TV_PORTS=$l4d2_tv_ports" >&2
echo "  L4D2_CMD_LIMIT=$l4d2_cmd_limit" >&2
fi
