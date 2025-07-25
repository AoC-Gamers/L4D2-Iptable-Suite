#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root or with sudo."
    exit 1
fi

if ! command -v dig >/dev/null 2>&1; then
    echo "❌ Error: 'dig' command is not installed. Run 'apt install dnsutils'."
    exit 1
fi

####################################################
############# Customize Stuff HERE #################
####################################################

# Load configuration from .env file
if [ -f "./.env" ]; then
    # Source the .env file, handling potential issues with spaces in values
    set -a  # automatically export all variables
    . "./.env"
    set +a  # disable automatic export
    echo "✅ Configuration loaded from .env file"
else
    echo "⚠️  .env file not found. Creating default configuration..."
    
    # Create default .env file
    cat > "./.env" << 'EOF'
# iptables iptables Configuration
# This file contains all customizable variables for the iptables script
# Modify these values according to your server setup

# Type of iptables chain to protect
# 0: INPUT only (native servers), 1: DOCKER only (containers), 2: BOTH
TYPECHAIN=0

# Enable/disable TCP protection against RCON spam
# true: Blocks malicious TCP connections to game ports (except whitelisted IPs)
# false: Allows normal TCP connections with basic rate-limiting
ENABLE_TCP_PROTECT=true

# Specific TCP ports to protect (optional when ENABLE_TCP_PROTECT=true)
# Format: "27001:27016" (range) or "27001,27002,27003" (specific)
# Empty: applies TCP protection to all GAMESERVERPORTS
# With value: applies protection only to these specific ports
TCP_PROTECTION=""

# Additional TCP ports for Docker containers (rate-limiting)
# Examples: "80,443" (HTTP/HTTPS), "8080" (HTTP-ALT), "3000:3100" (range)
# Empty: disabled. Only applies when TYPECHAIN includes DOCKER (1 or 2)
TCP_DOCKER=""

# Custom SSH ports for the system
# Format: "22" (standard), "422,4222,4223" (multiple), "2222:2230" (range)
# These ports are always allowed for remote administration
SSH_PORT="22"

# SSH ports for Docker containers (optional)
# Allows SSH access to specific containers. Same format as SSH_PORT
# Empty: disabled. Only applies when TYPECHAIN includes DOCKER (1 or 2)
SSH_DOCKER=""

# Source Engine game server ports (GameServer)
# These ports handle: player connections, A2S queries, Steam communication
# Standard format: "27001:27016" (16 servers), "27015" (single server)
GAMESERVERPORTS="27015"

# SourceTV ports (spectators and streaming)
# Separated from GameServer for better control. Only handle spectator traffic
# Standard format: "27101:27116" (matches GameServer count)
TVSERVERPORTS="27020"

# Server tickrate (determines cmdrate limits)
# Typical tickrates: 60 (casual), 100 - 128 (competitive)
# Used to calculate UDP limits: CMD_LIMIT+10 (burst), CMD_LIMIT+30 (maximum)
CMD_LIMIT=100

# Trusted IPs (complete system whitelist)
# These IPs bypass ALL iptables rules and have complete access to the entire machine
# Format: "1.2.3.4" (single IP), "1.2.3.4 5.6.7.8" (multiple space-separated)
# Use for: administrators, monitoring servers, absolutely trusted IPs only
# WARNING: These IPs will have unrestricted access to ALL ports and services
WHITELISTED_IPS=""

# Log prefixes for different packet types and attack patterns
# Used to categorize iptables logs for detailed analysis
# These prefixes help identify specific attack types in log files
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

    # Source the newly created .env file
    set -a
    . "./.env"
    set +a
    echo "✅ Default .env file created and loaded successfully"
    echo "📝 You can edit ./.env to customize your configuration"
    
    # Change ownership of .env file to the original user (not root)
    if [ -n "${SUDO_USER:-}" ]; then
        chown "$SUDO_USER:$SUDO_USER" "./.env"
        echo "🔧 File ownership changed to user: $SUDO_USER"
    fi
fi

# Set default values for any missing variables
TYPECHAIN=${TYPECHAIN:-0}
ENABLE_TCP_PROTECT=${ENABLE_TCP_PROTECT:-true}
TCP_PROTECTION=${TCP_PROTECTION:-""}
TCP_DOCKER=${TCP_DOCKER:-""}
SSH_PORT=${SSH_PORT:-"22"}
SSH_DOCKER=${SSH_DOCKER:-""}
GAMESERVERPORTS=${GAMESERVERPORTS:-"27015"}
TVSERVERPORTS=${TVSERVERPORTS:-"27020"}
CMD_LIMIT=${CMD_LIMIT:-100}
WHITELISTED_IPS=${WHITELISTED_IPS:-""}

