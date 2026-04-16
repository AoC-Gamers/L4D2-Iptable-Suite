#!/usr/bin/env python3
"""Check how the configured GeoIP policy classifies an IPv4 address/CIDR."""

from __future__ import annotations

import argparse
import ipaddress
import json
import shlex
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class NetworkEntry:
    network: ipaddress.IPv4Network
    source: str


@dataclass(frozen=True)
class Coverage:
    status: str
    matches: list[NetworkEntry]


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        try:
            parts = shlex.split(raw_value, comments=True, posix=True)
            value = " ".join(parts)
        except ValueError:
            value = raw_value.strip().strip('"').strip("'")

        env[key] = value

    return env


def resolve_config_path(value: str, project_root: Path) -> Path:
    if not value:
        return Path()
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / value.removeprefix("./")


def normalize_country_csv(value: str) -> list[str]:
    countries: list[str] = []
    for item in value.replace(";", ",").split(","):
        code = item.strip().upper()
        if code:
            countries.append(code)
    return countries


def parse_target(value: str) -> ipaddress.IPv4Network:
    raw = value.strip()
    if not raw:
        raise ValueError("empty IP/CIDR value")

    try:
        target = ipaddress.ip_network(raw if "/" in raw else f"{raw}/32", strict=False)
    except ValueError as exc:
        raise ValueError(f"invalid IPv4 address/CIDR: {raw}") from exc

    if target.version != 4:
        raise ValueError("geo_country_filter currently supports IPv4 only")

    return target


def parse_network(raw: str, source: str) -> NetworkEntry | None:
    value = raw.split("#", 1)[0].strip()
    if not value:
        return None

    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None

    if network.version != 4:
        return None

    return NetworkEntry(network=network, source=source)


def load_network_file(path: Path, source_prefix: str) -> list[NetworkEntry]:
    if not path.exists():
        return []

    entries: list[NetworkEntry] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        entry = parse_network(raw_line, f"{source_prefix}:{path.name}:{line_no}")
        if entry:
            entries.append(entry)
    return entries


def load_inline_networks(value: str, source_prefix: str) -> list[NetworkEntry]:
    entries: list[NetworkEntry] = []
    for raw in value.replace(",", " ").split():
        entry = parse_network(raw, source_prefix)
        if entry:
            entries.append(entry)
    return entries


def load_country_networks(data_dir: Path, countries: Iterable[str], source_prefix: str) -> list[NetworkEntry]:
    entries: list[NetworkEntry] = []
    for country in countries:
        path = data_dir / f"{country}.ipv4.txt"
        entries.extend(load_network_file(path, f"{source_prefix}:{country}"))
    return entries


def resolve_domain_entries(domains: str, source_prefix: str) -> list[NetworkEntry]:
    entries: list[NetworkEntry] = []
    for domain in domains.split():
        try:
            _, _, addresses = socket.gethostbyname_ex(domain)
        except OSError:
            continue

        for address in sorted(set(addresses)):
            entry = parse_network(address, f"{source_prefix}:{domain}")
            if entry:
                entries.append(entry)
    return entries


def coverage_for(target: ipaddress.IPv4Network, entries: list[NetworkEntry]) -> Coverage:
    matches = [entry for entry in entries if target.overlaps(entry.network)]
    if not matches:
        return Coverage(status="none", matches=[])

    remaining = [target]
    for entry in matches:
        next_remaining: list[ipaddress.IPv4Network] = []
        for network in remaining:
            if not network.overlaps(entry.network):
                next_remaining.append(network)
            elif network.subnet_of(entry.network):
                continue
            elif entry.network.subnet_of(network):
                next_remaining.extend(network.address_exclude(entry.network))
            else:
                next_remaining.append(network)
        remaining = list(ipaddress.collapse_addresses(next_remaining))

    return Coverage(status="full" if not remaining else "partial", matches=matches)


def format_matches(matches: list[NetworkEntry], limit: int = 8) -> list[str]:
    output = [f"{entry.network} ({entry.source})" for entry in matches[:limit]]
    if len(matches) > limit:
        output.append(f"... {len(matches) - limit} more")
    return output


def discover_country_membership(target: ipaddress.IPv4Network, data_dir: Path) -> list[str]:
    if not data_dir.is_dir():
        return []

    countries: list[str] = []
    for path in sorted(data_dir.glob("*.ipv4.txt")):
        entries = load_network_file(path, f"country:{path.stem.removesuffix('.ipv4')}")
        coverage = coverage_for(target, entries)
        if coverage.status != "none":
            countries.append(f"{path.stem.removesuffix('.ipv4')}:{coverage.status}")
    return countries


