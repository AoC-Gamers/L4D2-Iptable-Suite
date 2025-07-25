#!/usr/bin/env python3
"""
L4D2 iptables Log Analysis Tool
===============================

DESCRIPTION:
    Advanced log analysis script for L4D2 iptables with temporal analysis support
    and detailed JSON report generation by IP and general statistics.

USAGE:
    sudo python3 iptable.loggin.py [--env-file ENV_PATH]

COMPLETE COMMANDS:
    # Execute with default .env file (same directory)
    sudo python3 ./iptable.loggin.py

    # Execute specifying custom .env file
    sudo python3 ./iptable.loggin.py --env-file /custom/path/.env

    # From any directory (specify .env path)
    sudo python3 ./iptable.loggin.py --env-file ./.env

MENU OPTIONS:
    1. Install rsyslog and configure automatic logging
    2. Verify user permissions for log reading
    3. Add 'adm' group permissions to current user
    4. Analyze logs and generate reports (JSON with multiple analysis types)
    5. Exit

DEPENDENCIES:
    - pandas: pip install pandas
    - python-dotenv: pip install python-dotenv
    - .env file with LOG_PREFIX_* configuration variables

GENERATED FILES:
    - summary_by_ip.json: Detailed analysis by IP with timeline and multiple dates
      Contains: IP activity per date, attack timelines, duration calculations, 
      affected ports by type (GameServer/SourceTV), total statistics per IP
    
    - summary_by_port.json: Analysis grouped by destination port
      Contains: Port activity, attack types, time spans, top attackers per port
    
    - summary_by_day.json: Daily analysis with port breakdown
      Contains: Daily events, attack breakdown per port, attacker time distribution
    
    - summary_by_week.json: Weekly analysis with percentages
      Contains: Weekly totals, attack type breakdown, port distribution percentages
    
    - summary_by_month.json: Monthly analysis with comprehensive stats
      Contains: Monthly totals, attack/port breakdowns with percentages
    
    - summary_by_attack_type.json: Analysis grouped by attack pattern
      Contains: Attack type statistics, port distribution, temporal coverage

INPUT FILES:
    - .env: Configuration file with LOG_PREFIX_* variables and system paths
    - /var/log/l4d2-iptables.log: Main log file (configurable via LOGFILE in .env)
    - /etc/rsyslog.d/l4d2-iptables.conf: Rsyslog configuration (auto-generated)

ATTACK TYPES SUPPORTED:
    INVALID_SIZE, MALFORMED, A2S_INFO_FLOOD, A2S_PLAYERS_FLOOD, A2S_RULES_FLOOD,
    STEAM_GROUP_FLOOD, L4D2_CONNECT_FLOOD, L4D2_RESERVE_FLOOD, UDP_NEW_LIMIT,
    UDP_EST_LIMIT, TCP_RCON_BLOCK, ICMP_FLOOD

NOTE: Requires sudo permissions to configure rsyslog and access system logs.
"""

import argparse
import os
import subprocess
import re
import json
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

# Default values - will be overridden by .env file
LOGFILE = "/var/log/l4d2-iptables.log"
RSYSLOG_CONF = "/etc/rsyslog.d/l4d2-iptables.conf"

# Specific log prefixes for different attack types
LOG_PREFIXES = {
    "INVALID_SIZE": "INVALID_SIZE: ",
    "MALFORMED": "MALFORMED: ",
    "A2S_INFO_FLOOD": "A2S_INFO_FLOOD: ",
    "A2S_PLAYERS_FLOOD": "A2S_PLAYERS_FLOOD: ",
    "A2S_RULES_FLOOD": "A2S_RULES_FLOOD: ",
    "STEAM_GROUP_FLOOD": "STEAM_GROUP_FLOOD: ",
    "L4D2_CONNECT_FLOOD": "L4D2_CONNECT_FLOOD: ",
    "L4D2_RESERVE_FLOOD": "L4D2_RESERVE_FLOOD: ",
    "UDP_NEW_LIMIT": "UDP_NEW_LIMIT: ",
    "UDP_EST_LIMIT": "UDP_EST_LIMIT: ",
    "TCP_RCON_BLOCK": "TCP_RCON_BLOCK: ",
    "ICMP_FLOOD": "ICMP_FLOOD: "
}

