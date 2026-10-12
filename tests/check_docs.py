#!/usr/bin/env python3
"""Check repository Markdown links/anchors and navigation; no code execution/network."""
from collections import Counter, deque
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def prose(text):
    """Ignore fenced code, including indented fences, without interpreting it."""
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append("")
        else:
            result.append(line if fence is None else "")
    return "\n".join(result)


def anchors(text):
    found = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    counts = Counter()
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if not match:
            continue
        title = re.sub(r"<[^>]+>", "", match[1]).lower()
        title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", title)
        slug = "".join(c for c in title if c in " _-" or unicodedata.category(c)[0] in "LN").replace(" ", "-")
        number = counts[slug]
        counts[slug] += 1
        found.add(slug + (f"-{number}" if number else ""))
    return found


def links(text):
    definitions = {}
    for match in re.finditer(r"(?m)^\s*\[([^\]]+)\]:\s*(<[^>]+>|\S+)", text):
        definitions[match[1].strip().casefold()] = match[2].strip("<>")
    for match in re.finditer(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", text):
        yield match[1].strip("<>")
    yield from definitions.values()
    for match in re.finditer(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]", text):
        key = (match[2] or match[1]).strip().casefold()
        if key not in definitions:
            raise ValueError(f"Undefined reference: [{key}]")
    # Shortcut references resolve only when their definition exists.
    for match in re.finditer(r"!?\[([^\]\n]+)\](?![(:\[])", text):
        value = definitions.get(match[1].strip().casefold())
        if value:
            yield value
    for match in re.finditer(r'<(?:a|img)\s+[^>]*?(?:href|src)=["\']([^"\']+)', text):
        yield match[1]


def main():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        cwd=ROOT,
    ).decode().split("\0")
    pages = {p: prose((ROOT / p).read_text()) for p in set(paths) if p}
    targets = {p: anchors(t) for p, t in pages.items()}
    graph, errors, count, external = {}, [], 0, set()
    for source, text in sorted(pages.items()):
        graph[source] = set()
        try:
            destinations = list(links(text))
        except ValueError as exc:
            errors.append(f"{source}: {exc}")
            continue
        for raw in destinations:
            url = urlsplit(raw)
            if url.scheme or url.netloc:
                external.add(raw)
                continue
            count += 1
            if url.path.startswith("/"):
                errors.append(f"{source}: absolute internal link: {raw}")
                continue
            target = (ROOT / source).parent / unquote(url.path) if url.path else ROOT / source
            target = target.resolve()
            if not target.is_relative_to(ROOT):
                errors.append(f"{source}: outside repository: {raw}")
                continue
            if not target.exists():
                errors.append(f"{source}: missing target: {raw}")
                continue
            if target.is_dir():
                target /= "README.md"
            name = str(target.relative_to(ROOT))
            if name in pages:
                graph[source].add(name)
                if url.fragment and unquote(url.fragment) not in targets[name]:
                    errors.append(f"{source}: missing anchor: {raw}")
            elif url.fragment:
                errors.append(f"{source}: cannot check non-Markdown anchor: {raw}")
    # The canonical index must reach every document, including compatibility/history.
    queue, reached = deque(["docs/README.md"]), set()
    while queue:
        node = queue.popleft()
        if node in reached:
            continue
        reached.add(node)
        queue.extend(graph.get(node, ()))
    # Only explicit compatibility notices can be outside the primary navigation.
    mapping = pages.get("docs/migration/documentation-map.md", "")
    for name, body in pages.items():
        notice = body.startswith(("# Documento trasladado", "# Ficha trasladada", "# Catálogo trasladado"))
        classified_notice = notice and f"`{name}`" in mapping
        if name not in reached and not classified_notice:
            errors.append(f"Not reachable from docs/README.md: {name}")
    for unit in (ROOT / "systemd").glob("*.service"):
        for link in re.findall(r"(?m)^Documentation=file:/opt/l4d2-firewall/(.+)$", unit.read_text()):
            if not (ROOT / link).is_file():
                errors.append(f"{unit.relative_to(ROOT)}: missing Documentation target: {link}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"PASS: {len(pages)} Markdown pages, {count} local links/anchors, navigation and systemd Documentation references")
    print(f"NOT CHECKED: {len(external)} external destinations (network checks are separate); Markdown commands are never executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
