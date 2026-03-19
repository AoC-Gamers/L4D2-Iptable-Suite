#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root or with sudo."
    exit 1
fi

DIR_IPTABLES="/etc/iptables"
NFT_CONF_FILE="/etc/nftables.conf"
ACTIVE_BACKEND="iptables"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_ENV_FILE="${SUITE_ENV_FILE:-$SCRIPT_DIR/.env}"
SUITE_ENV_LOADED=false

C_RESET=""
C_BOLD=""
C_DIM=""
C_TITLE=""
C_INFO=""
C_OK=""
C_WARN=""
C_ERROR=""
C_MENU=""
C_SECTION_SERVICES=""
C_SECTION_RULES=""
C_SECTION_SYSTEM=""
C_BACKEND_IP=""
C_BACKEND_NF=""
B_TL="+"
B_TR="+"
B_BL="+"
B_BR="+"
B_H="-"
B_V="|"

setup_colors() {
    if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
        C_RESET="\033[0m"
        C_BOLD="\033[1m"
        C_DIM="\033[2m"
        C_TITLE="\033[1;36m"
        C_INFO="\033[0;34m"
        C_OK="\033[0;32m"
        C_WARN="\033[0;33m"
        C_ERROR="\033[0;31m"
        C_MENU="\033[0;35m"
        C_SECTION_SERVICES="\033[1;34m"
        C_SECTION_RULES="\033[1;36m"
        C_SECTION_SYSTEM="\033[1;35m"
        C_BACKEND_IP="\033[1;33m"
        C_BACKEND_NF="\033[1;32m"
    fi

}