# Log prefixes for different packet types and attack patterns
# Used to categorize iptables logs for detailed analysis
LOG_PREFIX_INVALID_SIZE=${LOG_PREFIX_INVALID_SIZE:-"INVALID_SIZE: "}
LOG_PREFIX_MALFORMED=${LOG_PREFIX_MALFORMED:-"MALFORMED: "}
LOG_PREFIX_A2S_INFO=${LOG_PREFIX_A2S_INFO:-"A2S_INFO_FLOOD: "}
LOG_PREFIX_A2S_PLAYERS=${LOG_PREFIX_A2S_PLAYERS:-"A2S_PLAYERS_FLOOD: "}
LOG_PREFIX_A2S_RULES=${LOG_PREFIX_A2S_RULES:-"A2S_RULES_FLOOD: "}
LOG_PREFIX_STEAM_GROUP=${LOG_PREFIX_STEAM_GROUP:-"STEAM_GROUP_FLOOD: "}
LOG_PREFIX_L4D2_CONNECT=${LOG_PREFIX_L4D2_CONNECT:-"L4D2_CONNECT_FLOOD: "}
LOG_PREFIX_L4D2_RESERVE=${LOG_PREFIX_L4D2_RESERVE:-"L4D2_RESERVE_FLOOD: "}
LOG_PREFIX_UDP_NEW_LIMIT=${LOG_PREFIX_UDP_NEW_LIMIT:-"UDP_NEW_LIMIT: "}
LOG_PREFIX_UDP_EST_LIMIT=${LOG_PREFIX_UDP_EST_LIMIT:-"UDP_EST_LIMIT: "}
LOG_PREFIX_TCP_RCON_BLOCK=${LOG_PREFIX_TCP_RCON_BLOCK:-"TCP_RCON_BLOCK: "}
LOG_PREFIX_ICMP_FLOOD=${LOG_PREFIX_ICMP_FLOOD:-"ICMP_FLOOD: "}

####################################################
############### Do not modify~! ####################
####################################################
CMD_LIMIT_LEEWAY=$((CMD_LIMIT + 10))
CMD_LIMIT_UPPER=$((CMD_LIMIT + 30))

###################################################################################################################
# _|___|___|___|___|___|___|___|___|___|___|___|___|                                                             ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        IPTables: Linux's Main line of Defense               ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        IPTables: Linux's way of saying no to DoS kids       ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__                                                             ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        Version 2.4   -                                      ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        IPTables Script created by Sir modified by lechuga   ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|                                                             ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        COVERED ATTACK PATTERNS:                             ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|                                                             ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        ✓ UDP Flooding (hashlimit rate-limiting)             ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        ✓ TCP RCON Spam (configurable TCP protection)        ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        ✓ A2S Query Flood (info/players/rules/steam group)   ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        ✓ Connection Flood (L4D2 connect/reserve strings)    ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        ✓ Invalid Packet Sizes (malformed UDP packets)       ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        ✓ ICMP Ping Flood (hashlimit rate-limiting)          ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        ✓ Steam Master Server Whitelisting (port 27011)      ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        ✓ GameServer vs SourceTV Port Separation             ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__        ✓ Docker Container Support (dual chain protection)   ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        ✓ IP Whitelist for Trusted Sources                   ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__                                                             ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|        Sources used and Studied;                            ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__  http://ipset.netfilter.org/iptables.man.html               ##
# _|___|___|___|___|___|___|___|___|___|___|___|___|  https://forums.alliedmods.net/showthread.php?t=151551      ##
# ___|___|___|___|___|___|___|___|___|___|___|___|__  http://www.cyberciti.biz/tips/linux-iptables-examples.html ##
###################################################################################################################

## Cleanup Rules First!
##--------------------
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
##--------------------

## Policies
##--------------------
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT
##--------------------