def load_config(env_file):
    """Load configuration from .env file and update global variables"""
    global LOGFILE, RSYSLOG_CONF, LOG_PREFIXES
    
    if not os.path.exists(env_file):
        print(f"❌ .env file not found: {env_file}")
        return False
    
    load_dotenv(dotenv_path=env_file)
    
    # Update global variables from environment
    LOGFILE = os.getenv("LOGFILE", LOGFILE)
    RSYSLOG_CONF = os.getenv("RSYSLOG_CONF", RSYSLOG_CONF)
    
    # Update log prefixes from .env file
    for key in LOG_PREFIXES.keys():
        env_key = f"LOG_PREFIX_{key}"
        LOG_PREFIXES[key] = os.getenv(env_key, LOG_PREFIXES[key])
    
    return True

def expand_ports(port_string):
    ports = []
    if not port_string:
        return ports
    for part in port_string.split(','):
        if ':' in part:
            start, end = map(int, part.split(':'))
            ports.extend(range(start, end + 1))
        else:
            ports.append(int(part))
    return ports

def classify_port(port, game_ports, tv_ports):
    if port in game_ports:
        return "GameServer"
    elif port in tv_ports:
        return "SourceTV"
    else:
        return "Other"

def parse_log(log_path, game_ports, tv_ports):
    """Parse log file and extract attack information with timestamps"""
    ip_re = re.compile(r'SRC=(\S+)')
    port_re = re.compile(r'DPT=(\d+)')
    length_re = re.compile(r'LEN=(\d+)')
    timestamp_re = re.compile(r'^(\w+\s+\d+\s+\d+:\d+:\d+)')
    
    entries = []
    
    with open(log_path, "r") as f:
        for line in f:
            # Extract timestamp
            timestamp_match = timestamp_re.search(line)
            if not timestamp_match:
                continue
                
            timestamp_str = timestamp_match.group(1)
            
            # Parse timestamp and extract date/time components
            try:
                # Add year to timestamp (assuming current year)
                current_year = datetime.now().year
                full_timestamp = f"{current_year} {timestamp_str}"
                dt = datetime.strptime(full_timestamp, "%Y %b %d %H:%M:%S")
                fecha = dt.strftime("%Y-%m-%d")
                hora = dt.strftime("%H:%M:%S")
            except ValueError:
                continue
            
            ip = ip_re.search(line)
            port = port_re.search(line)
            length = length_re.findall(line)
            
            if not (ip and port and length):
                continue
                
            port_num = int(port.group(1))
            
            # Detect attack pattern from log prefixes
            pattern_detected = "UNKNOWN"
            for pattern_name, prefix in LOG_PREFIXES.items():
                if prefix.strip() in line:
                    pattern_detected = pattern_name
                    break
            
            entries.append({
                "IP": ip.group(1),
                "Port": port_num,
                "PortType": classify_port(port_num, game_ports, tv_ports),
                "Pattern": pattern_detected,
                "Length": int(length[-1]),
                "Date": fecha,
                "Time": hora,
                "Timestamp": dt
            })

    return pd.DataFrame(entries)

