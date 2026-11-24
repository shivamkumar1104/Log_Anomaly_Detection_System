"""Bearer API-key authentication for the local single-operator deployment."""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)] = None,
) -> None:
    configured_key = os.getenv("LOG_ANOMALY_API_KEY", "").strip()
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer API key.")
    if not hmac.compare_digest(credentials.credentials, configured_key):
        raise HTTPException(status_code=401, detail="Invalid bearer API key.")
