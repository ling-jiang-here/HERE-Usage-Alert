from __future__ import annotations

import json
import os
import hashlib
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .client import HereClientError, HereUsageClient, _safe_error_details
from .models import UsageRecord
from .quota import QuotaStatus


@dataclass(frozen=True)
class RemediationResult:
    triggered: bool
    message: str
    api_key_disabled: bool = False
    oauth_credentials_disabled: bool = False
    skipped_to_protect_monitor: bool = False


class HereIdentityClient(HereUsageClient):
    def __init__(self) -> None:
        super().__init__()
        self.iam_base_url = "https://account.api.here.com/authentication/v1.1"
        self.authz_base_url = (
            os.getenv("HERE_AUTHZ_API_BASE_URL") or "https://account.api.here.com/authorization/v1.1"
        ).rstrip("/")

    def disable_api_key(self, app_id: str, api_key: str) -> None:
        self._post_without_body(
            f"{self.iam_base_url}/apps/{quote(app_id, safe='')}/apiKeys/{quote(api_key, safe='')}/disable"
        )

    def disable_access_key(self, app_id: str, access_key_id: str) -> None:
        self._post_without_body(
            f"{self.iam_base_url}/apps/{quote(app_id, safe='')}/accessKeys/{quote(access_key_id, safe='')}/disable"
        )

    def list_apps(self) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.iam_base_url}/apps",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "apps")

    def list_api_keys(self, app_id: str) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.iam_base_url}/apps/{quote(app_id, safe='')}/apiKeys",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "apiKeys")

    def list_access_keys(self, app_id: str) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.iam_base_url}/apps/{quote(app_id, safe='')}/accessKeys",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "accessKeys")

    def list_projects(self) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.authz_base_url}/projects",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "projects")

    def list_project_resources(self, project_hrn: str) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/resources",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "items")

    def remove_project_resource(self, project_hrn: str, resource_hrn: str) -> None:
        request = Request(
            f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/resources/{quote(resource_hrn, safe='')}?relation=reference",
            headers=self._authorized_headers(),
            method="DELETE",
        )
        self._request_json(request, allow_empty_response=True)

    def list_project_members(self, project_hrn: str) -> list[dict[str, object]]:
        payload = self._request_json(
            Request(
                f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/members",
                headers=self._authorized_headers(),
            )
        )
        return _items_from_payload(payload, "members")

    def create_project(self, project_id: str, name: str, description: str) -> dict[str, object]:
        payload = json.dumps({"id": project_id, "name": name, "description": description}).encode("utf-8")
        response = self._request_json(
            Request(
                f"{self.authz_base_url}/projects",
                data=payload,
                headers={**self._authorized_headers(), "Content-Type": "application/json"},
                method="POST",
            )
        )
        if isinstance(response, dict):
            return response
        raise HereClientError("HERE Authorization API returned an unsupported project payload.")

    def update_project(self, project_hrn: str, name: str, description: str) -> dict[str, object]:
        payload = json.dumps({"name": name, "description": description}).encode("utf-8")
        response = self._request_json(
            Request(
                f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}",
                data=payload,
                headers={**self._authorized_headers(), "Content-Type": "application/json"},
                method="PATCH",
            )
        )
        if isinstance(response, dict):
            return response
        raise HereClientError("HERE Authorization API returned an unsupported project payload.")

    def delete_project(self, project_hrn: str) -> None:
        request = Request(
            f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}",
            headers=self._authorized_headers(),
            method="DELETE",
        )
        self._request_json(request, allow_empty_response=True)

    def add_project_member(self, project_hrn: str, member_hrn: str) -> None:
        self._post_without_body(
            f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/members/{quote(member_hrn, safe='')}"
        )

    def remove_project_member(self, project_hrn: str, member_hrn: str) -> None:
        request = Request(
            f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/members/{quote(member_hrn, safe='')}",
            headers=self._authorized_headers(),
            method="DELETE",
        )
        self._request_json(request, allow_empty_response=True)

    def update_project_settings(self, project_hrn: str, scope_access: str) -> dict[str, object]:
        payload = json.dumps({"scopeAccess": scope_access}).encode("utf-8")
        response = self._request_json(
            Request(
                f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/settings",
                data=payload,
                headers={**self._authorized_headers(), "Content-Type": "application/json"},
                method="PATCH",
            )
        )
        if isinstance(response, dict):
            return response
        raise HereClientError("HERE Authorization API returned an unsupported project settings payload.")

    def set_default_scope(
        self, app_hrn: str, project_hrn: str, is_restricted: bool = True, always_project_scope: bool = True
    ) -> dict[str, object]:
        payload = json.dumps(
            {
                "scope": project_hrn,
                "isRestricted": is_restricted,
                "alwaysProjectScope": always_project_scope,
            }
        ).encode("utf-8")
        response = self._request_json(
            Request(
                f"{self.iam_base_url}/apps/{quote(app_hrn, safe='')}/defaultScope",
                data=payload,
                headers={**self._authorized_headers(), "Content-Type": "application/json"},
                method="PUT",
            )
        )
        if isinstance(response, dict):
            return response
        raise HereClientError("HERE Authentication API returned an unsupported default scope payload.")

    def add_project_resources(self, project_hrn: str, resource_hrns: list[str]) -> list[str]:
        unsupported_resources: list[str] = []
        current_resources = {
            item.get("resource")
            for item in self.list_project_resources(project_hrn)
            if isinstance(item.get("resource"), str)
        }
        for start in range(0, len(resource_hrns), 20):
            batch = [resource for resource in resource_hrns[start : start + 20] if resource not in current_resources]
            if not batch:
                continue
            try:
                self._add_project_resource_batch(project_hrn, batch)
                current_resources.update(batch)
                continue
            except HereClientError as error:
                if "404903" not in str(error):
                    raise
                current_resources = {
                    item.get("resource")
                    for item in self.list_project_resources(project_hrn)
                    if isinstance(item.get("resource"), str)
                }

            for resource in batch:
                if resource in current_resources:
                    continue
                try:
                    self._add_project_resource_batch(project_hrn, [resource])
                    current_resources.add(resource)
                except HereClientError as error:
                    if "404903" in str(error):
                        unsupported_resources.append(resource)
                        continue
                    raise
        return unsupported_resources

    def _add_project_resource_batch(self, project_hrn: str, resource_hrns: list[str]) -> None:
        payload = json.dumps(
            {"items": [{"resource": resource_hrn, "allowedActions": ["read"]} for resource_hrn in resource_hrns]}
        ).encode("utf-8")
        request = Request(
            f"{self.authz_base_url}/projects/{quote(project_hrn, safe='')}/resources?relation=reference",
            data=payload,
            headers={**self._authorized_headers(), "Content-Type": "application/json"},
            method="POST",
        )
        self._request_json(request, allow_empty_response=True)

    def list_external_service_resources(self) -> list[str]:
        payload = self._request_json(
            Request(
                f"{self.authz_base_url}/realm/externalResources?type=service&action=read",
                headers=self._authorized_headers(),
            )
        )
        return [
            item["hrn"].strip()
            for item in _items_from_payload(payload, "items")
            if isinstance(item.get("hrn"), str) and item["hrn"].strip()
        ]

    def _post_without_body(self, url: str) -> None:
        request = Request(url, data=b"", headers=self._authorized_headers(), method="POST")
        self._request_json(request, allow_empty_response=True)

    def _authorized_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": "application/json",
            "X-Correlation-ID": str(uuid.uuid4()),
        }

    def _request_json(self, request: Request, allow_empty_response: bool = False) -> object:
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
        except HTTPError as error:
            correlation_id = error.headers.get("X-Correlation-ID", "unavailable")
            details = _safe_error_details(error)
            raise HereClientError(
                f"HERE account request failed with HTTP {error.code}; {details} correlation ID: {correlation_id}."
            ) from error
        except URLError as error:
            raise HereClientError("HERE account request failed; verify network access and response format.") from error
        if not body:
            if allow_empty_response:
                return None
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise HereClientError("HERE IAM returned an invalid JSON document.") from error


