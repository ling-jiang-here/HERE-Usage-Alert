from __future__ import annotations

import base64
import json
import os
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HereClientError(RuntimeError):
    """Raised without including credentials or access tokens."""


class HereUsageClient:
    def __init__(self) -> None:
        self.base_url = _required("HERE_USAGE_API_BASE_URL").rstrip("/")
        self.realm_id = _required("HERE_REALM_ID")
        self.client_id = _required("HERE_USAGE_API_CLIENT_ID")
        self.client_secret = _required("HERE_USAGE_API_CLIENT_SECRET")
        self.token_url = os.getenv("HERE_OAUTH_TOKEN_URL") or "https://account.api.here.com/oauth2/token"
        self.scope = os.getenv("HERE_OAUTH_SCOPE", "")
        self.usage_path = os.getenv("HERE_USAGE_API_USAGE_PATH", "").strip()

    def fetch_usage(self, usage_date: date) -> str:
        if not self.usage_path.startswith("/"):
            raise HereClientError(
                "HERE_USAGE_API_USAGE_PATH must be set to the documented Usage API path starting with '/'."
            )
        token = self._access_token()
        query = urlencode({"realmId": self.realm_id, "from": usage_date.isoformat(), "to": usage_date.isoformat()})
        request = Request(
            f"{self.base_url}{self.usage_path}?{query}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except (HTTPError, URLError) as error:
            raise HereClientError(f"HERE Usage API request failed: {getattr(error, 'code', error.reason)}") from error

    def _access_token(self) -> str:
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        fields = {"grant_type": "client_credentials"}
        if self.scope:
            fields["scope"] = self.scope
        request = Request(
            self.token_url,
            data=urlencode(fields).encode(),
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError) as error:
            raise HereClientError("HERE OAuth token request failed; verify client credentials, scope, and token URL.") from error
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise HereClientError("HERE OAuth response did not include an access token.")
        return token


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HereClientError(f"Required environment variable {name} is not set.")
    return value