print_header() {
    local backend_color="$C_BACKEND_IP"
    local title_text="Firewall Persistent Manager (IP/NFT)"
    local min_width=40
    local width=${#title_text}
    local border
    local inner_line
    local left_pad
    local right_pad
    if [ "$ACTIVE_BACKEND" = "nftables" ]; then
        backend_color="$C_BACKEND_NF"
    fi

    if [ "$width" -lt "$min_width" ]; then
        width=$min_width
    fi

    left_pad=$(((width - ${#title_text}) / 2))
    right_pad=$((width - ${#title_text} - left_pad))
    inner_line=$(printf '%*s%s%*s' "$left_pad" '' "$title_text" "$right_pad" '')
    border=$(printf '%*s' "$width" '' | tr ' ' "$B_H")

    echo ""
    echo -e "${C_TITLE}${B_TL}${border}${B_TR}${C_RESET}"
    printf "%b%s%b%b%s%b%b%s%b\n" "$C_TITLE" "$B_V" "$C_RESET" "$C_BOLD" "$inner_line" "$C_RESET" "$C_TITLE" "$B_V" "$C_RESET"
    echo -e "${C_TITLE}${B_BL}${border}${B_BR}${C_RESET}"
    echo -e "${C_DIM}Backend activo:${C_RESET} ${backend_color}${ACTIVE_BACKEND}${C_RESET}"
    echo ""
}

print_section() {
    echo -e "${C_MENU}$1${C_RESET}"
}

print_section_services() {
    local style="$C_SECTION_SERVICES"
    if [ -z "$style" ]; then
        style="$C_MENU"
    fi
    echo -e "${style}$1${C_RESET}"
}

print_section_rules() {
    local style="$C_SECTION_RULES"
    if [ -z "$style" ]; then
        style="$C_MENU"
    fi
    echo -e "${style}$1${C_RESET}"
}

print_section_system() {
    local style="$C_SECTION_SYSTEM"
    if [ -z "$style" ]; then
        style="$C_MENU"
    fi
    echo -e "${style}$1${C_RESET}"
}

print_option() {
    local number="$1"
    shift
    printf "  %2s) %s\n" "$number" "$*"
}

msg_info() {
    echo -e "${C_INFO}INFO:${C_RESET} $*"
}

msg_ok() {
    echo -e "${C_OK}OK:${C_RESET} $*"
}

msg_warn() {
    echo -e "${C_WARN}WARNING:${C_RESET} $*"
}

msg_error() {
    echo -e "${C_ERROR}ERROR:${C_RESET} $*"
}

pause_screen() {
    echo ""
    echo -ne "${C_DIM}Press Enter to continue...${C_RESET}"
    read -r
}

detect_default_backend() {
    if command -v nft >/dev/null 2>&1 && nft_suite_primary_table_exists; then
        ACTIVE_BACKEND="nftables"
    else
        ACTIVE_BACKEND="iptables"
    fi
}

nft_suite_primary_table_exists() {
    nft list table inet firewall_main >/dev/null 2>&1 \
        || nft list table inet l4d2_filter >/dev/null 2>&1
}

load_suite_env_if_present() {
    if [ "$SUITE_ENV_LOADED" = "true" ]; then
        return 0
    fi

    if [ -f "$SUITE_ENV_FILE" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$SUITE_ENV_FILE"
        set +a
        SUITE_ENV_LOADED=true
        return 0
    fi

    return 1
}

iptables_chain_exists() {
    local chain="$1"
    iptables -S "$chain" >/dev/null 2>&1
}

iptables_delete_rule_spec() {
    local chain="$1"
    shift

    while iptables -C "$chain" "$@" 2>/dev/null; do
        iptables -D "$chain" "$@" >/dev/null 2>&1 || break
    done
}

iptables_flush_delete_chain_if_exists() {
    local chain="$1"
    iptables -F "$chain" 2>/dev/null || true
    iptables -X "$chain" 2>/dev/null || true
}

iptables_flush_chain_if_exists() {
    local chain="$1"
    iptables -F "$chain" 2>/dev/null || true
}

iptables_ensure_l4d2_chains() {
    local chain
    for chain in \
        UDP_GAME_NEW_LIMIT \
        UDP_GAME_NEW_LIMIT_GLOBAL \
        UDP_GAME_ESTABLISHED_LIMIT \
        A2S_LIMITS \
        A2S_PLAYERS_LIMITS \
        A2S_RULES_LIMITS \
        STEAM_GROUP_LIMITS \
        l4d2loginfilter \
        TCPfilter; do
        iptables -N "$chain" 2>/dev/null || true
    done
}

clear_l4d2_rules_iptables() {
    local game_ports tv_ports query_ports protected_ports
    local steam_signatures_csv steam_sig
    local -a steam_signatures
    local invalid_log malformed_log tcp_log
    local chain

    if ! load_suite_env_if_present; then
        msg_error "Suite env not found at $SUITE_ENV_FILE; cannot safely derive L4D2 iptables rule specs."
        msg_info "Apply from the repo root with .env present, or use the nftables backend selective cleanup."
        return 1
    fi

    game_ports="${L4D2_GAMESERVER_PORTS:-}"
    tv_ports="${L4D2_TV_PORTS:-}"
    query_ports="${game_ports},${tv_ports}"
    query_ports="${query_ports//,,/,}"
    query_ports="${query_ports#,}"
    query_ports="${query_ports%,}"
    protected_ports="${L4D2_TCP_PROTECTION:-$game_ports}"

    invalid_log="${LOG_PREFIX_INVALID_SIZE:-INVALID_SIZE: }"
    malformed_log="${LOG_PREFIX_MALFORMED:-MALFORMED: }"
    tcp_log="${LOG_PREFIX_TCP_RCON_BLOCK:-TCP_RCON_BLOCK: }"

    msg_info "Clearing only L4D2 iptables restrictions..."

    for chain in INPUT DOCKER-USER; do
        iptables_chain_exists "$chain" || continue

        if [ -n "$game_ports" ]; then
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m state --state NEW -j UDP_GAME_NEW_LIMIT
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 0:28 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 2521:65535 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 30:32 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 46:46 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 60:60 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$invalid_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$invalid_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$game_ports" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
        fi

        if [ -n "$tv_ports" ]; then
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m state --state NEW -j UDP_GAME_NEW_LIMIT
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 0:28 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 2521:65535 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 30:32 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 46:46 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 60:60 -j DROP
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$invalid_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$invalid_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$tv_ports" -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$malformed_log" --log-level 4
        fi

        if [ -n "$query_ports" ]; then
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$query_ports" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$query_ports" -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$query_ports" -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS
            iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$query_ports" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF0000|' -j DROP

            steam_signatures_csv="${STEAM_GROUP_SIGNATURES:-69}"
            steam_signatures_csv="${steam_signatures_csv//[[:space:]]/}"
            IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
            for steam_sig in "${steam_signatures[@]}"; do
                [ -z "$steam_sig" ] && continue
                steam_sig="${steam_sig^^}"
                iptables_delete_rule_spec "$chain" -p udp -m multiport --dports "$query_ports" -m string --algo bm --hex-string "|FFFFFFFF${steam_sig}|" -j STEAM_GROUP_LIMITS
            done
        fi

        if [ -n "$protected_ports" ]; then
            iptables_delete_rule_spec "$chain" -p tcp -m multiport --dports "$protected_ports" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$tcp_log" --log-level 4
            iptables_delete_rule_spec "$chain" -p tcp -m multiport --dports "$protected_ports" -j DROP
        fi
    done

    for chain in \
        UDP_GAME_NEW_LIMIT \
        UDP_GAME_NEW_LIMIT_GLOBAL \
        UDP_GAME_ESTABLISHED_LIMIT \
        A2S_LIMITS \
        A2S_PLAYERS_LIMITS \
        A2S_RULES_LIMITS \
        STEAM_GROUP_LIMITS \
        l4d2loginfilter \
        TCPfilter; do
        iptables_flush_chain_if_exists "$chain"
    done

    msg_ok "L4D2 iptables rules cleared (VPN/SSH/Web rules preserved)"
}

clear_l4d2_rules_nftables() {
    local chain
    local table_family="inet"
    local table_name="firewall_main"

    if ! nft list table "$table_family" "$table_name" >/dev/null 2>&1; then
        msg_error "Table $table_family $table_name not found. Apply the current nftables.rules.sh layout first."
        msg_info "Legacy table inet l4d2_filter detected by ipp is not cleaned selectively because domains were mixed there."
        return 1
    fi

    msg_info "Clearing only L4D2 nftables chains from $table_family $table_name..."

    for chain in \
        input_l4d2_tcp \
        forward_l4d2_tcp \
        input_l4d2_udp \
        forward_l4d2_udp; do
        nft flush chain "$table_family" "$table_name" "$chain" 2>/dev/null || true
    done

    for chain in \
        udp_new_limit \
        udp_new_limit_global \
        udp_established_limit \
        a2s_info_limit \
        a2s_players_limit \
        a2s_rules_limit \
        steam_group_limit \
        login_connect_limit \
        login_reserve_limit; do
        nft flush chain "$table_family" "$table_name" "$chain" 2>/dev/null || true
        nft delete chain "$table_family" "$table_name" "$chain" 2>/dev/null || true
    done

    msg_ok "L4D2 nftables rules cleared (VPN/SSH/Web rules preserved)"
}

clear_l4d2_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        clear_l4d2_rules_iptables
    else
        clear_l4d2_rules_nftables
    fi
}

restore_l4d2_rules_iptables() {
    if ! load_suite_env_if_present; then
        msg_error "Suite env not found at $SUITE_ENV_FILE; cannot restore selective L4D2 iptables rules."
        return 1
    fi

    clear_l4d2_rules_iptables
    iptables_ensure_l4d2_chains

    msg_info "Reapplying only L4D2 iptables modules..."
    "$SCRIPT_DIR/iptables.rules.sh" \
        --env-file "$SUITE_ENV_FILE" \
        --set MODULES_ONLY="l4d2_tcpfilter_chain,l4d2_tcp_protect,l4d2_udp_base,l4d2_packet_validation,l4d2_a2s_filters" \
        --set MODULES_EXCLUDE= \
        --skip chain_setup \
        --skip finalize

    msg_ok "L4D2 iptables rules restored"
}

restore_l4d2_rules_nftables() {
    if ! load_suite_env_if_present; then
        msg_error "Suite env not found at $SUITE_ENV_FILE; cannot restore selective L4D2 nftables rules."
        return 1
    fi

    if ! nft list table inet firewall_main >/dev/null 2>&1; then
        msg_error "Table inet firewall_main not found. Apply the current nftables.rules.sh layout first."
        return 1
    fi

    clear_l4d2_rules_nftables

    msg_info "Reapplying only L4D2 nftables modules..."
    "$SCRIPT_DIR/nftables.rules.sh" \
        --env-file "$SUITE_ENV_FILE" \
        --set MODULES_ONLY="l4d2_tcp_protect,l4d2_udp_base,l4d2_packet_validation,l4d2_a2s_filters" \
        --set MODULES_EXCLUDE= \
        --skip chain_setup \
        --skip finalize

    msg_ok "L4D2 nftables rules restored"
}

restore_l4d2_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        restore_l4d2_rules_iptables
    else
        restore_l4d2_rules_nftables
    fi
}

nft_managed_table_entries_live() {
    nft list tables 2>/dev/null | awk '
        $1 == "table" && ($3 == "firewall_main" || $3 == "vpn_s2s_nat" || $3 ~ /^l4d2(_|$)/) {
            print $2 " " $3
        }
    '
}

nft_managed_table_entries_file() {
    local source_file="${1:-$NFT_CONF_FILE}"

    [ -f "$source_file" ] || return 0

    awk '
        $1 == "table" && ($3 == "firewall_main" || $3 == "vpn_s2s_nat" || $3 ~ /^l4d2(_|$)/) {
            print $2 " " $3
        }
    ' "$source_file" | awk '!seen[$0]++'
}

nft_write_managed_tables() {
    local output_file="$1"
    local tmp_file
    local entries=()
    local entry family table_name

    mapfile -t entries < <(nft_managed_table_entries_live)

    if [ "${#entries[@]}" -eq 0 ]; then
        msg_error "No managed nftables tables found (expected firewall_main / vpn_s2s_nat or legacy l4d2_*)."
        return 1
    fi

    tmp_file="$(mktemp)"
    trap 'rm -f "$tmp_file"' RETURN

    : > "$tmp_file"
    for entry in "${entries[@]}"; do
        family="${entry%% *}"
        table_name="${entry#* }"
        nft list table "$family" "$table_name" >> "$tmp_file"
        printf '\n' >> "$tmp_file"
    done

    chmod 644 "$tmp_file"
    mv "$tmp_file" "$output_file"
    trap - RETURN
}

nft_delete_managed_tables() {
    local source_file="${1:-$NFT_CONF_FILE}"
    local entries=()
    local entry family table_name

    mapfile -t entries < <(nft_managed_table_entries_file "$source_file")

    for entry in "${entries[@]}"; do
        family="${entry%% *}"
        table_name="${entry#* }"
        nft delete table "$family" "$table_name" 2>/dev/null || true
    done
}


# Function to display menu
show_menu() {
    print_header
    print_section_services "[Services]"
    print_option 1 "Install persistent service"
    print_option 2 "Remove  persistent service"
    echo ""
    print_section_rules "[Rules]"
    print_option 3 "Show current firewall rules"
    print_option 4 "Clear all active firewall rules"
    print_option 11 "Clear only L4D2 rules"
    print_option 12 "Restore only L4D2 rules"
    print_option 5 "Save current rules (persistent)"
    print_option 6 "Show saved rules file"
    print_option 7 "Clear saved rules file"
    print_option 8 "Reload saved rules"
    echo ""
    print_section_system "[System]"
    print_option 9 "Status of persistent service"
    print_option 10 "Switch backend (iptables/nftables)"
    print_option 0 "Exit"
    echo ""
    echo -ne "${C_BOLD}Select option [0-12]: ${C_RESET}"
}

# Function to install persistent service
install_persistent() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "Installing iptables-persistent..."

        echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
        echo iptables-persistent iptables-persistent/autosave_v6 boolean false | debconf-set-selections

        apt-get update -qq
        apt-get install -y iptables-persistent

        [ -f "$DIR_IPTABLES/rules.v6" ] && rm -f "$DIR_IPTABLES/rules.v6"
        mkdir -p "$DIR_IPTABLES"

        msg_ok "iptables-persistent installed successfully"
        msg_info "IPv6 support disabled (rules.v6 removed)"
    else
        msg_info "Installing nftables service..."
        apt-get update -qq
        apt-get install -y nftables
        systemctl enable --now nftables
        msg_ok "nftables installed and enabled"
    fi
}

# Function to remove persistent service
remove_persistent() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "Removing iptables-persistent..."
        apt-get purge -y iptables-persistent
        msg_ok "iptables-persistent removed successfully"
    else
        msg_info "Removing nftables service..."
        systemctl disable --now nftables || true
        apt-get purge -y nftables
        msg_ok "nftables removed successfully"
    fi
}

# Function to show current rules
show_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "Current iptables rules"
        echo "──────────────────────────"
        iptables -L -n -v --line-numbers
        echo ""
        msg_info "NAT table rules"
        echo "────────────────"
        iptables -t nat -L -n -v --line-numbers
    else
        msg_info "Current nftables ruleset"
        echo "────────────────────────"
        nft list ruleset
    fi
}

# Function to clear all rules
clear_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "Clearing all iptables rules..."

        iptables -P INPUT ACCEPT
        iptables -P FORWARD ACCEPT
        iptables -P OUTPUT ACCEPT

        iptables -F
        iptables -X
        iptables -t nat -F
        iptables -t nat -X
        iptables -t mangle -F
        iptables -t mangle -X

        msg_ok "All iptables rules cleared"
    else
        msg_info "Clearing all nftables rules..."
        nft flush ruleset
        msg_ok "All nftables rules cleared"
    fi
}

# Function to save current rules
save_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "Saving current iptables rules..."

        mkdir -p "$DIR_IPTABLES"
        iptables-save > "$DIR_IPTABLES/rules.v4"
        chmod 644 "$DIR_IPTABLES/rules.v4"

        msg_ok "Rules saved to $DIR_IPTABLES/rules.v4"
        msg_info "Total rules saved: $(grep -c '^-A' "$DIR_IPTABLES/rules.v4" 2>/dev/null || echo 0)"
    else
        msg_info "Saving current nftables rules..."

        if ! nft_suite_primary_table_exists; then
            msg_error "Managed nftables table not found (expected inet firewall_main or legacy inet l4d2_filter). Apply nftables.rules.sh first."
            return 1
        fi

        nft_write_managed_tables "$NFT_CONF_FILE"
        msg_ok "Rules saved to $NFT_CONF_FILE"
        msg_info "Managed tables saved: $(nft_managed_table_entries_file "$NFT_CONF_FILE" | wc -l)"
        msg_info "Total lines saved: $(wc -l < "$NFT_CONF_FILE" 2>/dev/null || echo 0)"
    fi
}

# Function to show saved rules
show_saved_rules() {
    local target_file
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        target_file="$DIR_IPTABLES/rules.v4"
    else
        target_file="$NFT_CONF_FILE"
    fi

    if [ -f "$target_file" ]; then
        msg_info "Saved rules from $target_file"
        echo "─────────────────────────────────────────────"
        less "$target_file"
    else
        msg_error "No saved rules file found at $target_file"
        msg_info "Use option 5 to save current rules first"
    fi
}

# Function to clear saved rules
clear_saved_rules() {
    local target_file
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        target_file="$DIR_IPTABLES/rules.v4"
    else
        target_file="$NFT_CONF_FILE"
    fi

    if [ -f "$target_file" ]; then
        msg_info "Clearing saved rules file..."
        > "$target_file"
        msg_ok "Saved rules file cleared"
    else
        msg_warn "No saved rules file found at $target_file"
    fi
}

# Function to reload saved rules
reload_rules() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        if [ -f "$DIR_IPTABLES/rules.v4" ]; then
            msg_info "Reloading saved iptables rules..."
            iptables-restore < "$DIR_IPTABLES/rules.v4"
            msg_ok "Rules reloaded successfully"
        else
            msg_error "No saved rules file found at $DIR_IPTABLES/rules.v4"
            msg_info "Use option 5 to save current rules first"
        fi
    else
        if [ -f "$NFT_CONF_FILE" ]; then
            msg_info "Reloading saved nftables rules..."

            nft_delete_managed_tables "$NFT_CONF_FILE"
            nft -f "$NFT_CONF_FILE"
            msg_ok "Rules reloaded successfully"
        else
            msg_error "No saved rules file found at $NFT_CONF_FILE"
            msg_info "Use option 5 to save current rules first"
        fi
    fi
}

# Function to show service status
show_status() {
    if [ "$ACTIVE_BACKEND" = "iptables" ]; then
        msg_info "IPTables service status"
        echo "────────────────────────"

        if dpkg -l | grep -q iptables-persistent; then
            msg_ok "iptables-persistent: INSTALLED"
        else
            msg_error "iptables-persistent: NOT INSTALLED"
        fi

        if [ -f "$DIR_IPTABLES/rules.v4" ]; then
            msg_ok "Rules file: EXISTS ($DIR_IPTABLES/rules.v4)"
            msg_info "Total saved rules: $(grep -c '^-A' "$DIR_IPTABLES/rules.v4" 2>/dev/null || echo 0)"
        else
            msg_error "Rules file: NOT FOUND"
        fi

        msg_info "Current active rules: $(iptables -S | wc -l)"
    else
        msg_info "NFTables service status"
        echo "────────────────────────"

        if dpkg -l | grep -q '^ii\s\+nftables\s'; then
            msg_ok "nftables package: INSTALLED"
        else
            msg_error "nftables package: NOT INSTALLED"
        fi

        if systemctl is-enabled nftables >/dev/null 2>&1; then
            msg_ok "nftables service: ENABLED"
        else
            msg_warn "nftables service: NOT ENABLED"
        fi

        if [ -f "$NFT_CONF_FILE" ]; then
            msg_ok "Rules file: EXISTS ($NFT_CONF_FILE)"
            msg_info "Total saved lines: $(wc -l < "$NFT_CONF_FILE" 2>/dev/null || echo 0)"
            msg_info "Managed tables in file: $(nft_managed_table_entries_file "$NFT_CONF_FILE" | wc -l)"
        else
            msg_error "Rules file: NOT FOUND ($NFT_CONF_FILE)"
        fi

        msg_info "Current active tables: $(nft list tables 2>/dev/null | wc -l)"
        msg_info "Current managed tables: $(nft_managed_table_entries_live | wc -l)"
    fi
}

switch_backend() {
    print_section "[Switch backend]"
    echo "  1) iptables"
    echo "  2) nftables"
    echo -ne "${C_BOLD}Choice [1-2]: ${C_RESET}"
    read -r backend_choice
    case "$backend_choice" in
        1)
            ACTIVE_BACKEND="iptables"
            msg_ok "Backend switched to iptables"
            ;;
        2)
            ACTIVE_BACKEND="nftables"
            msg_ok "Backend switched to nftables"
            ;;
        *)
            msg_error "Invalid backend choice"
            ;;
    esac
}