def _items_from_payload(payload: object, collection_name: str) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", collection_name):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise HereClientError("HERE account API listing returned an unsupported JSON shape.")


def maybe_disable_app_credentials(
    month_records: list[UsageRecord], quota_alerts: list[QuotaStatus], identity_client: HereIdentityClient | None = None
) -> RemediationResult:
    if not _env_enabled("HERE_AUTO_DISABLE_APP_CREDENTIALS"):
        return RemediationResult(False, "")

    exceeded_metrics = tuple(sorted({item.metric for item in quota_alerts if item.status == "EXCEEDED"}))
    if not exceeded_metrics:
        return RemediationResult(False, "")

    implicated_apps = _implicated_apps(month_records, exceeded_metrics)
    if not implicated_apps:
        return RemediationResult(False, "")

    client = identity_client or HereIdentityClient()
    any_api_key_disabled = False
    any_access_key_disabled = False
    skipped_to_protect_monitor = False
    messages: list[str] = []

    for app_id, metrics in implicated_apps:
        try:
            app_hrn = _resolve_app_hrn(client, app_id)
        except HereClientError as error:
            messages.append(f"Credential auto-disable failed for app {app_id}: {error}")
            continue

        try:
            access_key_items = client.list_access_keys(app_hrn)
        except HereClientError as error:
            messages.append(f"Credential auto-disable failed for app {app_id}: {error}")
            continue

        metric_list = ", ".join(metrics)
        if _monitor_uses_target_app_credentials(access_key_items):
            skipped_to_protect_monitor = True
            messages.append(
                f"Automatic credential disable was skipped for app {app_id} on exceeded services: {metric_list}. "
                f"The monitor is using credentials from this same app, so disabling it would stop future usage checks. "
                f"Separate the monitor credential from the app credential used for service queries."
            )
            continue

        api_key_status, api_keys_disabled = _disable_api_keys_for_app(client, app_hrn)
        access_key_status, access_keys_disabled = _disable_access_keys_for_app(client, app_hrn, access_key_items)
        any_api_key_disabled = any_api_key_disabled or api_keys_disabled
        any_access_key_disabled = any_access_key_disabled or access_keys_disabled
        messages.append(
            f"Credential auto-disable triggered for app {app_id} on exceeded services: {metric_list}. "
            f"{api_key_status} {access_key_status}"
        )

    return RemediationResult(
        any_api_key_disabled or any_access_key_disabled,
        " ".join(messages),
        api_key_disabled=any_api_key_disabled,
        oauth_credentials_disabled=any_access_key_disabled,
        skipped_to_protect_monitor=skipped_to_protect_monitor,
    )