def decide(target: ipaddress.IPv4Network, env: dict[str, str], project_root: Path, resolve_domains: bool) -> dict[str, object]:
    mode = env.get("GEO_POLICY_MODE", "off").strip().lower() or "off"
    data_dir = resolve_config_path(env.get("GEO_POLICY_DATA_DIR", "./geoip/generated/countries"), project_root)
    manual_allow_file = resolve_config_path(env.get("GEO_POLICY_MANUAL_ALLOW_FILE", "./geoip/manual/allow_ipv4.txt"), project_root)
    manual_deny_file = resolve_config_path(env.get("GEO_POLICY_MANUAL_DENY_FILE", "./geoip/manual/deny_ipv4.txt"), project_root)

    whitelist_entries = load_inline_networks(env.get("WHITELISTED_IPS", ""), "WHITELISTED_IPS")
    if resolve_domains:
        whitelist_entries.extend(resolve_domain_entries(env.get("WHITELISTED_DOMAINS", ""), "WHITELISTED_DOMAINS"))

    manual_deny_entries = load_network_file(manual_deny_file, "manual_deny")
    manual_allow_entries = load_network_file(manual_allow_file, "manual_allow")
    country_deny_entries = load_country_networks(
        data_dir,
        normalize_country_csv(env.get("GEO_POLICY_DENIED_COUNTRIES", "")),
        "country_deny",
    )
    country_allow_entries = load_country_networks(
        data_dir,
        normalize_country_csv(env.get("GEO_POLICY_ALLOWED_COUNTRIES", "")),
        "country_allow",
    )

    checks: dict[str, dict[str, object]] = {}
    whitelist = coverage_for(target, whitelist_entries)
    checks["whitelist"] = {"status": whitelist.status, "matches": format_matches(whitelist.matches)}

    if whitelist.status == "full":
        decision = "ALLOW"
        reason = "target is fully covered by WHITELISTED_IPS/WHITELISTED_DOMAINS before geo policy"
    elif whitelist.status == "partial":
        decision = "PARTIAL"
        reason = "part of the target is covered by WHITELISTED_IPS/WHITELISTED_DOMAINS before geo policy"
    elif mode == "off":
        decision = "ALLOW"
        reason = "GEO_POLICY_MODE=off, so country filtering is disabled"
    elif mode not in {"allowlist", "denylist"}:
        decision = "UNKNOWN"
        reason = f"unsupported GEO_POLICY_MODE={mode!r}; expected off, allowlist or denylist"
    else:
        manual_deny = coverage_for(target, manual_deny_entries)
        manual_allow = coverage_for(target, manual_allow_entries)
        checks["manual_deny"] = {"status": manual_deny.status, "matches": format_matches(manual_deny.matches)}
        checks["manual_allow"] = {"status": manual_allow.status, "matches": format_matches(manual_allow.matches)}

        if manual_deny.status == "full":
            decision = "DENY"
            reason = "target is fully covered by GEO_POLICY_MANUAL_DENY_FILE"
        elif manual_deny.status == "partial":
            decision = "PARTIAL"
            reason = "part of the target is covered by GEO_POLICY_MANUAL_DENY_FILE"
        elif manual_allow.status == "full":
            decision = "ALLOW"
            reason = "target is fully covered by GEO_POLICY_MANUAL_ALLOW_FILE"
        elif manual_allow.status == "partial":
            decision = "PARTIAL"
            reason = "part of the target is covered by GEO_POLICY_MANUAL_ALLOW_FILE"
        elif mode == "denylist":
            country_deny = coverage_for(target, country_deny_entries)
            checks["country_deny"] = {"status": country_deny.status, "matches": format_matches(country_deny.matches)}
            if country_deny.status == "full":
                decision = "DENY"
                reason = "target is fully covered by GEO_POLICY_DENIED_COUNTRIES"
            elif country_deny.status == "partial":
                decision = "PARTIAL"
                reason = "part of the target is covered by GEO_POLICY_DENIED_COUNTRIES"
            else:
                decision = "ALLOW"
                reason = "denylist mode allows targets not covered by manual/country deny entries"
        else:
            country_allow = coverage_for(target, country_allow_entries)
            checks["country_allow"] = {"status": country_allow.status, "matches": format_matches(country_allow.matches)}
            if country_allow.status == "full":
                decision = "ALLOW"
                reason = "target is fully covered by GEO_POLICY_ALLOWED_COUNTRIES"
            elif country_allow.status == "partial":
                decision = "PARTIAL"
                reason = "part of the target is covered by GEO_POLICY_ALLOWED_COUNTRIES"
            else:
                decision = "DENY"
                reason = "allowlist mode drops targets not covered by manual/country allow entries"

    return {
        "target": str(target),
        "decision": decision,
        "reason": reason,
        "geo_policy_mode": mode,
        "data_dir": str(data_dir),
        "manual_allow_file": str(manual_allow_file),
        "manual_deny_file": str(manual_deny_file),
        "domain_resolution": resolve_domains,
        "country_membership": discover_country_membership(target, data_dir),
        "checks": checks,
    }


def print_text(result: dict[str, object]) -> None:
    print(f"Target: {result['target']}")
    print(f"Decision: {result['decision']}")
    print(f"Reason: {result['reason']}")
    print(f"Geo mode: {result['geo_policy_mode']}")
    print("Scope: nft geo_country_filter for L4D2 UDP ports only")
    print(f"Domain resolution: {'enabled' if result['domain_resolution'] else 'disabled'}")

    country_membership = result.get("country_membership") or []
    if country_membership:
        print("Generated country membership: " + ", ".join(country_membership))

    checks = result.get("checks") or {}
    if checks:
        print("\nChecks:")
        for name, check in checks.items():
            print(f"- {name}: {check['status']}")
            for match in check.get("matches", []):
                print(f"  - {match}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether an IPv4 address/CIDR is allowed or denied by the configured GeoIP policy.",
    )
    parser.add_argument("target", help="IPv4 address or CIDR to check, e.g. 179.6.17.240 or 179.6.17.240/28")
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"), help="Path to .env file")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="Project root for relative paths in .env")
    parser.add_argument("--resolve-domains", action="store_true", help="Resolve WHITELISTED_DOMAINS and include them as bypass entries")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--fail-on-deny", action="store_true", help="Exit with code 1 when the decision is DENY or PARTIAL")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        project_root = Path(args.project_root).resolve()
        env = parse_env_file(Path(args.env_file).resolve())
        target = parse_target(args.target)
        result = decide(target, env, project_root, args.resolve_domains)
    except Exception as exc:  # noqa: BLE001 - CLI should report concise user-facing errors.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text(result)

    if args.fail_on_deny and result["decision"] in {"DENY", "PARTIAL"}:
        return 1
    if result["decision"] == "UNKNOWN":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
