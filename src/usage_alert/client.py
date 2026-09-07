from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class HereClientError(RuntimeError):
    """Raised without including credentials or access tokens."""


class HereUsageClient:
    def __init__(self) -> None:
        self.base_url = "https://usage.bam.api.here.com/v2"
        self.client_id = _required_any(("here.access.key.id", "HERE_ACCESS_KEY_ID"))
        self.client_secret = _required_any(("here.access.key.secret", "HERE_ACCESS_KEY_SECRET"))
        self.app_client_id = _optional(("here.client.id", "HERE_CLIENT_ID"))
        self.token_url = "https://account.api.here.com/oauth2/token"
        self.account_base_url = "https://account.api.here.com"
        self.bam_base_url = "https://customer.bam.api.here.com/v1"
        self.usage_alert_base_url = "https://alert.usage.hereapi.com/v1"
        self.usage_path = "/usage/realms/{realmId}"
        self.channel_id = os.getenv("HERE_USAGE_API_CHANNEL_ID", "cold").strip() or "cold"
        self._realm_id = os.getenv("HERE_REALM_ID", "").strip() or None

    @property
    def realm_id(self) -> str:
        if self._realm_id is None:
            self._realm_id = self._resolve_realm_id()
        return self._realm_id

    def fetch_usage(self, usage_date: date) -> str:
        return self._fetch_usage_window(
            f"{usage_date.isoformat()}T00:00:00Z", f"{usage_date.isoformat()}T23:59:59Z", "day"
        )

    def fetch_usage_hour(self, usage_hour_utc: datetime) -> str:
        if usage_hour_utc.tzinfo is None:
            usage_hour_utc = usage_hour_utc.replace(tzinfo=timezone.utc)
        usage_hour_utc = usage_hour_utc.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = usage_hour_utc.isoformat().replace("+00:00", "Z")
        end = (usage_hour_utc.replace(minute=59, second=59)).isoformat().replace("+00:00", "Z")
        return self._fetch_usage_window(start, end, "hour")

    def fetch_usage_window(self, start_utc: datetime, end_utc: datetime) -> str:
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        if end_utc.tzinfo is None:
            end_utc = end_utc.replace(tzinfo=timezone.utc)
        start_utc = start_utc.astimezone(timezone.utc).replace(microsecond=0)
        end_utc = end_utc.astimezone(timezone.utc).replace(microsecond=0)
        if start_utc >= end_utc:
            raise HereClientError("HERE usage window start must be before end.")
        start = start_utc.isoformat().replace("+00:00", "Z")
        end = end_utc.isoformat().replace("+00:00", "Z")
        return self._fetch_usage_window(start, end, "hour")

    def _fetch_usage_window(self, start: str, end: str, detail_level: str) -> str:
        token = self._access_token()
        path = self.usage_path.replace("{realmId}", quote(self.realm_id, safe=""))
        parameters = {
            "startDate": start,
            "endDate": end,
            "channelId": self.channel_id,
            "detailLevel": detail_level,
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

    def fetch_bam_subscriptions(self) -> list[dict[str, object]]:
        """Fetch BAM commercial subscriptions for the realm."""
        token = self._access_token()
        payload = self._request_json("HERE BAM Customer", f"{self.bam_base_url}/subscriptions", token, {"offset": 0, "limit": 100})
        subscriptions = payload.get("subscriptions")
        if not isinstance(subscriptions, list):
            raise HereClientError("HERE BAM Customer API response did not include a subscriptions list.")
        return subscriptions

    def fetch_bam_subscription_products(self, subscription_id: str) -> list[dict[str, object]]:
        """Fetch the licensed products of one BAM subscription."""
        token = self._access_token()
        path = f"/subscriptions/{quote(subscription_id, safe='')}/products"
        payload = self._request_json("HERE BAM Customer", f"{self.bam_base_url}{path}", token)
        products = payload.get("items")
        if not isinstance(products, list):
            raise HereClientError("HERE BAM Customer API response did not include a products list.")
        return products

    def fetch_app_authorization(self) -> dict[str, object]:
        """Fetch the monitor app's IAM profile including its realm and any linked plans and policies."""
        token = self._access_token()
        return self._request_json("HERE Account", f"{self.account_base_url}/app/me/authorization", token)

    def fetch_usage_alert_rules(self) -> dict[str, object]:
        """Fetch the usage alert rules configured for the realm (named/partner accounts only)."""
        token = self._access_token()
        path = f"/realm/{quote(self.realm_id, safe='')}/rules"
        return self._request_json("HERE Usage Alert", f"{self.usage_alert_base_url}{path}", token)

    def _resolve_realm_id(self) -> str:
        authorization = self.fetch_app_authorization()
        app = authorization.get("app")
        if not isinstance(app, dict):
            raise HereClientError("HERE Account authorization response did not include app details.")
        discovered_realm = app.get("realm")
        if not isinstance(discovered_realm, str) or not discovered_realm:
            raise HereClientError("HERE Account authorization response did not include a realm.")
        discovered_client_id = app.get("clientId")
        if self.app_client_id and isinstance(discovered_client_id, str) and discovered_client_id != self.app_client_id:
            raise HereClientError(
                f"Configured app client id {self.app_client_id} does not match the credential's app "
                f"{discovered_client_id}; check here.client.id / HERE_CLIENT_ID."
            )
        return discovered_realm

    def _request_usage(self, url: str, token: str, parameters: dict[str, object]) -> dict[str, object]:
        return self._request_json("HERE Usage", url, token, parameters)

    def _request_json(
        self,
        service_label: str,
        url: str,
        token: str,
        parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        request_url = f"{url}?{urlencode(parameters)}" if parameters else url
        request = Request(
            request_url,
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
                f"{service_label} API request failed with HTTP {error.code}; {details} correlation ID: {correlation_id}."
            ) from error
        except (URLError, json.JSONDecodeError) as error:
            raise HereClientError(
                f"{service_label} API request failed; verify network access and response format."
            ) from error
        if not isinstance(payload, dict):
            raise HereClientError(f"{service_label} API returned an invalid JSON document.")
        return payload

    def _access_token(self) -> str:
        fields = {"grant_type": "client_credentials"}
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
            raise HereClientError("HERE OAuth token request failed; verify client credentials and token URL.") from error
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise HereClientError("HERE OAuth response did not include an access token.")
        return token


def _required_any(names: tuple[str, ...]) -> str:
    value = _optional(names)
    if not value:
        raise HereClientError(f"Required environment variable {' or '.join(names)} is not set.")
    return value


def _optional(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


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