def generate_summary_by_ip(df):
    """Generate IP-grouped summary with multiple dates structure"""
    if df.empty:
        return []
    
    result = []
    
    # Group by IP
    for ip, ip_group in df.groupby("IP"):
        ip_data = {
            "IP": ip,
            "Activity_By_Date": {},
            "Total_Statistics": {},
            "Affected_Ports": {
                "GameServer": [],
                "SourceTV": []
            }
        }
        
        # Group by date for this IP
        for fecha, fecha_group in ip_group.groupby("Date"):
            # Calculate timeline for this date
            timestamps = fecha_group["Timestamp"].sort_values()
            first_attack = timestamps.iloc[0].strftime("%H:%M:%S")
            last_attack = timestamps.iloc[-1].strftime("%H:%M:%S")
            
            # Calculate duration
            if len(timestamps) > 1:
                duration_seconds = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds()
                if duration_seconds < 60:
                    duration = f"{int(duration_seconds)} seconds"
                elif duration_seconds < 3600:
                    minutes = int(duration_seconds // 60)
                    seconds = int(duration_seconds % 60)
                    duration = f"{minutes} minutes {seconds} seconds" if seconds > 0 else f"{minutes} minutes"
                else:
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    duration = f"{hours} hours {minutes} minutes" if minutes > 0 else f"{hours} hours"
            else:
                duration = "0 seconds"
            
            # Get unique attack types for this date
            attack_types = sorted(fecha_group["Pattern"].unique())
            
            ip_data["Activity_By_Date"][fecha] = {
                "Timeline": {
                    "First_Attack": first_attack,
                    "Last_Attack": last_attack,
                    "Attack_Duration": duration
                },
                "Events": len(fecha_group),
                "Types": attack_types
            }
        
        # Calculate total statistics
        attack_counts = ip_group["Pattern"].value_counts().to_dict()
        ip_data["Total_Statistics"]["Total_Events"] = len(ip_group)
        ip_data["Total_Statistics"].update(attack_counts)
        
        # Get affected ports by type
        gameserver_ports = sorted([p for p in ip_group["Port"].unique() 
                                 if ip_group[ip_group["Port"] == p]["PortType"].iloc[0] == "GameServer"])
        sourcetv_ports = sorted([p for p in ip_group["Port"].unique() 
                               if ip_group[ip_group["Port"] == p]["PortType"].iloc[0] == "SourceTV"])
        
        ip_data["Affected_Ports"]["GameServer"] = [str(p) for p in gameserver_ports]
        ip_data["Affected_Ports"]["SourceTV"] = [str(p) for p in sourcetv_ports]
        
        result.append(ip_data)
    
    return result

def generate_summary_by_port(df):
    """Generate port-grouped summary with attackers breakdown"""
    if df.empty:
        return {"summary_by_port": []}
    
    result = []
    
    # Group by port
    for port, port_group in df.groupby("Port"):
        port_type = port_group["PortType"].iloc[0]
        
        # Calculate time span
        timestamps = port_group["Timestamp"].sort_values()
        first_attack = timestamps.iloc[0].strftime("%Y-%m-%dT%H:%M:%S")
        last_attack = timestamps.iloc[-1].strftime("%Y-%m-%dT%H:%M:%S")
        
        # Calculate duration
        duration_seconds = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds()
        if duration_seconds < 86400:  # Less than 1 day
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            duration = f"{hours} hours, {minutes} minutes"
        else:
            days = int(duration_seconds // 86400)
            hours = int((duration_seconds % 86400) // 3600)
            duration = f"{days} days, {hours} hours"
        
        # Events breakdown
        events_breakdown = port_group["Pattern"].value_counts().to_dict()
        
        # Top attackers for this port
        attackers = []
        for ip, ip_group in port_group.groupby("IP"):
            ip_timestamps = ip_group["Timestamp"].sort_values()
            
            # Count per day for this attacker
            count_per_day = {}
            for date, date_group in ip_group.groupby("Date"):
                count_per_day[date] = len(date_group)
            
            attackers.append({
                "attack_ip": ip,
                "attack_total_events": len(ip_group),
                "attack_events_breakdown": ip_group["Pattern"].value_counts().to_dict(),
                "attack_time_sample": {
                    "first": ip_timestamps.iloc[0].strftime("%Y-%m-%dT%H:%M:%S"),
                    "last": ip_timestamps.iloc[-1].strftime("%Y-%m-%dT%H:%M:%S"),
                    "count_per_day": count_per_day
                }
            })
        
        # Sort attackers by total events (descending)
        attackers.sort(key=lambda x: x["attack_total_events"], reverse=True)
        
        result.append({
            "port": port,
            "port_type": port_type,
            "total_events": len(port_group),
            "events_breakdown": events_breakdown,
            "time_span": {
                "first": first_attack,
                "last": last_attack,
                "duration": duration
            },
            "attackers": attackers[:10]  # Top 10 attackers
        })
    
    # Sort by total events (descending)
    result.sort(key=lambda x: x["total_events"], reverse=True)
    
    return {"summary_by_port": result}

def generate_summary_by_day(df):
    """Generate daily summary with port and attacker breakdown"""
    if df.empty:
        return {"summary_by_day": []}
    
    result = []
    
    # Group by date
    for date, date_group in df.groupby("Date"):
        ports = []
        
        # Group by port within this date
        for port, port_group in date_group.groupby("Port"):
            port_type = port_group["PortType"].iloc[0]
            
            # Attack breakdown for this port on this date
            breakdown = port_group["Pattern"].value_counts().to_dict()
            
            # Attackers for this port on this date
            attackers = []
            for ip, ip_group in port_group.groupby("IP"):
                # Time distribution in 6-hour buckets
                time_distribution = {
                    "00:00-06:00": 0,
                    "06:00-12:00": 0,
                    "12:00-18:00": 0,
                    "18:00-24:00": 0
                }
                
                for _, row in ip_group.iterrows():
                    hour = row["Timestamp"].hour
                    if 0 <= hour < 6:
                        time_distribution["00:00-06:00"] += 1
                    elif 6 <= hour < 12:
                        time_distribution["06:00-12:00"] += 1
                    elif 12 <= hour < 18:
                        time_distribution["12:00-18:00"] += 1
                    else:
                        time_distribution["18:00-24:00"] += 1
                
                attackers.append({
                    "attack_ip": ip,
                    "events": len(ip_group),
                    "events_breakdown": ip_group["Pattern"].value_counts().to_dict(),
                    "time_distribution": time_distribution
                })
            
            # Sort attackers by events (descending)
            attackers.sort(key=lambda x: x["events"], reverse=True)
            
            ports.append({
                "port": port,
                "port_type": port_type,
                "events": len(port_group),
                "breakdown": breakdown,
                "attackers": attackers[:5]  # Top 5 attackers per port
            })
        
        # Sort ports by events (descending)
        ports.sort(key=lambda x: x["events"], reverse=True)
        
        result.append({
            "date": date,
            "total_events": len(date_group),
            "ports": ports
        })
    
    # Sort by date (descending)
    result.sort(key=lambda x: x["date"], reverse=True)
    
    return {"summary_by_day": result}

def generate_summary_by_week(df):
    """Generate weekly summary with percentages"""
    if df.empty:
        return {"summary_by_week": []}
    
    result = []
    
    # Add week column
    df['Week'] = df['Timestamp'].dt.to_period('W').apply(lambda r: r.start_time)
    
    # Group by week
    for week_start, week_group in df.groupby('Week'):
        week_end = week_start + pd.Timedelta(days=6)
        week_str = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        
        total_events = len(week_group)
        
        # Attack breakdown
        attack_breakdown = week_group["Pattern"].value_counts().to_dict()
        attack_breakdown_percent = {k: round((v/total_events)*100, 1) for k, v in attack_breakdown.items()}
        
        # Port breakdown
        attacked_ports = week_group["Port"].value_counts().to_dict()
        attacked_ports_percent = {str(k): round((v/total_events)*100, 1) for k, v in attacked_ports.items()}
        
        result.append({
            "week": week_str,
            "total_events": total_events,
            "attack_breakdown": attack_breakdown,
            "attack_breakdown_percent": attack_breakdown_percent,
            "attacked_ports": {str(k): v for k, v in attacked_ports.items()},
            "attacked_ports_percent": attacked_ports_percent
        })
    
    # Sort by week (descending)
    result.sort(key=lambda x: x["week"], reverse=True)
    
    return {"summary_by_week": result}

def generate_summary_by_month(df):
    """Generate monthly summary with comprehensive stats"""
    if df.empty:
        return {"summary_by_month": []}
    
    result = []
    
    # Add month column
    df['Month'] = df['Timestamp'].dt.to_period('M')
    
    # Group by month
    for month, month_group in df.groupby('Month'):
        month_str = month.strftime('%Y-%m')
        
        total_events = len(month_group)
        
        # Attack breakdown
        attack_breakdown = month_group["Pattern"].value_counts().to_dict()
        attack_breakdown_percent = {k: round((v/total_events)*100, 1) for k, v in attack_breakdown.items()}
        
        # Port breakdown
        attacked_ports = month_group["Port"].value_counts().to_dict()
        attacked_ports_percent = {str(k): round((v/total_events)*100, 1) for k, v in attacked_ports.items()}
        
        result.append({
            "month": month_str,
            "total_events": total_events,
            "attack_breakdown": attack_breakdown,
            "attack_breakdown_percent": attack_breakdown_percent,
            "attacked_ports": {str(k): v for k, v in attacked_ports.items()},
            "attacked_ports_percent": attacked_ports_percent
        })
    
    # Sort by month (descending)
    result.sort(key=lambda x: x["month"], reverse=True)
    
    return {"summary_by_month": result}

def generate_summary_by_attack_type(df):
    """Generate attack type summary with port distribution"""
    if df.empty:
        return {"summary_by_attack_type": []}
    
    result = []
    total_events = len(df)
    
    # Group by attack pattern
    for pattern, pattern_group in df.groupby("Pattern"):
        pattern_events = len(pattern_group)
        
        # Port distribution
        port_distribution = {}
        for port_type in pattern_group["PortType"].unique():
            port_type_data = pattern_group[pattern_group["PortType"] == port_type]
            port_distribution[port_type] = len(port_type_data)
        
        # Days with events
        days_with_events = pattern_group["Date"].nunique()
        
        result.append({
            "attack_type": pattern,
            "total_events": pattern_events,
            "percentage_of_total": round((pattern_events/total_events)*100, 1),
            "port_distribution": port_distribution,
            "days_with_events": days_with_events
        })
    
    # Sort by total events (descending)
    result.sort(key=lambda x: x["total_events"], reverse=True)
    
    return {"summary_by_attack_type": result}

def menu_analysis_options():
    """Menu to select analysis type (JSON only)"""
    print("\n=== ANALYSIS TYPE ===")
    print("1. Summary by IP (detailed structure with multiple dates)")
    print("2. Summary by Port (port-focused with top attackers)")
    print("3. Summary by Day (daily breakdown with time distribution)")
    print("4. Summary by Week (weekly analysis with percentages)")
    print("5. Summary by Month (monthly comprehensive stats)")
    print("6. Summary by Attack Type (attack pattern analysis)")
    print("7. Generate ALL reports (all analysis types)")
    print("8. Cancel")
    
    choice = input("Select analysis type [1-8]: ").strip()
    if choice == "8":
        return None, None
    elif choice not in ["1", "2", "3", "4", "5", "6", "7"]:
        print("❌ Invalid option")
        return None, None
    
    if choice == "7":
        return "all", "all"
    
    analysis_types = {
        "1": "by_ip",
        "2": "by_port", 
        "3": "by_day",
        "4": "by_week",
        "5": "by_month",
        "6": "by_attack_type"
    }
    
    analysis_type = analysis_types[choice]
    
    # Generate JSON filename in script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = f"summary_{analysis_type}.json"
    filepath = os.path.join(script_dir, filename)
    
    return filepath, analysis_type

def generate_all_reports(df):
    """Generate all analysis types in JSON format"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    reports = {
        "by_ip": generate_summary_by_ip,
        "by_port": generate_summary_by_port,
        "by_day": generate_summary_by_day,
        "by_week": generate_summary_by_week,
        "by_month": generate_summary_by_month,
        "by_attack_type": generate_summary_by_attack_type
    }
    
    generated_files = []
    
    print("🔄 Generating all analysis reports...")
    
    for analysis_type, generator_func in reports.items():
        try:
            print(f"  📊 Generating {analysis_type} analysis...")
            
            # Generate the analysis data
            summary_data = generator_func(df)
            
            # Create filepath
            filename = f"summary_{analysis_type}.json"
            filepath = os.path.join(script_dir, filename)
            
            # Export to JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False, default=str)
            
            generated_files.append({
                'type': analysis_type,
                'file': filepath,
                'size': os.path.getsize(filepath)
            })
            
            print(f"    ✅ {filename} created successfully")
            
        except Exception as e:
            print(f"    ❌ Error generating {analysis_type}: {e}")
    
    return generated_files

def check_permissions():
    import getpass
    user = os.environ.get("SUDO_USER") or getpass.getuser()
    result = subprocess.run(["id", "-nG", user], capture_output=True, text=True)
    return "adm" in result.stdout.split()

def install_rsyslog_and_config():
    print("[1] Installing rsyslog and creating custom configuration...")

    if subprocess.call(["which", "rsyslogd"], stdout=subprocess.DEVNULL) != 0:
        print("⏳ Installing rsyslog...")
        subprocess.call(["apt", "update"])
        subprocess.call(["apt", "install", "-y", "rsyslog"])
    else:
        print("✅ rsyslog is already installed.")

    print("🛠️ Configuring", RSYSLOG_CONF)
    with open(RSYSLOG_CONF, "w") as f:
        for pattern_name, prefix in LOG_PREFIXES.items():
            f.write(f':msg,contains,"{prefix.strip()}"    {LOGFILE}\n')
        f.write("& stop\n")

    subprocess.call(["systemctl", "restart", "rsyslog"])
    print("✅ Installation and configuration completed.")
    print(f"📝 Optimized configuration: only {len(LOG_PREFIXES)} specific prefixes")

def verify_permissions():
    user = os.environ.get("SUDO_USER") or os.getlogin()
    print(f"[2] Verifying if '{user}' belongs to 'adm' group...")
    if check_permissions():
        print(f"✅ User '{user}' belongs to 'adm' and can read logs.")
    else:
        print(f"❌ User '{user}' does NOT belong to 'adm' group.")

def add_permissions():
    user = os.environ.get("SUDO_USER") or os.getlogin()
    print(f"[3] Adding permissions for '{user}'...")
    if check_permissions():
        print(f"✅ User '{user}' already belongs to 'adm' group. Nothing to do.")
    else:
        subprocess.call(["usermod", "-aG", "adm", user])
        print("✅ Permissions added. Please log out and log back in for changes to take effect.")

def run_analysis(env_file):
    if not load_config(env_file):
        return

    if not os.path.exists(LOGFILE):
        print(f"❌ Log file not found: {LOGFILE}")
        return

    print(f"📁 Reading logs from: {LOGFILE}")
    game_ports = expand_ports(os.getenv("GAMESERVERPORTS", ""))
    tv_ports = expand_ports(os.getenv("TVSERVERPORTS", ""))
    df = parse_log(LOGFILE, game_ports, tv_ports)
    
    if df.empty:
        print("⚠️  No events found in log file")
        return
    
    print(f"📊 Found {len(df)} events from {df['IP'].nunique()} different IPs")
    print(f"🗓️  Temporal coverage: {df['Date'].nunique()} unique days")

    output_path, analysis_type = menu_analysis_options()
    if not output_path:
        print("❌ Operation cancelled.")
        return

    if analysis_type == "all":
        # Generate all reports
        generated_files = generate_all_reports(df)
        
        if generated_files:
            print(f"\n✅ All analysis reports generated successfully!")
            print(f"📂 Location: {os.path.dirname(os.path.abspath(__file__))}")
            print(f"📊 Summary: {len(generated_files)} files generated")
            
            # Show detailed summary
            total_size = sum(f['size'] for f in generated_files)
            print(f"📈 Total data size: {total_size:,} bytes")
            
            print("\n📋 Generated files:")
            for file_info in generated_files:
                filename = os.path.basename(file_info['file'])
                size_kb = file_info['size'] / 1024
                print(f"  • {filename} ({size_kb:.1f} KB)")
        else:
            print("❌ No files were generated successfully")
        return

    print(f"🔄 Generating {analysis_type} analysis in JSON format...")
    
    try:
        if analysis_type == "by_ip":
            summary_data = generate_summary_by_ip(df)
        elif analysis_type == "by_port":
            summary_data = generate_summary_by_port(df)
        elif analysis_type == "by_day":
            summary_data = generate_summary_by_day(df)
        elif analysis_type == "by_week":
            summary_data = generate_summary_by_week(df)
        elif analysis_type == "by_month":
            summary_data = generate_summary_by_month(df)
        elif analysis_type == "by_attack_type":
            summary_data = generate_summary_by_attack_type(df)
        else:
            print("❌ Unknown analysis type")
            return
        
        # Export to JSON with proper formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"✅ Analysis exported successfully to: {output_path}")
        print(f"📂 Location: {os.path.abspath(output_path)}")
        
        # Show quick summary based on analysis type
        if analysis_type == "by_ip":
            print(f"📈 Summary: {len(summary_data)} IPs analyzed")
        elif analysis_type == "by_port":
            port_count = len(summary_data.get('summary_by_port', []))
            print(f"📈 Summary: {port_count} ports analyzed")
        elif analysis_type == "by_day":
            day_count = len(summary_data.get('summary_by_day', []))
            print(f"📈 Summary: {day_count} days analyzed")
        elif analysis_type == "by_week":
            week_count = len(summary_data.get('summary_by_week', []))
            print(f"📈 Summary: {week_count} weeks analyzed")
        elif analysis_type == "by_month":
            month_count = len(summary_data.get('summary_by_month', []))
            print(f"📈 Summary: {month_count} months analyzed")
        elif analysis_type == "by_attack_type":
            attack_count = len(summary_data.get('summary_by_attack_type', []))
            print(f"📈 Summary: {attack_count} attack types analyzed")
        
    except Exception as e:
        print(f"❌ Error generating analysis: {e}")
        return

def main_menu(env_file):
    while True:
        print("\n===== L4D2 Logging Manager =====")
        print("1. Install rsyslog and configure logging")
        print("2. Verify current user permissions")
        print("3. Add permissions ('adm' group)")
        print("4. Analyze logs and generate summary")
        print("5. Exit")
        print("================================")
        opt = input("Select an option [1-5]: ").strip()

        if opt == "1":
            if load_config(env_file):
                install_rsyslog_and_config()
        elif opt == "2":
            verify_permissions()
        elif opt == "3":
            add_permissions()
        elif opt == "4":
            run_analysis(env_file)
        elif opt == "5":
            print("👋 Exiting...")
            break
        else:
            print("❌ Invalid option.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("❌ This script must be run as root or with sudo.")
        print(f"➡️  Use: sudo {__file__}")
        exit(1)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="L4D2 iptables Log Manager")
    parser.add_argument(
        "--env-file", 
        default=".env",
        help="Path to .env file with configuration (default: .env)"
    )
    
    args = parser.parse_args()
    main_menu(args.env_file)