def maybe_remediate_app_access(
    month_records: list[UsageRecord], quota_alerts: list[QuotaStatus], identity_client: HereIdentityClient | None = None
) -> RemediationResult:
    if _env_enabled("HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT"):
        return maybe_limit_app_to_within_free_tier_project(month_records, quota_alerts, identity_client)
    return maybe_disable_app_credentials(month_records, quota_alerts, identity_client)


def maybe_limit_app_to_within_free_tier_project(
    month_records: list[UsageRecord], quota_alerts: list[QuotaStatus], identity_client: HereIdentityClient | None = None
) -> RemediationResult:
    if not _env_enabled("HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT"):
        return RemediationResult(False, "")

    exceeded_metrics = tuple(sorted({item.metric for item in quota_alerts if item.status == "EXCEEDED"}))
    metrics_by_app = dict(_implicated_apps(month_records, exceeded_metrics)) if exceeded_metrics else {}

    client = identity_client or HereIdentityClient()
    try:
        external_service_resources = set(client.list_external_service_resources())
        managed_projects = {}
        managed_project_apps = {}
        apps = [_app_from_item(item) for item in client.list_apps()]
        apps_by_id = {app["id"]: app for app in apps if app is not None}
        project_ids_by_app = {_managed_project_id(app_id): app_id for app_id in apps_by_id}
        for project in client.list_projects():
            project_id = project.get("id")
            project_hrn = project.get("hrn")
            if not isinstance(project_id, str) or not isinstance(project_hrn, str):
                continue
            managed_projects[project_id] = project
            managed_app_id = _managed_app_id_from_project(project) or project_ids_by_app.get(project_id)
            if managed_app_id:
                managed_project_apps[project_id] = managed_app_id
    except HereClientError as error:
        return RemediationResult(False, f"Project-based service restriction failed: {error}")

    app_ids = sorted(
        {record.app_id for record in month_records if record.app_id}
        | set(metrics_by_app)
        | set(managed_project_apps.values())
    )
    if not app_ids:
        return RemediationResult(False, "")

    messages: list[str] = []
    restricted_any_app = False
    for app_id in app_ids:
        metrics = metrics_by_app.get(app_id, ())
        project_id = _managed_project_id(app_id)
        existing_project = managed_projects.get(project_id)
        if not metrics and existing_project is None:
            continue

        metric_list = ", ".join(metrics) if metrics else "no currently exceeded service"
        try:
            app = apps_by_id.get(app_id) or _resolve_app(client, app_id)
        except HereClientError as error:
            messages.append(f"Project-based service restriction failed for app {app_id}: {error}")
            continue

        blocked_resources = _blocked_service_resources(month_records, app_id, metrics)
        unresolved_resources = _unresolved_service_records(month_records, app_id, metrics)
        if unresolved_resources:
            messages.append(
                f"Project-based service restriction failed for app {app_id} on exceeded services: {metric_list}. "
                f"Usage records could not be mapped to service resources: {', '.join(sorted(unresolved_resources))}. "
                "No all-services allowlist was applied."
            )
            continue

        missing_resources = sorted(blocked_resources - external_service_resources)
        if missing_resources:
            messages.append(
                f"Project-based service restriction failed for app {app_id} on exceeded services: {metric_list}. "
                f"These service resources could not be matched in HERE Authorization API: {', '.join(missing_resources)}."
            )
            continue

        allowed_resources = sorted(external_service_resources - blocked_resources)
        if not allowed_resources:
            messages.append(
                f"Project-based service restriction failed for app {app_id} on exceeded services: {metric_list}. "
                "No allowlisted service resources remained after excluding the exceeded services."
            )
            continue

        project_created = False
        project_hrn = ""
        already_fully_restored = False
        try:
            desired_project_name = _managed_project_name(app.get("name") or app_id, app_id)
            desired_project_description = _managed_project_description(app_id)
            if existing_project is not None:
                project = {
                    "id": project_id,
                    "hrn": str(existing_project["hrn"]),
                    "name": desired_project_name,
                }
            else:
                project, project_created = _ensure_project_for_app(client, app_id, app.get("name") or app_id)
            project_hrn = project["hrn"]
            if not metrics and not project_created:
                current_resources = _project_service_resources(client.list_project_resources(project_hrn))
                already_fully_restored = current_resources == set(allowed_resources)
            if not project_created and (
                existing_project is None
                or existing_project.get("name") != desired_project_name
                or existing_project.get("description") != desired_project_description
            ):
                try:
                    client.update_project(project_hrn, desired_project_name, desired_project_description)
                except HereClientError as error:
                    messages.append(f"Managed project metadata update failed for app {app_id}: {error}")
            client.update_project_settings(project_hrn, "thisProjectOnly")
            unsupported_resources = _reconcile_project_resources(client, project_hrn, allowed_resources, project_created)
            _ensure_project_member(client, project_hrn, app["hrn"])
            client.set_default_scope(app["hrn"], project_hrn)
        except HereClientError as error:
            _cleanup_project_if_created(client, project_hrn, project_created)
            messages.append(
                f"Project-based service restriction failed for app {app_id} on exceeded services: {metric_list}. "
                f"No complete project restriction was confirmed. {error}"
            )
            continue

        restricted_any_app = restricted_any_app or bool(metrics) or not already_fully_restored
        unavailable = (
            f" HERE skipped unavailable service resources: {', '.join(unsupported_resources)}."
            if unsupported_resources
            else ""
        )
        if metrics:
            messages.append(
                f"Project-based service restriction was applied for app {app_id} on exceeded services: {metric_list}. "
                f"Project {project.get('name') or app_id} preserves {len(allowed_resources) - len(unsupported_resources)} valid service resources, "
                f"excludes {len(blocked_resources)} exceeded service resource(s), and is set as the app's restricted default project.{unavailable}"
            )
        elif not already_fully_restored:
            messages.append(
                f"Project-based service restriction was restored for app {app_id}. "
                f"Project {project.get('name') or app_id} now allows all valid service resources and remains the app's restricted default project.{unavailable}"
            )

    return RemediationResult(restricted_any_app, " ".join(messages))


