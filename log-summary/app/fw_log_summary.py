#!/usr/bin/env python3
import json
import os
import re
import time
from typing import List, Dict
from collections import Counter, defaultdict
from datetime import datetime, timedelta

LOG_PATH = os.getenv("SUMMARY_LOG_PATH", "/var/log/firewall-suite.log")
OUTPUT_DIR = os.getenv("SUMMARY_OUTPUT_DIR", "/output")
TOP_N = int(os.getenv("SUMMARY_TOP_N", "20"))
WINDOW_MINUTES = int(os.getenv("SUMMARY_WINDOW_MINUTES", "60"))
POLL_SECONDS = int(os.getenv("SUMMARY_POLL_SECONDS", "60"))
RUN_MODE = os.getenv("SUMMARY_RUN_MODE", "loop").strip().lower()
STATUS_PATH = os.getenv("SUMMARY_STATUS_PATH", os.path.join(OUTPUT_DIR, "summary.status.json"))

FW_EVT_RE = re.compile(r"FW_EVT\s+(.*?):")
KV_RE = re.compile(r"(\w+)=([^\s:]+)")
SRC_RE = re.compile(r"SRC=([^\s]+)")
DPT_RE = re.compile(r"DPT=(\d+)")
LEN_RE = re.compile(r"LEN=(\d+)")
TS_RE = re.compile(r"^(\w+\s+\d+\s+\d+:\d+:\d+)")


MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def log(level: str, message: str):
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"{ts} [{level}] {message}", flush=True)


def print_startup_banner():
    log("INFO", "==================================================")
    log("INFO", "Firewall Log Summary Container - Startup")
    log("INFO", "==================================================")
    log("INFO", f"SUMMARY_LOG_MOUNT_DIR={os.getenv('SUMMARY_LOG_MOUNT_DIR', '')}")
    log("INFO", f"SUMMARY_LOG_PATH={LOG_PATH}")
    log("INFO", f"SUMMARY_OUTPUT_DIR={OUTPUT_DIR}")
    log("INFO", f"SUMMARY_TOP_N={TOP_N}")
    log("INFO", f"SUMMARY_WINDOW_MINUTES={WINDOW_MINUTES}")
    log("INFO", f"SUMMARY_POLL_SECONDS={POLL_SECONDS}")
    log("INFO", f"SUMMARY_RUN_MODE={RUN_MODE}")
    log("INFO", "==================================================")


def parse_syslog_timestamp(line: str, now: datetime):
    match = TS_RE.search(line)
    if not match:
        return None

    parts = match.group(1).split()
    if len(parts) != 3:
        return None

    month_name, day_str, hms = parts
    month = MONTHS.get(month_name)
    if not month:
        return None

    try:
        day = int(day_str)
        hour, minute, second = map(int, hms.split(":"))
    except ValueError:
        return None

    year = now.year
    try:
        candidate = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None

    # Handle Jan logs seen during Dec->Jan boundary.
    if candidate > now + timedelta(days=2):
        try:
            candidate = datetime(year - 1, month, day, hour, minute, second)
        except ValueError:
            return None

    return candidate


def parse_fw_evt(line: str):
    match = FW_EVT_RE.search(line)
    if not match:
        return None

    fields = {}
    for key, value in KV_RE.findall(match.group(1)):
        fields[key] = value

    if "attack" not in fields:
        return None

    src_match = SRC_RE.search(line)
    dpt_match = DPT_RE.search(line)
    len_match = LEN_RE.search(line)

    fields["src"] = src_match.group(1) if src_match else ""
    fields["dpt"] = dpt_match.group(1) if dpt_match else ""
    fields["pkt_len"] = len_match.group(1) if len_match else ""

    return fields


def ensure_output_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_atomic(path: str, content: str):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)


