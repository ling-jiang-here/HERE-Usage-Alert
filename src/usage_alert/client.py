from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
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
        if not self.usage_path.startswith("/") or "{realmId}" not in self.usage_path:
            raise HereClientError(
                "HERE_USAGE_API_USAGE_PATH must be the documented path containing '{realmId}'."
            )
        token = self._access_token()
        path = self.usage_path.replace("{realmId}", quote(self.realm_id, safe=""))
        parameters = {
            "startDate": f"{usage_date.isoformat()}T00:00:00",
            "endDate": f"{usage_date.isoformat()}T23:59:59",
            "detailLevel": "day",
            "groupBy": "appId,billingTag,project",
            "limit": 100,
            "offset": 0,
        }
        items: list[object] = []
        while True:
            response = self._request_usage(f"{self.base_url}{path}", token, parameters)
            page_items = response.get("items")
            if not isinstance(page_items, list):
                raise HereClientError("HERE Usage API response did not include an items list.")
            items.extend(page_items)
            next_offset = response.get("nextOffset")
            if next_offset is None:
                break
            last_offset = response.get("lastOffset")
            if next_offset == parameters["offset"] and last_offset == parameters["offset"]:
                break
            if not isinstance(next_offset, int) or next_offset <= parameters["offset"]:
                raise HereClientError("HERE Usage API returned an invalid pagination offset.")
            parameters["offset"] = next_offset
        return json.dumps({"items": items})

    def _request_usage(self, url: str, token: str, parameters: dict[str, object]) -> dict[str, object]:
        request = Request(
            f"{url}?{urlencode(parameters)}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Correlation-ID": str(uuid.uuid4()),
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            correlation_id = error.headers.get("X-Correlation-ID", "unavailable")
            details = _safe_error_details(error)
            raise HereClientError(
                f"HERE Usage API request failed with HTTP {error.code}; {details} correlation ID: {correlation_id}."
            ) from error
        except (URLError, json.JSONDecodeError) as error:
            raise HereClientError("HERE Usage API request failed; verify network access and response format.") from error
        if not isinstance(payload, dict):
            raise HereClientError("HERE Usage API returned an invalid JSON document.")
        return payload

    def _access_token(self) -> str:
        fields = {"grant_type": "client_credentials"}
        if self.scope:
            fields["scope"] = self.scope
        authorization = _oauth1_authorization_header(self.token_url, fields, self.client_id, self.client_secret)
        request = Request(
            self.token_url,
            data=urlencode(fields).encode(),
            headers={"Authorization": authorization, "Content-Type": "application/x-www-form-urlencoded"},
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


def _oauth1_authorization_header(
    url: str, body_parameters: dict[str, str], client_id: str, client_secret: str
) -> str:
    oauth_parameters = {
        "oauth_consumer_key": client_id,
        "oauth_nonce": secrets.token_urlsafe(24),
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
    }
    signature_parameters = {**body_parameters, **oauth_parameters}
    normalized_parameters = "&".join(
        f"{_oauth_quote(key)}={_oauth_quote(value)}"
        for key, value in sorted(signature_parameters.items())
    )
    signature_base = f"POST&{_oauth_quote(url)}&{_oauth_quote(normalized_parameters)}"
    signing_key = f"{_oauth_quote(client_secret)}&"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), signature_base.encode(), hashlib.sha256).digest()
    ).decode()
    oauth_parameters["oauth_signature"] = signature
    return "OAuth " + ", ".join(
        f'{_oauth_quote(key)}="{_oauth_quote(value)}"'
        for key, value in sorted(oauth_parameters.items())
    )


def _oauth_quote(value: object) -> str:
    return quote(str(value), safe="~")


def _safe_error_details(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "No structured error details were returned."
    if not isinstance(payload, dict):
        return "No structured error details were returned."
    fields = ("code", "cause", "action")
    details = "; ".join(f"{field}={payload[field]}" for field in fields if payload.get(field))
    return f"{details}." if details else "No structured error details were returned."