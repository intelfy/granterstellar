from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import FileUpload
import os
import re
import mimetypes
import shutil
import subprocess
import tempfile
from shlex import split as shlex_split
from django.core.exceptions import SuspiciousOperation

def _ocr_image_if_enabled(path: str, content_type: str) -> str:
    """Optional OCR for images when OCR_IMAGE=1 and pytesseract/PIL are available.
    Falls back to empty string on any error.
    """
    import os as _os
    if _os.getenv('OCR_IMAGE', '0') != '1':
        return ''
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        return ''
    try:
        if content_type and content_type.startswith('image/'):
            img = Image.open(path)
            txt = pytesseract.image_to_string(img) or ''
            return txt[:50000]
    except Exception:
        return ''
    return ''


def _extract_pdf_text(path: str) -> str:
    """Extract text from a PDF using pdfminer.six if available.
    Returns empty string on error.
    """
    # Only operate on files stored under MEDIA_ROOT
    if not _is_under_media_root(path):
        return ''
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        return ''
    try:
        txt = extract_text(path) or ''
        # Normalize whitespace a bit
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt[:50000]
    except Exception:
        return ''


def _ocr_pdf_if_enabled(path: str) -> str:
    """Optional OCR for PDFs when OCR_PDF=1 and `ocrmypdf` CLI is available.
    - Uses --skip-text to avoid re-OCR on digital PDFs
    - Timeouts after 30s
    - Returns extracted text from the OCR'd PDF using pdfminer
    """
    if os.getenv('OCR_PDF', '0') != '1':
        return ''
    if not _is_under_media_root(path):
        return ''
    # Require CLI binary present
    if not shutil.which('ocrmypdf'):
        return ''
    # Work in a temp file next to original to avoid permission issues
    with tempfile.TemporaryDirectory() as tmpd:
        out_pdf = os.path.join(tmpd, 'out.pdf')
        try:
            # --skip-text will only OCR images-only PDFs; quiet to reduce logs
            subprocess.run(
                ['ocrmypdf', '--skip-text', '--quiet', '--force-ocr', path, out_pdf],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except Exception:
            return ''
        # Now extract text from the OCR'd PDF
        return _extract_pdf_text(out_pdf)

def _has_signature(path: str, ext: str) -> bool:
    # Ensure we only touch files stored under MEDIA_ROOT
    if not _is_under_media_root(path):
        return False
    try:
        with _safe_open_for_read(path) as fh:
            head = fh.read(16)
        ext = ext.lower().lstrip('.')
        if ext == 'pdf':
            return head.startswith(b'%PDF')
        if ext == 'png':
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        if ext in ('jpg', 'jpeg'):
            return head.startswith(b"\xFF\xD8")
        if ext == 'docx':
            # DOCX is a ZIP: PK\x03\x04
            return head.startswith(b'PK\x03\x04')
        # txt or others we don't enforce
        return True
    except Exception:
        return False


ALLOWED = set(settings.ALLOWED_UPLOAD_EXTENSIONS)
MAX_BYTES = int(getattr(settings, 'FILE_UPLOAD_MAX_BYTES', getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)))
TEXT_MAX = int(getattr(settings, 'TEXT_EXTRACTION_MAX_BYTES', 8 * 1024 * 1024))

def _is_under_media_root(p: str) -> bool:
    """Return True if p is a regular file under MEDIA_ROOT (no symlinks).

    Uses realpath and commonpath to avoid prefix tricks and rejects symlinks.
    """
    try:
        root = os.path.realpath(settings.MEDIA_ROOT)
        cand = os.path.realpath(p)
        # Reject symlinks explicitly
        if os.path.islink(p) or os.path.islink(cand):
            return False
        # Ensure candidate is a regular file under the media root
        if not os.path.isfile(cand):
            return False
        return os.path.commonpath([root, cand]) == root
    except Exception:
        return False