## Create Chains
##---------------------
iptables -N UDP_GAME_NEW_LIMIT 2>/dev/null || true
iptables -N UDP_GAME_NEW_LIMIT_GLOBAL 2>/dev/null || true
iptables -N UDP_GAME_ESTABLISHED_LIMIT 2>/dev/null || true
iptables -N A2S_LIMITS 2>/dev/null || true
iptables -N A2S_PLAYERS_LIMITS 2>/dev/null || true
iptables -N A2S_RULES_LIMITS 2>/dev/null || true
iptables -N STEAM_GROUP_LIMITS 2>/dev/null || true

## Sheo Iptable
iptables -N l4d2loginfilter 2>/dev/null || true

if [ "$ENABLE_TCP_PROTECT" = "true" ]; then
    iptables -N TCPfilter 2>/dev/null || true
elif [ -n "$TCP_PROTECTION" ] || [ -n "$TCP_DOCKER" ]; then
    iptables -N TCPfilter 2>/dev/null || true
fi

if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -N DOCKER 2>/dev/null || true
fi

##---------------------
## Restart Docker Service
##--------------------
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    service docker restart
fi
##--------------------

## Create Rules
##---------------------
if [ "$ENABLE_TCP_PROTECT" = "true" ] || [ -n "$TCP_PROTECTION" ] || [ -n "$TCP_DOCKER" ]; then
    iptables -A TCPfilter -m state --state NEW -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 5 --hashlimit-mode srcip,dstport --hashlimit-name TCPDOSPROTECT --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999999 -j ACCEPT
fi

iptables -A UDP_GAME_NEW_LIMIT -m hashlimit --hashlimit-upto 1/s --hashlimit-burst 3 --hashlimit-mode srcip,dstport --hashlimit-name L4D2_NEW_HASHLIMIT --hashlimit-htable-expire 5000 -j UDP_GAME_NEW_LIMIT_GLOBAL
iptables -A UDP_GAME_NEW_LIMIT -j DROP
iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -m hashlimit --hashlimit-upto 10/s --hashlimit-burst 20 --hashlimit-mode dstport --hashlimit-name L4D2_NEW_HASHLIMIT_GLOBAL --hashlimit-htable-expire 5000 -j ACCEPT
iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -j DROP
iptables -A UDP_GAME_ESTABLISHED_LIMIT -m hashlimit --hashlimit-upto ${CMD_LIMIT_LEEWAY}/s --hashlimit-burst ${CMD_LIMIT_UPPER} --hashlimit-mode srcip,srcport,dstport --hashlimit-name L4D2_ESTABLISHED_HASHLIMIT -j ACCEPT
iptables -A UDP_GAME_ESTABLISHED_LIMIT -j DROP
iptables -A A2S_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SFilter --hashlimit-htable-expire 5000 -j ACCEPT
iptables -A A2S_LIMITS -j DROP
iptables -A A2S_PLAYERS_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SPlayersFilter --hashlimit-htable-expire 5000 -j ACCEPT
iptables -A A2S_PLAYERS_LIMITS -j DROP
iptables -A A2S_RULES_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SRulesFilter --hashlimit-htable-expire 5000 -j ACCEPT
iptables -A A2S_RULES_LIMITS -j DROP
iptables -A STEAM_GROUP_LIMITS -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 3 --hashlimit-mode srcip,dstport --hashlimit-name STEAMGROUPFilter --hashlimit-htable-expire 5000 -j ACCEPT
iptables -A STEAM_GROUP_LIMITS -j DROP

# L4D2 login flood protection filter
# Prevents mass connection attacks using "connect" and "reserve" strings
iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 1 --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2CONNECTPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "connect" -j ACCEPT
iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 1 --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2RESERVEPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "reserve" -j ACCEPT
iptables -A l4d2loginfilter -j DROP

# Allow loopback traffic (local interface)
iptables -A INPUT -i lo -j ACCEPT
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A DOCKER -i lo -j ACCEPT
fi

# Allow all traffic from whitelisted IPs (complete system access)
# Applies to ALL ports and protocols for complete administration
for ip in $WHITELISTED_IPS; do

    if [ $TYPECHAIN -eq 0 ] || [ $TYPECHAIN -eq 2 ]; then
        # Allow all TCP and UDP traffic from whitelisted IPs (entire machine)
        iptables -A INPUT -s $ip -j ACCEPT
    fi
    if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
        # Allow all TCP and UDP traffic from whitelisted IPs (Docker containers)
        iptables -A DOCKER -s $ip -j ACCEPT
    fi
done