setup_colors
detect_default_backend

# Main menu loop
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1)
            install_persistent
            ;;
        2)
            remove_persistent
            ;;
        3)
            show_rules
            ;;
        4)
            msg_warn "This will clear ALL active firewall rules in backend '$ACTIVE_BACKEND'. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clear_rules
            else
                msg_error "Operation cancelled"
            fi
            ;;
        11)
            msg_warn "This will clear only L4D2 rules in backend '$ACTIVE_BACKEND' and keep VPN/SSH/Web rules. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clear_l4d2_rules
            else
                msg_error "Operation cancelled"
            fi
            ;;
        12)
            msg_warn "This will restore only L4D2 rules in backend '$ACTIVE_BACKEND' and keep VPN/SSH/Web rules untouched. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                restore_l4d2_rules
            else
                msg_error "Operation cancelled"
            fi
            ;;
        5)
            save_rules
            ;;
        6)
            show_saved_rules
            ;;
        7)
            msg_warn "This will clear the saved rules file for backend '$ACTIVE_BACKEND'. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clear_saved_rules
            else
                msg_error "Operation cancelled"
            fi
            ;;
        8)
            reload_rules
            ;;
        9)
            show_status
            ;;
        10)
            switch_backend
            ;;
        0)
            echo -e "${C_BOLD}EXIT:${C_RESET} Exiting..."
            break
            ;;
        *)
            msg_error "Invalid option. Please select 0-12."
            ;;
    esac

    pause_screen
done