def _extract_text_stub(path: str, content_type: str) -> str:
    # Guard against unexpected paths
    if not _is_under_media_root(path):
        return ''
    # Best-effort extraction for txt/docx/pdf/images
    if content_type in ('text/plain',):
        try:
            with _safe_open_for_read(path) as f:
                data = f.read(min(50000, TEXT_MAX))
                try:
                    return data.decode('utf-8', errors='ignore')
                except Exception:
                    return ''
        except Exception:
            return ''
    # PDFs: try digital text first, then optional OCR pipeline
    if content_type == 'application/pdf' or path.lower().endswith('.pdf'):
        txt = _extract_pdf_text(path)
        if txt:
            return txt
        # If no digital text, optionally OCR
        ocr_txt = _ocr_pdf_if_enabled(path)
        if ocr_txt:
            return ocr_txt
        return ''
    if (
        content_type in (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
        )
        or path.lower().endswith('.docx')
    ):
        try:
            from docx import Document  # type: ignore
            # Avoid parsing extremely large documents
            if os.path.getsize(path) > TEXT_MAX:
                return ''
            doc = Document(path)
            parts = []
            for p in doc.paragraphs:
                txt = (p.text or '').strip()
                if txt:
                    parts.append(txt)
            return ('\n'.join(parts))[:50000]
        except Exception:
            return ''
    # Optional OCR for images
    if content_type.startswith('image/'):
        return _ocr_image_if_enabled(path, content_type)
    return ''


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload(request):
    f = request.FILES.get('file')
    if not f:
        return Response({"error": "missing_file"}, status=status.HTTP_400_BAD_REQUEST)
    # Normalize filename: strip paths and suspicious chars
    raw_name = f.name or ''
    base = os.path.basename(raw_name)
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base) or 'upload.bin'
    ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
    if ext not in ALLOWED:
        return Response(
            {"error": "unsupported_type", "allowed": sorted(ALLOWED)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    size = getattr(f, 'size', 0)
    # Enforce hard cap
    if size and size > MAX_BYTES:
        return Response(
            {"error": "file_too_large", "limit": MAX_BYTES},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    upload = FileUpload.objects.create(
        owner=request.user if request.user.is_authenticated else None,
        file=f,
        content_type=f.content_type or '',
        size=size,
    )
    # Ensure the stored file path resolves under MEDIA_ROOT to mitigate traversal
    fpath = getattr(upload.file, 'path', '')
    if not fpath or not _is_under_media_root(fpath):
        try:
            upload.delete()
        except Exception:
            pass
        return Response({"error": "invalid_storage_path"}, status=status.HTTP_400_BAD_REQUEST)
    # Extra guard: reject symlinks outright even if they resolve under MEDIA_ROOT
    try:
        if os.path.islink(fpath):
            upload.delete()
            return Response({"error": "invalid_storage_path"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        pass
    # Best-effort MIME validation
    guessed, _ = mimetypes.guess_type(base)
    if guessed and ext in { 'png', 'jpg', 'jpeg', 'pdf' }:
        if not (guessed.startswith('image/') or guessed == 'application/pdf'):
            upload.delete()
            return Response({"error": "mismatched_content_type"}, status=status.HTTP_400_BAD_REQUEST)
    # Magic-byte signature validation
    if ext in { 'png', 'jpg', 'jpeg', 'pdf', 'docx' } and not _has_signature(fpath, ext):
        upload.delete()
        return Response({"error": "mismatched_signature"}, status=status.HTTP_400_BAD_REQUEST)
    # Optional virus scan hook
    try:
        cmd_tpl = getattr(settings, 'VIRUSSCAN_CMD', '')
        if cmd_tpl:
            # Build argv safely without shell. Allow basic pattern: "scanner [args...] {path}".
            # Reject if command contains suspicious characters that imply shell features.
            if any(c in cmd_tpl for c in ['|', ';', '&', '>', '<', '`']):
                raise ValueError('invalid scanner command')
            parts = shlex_split(cmd_tpl)
            if not parts:
                raise ValueError('invalid scanner command')
            # Disallow passing user-controlled path placeholders or redirection-like args
            for a in parts[1:]:
                if a.startswith('-') and any(tok in a for tok in ['-exec', '--exec', '-format=sh']):
                    raise SuspiciousOperation('disallowed scanner argument')
            # Only allow calling a binary by name or absolute path; no directory traversal in args
            scanner = parts[0]
            allowed_bins = set(getattr(settings, 'VIRUSSCAN_ALLOWED_BINARIES', []))
            # If a path is provided, require absolute and optionally allow-list
            if '/' in scanner:
                if not os.path.isabs(scanner):
                    raise SuspiciousOperation('scanner must be absolute path')
                if allowed_bins and scanner not in allowed_bins:
                    raise SuspiciousOperation('scanner not allowed')
                if not os.path.exists(scanner):
                    raise ValueError('scanner not found')
            else:
                # Bare command name: ensure allowed and resolve with which()
                if allowed_bins and scanner not in allowed_bins:
                    raise SuspiciousOperation('scanner not allowed')
                resolved = shutil.which(scanner)
                if not resolved:
                    raise ValueError('scanner not found')
                parts[0] = resolved
            # Append the scanned file path as the last argv element
            argv = parts + [fpath]
            # Execute without a shell to avoid injection; argv only
            proc = subprocess.run(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1, int(getattr(settings, 'VIRUSSCAN_TIMEOUT_SECONDS', 10))),
                check=False,
                shell=False,
            )
            # Exit code 0 => clean; non-zero => infected or error
            if proc.returncode != 0:
                upload.delete()
                return Response({"error": "infected"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        # Fail-closed on scanner invocation errors
        try:
            upload.delete()
        except Exception:
            pass
        return Response({"error": "scan_error"}, status=status.HTTP_400_BAD_REQUEST)

    # Best-effort OCR/parse stub
    # Only attempt text/OCR extraction for safely stored paths
    # Skip extraction if file exceeds configured TEXT_MAX to avoid heavy work
    if os.path.getsize(fpath) <= TEXT_MAX:
        upload.ocr_text = _extract_text_stub(fpath, upload.content_type) if _is_under_media_root(fpath) else ''
    else:
        upload.ocr_text = ''
    upload.save(update_fields=['ocr_text'])
    return Response({
        "id": upload.pk,
        "url": f"{settings.MEDIA_URL}{upload.file.name}",
        "content_type": upload.content_type,
        "size": upload.size,
        "ocr_text": upload.ocr_text[:2000],
    })


def _safe_open_for_read(path: str):
    """Open a file for read in a way that avoids following symlinks.

    - Ensures the path is under MEDIA_ROOT via _is_under_media_root
    - Uses os.open with O_NOFOLLOW and wraps with a buffered reader
    """
    if not _is_under_media_root(path):
        raise FileNotFoundError("invalid path")
    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    # Wrap in a file object opened in binary mode
    return os.fdopen(fd, 'rb', buffering=64 * 1024)