# UDP packet length validation for GameServers
# Blocks malformed packets that would never be valid in Source Engine
# 0-28 bytes: Too small for any valid command
# 2521+ bytes: Exceed standard MTU, possible malicious fragments
# 30-32, 46, 60 bytes: Specific sizes used in known attacks
if [ $TYPECHAIN -eq 0 ] || [ $TYPECHAIN -eq 2 ]; then
    # Too small packets (0-28 bytes)
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 0:28 -j DROP
    # Too large packets (2521+ bytes)
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 2521:65535 -j DROP

    # Malformed packets with specific attack sizes
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 30:32 -j DROP
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 46:46 -j DROP
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 60:60 -j DROP
fi
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    # Too small packets (0-28 bytes)
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 0:28 -j DROP
    # Too large packets (2521+ bytes)
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 2521:65535 -j DROP

    # Malformed packets with specific attack sizes
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 30:32 -j DROP
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 46:46 -j DROP
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 60:60 -j DROP
fi

# UDP packet length validation for SourceTV
# Applies same anti-flood validations as GameServers
# SourceTV only handles spectator streaming, but needs similar protection
if [ $TYPECHAIN -eq 0 ] || [ $TYPECHAIN -eq 2 ]; then
    # Too small packets (0-28 bytes)
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 0:28 -j DROP
    # Too large packets (2521+ bytes)
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 2521:65535 -j DROP

    # Malformed packets with specific attack sizes
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 30:32 -j DROP
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 46:46 -j DROP
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A INPUT -p udp -m multiport --dports $TVSERVERPORTS -m length --length 60:60 -j DROP
fi
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    # Too small packets (0-28 bytes)
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 0:28 -j DROP
    # Too large packets (2521+ bytes)
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 2521:65535 -j DROP

    # Malformed packets with specific attack sizes
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 30:32 -j DROP
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 46:46 -j DROP
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A DOCKER -p udp -m multiport --dports $TVSERVERPORTS -m length --length 60:60 -j DROP
fi