def _implicated_apps(month_records: list[UsageRecord], exceeded_metrics: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    metrics_by_app: dict[str, set[str]] = {}
    metric_set = set(exceeded_metrics)
    for record in month_records:
        if not record.app_id or record.quantity <= 0:
            continue
        if record.metric in metric_set:
            metric = record.metric
        elif "Data IO total" in metric_set and record.category in {"DataIO", "DataStorage"}:
            metric = "Data IO total"
        else:
            continue
        metrics_by_app.setdefault(record.app_id, set()).add(metric)
    return [(app_id, tuple(sorted(metrics))) for app_id, metrics in sorted(metrics_by_app.items())]


def _managed_app_id_from_project(project: dict[str, object]) -> str | None:
    description = project.get("description")
    prefix = "Managed by usage-alert to restrict app "
    if not isinstance(description, str) or not description.startswith(prefix):
        return None
    app_id = description[len(prefix) :].split(" to ", 1)[0].split(";", 1)[0].strip()
    return app_id or None


def _project_service_resources(items: object) -> set[str]:
    if not isinstance(items, list):
        raise HereClientError("HERE Authorization API returned an unsupported project resource payload.")
    return {
        item["resource"]
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("resource"), str)
        and item.get("type", "service") == "service"
        and item.get("relation", "reference") == "reference"
    }


