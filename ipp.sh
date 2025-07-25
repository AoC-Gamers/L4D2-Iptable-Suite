#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "❌ This script must be run as root or with sudo."
    exit 1
fi

DIR_IPTABLES="/etc/iptables"


# Function to display menu
show_menu() {
    echo ""
    echo "========================================="
    echo "       IPTables Persistent Manager      "
    echo "========================================="
    echo "1 - Install iptables-persistent"
    echo "2 - Remove  iptables-persistent"
    echo ""
    echo "3 - Show current iptables rules"
    echo "4 - Clear all iptables rules"
    echo ""
    echo "5 - Save current rules (persistent)"
    echo "6 - Show saved rules file"
    echo "7 - Clear saved rules file"
    echo ""
    echo "8 - Reload saved rules"
    echo "9 - Status of iptables service"
    echo ""
    echo "0 - Exit"
    echo "========================================="
    echo -n "Select option [0-9]: "
}

# Function to install iptables-persistent
install_persistent() {
    echo "🔄 Installing iptables-persistent..."
    
    # Pre-configure debconf to avoid interactive prompts
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean false | debconf-set-selections
    
    apt-get update -qq
    apt-get install -y iptables-persistent
    
    # Remove IPv6 rules file if it exists (we don't use IPv6)
    [ -f "$DIR_IPTABLES/rules.v6" ] && rm -f "$DIR_IPTABLES/rules.v6"
    
    # Ensure the directory exists
    mkdir -p "$DIR_IPTABLES"
    
    echo "✅ iptables-persistent installed successfully"
    echo "📝 IPv6 support disabled (rules.v6 removed)"
}

# Function to remove iptables-persistent
remove_persistent() {
    echo "🔄 Removing iptables-persistent..."
    apt-get purge -y iptables-persistent
    echo "✅ iptables-persistent removed successfully"
}

# Function to show current rules
show_rules() {
    echo "📋 Current iptables rules:"
    echo "=========================="
    iptables -L -n -v --line-numbers
    echo ""
    echo "📋 NAT table rules:"
    echo "=================="
    iptables -t nat -L -n -v --line-numbers
}

# Function to clear all rules
clear_rules() {
    echo "🧹 Clearing all iptables rules..."
    
    # Set default policies to ACCEPT
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    
    # Flush all rules and delete custom chains
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    iptables -t mangle -F
    iptables -t mangle -X
    
    echo "✅ All iptables rules cleared"
}

# Function to save current rules
save_rules() {
    echo "💾 Saving current iptables rules..."
    
    # Ensure directory exists
    mkdir -p "$DIR_IPTABLES"
    
    # Save IPv4 rules
    iptables-save > "$DIR_IPTABLES/rules.v4"
    
    # Set proper permissions
    chmod 644 "$DIR_IPTABLES/rules.v4"
    
    echo "✅ Rules saved to $DIR_IPTABLES/rules.v4"
    echo "📊 Total rules saved: $(grep -c '^-A' "$DIR_IPTABLES/rules.v4" 2>/dev/null || echo 0)"
}

# Function to show saved rules
show_saved_rules() {
    if [ -f "$DIR_IPTABLES/rules.v4" ]; then
        echo "📋 Saved iptables rules from $DIR_IPTABLES/rules.v4:"
        echo "============================================="
        less "$DIR_IPTABLES/rules.v4"
    else
        echo "❌ No saved rules file found at $DIR_IPTABLES/rules.v4"
        echo "💡 Use option 5 to save current rules first"
    fi
}

# Function to clear saved rules
clear_saved_rules() {
    if [ -f "$DIR_IPTABLES/rules.v4" ]; then
        echo "🗑️  Clearing saved rules file..."
        > "$DIR_IPTABLES/rules.v4"
        echo "✅ Saved rules file cleared"
    else
        echo "⚠️  No saved rules file found at $DIR_IPTABLES/rules.v4"
    fi
}

# Function to reload saved rules
reload_rules() {
    if [ -f "$DIR_IPTABLES/rules.v4" ]; then
        echo "🔄 Reloading saved iptables rules..."
        iptables-restore < "$DIR_IPTABLES/rules.v4"
        echo "✅ Rules reloaded successfully"
    else
        echo "❌ No saved rules file found at $DIR_IPTABLES/rules.v4"
        echo "💡 Use option 5 to save current rules first"
    fi
}

# Function to show service status
show_status() {
    echo "📊 IPTables service status:"
    echo "=========================="
    
    # Check if iptables-persistent is installed
    if dpkg -l | grep -q iptables-persistent; then
        echo "✅ iptables-persistent: INSTALLED"
    else
        echo "❌ iptables-persistent: NOT INSTALLED"
    fi
    
    # Check if rules file exists
    if [ -f "$DIR_IPTABLES/rules.v4" ]; then
        echo "✅ Rules file: EXISTS ($DIR_IPTABLES/rules.v4)"
        echo "📊 Total saved rules: $(grep -c '^-A' "$DIR_IPTABLES/rules.v4" 2>/dev/null || echo 0)"
    else
        echo "❌ Rules file: NOT FOUND"
    fi
    
    # Show current rule count
    echo "📊 Current active rules: $(iptables -S | wc -l)"
}

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
            echo "⚠️  This will clear ALL iptables rules. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clear_rules
            else
                echo "❌ Operation cancelled"
            fi
            ;;
        5)
            save_rules
            ;;
        6)
            show_saved_rules
            ;;
        7)
            echo "⚠️  This will clear the saved rules file. Continue? [y/N]"
            read -r confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clear_saved_rules
            else
                echo "❌ Operation cancelled"
            fi
            ;;
        8)
            reload_rules
            ;;
        9)
            show_status
            ;;
        0)
            echo "👋 Exiting..."
            break
            ;;
        *)
            echo "❌ Invalid option. Please select 0-9."
            ;;
    esac
    
    echo ""
    echo "Press Enter to continue..."
    read -r
done