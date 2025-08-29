#!/usr/bin/env python3
"""
Simple link checker for this repo:
- Scans .md and .html files for links (href/src) and Markdown images/links
- Verifies local file paths exist
- Optionally checks external http(s) links with HEAD/GET

Usage:
  python scripts/linkcheck.py [--no-external]

Exclusions:
- Domains ending with .example (docs placeholders)
- Local dev-only paths starting with /api or /media
- Mailgun/analytics placeholders if any
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple

try:
    import requests
except Exception:
    requests = None  # external checks will be disabled if requests is missing


MD_LINK_RE = re.compile(r"!??\[[^\]]*\]\(([^\)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_HREF_RE = re.compile(r"\b(?:href|src)=['\"]([^'\"]+)['\"]", re.IGNORECASE)

EXTERNAL_EXCLUDE_PATTERNS = (
    ".example",  # placeholder domains
)

LOCAL_EXCLUDE_PREFIXES = (
    "/api",  # served via dev/prod server
    "/media",  # served by API
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
)


@dataclass
class Finding:
    file: str
    link: str
    kind: str  # local|external
    error: str


def iter_repo_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        # skip virtual envs and media/output
        parts = dirpath.split(os.sep)
        if ".venv" in parts or "node_modules" in parts or "media" in parts or ".git" in parts:
            continue
        for f in filenames:
            if f.endswith((".md", ".html")):
                yield os.path.join(dirpath, f)


def extract_links(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return []
    links = []
    links += MD_LINK_RE.findall(text)
    links += HTML_HREF_RE.findall(text)
    return links


def is_external(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def should_skip(url: str, external: bool) -> bool:
    # anchors only
    if url.startswith("#"):
        return True
    # query only (unlikely)
    if url.strip() == "":
        return True
    if external:
        for pat in EXTERNAL_EXCLUDE_PATTERNS:
            if pat in url:
                return True
    else:
        for pref in LOCAL_EXCLUDE_PREFIXES:
            if url.startswith(pref):
                return True
    return False


def check_local(path: str, link: str) -> Tuple[bool, str]:
    # strip anchors
    target, *_ = link.split("#", 1)
    # ignore root-absolute paths like /api/* or /media/* handled by skip
    if target.startswith("/"):
        return True, "skipped (root-absolute)"
    # resolve
    base = os.path.dirname(path)
    full = os.path.normpath(os.path.join(base, target))
    if os.path.exists(full):
        return True, "ok"
    return False, f"missing file: {full}"


def check_external(url: str, timeout: float = 6.0) -> Tuple[bool, str]:
    if requests is None:
        return True, "skipped (requests not installed)"
    try:
        # Prefer HEAD; fallback to GET on 405/403
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code >= 200 and r.status_code < 400:
            return True, f"{r.status_code}"
        if r.status_code in (403, 405):
            r = requests.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code >= 200 and r.status_code < 400:
                return True, f"{r.status_code}"
        return False, f"HTTP {r.status_code}"
    except requests.exceptions.SSLError as e:
        return False, f"SSL error: {e.__class__.__name__}"
    except requests.exceptions.RequestException as e:
        return False, f"{e.__class__.__name__}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-external", action="store_true", help="skip external http(s) checks")
    args = ap.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    findings: List[Finding] = []
    files_scanned = 0
    links_checked = 0

    t0 = time.time()
    for path in iter_repo_files(root):
        files_scanned += 1
        for link in extract_links(path):
            if is_external(link):
                if args.no_external or should_skip(link, external=True):
                    continue
                ok, info = check_external(link)
                links_checked += 1
                if not ok:
                    findings.append(Finding(path, link, "external", info))
            else:
                if should_skip(link, external=False):
                    continue
                ok, info = check_local(path, link)
                links_checked += 1
                if not ok:
                    findings.append(Finding(path, link, "local", info))

    dt = time.time() - t0
    if findings:
        print(f"Link check: FAIL — {len(findings)} issues across {files_scanned} files, {links_checked} links checked in {dt:.1f}s")
        for f in findings:
            print(f"- [{f.kind}] {f.file}: {f.link} — {f.error}")
        return 1
    else:
        print(f"Link check: PASS — {files_scanned} files, {links_checked} links checked in {dt:.1f}s")
        return 0


if __name__ == "__main__":
    sys.exit(main())