def _reconcile_project_resources(
    client: HereIdentityClient, project_hrn: str, desired_resources: list[str], project_created: bool
) -> list[str]:
    desired = set(desired_resources)
    current = set() if project_created else _project_service_resources(client.list_project_resources(project_hrn))
    for resource_hrn in sorted(current - desired):
        client.remove_project_resource(project_hrn, resource_hrn)
    unsupported = client.add_project_resources(project_hrn, sorted(desired - current))
    return unsupported if isinstance(unsupported, list) else []


def _ensure_project_member(client: HereIdentityClient, project_hrn: str, member_hrn: str) -> None:
    members = client.list_project_members(project_hrn)
    if not isinstance(members, list):
        raise HereClientError("HERE Authorization API returned an unsupported project member payload.")
    if any(isinstance(item, dict) and item.get("member") == member_hrn for item in members):
        return
    client.add_project_member(project_hrn, member_hrn)


def _unresolved_service_records(month_records: list[UsageRecord], app_id: str, metrics: tuple[str, ...]) -> set[str]:
    metric_set = set(metrics)
    unresolved: set[str] = set()
    for record in month_records:
        data_io_record = "Data IO total" in metric_set and record.category in {"DataIO", "DataStorage"}
        if record.app_id != app_id or record.quantity <= 0 or (record.metric not in metric_set and not data_io_record):
            continue
        if not _service_resource_hrn(record.feature_id):
            unresolved.add(record.feature_id or record.metric)
    return unresolved


