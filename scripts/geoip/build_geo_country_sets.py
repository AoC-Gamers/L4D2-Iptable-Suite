#!/usr/bin/env python3
import argparse
import csv
import pathlib
import os
import tempfile
import sys
import zipfile
import ipaddress
import re
import stat


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build per-country IPv4 CIDR files from MaxMind GeoLite2 Country CSV data"
    )
    parser.add_argument("--csv-zip", help="Path to GeoLite2 Country CSV zip")
    parser.add_argument("--csv-dir", help="Path to extracted GeoLite2 Country CSV directory")
    parser.add_argument("--output-dir", required=True, help="Directory where CC.ipv4.txt files will be written")
    parser.add_argument("--countries", required=True, help="Comma-separated ISO country codes")
    return parser.parse_args()


def find_member_name(names, suffix):
    for name in names:
        if name.endswith(suffix):
            return name
    raise FileNotFoundError(f"Missing required CSV member: {suffix}")


def load_rows_from_zip(zip_path, suffix):
    with zipfile.ZipFile(zip_path) as archive:
        member = find_member_name(archive.namelist(), suffix)
        with archive.open(member) as handle:
            lines = (line.decode("utf-8-sig") for line in handle)
            return list(csv.DictReader(lines))


def load_rows_from_dir(csv_dir, filename):
    path = pathlib.Path(csv_dir) / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing required CSV file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_maxmind_rows(csv_zip, csv_dir):
    if csv_zip:
        return (
            load_rows_from_zip(csv_zip, "GeoLite2-Country-Locations-en.csv"),
            load_rows_from_zip(csv_zip, "GeoLite2-Country-Blocks-IPv4.csv"),
        )
    if csv_dir:
        return (
            load_rows_from_dir(csv_dir, "GeoLite2-Country-Locations-en.csv"),
            load_rows_from_dir(csv_dir, "GeoLite2-Country-Blocks-IPv4.csv"),
        )
    raise ValueError("One of --csv-zip or --csv-dir is required")


def build_country_map(locations):
    mapping = {}
    for row in locations:
        geoname_id = (row.get("geoname_id") or "").strip()
        country_code = (row.get("country_iso_code") or "").strip().upper()
        if geoname_id and country_code:
            mapping[geoname_id] = country_code
    return mapping


def pick_country_code(row, geoname_to_country):
    for key in ("geoname_id", "registered_country_geoname_id", "represented_country_geoname_id"):
        value = (row.get(key) or "").strip()
        if value and value in geoname_to_country:
            return geoname_to_country[value]
    return None


def main():
    args = parse_args()

    countries = [item.strip().upper() for item in args.countries.split(",") if item.strip()]
    if not countries:
        print("ERROR: --countries cannot be empty", file=sys.stderr)
        return 2
    if len(countries) > 256 or any(not re.fullmatch('[A-Z]{2}', country) for country in countries):
        raise ValueError('Countries must be two-letter ISO codes; path components are forbidden')

    locations, blocks_v4 = load_maxmind_rows(args.csv_zip, args.csv_dir)
    geoname_to_country = build_country_map(locations)
    selected = set(countries)
    cidrs_by_country = {country: [] for country in countries}

    for row in blocks_v4:
        network = (row.get("network") or "").strip()
        if not network:
            continue
        network = str(ipaddress.IPv4Network(network, strict=True))
        country = pick_country_code(row, geoname_to_country)
        if country in selected:
            cidrs_by_country[country].append(network)

    output_dir = pathlib.Path(args.output_dir)
    if os.geteuid() == 0:
        # Validate existing ancestors before mkdir/write; do not follow symlinks
        # into another administrator's directory or shared writable parents.
        for path in [output_dir.absolute(), *output_dir.absolute().parents]:
            if not path.exists() and not path.is_symlink():
                continue
            info = path.lstat()
            if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
                raise ValueError(f'Untrusted GeoIP output ancestor: {path}')
    output_dir.mkdir(parents=True, exist_ok=True)

    for country in countries:
        output_path = output_dir / f"{country}.ipv4.txt"
        fd, temp_path = tempfile.mkstemp(prefix="." + country + ".", dir=output_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"# Generated from MaxMind GeoLite2 Country CSV for {country}\n")
            for network in cidrs_by_country[country]:
                handle.write(f"{network}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, output_path)
        parent_fd = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        print(f"OK: wrote {output_path} ({len(cidrs_by_country[country])} prefixes)")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(2) from error
