"""The ``--json`` output envelope shared by every cli-web-* CLI.

Success: ``{"success": true, "data": ...}``
Error:   ``{"error": true, "code": "...", "message": "..."}``
"""

from __future__ import annotations

import json
from typing import Any


def json_success(data: Any, **extra: Any) -> str:
    payload: dict[str, Any] = {"success": True, "data": data}
    payload.update(extra)
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def json_error(code: str, message: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"error": True, "code": code, "message": message}
    payload.update(extra)
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