# A2S and Steam Group queries (GameServer ports only)
# A2S_INFO (0x54): Requests basic server information
# A2S_PLAYERS (0x55): Requests list of connected players
# A2S_RULES (0x56): Requests server variables/rules
# Steam Group (0x00): Steam group related queries
# IMPORTANT: SourceTV does NOT handle these queries, only GameServers
if [ $TYPECHAIN -eq 0 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF00|' -j STEAM_GROUP_LIMITS

    # Additional protection against specific attack patterns
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF0000|' -j DROP
    iptables -A INPUT -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
fi
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m string --algo bm --hex-string '|FFFFFFFF00|' -j STEAM_GROUP_LIMITS

    # Additional protection against specific attack patterns
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF0000|' -j DROP
    iptables -A DOCKER -p udp -m multiport --dports $GAMESERVERPORTS -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
fi

# ---------------------------------------
# TCP Protection: RCON Access Control
# ---------------------------------------
if [ "$ENABLE_TCP_PROTECT" = "true" ]; then
    echo "TCP Protection ENABLED: blocking RCON spam"

    # First, pre-accept SSH for INPUT
    iptables -A INPUT -p tcp -m multiport --dports $SSH_PORT -j ACCEPT
    # Note: WHITELISTED_IPS already have complete system access from above rules

    # Then, if TCP_PROTECTION is defined, only block those ports;
    # if not, block all TCP to game ports
    if [ -n "$TCP_PROTECTION" ]; then
        iptables -A INPUT -p tcp -m multiport --dports $TCP_PROTECTION -j DROP
    else
        iptables -A INPUT -p tcp -m multiport --dports $GAMESERVERPORTS -j DROP
    fi
    
    # Apply same rules for DOCKER if enabled
    if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
        # Note: WHITELISTED_IPS already have complete system access from above rules
        if [ -n "$TCP_PROTECTION" ]; then
            iptables -A DOCKER -p tcp -m multiport --dports $TCP_PROTECTION -j DROP
        else
            iptables -A DOCKER -p tcp -m multiport --dports $GAMESERVERPORTS -j DROP
        fi
    fi
else
    echo "TCP Protection DISABLED: no RCON blocks applied"
    # Original TCP rules when protection is disabled
    if [ -n "$TCP_PROTECTION" ]; then
        iptables -A INPUT -p tcp -m multiport --dports $TCP_PROTECTION -j TCPfilter
    fi
fi

# Rate-limiting for TCP ports in Docker containers
# Applies TCP traffic control when TYPECHAIN includes Docker (1 or 2)
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    if [ -n "$TCP_DOCKER" ]; then
        iptables -I DOCKER -p tcp -m multiport --dports $TCP_DOCKER -j TCPfilter
    fi
fi

# ---------------------------------------
# UDP Rules: Rate-limiting for GameServers and SourceTV
# ---------------------------------------
# Applies UDP rate limits to both server types according to TYPECHAIN configuration
# Controls NEW and ESTABLISHED connections separately for performance optimization
for chain in INPUT DOCKER; do
    # Skip chains not configured according to TYPECHAIN
    if [ "$chain" = "DOCKER" ] && [ $TYPECHAIN -eq 0 ]; then
        continue
    fi
    if [ "$chain" = "INPUT" ] && [ $TYPECHAIN -eq 1 ]; then
        continue
    fi
    
    # Rate-limiting for new UDP connections (GameServer + SourceTV)
    iptables -A $chain -p udp -m multiport --dports $GAMESERVERPORTS -m state --state NEW -j UDP_GAME_NEW_LIMIT
    iptables -A $chain -p udp -m multiport --dports $TVSERVERPORTS -m state --state NEW -j UDP_GAME_NEW_LIMIT
    
    # Rate-limiting for established UDP connections (GameServer + SourceTV)
    iptables -A $chain -p udp -m multiport --dports $GAMESERVERPORTS -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
    iptables -A $chain -p udp -m multiport --dports $TVSERVERPORTS -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
done

# Allow established and related connections (outbound traffic responses)
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A DOCKER -m state --state ESTABLISHED,RELATED -j ACCEPT
fi

# Allow DNS responses (outbound server queries)
iptables -A INPUT -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A DOCKER -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
fi

# ICMP (ping) protection with anti-flood rate-limiting
if [ $TYPECHAIN -eq 0 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A INPUT -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
fi
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    iptables -A DOCKER -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
fi

# Allow SSH access for server administration
iptables -A INPUT -p tcp -m multiport --dports $SSH_PORT -j ACCEPT
if [ $TYPECHAIN -eq 1 ] || [ $TYPECHAIN -eq 2 ]; then
    if [ -n "$SSH_DOCKER" ]; then
        iptables -I DOCKER -p tcp -m multiport --dports $SSH_DOCKER -j ACCEPT
    fi
fi

# ---------------------------------------
# Steam Master Server: Dynamic Whitelist
# ---------------------------------------
# Allows communication with Steam's master server for:
# - Server registration in public list
# - Heartbeats and status communication
# Dynamically resolves IPs for hl2master.steampowered.com
STEAM_MASTER_IPS=$(dig +short hl2master.steampowered.com A || true)
if [ -n "$STEAM_MASTER_IPS" ]; then
    echo "Adding allowed IPs for hl2master.steampowered.com (port 27011/UDP)"
    for ip in $STEAM_MASTER_IPS; do
        # Allow GameServer ↔ Steam Master Server communication
        iptables -C INPUT -p udp -s "$ip" --sport 27011 -m multiport --dports $GAMESERVERPORTS -j ACCEPT 2>/dev/null || \
        iptables -A INPUT -p udp -s "$ip" --sport 27011 -m multiport --dports $GAMESERVERPORTS -j ACCEPT
        # Allow SourceTV ↔ Steam Master Server communication
        iptables -C INPUT -p udp -s "$ip" --sport 27011 -m multiport --dports $TVSERVERPORTS -j ACCEPT 2>/dev/null || \
        iptables -A INPUT -p udp -s "$ip" --sport 27011 -m multiport --dports $TVSERVERPORTS -j ACCEPT
    done
else
    echo "❌ Could not resolve hl2master.steampowered.com"
fi

# Final policies: Deny all unauthorized traffic
##--------------------
iptables -A INPUT -j DROP
iptables -A FORWARD -j DROP
iptables -A OUTPUT -j ACCEPT
##--------------------

echo "✅ iptables rules applied successfully"
echo "   - SourceTV separated: Ports $TVSERVERPORTS"
echo "   - TCP Protection: $ENABLE_TCP_PROTECT"
echo "   - Chain type: $TYPECHAIN (0=INPUT, 1=DOCKER, 2=BOTH)"