def read_status(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def summarize_events(events, generated_at):
    attack_counter = Counter()
    source_counter = Counter()
    port_counter = Counter()
    severity_counter = Counter()
    module_counter = Counter()
    chain_counter = Counter()
    action_counter = Counter()

    unique_sources_by_attack = defaultdict(set)

    for evt in events:
        attack = evt.get("attack", "unknown")
        source = evt.get("src", "unknown")
        dpt = evt.get("dpt", "unknown")
        severity = evt.get("severity", "unknown")
        module = evt.get("module", "unknown")
        chain = evt.get("chain", "unknown")
        action = evt.get("action", "unknown")

        attack_counter[attack] += 1
        source_counter[source] += 1
        port_counter[dpt] += 1
        severity_counter[severity] += 1
        module_counter[module] += 1
        chain_counter[chain] += 1
        action_counter[action] += 1

        unique_sources_by_attack[attack].add(source)

    summary = {
        "generated_at": generated_at.isoformat(),
        "window_minutes": WINDOW_MINUTES,
        "events_total": len(events),
        "top_n": TOP_N,
        "by_attack": attack_counter.most_common(TOP_N),
        "by_source": source_counter.most_common(TOP_N),
        "by_port": port_counter.most_common(TOP_N),
        "by_severity": severity_counter.most_common(TOP_N),
        "by_module": module_counter.most_common(TOP_N),
        "by_chain": chain_counter.most_common(TOP_N),
        "by_action": action_counter.most_common(TOP_N),
        "unique_sources_by_attack": {
            attack: len(srcs) for attack, srcs in sorted(unique_sources_by_attack.items())
        },
    }

    return summary


def render_text(summary):
    lines = []
    lines.append("Firewall Log Summary")
    lines.append(f"Generated at: {summary['generated_at']}")
    lines.append(f"Window minutes: {summary['window_minutes']}")
    lines.append(f"Events total: {summary['events_total']}")
    lines.append("")

    sections = [
        ("Top attacks", "by_attack"),
        ("Top sources", "by_source"),
        ("Top destination ports", "by_port"),
        ("By severity", "by_severity"),
        ("By module", "by_module"),
        ("By chain", "by_chain"),
        ("By action", "by_action"),
    ]

    for title, key in sections:
        lines.append(f"[{title}]")
        items = summary.get(key, [])
        if not items:
            lines.append("- none")
        else:
            for name, count in items:
                lines.append(f"- {name}: {count}")
        lines.append("")

    lines.append("[Unique sources by attack]")
    unique_map = summary.get("unique_sources_by_attack", {})
    if not unique_map:
        lines.append("- none")
    else:
        for attack, count in unique_map.items():
            lines.append(f"- {attack}: {count}")

    lines.append("")
    return "\n".join(lines)


def load_events(now: datetime) -> List[Dict[str, str]]:
    events = []
    min_dt = None
    if WINDOW_MINUTES > 0:
        min_dt = now - timedelta(minutes=WINDOW_MINUTES)

    if os.path.isdir(LOG_PATH):
        log(
            "WARNING",
            f"SUMMARY_LOG_PATH points to a directory, not a file: {LOG_PATH}. "
            "Check SUMMARY_LOG_PATH and SUMMARY_LOG_MOUNT_DIR in env files.",
        )
        return []

    try:
        total_lines = 0
        matched_events = 0
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                evt = parse_fw_evt(line)
                if not evt:
                    continue

                if min_dt is not None:
                    ts = parse_syslog_timestamp(line, now)
                    if ts is None or ts < min_dt:
                        continue

                events.append(evt)
                matched_events += 1
        log(
            "INFO",
            f"log scan complete: total_lines={total_lines}, fw_evt_events={matched_events}, "
            f"window_minutes={WINDOW_MINUTES}",
        )
    except FileNotFoundError:
        log("WARNING", f"log file not found: {LOG_PATH}")
        return []
    except PermissionError:
        log("WARNING", f"permission denied reading log file: {LOG_PATH}")
        return []
    except IsADirectoryError:
        log("WARNING", f"log path is a directory, expected file: {LOG_PATH}")
        return []

    return events


def run_once():
    now = datetime.now()
    ensure_output_dir(OUTPUT_DIR)
    log("INFO", "starting summary cycle")

    events = load_events(now)
    summary = summarize_events(events, now)

    summary_json = json.dumps(summary, indent=2, ensure_ascii=False)
    summary_txt = render_text(summary)

    previous_status = read_status(STATUS_PATH)
    prev_empty = int(previous_status.get("consecutive_empty_cycles", 0))
    if summary["events_total"] == 0:
        empty_cycles = prev_empty + 1
    else:
        empty_cycles = 0

    status = {
        "last_run": now.isoformat(),
        "events_total": summary["events_total"],
        "consecutive_empty_cycles": empty_cycles,
        "window_minutes": WINDOW_MINUTES,
        "log_path": LOG_PATH,
    }

    write_atomic(os.path.join(OUTPUT_DIR, "summary.latest.json"), summary_json + "\n")
    write_atomic(os.path.join(OUTPUT_DIR, "summary.latest.txt"), summary_txt)
    write_atomic(STATUS_PATH, json.dumps(status, indent=2, ensure_ascii=False) + "\n")
    log(
        "INFO",
        f"files written: {os.path.join(OUTPUT_DIR, 'summary.latest.json')}, "
        f"{os.path.join(OUTPUT_DIR, 'summary.latest.txt')}, {STATUS_PATH}",
    )

    log(
        "INFO",
        f"generated summary: events_total={summary['events_total']}, "
        f"window_minutes={WINDOW_MINUTES}, top_n={TOP_N}, "
        f"consecutive_empty_cycles={empty_cycles}",
    )


def main():
    print_startup_banner()

    if RUN_MODE == "once":
        log("INFO", "run mode is 'once'; executing single cycle")
        run_once()
        log("INFO", "single cycle completed; exiting")
        return

    log("INFO", "run mode is 'loop'; entering periodic execution")
    while True:
        run_once()
        log("INFO", f"sleeping for {POLL_SECONDS} seconds")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
