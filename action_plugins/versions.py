#!/usr/bin/env python3
"""
Ansible action plugin for detecting the latest AIPscan release, the most
appropriate Python version for that release, and the latest uv version.

The resolved versions are returned as:
  - aipscan_version
  - aipscan_uv_version
  - aipscan_python_version
"""

import json
import re
import time
import urllib.error
import urllib.request

from ansible.plugins.action import ActionBase


PYPI_AIPSCAN_METADATA_URL = "https://pypi.org/pypi/aipscan/json"
UV_LATEST_RELEASE_URL = "https://github.com/astral-sh/uv/releases/latest"
PYTHON_VERSION_TEMPLATE = "https://raw.githubusercontent.com/artefactual-labs/AIPscan/refs/tags/{tag}/.python-version"
DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {"User-Agent": "ansible-aipscan/1.0"}
HTTP_RETRIES = 3
HTTP_RETRY_BACKOFF = 0.5


class ResolutionError(Exception):
    """Raised when a component version cannot be determined."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


class HttpClient:
    """Tiny HTTP helper that wraps urllib with retry and header defaults."""

    def __init__(self, retries=HTTP_RETRIES, backoff=HTTP_RETRY_BACKOFF):
        self.retries = max(1, int(retries))
        self.backoff = max(0.0, float(backoff))

    def fetch_bytes(self, url, timeout, method="GET", headers=None, opener=None):
        def call():
            request = urllib.request.Request(
                url, method=method, headers=self._merge_headers(headers)
            )
            if opener:
                return opener.open(request, timeout=timeout)
            return urllib.request.urlopen(request, timeout=timeout)

        response = self._request_with_retry(call)
        try:
            return response.read()
        finally:
            response.close()

    def head(self, url, timeout, headers=None, opener=None):
        def call():
            request = urllib.request.Request(
                url, method="HEAD", headers=self._merge_headers(headers)
            )
            if opener:
                return opener.open(request, timeout=timeout)
            return urllib.request.urlopen(request, timeout=timeout)

        response = self._request_with_retry(call)
        try:
            response.read()
        finally:
            response.close()

    def _request_with_retry(self, call):
        attempt = 0
        while True:
            try:
                return call()
            except urllib.error.HTTPError as exc:
                if exc.code < 500 or attempt >= self.retries - 1:
                    raise
                self._sleep(attempt)
                attempt += 1
            except urllib.error.URLError as exc:
                if attempt >= self.retries - 1:
                    raise
                self._sleep(attempt)
                attempt += 1

    def _sleep(self, attempt):
        if self.backoff <= 0:
            return
        time.sleep(self.backoff * (attempt + 1))

    def _merge_headers(self, custom):
        headers = dict(DEFAULT_HEADERS)
        if custom:
            headers.update(custom)
        return headers


def _trim(value):
    return (value or "").strip()


class AIPscanResolver:
    """Determine the AIPscan package version, falling back to PyPI metadata."""

    def __init__(self, http_client, timeout, explicit_value):
        self.http_client = http_client
        self.timeout = timeout
        self.explicit_value = explicit_value or ""

    def resolve(self):
        trimmed = _trim(self.explicit_value)
        if trimmed:
            return trimmed

        payload = self._fetch_json(PYPI_AIPSCAN_METADATA_URL)
        version = _trim(payload.get("info", {}).get("version"))
        if not version:
            raise ResolutionError(
                "PyPI metadata for AIPscan did not include a version field."
            )
        return version

    def _fetch_json(self, url):
        try:
            body = self.http_client.fetch_bytes(url, self.timeout).decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ResolutionError(f"HTTP {exc.code} retrieving {url}") from exc
        except urllib.error.URLError as exc:
            raise ResolutionError(f"Unable to retrieve JSON from {url}: {exc}") from exc
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ResolutionError(f"Failed to parse JSON from {url}: {exc}") from exc


class UvResolver:
    """Resolve the uv release tag by inspecting GitHub's latest-release redirect."""

    def __init__(self, http_client, timeout, explicit_value):
        self.http_client = http_client
        self.timeout = timeout
        self.explicit_value = explicit_value or ""

    def resolve(self):
        trimmed = _trim(self.explicit_value)
        if trimmed:
            return trimmed

        try:
            self.http_client.head(
                UV_LATEST_RELEASE_URL,
                self.timeout,
                opener=urllib.request.build_opener(NoRedirectHandler),
            )
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location:
                    raise ResolutionError(
                        "GitHub redirected for the latest uv release but did not provide a Location header."
                    )
                version = self._extract_uv_version_from_location(location)
                if not version:
                    raise ResolutionError(
                        "Failed to extract the uv release version from redirect Location header."
                    )
                return version
            raise ResolutionError(
                f"Unexpected response retrieving latest uv release: HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ResolutionError(
                f"Unable to discover the latest uv release: {exc}"
            ) from exc

        raise ResolutionError(
            "Expected GitHub to redirect for the latest uv release, but the request completed without a redirect."
        )

    def _extract_uv_version_from_location(self, location):
        match = re.search(r"/tag/([^/?#]+)", location)
        if not match:
            return ""
        tag = match.group(1)
        return _trim(tag.split("?")[0])


