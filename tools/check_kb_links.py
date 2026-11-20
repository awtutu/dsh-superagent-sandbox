#!/usr/bin/env python3
"""Check relative links in Markdown files for missing targets.

Scans every Markdown file under one or more roots, extracts links and images
whose destination is a relative path (``[text](path)``, ``![alt](path)``,
reference definitions such as ``[id]: path`` and inline HTML ``href``/``src``
attributes), resolves them against the directory of the containing file and
reports the ones that point at nothing on disk.

Absolute URLs (``https:``, ``mailto:`` ...), protocol-relative URLs
(``//host/path``), root-relative paths (``/path``) and pure ``#fragment``
links are ignored because they do not reference a file in the tree.

Exit status:
    0  every scanned relative link resolves
    1  at least one link is broken (the missing targets are printed)
    2  bad command line (e.g. a root that is not an existing directory)

Standard library only; works with Python 3.8+.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import unquote

MARKDOWN_SUFFIXES = (".md", ".markdown")

# A fenced code block (``` or ~~~) is skipped so that examples inside
# documentation are not reported as real links.
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# [text](destination "optional title") -- one level of nested brackets and
# parentheses in the link text/destination keeps common Markdown working.
_INLINE_LINK_RE = re.compile(
    r"""!?\[(?:[^\[\]\\]|\\.|\[[^\[\]]*\])*\]\(\s*"""
    r"""(?:<(?P<angle>[^<>\n]*)>|(?P<bare>[^\s()<>]*(?:\([^\s()<>]*\)[^\s()<>]*)*))"""
    r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)"""
)

# [id]: destination "optional title"
_REFERENCE_DEF_RE = re.compile(
    r"""^\s{0,3}\[[^\]]+\]:\s*"""
    r"""(?:<(?P<angle>[^<>\n]*)>|(?P<bare>\S+))"""
)

# <a href="...">, <img src='...'>, <link href=...>, <script src=...>
_HTML_ATTR_RE = re.compile(
    r"""<(?:a|img|link|script|source|iframe)\b[^>]*?\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""",
    re.IGNORECASE,
)

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


@dataclass(frozen=True)
class Link:
    """A relative link found in a Markdown file."""

    source: Path  # the Markdown file containing the link
    line: int  # 1-based line number
    raw: str  # destination as written in the document
    target: Path  # resolved absolute path expected to exist


def iter_markdown_files(root: Path) -> Iterable[Path]:
    """Yield Markdown files under ``root`` (or ``root`` itself), sorted."""
    if root.is_file():
        if root.suffix.lower() in MARKDOWN_SUFFIXES:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.lower().endswith(MARKDOWN_SUFFIXES):
                yield Path(dirpath) / name


def _strip_angle(dest: str) -> str:
    return dest.strip().strip("<>").strip()


def _link_destination(raw: str) -> Optional[str]:
    """Return the file part of a link destination, or None if not relative."""
    dest = _strip_angle(raw)
    if not dest or dest.startswith("#"):
        return None
    if dest.startswith("//") or dest.startswith("/"):
        return None
    if _SCHEME_RE.match(dest):
        return None
    # Drop query string and fragment, then percent-decode.
    for sep in ("#", "?"):
        index = dest.find(sep)
        if index != -1:
            dest = dest[:index]
    dest = unquote(dest)
    return dest or None


def find_links(markdown_file: Path) -> List[Link]:
    """Extract every resolvable-relative link from one Markdown file."""
    text = markdown_file.read_text(encoding="utf-8", errors="replace")
    base = markdown_file.parent
    links: List[Link] = []

    fence: Optional[str] = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= len(fence):
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            continue

        candidates: List[str] = []
        for match in _INLINE_LINK_RE.finditer(line):
            candidates.append(match.group("angle") if match.group("angle") is not None else match.group("bare"))
        ref_match = _REFERENCE_DEF_RE.match(line)
        if ref_match:
            candidates.append(ref_match.group("angle") if ref_match.group("angle") is not None else ref_match.group("bare"))
        for match in _HTML_ATTR_RE.finditer(line):
            candidates.append(match.group(1) if match.group(1) is not None else match.group(2))

        for raw in candidates:
            rel = _link_destination(raw)
            if rel is None:
                continue
            links.append(Link(source=markdown_file, line=lineno, raw=raw.strip(), target=(base / rel)))
    return links


def is_broken(link: Link) -> bool:
    """True when the link target does not exist on disk."""
    try:
        return not link.target.exists()
    except OSError:
        return True


def check_roots(roots: Sequence[Path]) -> Tuple[List[Link], List[Path], int]:
    """Scan the roots; return (broken links, files scanned, links checked)."""
    broken: List[Link] = []
    scanned: List[Path] = []
    checked = 0
    seen: Set[Path] = set()
    for root in roots:
        for md in iter_markdown_files(Path(root)):
            resolved = md.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            scanned.append(md)
            links = find_links(md)
            checked += len(links)
            broken.extend(link for link in links if is_broken(link))
    return broken, scanned, checked


def _display(path: Path) -> str:
    """Show paths relative to the current directory when possible."""
    try:
        return os.path.relpath(path)
    except ValueError:  # different drive on Windows
        return str(path)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report relative links in Markdown files whose target is missing.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="directories (or Markdown files) to scan; defaults to the current directory",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    roots = [Path(p) for p in args.paths]
    for root in roots:
        if not root.exists():
            print("error: no such file or directory: %s" % root, file=sys.stderr)
            return 2

    broken, scanned, checked = check_roots(roots)
    if broken:
        for link in broken:
            print(
                "%s:%d: broken link %r -> %s"
                % (_display(link.source), link.line, link.raw, _display(link.target))
            )
        print("FAILED: %d broken link(s) in %d Markdown file(s)" % (len(broken), len(scanned)))
        return 1

    print("OK: %d relative link(s) checked in %d Markdown file(s)" % (checked, len(scanned)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
