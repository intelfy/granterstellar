from typing import Any, Dict, Optional

DEFAULT_VERSION = 'v1'


def error_response(error_code: str, message: str, *, status: int = 400, meta: Optional[Dict[str, Any]] = None):
    """Return a standardized error payload structure.

    Shape:
      {"error": {"code": str, "message": str, "meta": {...}, "version": "v1"}}
    """
    from rest_framework.response import Response  # local import to avoid global DRF binding during migrations

    payload = {
        'error': {
            'code': error_code,
            'message': message,
            'version': DEFAULT_VERSION,
        }
    }
    if meta:
        payload['error']['meta'] = meta  # type: ignore[assignment]
    return Response(payload, status=status)