class PythonResolver:
    """Resolve the Python version required by a specific AIPscan release."""

    def __init__(self, http_client, timeout, explicit_value):
        self.http_client = http_client
        self.timeout = timeout
        self.explicit_value = explicit_value or ""

    def resolve(self, aipscan_version):
        trimmed = _trim(self.explicit_value)
        if trimmed:
            return trimmed
        if not aipscan_version:
            raise ResolutionError(
                "Cannot determine Python version because the AIPscan version is unset."
            )

        source_url = PYTHON_VERSION_TEMPLATE.format(tag=aipscan_version)
        content = self._fetch_text(source_url)
        version = _trim(content)
        if not version:
            raise ResolutionError(
                f"The .python-version file for AIPscan {aipscan_version} was empty or whitespace-only."
            )
        return version

    def _fetch_text(self, url):
        try:
            return self.http_client.fetch_bytes(url, self.timeout).decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ResolutionError(f"HTTP {exc.code} retrieving {url}") from exc
        except urllib.error.URLError as exc:
            raise ResolutionError(f"Unable to retrieve text from {url}: {exc}") from exc


class ResolverFactory:
    """Create resolver instances for the action module."""

    def build(self, http_client, timeout, params):
        params = params or {}
        return (
            AIPscanResolver(http_client, timeout, params.get("aipscan_version")),
            UvResolver(http_client, timeout, params.get("aipscan_uv_version")),
            PythonResolver(http_client, timeout, params.get("aipscan_python_version")),
        )


class ActionModule(ActionBase):
    """Ansible action plugin entry point for resolving component versions."""

    def __init__(
        self,
        task,
        connection,
        play_context,
        loader,
        templar,
        shared_loader_obj=None,
        resolver_factory=None,
    ):
        super().__init__(
            task,
            connection,
            play_context,
            loader,
            templar,
            shared_loader_obj,
        )
        self._resolver_factory = resolver_factory or ResolverFactory()

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        params = self._gather_params(task_vars)
        timeout = self._normalize_timeout(params.get("timeout"))
        http_client = HttpClient()

        try:
            (
                aipscan_resolver,
                uv_resolver,
                python_resolver,
            ) = self._resolver_factory.build(http_client, timeout, params)
            aipscan_version = aipscan_resolver.resolve()
            uv_version = uv_resolver.resolve()
            python_version = python_resolver.resolve(aipscan_version)
        except ResolutionError as exc:
            result.update(failed=True, msg=str(exc))
            return result

        result.update(
            changed=False,
            ansible_facts=dict(
                aipscan_version=aipscan_version,
                aipscan_uv_version=uv_version,
                aipscan_python_version=python_version,
            ),
        )
        return result

    def _gather_params(self, task_vars):
        params = {}
        context = task_vars or {}
        for key in (
            "timeout",
            "aipscan_version",
            "aipscan_uv_version",
            "aipscan_python_version",
        ):
            if key in context:
                params[key] = context[key]
        params.update(self._task.args or {})
        return params

    def _normalize_timeout(self, value):
        try:
            timeout = int(value)
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT
        if timeout <= 0:
            return DEFAULT_TIMEOUT
        return timeout