def _resolve_app(client: HereIdentityClient, app_id: str) -> dict[str, str]:
    for item in client.list_apps():
        app = _app_from_item(item)
        if app is not None and app["id"] == app_id:
            return app
    raise HereClientError(f"HERE IAM could not resolve app {app_id} to an app HRN.")


def _app_from_item(item: dict[str, object]) -> dict[str, str] | None:
    app_id = item.get("id")
    hrn = item.get("hrn")
    if not isinstance(app_id, str) or not app_id.strip() or not isinstance(hrn, str) or not hrn.strip():
        return None
    name = item.get("name")
    return {
        "id": app_id.strip(),
        "hrn": hrn.strip(),
        "name": name.strip() if isinstance(name, str) and name.strip() else app_id.strip(),
    }


def _resolve_app_hrn(client: HereIdentityClient, app_id: str) -> str:
    return _resolve_app(client, app_id)["hrn"]


def _ensure_project_for_app(client: HereIdentityClient, app_id: str, app_name: object) -> tuple[dict[str, str], bool]:
    project_id = _managed_project_id(app_id)
    project_name = _managed_project_name(app_name, app_id)
    description = _managed_project_description(app_id)
    try:
        project = client.create_project(project_id, project_name, description)
        project_hrn = project.get("hrn")
        if not isinstance(project_hrn, str) or not project_hrn.strip():
            raise HereClientError("HERE Authorization API returned a project without an HRN.")
        return ({"id": project_id, "hrn": project_hrn.strip(), "name": project_name}, True)
    except HereClientError as error:
        if not any(marker in str(error) for marker in ("HTTP 409", "400983", "project ID has already been used")):
            raise

    for project in client.list_projects():
        if project.get("id") != project_id:
            continue
        project_hrn = project.get("hrn")
        if not isinstance(project_hrn, str) or not project_hrn.strip():
            break
        name = project.get("name")
        return (
            {
                "id": project_id,
                "hrn": project_hrn.strip(),
                "name": name.strip() if isinstance(name, str) and name.strip() else project_name,
            },
            False,
        )
    raise HereClientError(f"HERE Authorization API could not resolve managed project {project_id} after a create conflict.")


def _cleanup_project_if_created(client: HereIdentityClient, project_hrn: str, project_created: bool) -> None:
    if not project_created or not project_hrn:
        return
    try:
        resources = client.list_project_resources(project_hrn)
        if isinstance(resources, list):
            for resource_hrn in sorted(_project_service_resources(resources)):
                client.remove_project_resource(project_hrn, resource_hrn)
        members = client.list_project_members(project_hrn)
        if isinstance(members, list):
            for item in members:
                member_hrn = item.get("member") if isinstance(item, dict) else None
                if isinstance(member_hrn, str) and member_hrn:
                    client.remove_project_member(project_hrn, member_hrn)
        client.delete_project(project_hrn)
    except HereClientError:
        return


def _managed_project_id(app_id: str) -> str:
    return f"ua-{hashlib.sha1((app_id + ':project-v2').encode('utf-8')).hexdigest()[:13]}"


def _managed_project_name(app_name: object, app_id: str) -> str:
    resolved_app_name = str(app_name).strip() or app_id
    return f"Service Restriction - {resolved_app_name} - {app_id}"


def _managed_project_description(app_id: str) -> str:
    return f"Managed by usage-alert to restrict app {app_id} to within-free-tier services."


