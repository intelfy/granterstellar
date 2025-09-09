"""Centralized file utilities used across apps.

Design goals:
- Minimal surface area; stable deterministic helpers.
- Safe filename normalization (ASCII fallback; preserve extension).
- Consistent SHA-256 checksum for bytes, paths or file-like objects.
- Convenience readers with size caps to avoid large memory usage.

These helpers intentionally avoid depending on Django settings so they can
be imported in migrations or celery contexts without side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import BinaryIO, Iterable

_CHUNK_SIZE = 1024 * 1024  # 1MB
_SAFE_FILENAME_RE = re.compile(r'[^A-Za-z0-9._-]+')


@dataclass(slots=True)
class Checksum:
    algo: str
    hex: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.hex


def compute_checksum(data: bytes | bytearray | memoryview | str | os.PathLike | BinaryIO) -> Checksum:
    """Return SHA-256 checksum of diverse input types.

    Accepts:
    - bytes-like (bytes, bytearray, memoryview)
    - filesystem path (str | Path | os.PathLike)
    - open binary file object (with .read)

    Streams large files in chunks. Closes nothing it did not open.
    """
    sha = hashlib.sha256()

    def _update_from_fileobj(f: BinaryIO) -> None:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)

    if isinstance(data, (bytes, bytearray, memoryview)):
        sha.update(data if isinstance(data, (bytes, bytearray)) else bytes(data))
    elif isinstance(data, (str, os.PathLike, Path)):
        with open(data, 'rb') as f:  # noqa: PTH123
            _update_from_fileobj(f)
    elif hasattr(data, 'read'):
        _update_from_fileobj(data)  # type: ignore[arg-type]
    else:  # pragma: no cover - defensive
        raise TypeError('Unsupported data type for checksum')
    return Checksum(algo='sha256', hex=sha.hexdigest())


def safe_filename(name: str, max_length: int = 100) -> str:
    """Return a sanitized filename base while preserving extension.

    Steps:
    - Split extension (last dot) if any (<=15 chars ext preserved).
    - Normalize unicode to NFKD and strip combining marks.
    - Replace invalid chars with '-'; collapse repeats; strip dots.
    - Enforce length (including extension); never return empty => 'file'.
    """
    name = name.strip().replace('\x00', '') or 'file'
    base, ext = os.path.splitext(name)
    if len(ext) > 16:  # suspicious long ext -> treat as part of base
        base = name
        ext = ''
    norm = unicodedata.normalize('NFKD', base)
    norm = ''.join(ch for ch in norm if not unicodedata.combining(ch))
    norm = _SAFE_FILENAME_RE.sub('-', norm)
    norm = re.sub(r'-+', '-', norm).strip('.-') or 'file'
    # Reserve space for extension
    avail = max_length - len(ext)
    if avail < 1:
        # truncate extension aggressively if pathological
        ext = ext[: max(0, max_length - 1)]
        avail = max_length - len(ext)
    norm = norm[:avail]
    return f'{norm}{ext}' if ext else norm


def read_text_file(path: str | os.PathLike | Path, max_bytes: int = 256_000, encoding: str = 'utf-8') -> str:
    """Read a text file up to max_bytes; returns decoded text.

    Truncates without error if file exceeds cap. Adds trailing '…' marker
    when truncated for clarity.
    """
    p = Path(path)
    with p.open('rb') as f:  # noqa: PTH123
        data = f.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    text = data.decode(encoding, errors='replace')
    return text + ('…' if truncated else '')


def write_bytes(path: str | os.PathLike | Path, data: bytes, *, mkdirs: bool = True) -> None:
    """Write bytes to path atomically (best-effort) creating dirs if needed."""
    p = Path(path)
    if mkdirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    with tmp.open('wb') as f:  # noqa: PTH123
        f.write(data)
    tmp.replace(p)


def iter_chunks(fileobj: BinaryIO, chunk_size: int = _CHUNK_SIZE) -> Iterable[bytes]:
    """Yield chunks from a binary file-like until EOF."""
    while True:
        chunk = fileobj.read(chunk_size)
        if not chunk:
            break
        yield chunk