def _blocked_service_resources(month_records: list[UsageRecord], app_id: str, metrics: tuple[str, ...]) -> set[str]:
    blocked_resources: set[str] = set()
    metric_set = set(metrics)
    for record in month_records:
        if record.app_id != app_id or record.metric not in metric_set or record.quantity <= 0:
            continue
        resource_hrn = _service_resource_hrn(record.feature_id)
        if resource_hrn:
            blocked_resources.add(resource_hrn)
    return blocked_resources


def _service_resource_hrn(feature_id: str | None) -> str | None:
    if not feature_id or not feature_id.startswith("hrn:here:service::"):
        return None
    prefix, separator, tail = feature_id.partition("::")
    if not separator:
        return feature_id
    tail_parts = tail.split(":")
    if len(tail_parts) <= 2:
        return feature_id
    return f"{prefix}{separator}{':'.join(tail_parts[:2])}"


def _disable_api_keys_for_app(client: HereIdentityClient, app_hrn: str) -> tuple[str, bool]:
    try:
        items = client.list_api_keys(app_hrn)
    except HereClientError as error:
        return (f"API key disable failed: {error}", False)

    identifiers = [_api_key_identifier(item) for item in items if _item_enabled(item)]
    resolved_identifiers = [identifier for identifier in identifiers if identifier]
    if not resolved_identifiers:
        return ("API key disable was skipped because no enabled API keys were discoverable for the app.", False)

    disabled_count = 0
    for identifier in resolved_identifiers:
        try:
            client.disable_api_key(app_hrn, identifier)
            disabled_count += 1
        except HereClientError as error:
            return (f"API key disable failed after disabling {disabled_count} API key(s): {error}", disabled_count > 0)

    label = "API key was disabled." if disabled_count == 1 else f"{disabled_count} API keys were disabled."
    return (label, disabled_count > 0)


def _disable_access_keys_for_app(
    client: HereIdentityClient, app_hrn: str, access_key_items: list[dict[str, object]]
) -> tuple[str, bool]:
    resolved_identifiers = [
        _access_key_identifier(item)
        for item in access_key_items
        if _item_enabled(item) and not _item_matches_monitor_access_key(item)
    ]
    resolved_identifiers = [identifier for identifier in resolved_identifiers if identifier]
    if not resolved_identifiers:
        return ("OAuth credential disable was skipped because no enabled non-monitor access keys were discoverable.", False)

    disabled_count = 0
    for identifier in resolved_identifiers:
        try:
            client.disable_access_key(app_hrn, identifier)
            disabled_count += 1
        except HereClientError as error:
            return (
                f"OAuth credential disable failed after disabling {disabled_count} access key(s): {error}",
                disabled_count > 0,
            )

    label = "OAuth credentials were disabled." if disabled_count == 1 else f"{disabled_count} OAuth credentials were disabled."
    return (label, disabled_count > 0)


def _api_key_identifier(item: dict[str, object]) -> str | None:
    for key in ("apiKey", "apiKeyHrn", "hrn", "apiKeyId", "id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _access_key_identifier(item: dict[str, object]) -> str | None:
    for key in ("accessKeyHrn", "hrn", "accessKeyId", "id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _item_enabled(item: dict[str, object]) -> bool:
    enabled = item.get("enabled")
    return enabled is not False


def _flatten_item_strings(item: dict[str, object]) -> set[str]:
    values: set[str] = set()
    for value in item.values():
        if isinstance(value, str):
            values.add(value.strip())
    return values


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _monitor_uses_target_app_credentials(items: list[dict[str, object]]) -> bool:
    return any(_item_matches_monitor_access_key(item) for item in items)


def _item_matches_monitor_access_key(item: dict[str, object]) -> bool:
    monitor_access_key_id = _monitor_access_key_id()
    return bool(monitor_access_key_id) and monitor_access_key_id in _flatten_item_strings(item)


def _monitor_access_key_id() -> str:
    return (os.getenv("here.access.key.id") or os.getenv("HERE_MONITOR_ACCESS_KEY_ID", "")).strip()
