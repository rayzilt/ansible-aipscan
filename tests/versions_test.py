#!/usr/bin/env python3
"""Interface-focused tests for the versions action plugin."""

import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from action_plugins.versions import (
    ActionModule,
    AIPscanResolver,
    PythonResolver,
    ResolutionError,
    UvResolver,
)


class FakeHttpClient:
    def __init__(self, fetch_responses=None, head_response=None):
        self.fetch_responses = list(fetch_responses or [])
        self.head_response = head_response
        self.fetch_calls = []
        self.head_calls = []

    def fetch_bytes(self, url, timeout, **kwargs):
        self.fetch_calls.append((url, timeout))
        if not self.fetch_responses:
            raise AssertionError("fetch_bytes called unexpectedly")
        value = self.fetch_responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def head(self, url, timeout, **kwargs):
        self.head_calls.append((url, timeout))
        if isinstance(self.head_response, Exception):
            raise self.head_response
        return self.head_response


class FakeResolver:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = []

    def resolve(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error
        return self.value


class FakeResolverFactory:
    def __init__(self, aipscan_resolver, uv_resolver, python_resolver):
        self._resolvers = (
            aipscan_resolver,
            uv_resolver,
            python_resolver,
        )
        self.http_client = None
        self.timeout = None
        self.params = None

    def build(self, http_client, timeout, params):
        self.http_client = http_client
        self.timeout = timeout
        self.params = params
        return self._resolvers


def _make_action_module(resolver_factory):
    module = ActionModule(
        task=MagicMock(),
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
        resolver_factory=resolver_factory,
    )
    module._task.args = {}
    module._task.async_val = False
    return module


# ---------------------------------------------------------------------------
# Action interface tests
# ---------------------------------------------------------------------------


def test_run_resolves_using_provided_resolvers():
    aipscan_resolver = FakeResolver("4.5.6")
    uv_resolver = FakeResolver("0.5.11")
    python_resolver = FakeResolver("3.11.9")
    factory = FakeResolverFactory(aipscan_resolver, uv_resolver, python_resolver)
    module = _make_action_module(factory)

    result = module.run(task_vars={})

    assert result["changed"] is False
    facts = result["ansible_facts"]
    assert facts["aipscan_version"] == "4.5.6"
    assert facts["aipscan_uv_version"] == "0.5.11"
    assert facts["aipscan_python_version"] == "3.11.9"
    assert python_resolver.calls[0][0] == "4.5.6"
    assert factory.params == {}


def test_run_uses_explicit_versions_from_params():
    aipscan_resolver = FakeResolver("9.9.9")
    uv_resolver = FakeResolver("1.2.3")
    python_resolver = FakeResolver("3.12.1")
    factory = FakeResolverFactory(aipscan_resolver, uv_resolver, python_resolver)
    module = _make_action_module(factory)
    module._task.args = {
        "aipscan_version": "9.9.9",
        "aipscan_uv_version": "1.2.3",
    }

    result = module.run(task_vars={})

    facts = result["ansible_facts"]
    assert facts["aipscan_version"] == "9.9.9"
    assert facts["aipscan_uv_version"] == "1.2.3"
    assert facts["aipscan_python_version"] == "3.12.1"
    assert factory.params["aipscan_version"] == "9.9.9"
    assert factory.params["aipscan_uv_version"] == "1.2.3"
    assert python_resolver.calls[0][0] == "9.9.9"


def test_run_bubbles_up_resolution_errors():
    aipscan_resolver = FakeResolver("4.5.6")
    uv_resolver = FakeResolver("0.5.11")
    python_resolver = FakeResolver(
        error=ResolutionError("Could not determine python version")
    )
    factory = FakeResolverFactory(aipscan_resolver, uv_resolver, python_resolver)
    module = _make_action_module(factory)

    result = module.run(task_vars={})

    assert result["failed"] is True
    assert "Could not determine python version" in result["msg"]


# ---------------------------------------------------------------------------
# Resolver unit tests
# ---------------------------------------------------------------------------


def test_aipscan_resolver_returns_explicit_value():
    resolver = AIPscanResolver(FakeHttpClient(), timeout=10, explicit_value=" 1.2.3 ")

    assert resolver.resolve() == "1.2.3"


def test_aipscan_resolver_fetches_latest_version():
    payload = json.dumps({"info": {"version": "4.5.6"}}).encode("utf-8")
    client = FakeHttpClient(fetch_responses=[payload])
    resolver = AIPscanResolver(client, timeout=10, explicit_value="")

    assert resolver.resolve() == "4.5.6"
    assert client.fetch_calls[0][0] == "https://pypi.org/pypi/aipscan/json"


def test_aipscan_resolver_missing_version_raises():
    payload = json.dumps({"info": {}}).encode("utf-8")
    client = FakeHttpClient(fetch_responses=[payload])
    resolver = AIPscanResolver(client, timeout=10, explicit_value=None)

    with pytest.raises(ResolutionError, match="did not include a version"):
        resolver.resolve()


def test_aipscan_resolver_http_error_propagates():
    error = urllib.error.HTTPError("url", 503, "Unavailable", {}, None)
    client = FakeHttpClient(fetch_responses=[error])
    resolver = AIPscanResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="HTTP 503"):
        resolver.resolve()


def test_aipscan_resolver_invalid_json():
    client = FakeHttpClient(fetch_responses=[b"not json"])
    resolver = AIPscanResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="Failed to parse JSON"):
        resolver.resolve()


def test_uv_resolver_returns_explicit_value():
    resolver = UvResolver(FakeHttpClient(), timeout=10, explicit_value=" 0.5.4 ")

    assert resolver.resolve() == "0.5.4"


def test_uv_resolver_reads_redirect_location():
    location = "https://github.com/astral-sh/uv/releases/tag/0.5.11"
    redirect = urllib.error.HTTPError(
        "url",
        302,
        "Found",
        {"Location": location},
        None,
    )
    client = FakeHttpClient(head_response=redirect)
    resolver = UvResolver(client, timeout=10, explicit_value="")

    assert resolver.resolve() == "0.5.11"
    assert client.head_calls[0][0] == "https://github.com/astral-sh/uv/releases/latest"


def test_uv_resolver_missing_location_header():
    redirect = urllib.error.HTTPError("url", 302, "Found", {}, None)
    client = FakeHttpClient(head_response=redirect)
    resolver = UvResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="did not provide a Location"):
        resolver.resolve()


def test_uv_resolver_unexpected_http_code():
    error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
    client = FakeHttpClient(head_response=error)
    resolver = UvResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="Unexpected response"):
        resolver.resolve()


def test_uv_resolver_url_error():
    error = urllib.error.URLError("Timeout")
    client = FakeHttpClient(head_response=error)
    resolver = UvResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="Unable to discover"):
        resolver.resolve()


def test_uv_resolver_without_redirect():
    client = FakeHttpClient(head_response=None)
    resolver = UvResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="completed without a redirect"):
        resolver.resolve()


def test_python_resolver_returns_explicit_value():
    resolver = PythonResolver(FakeHttpClient(), timeout=10, explicit_value=" 3.11 ")

    assert resolver.resolve("ignored") == "3.11"


def test_python_resolver_fetches_version_file():
    client = FakeHttpClient(fetch_responses=[b"3.11.9\n"])
    resolver = PythonResolver(client, timeout=10, explicit_value="")

    assert resolver.resolve("1.2.3") == "3.11.9"
    assert client.fetch_calls[0][0].endswith("1.2.3/.python-version")


def test_python_resolver_requires_aipscan_version():
    resolver = PythonResolver(FakeHttpClient(), timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="AIPscan version is unset"):
        resolver.resolve("")


def test_python_resolver_empty_file():
    client = FakeHttpClient(fetch_responses=[b"   \n  "])
    resolver = PythonResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="empty or whitespace-only"):
        resolver.resolve("1.2.3")


def test_python_resolver_http_error():
    error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
    client = FakeHttpClient(fetch_responses=[error])
    resolver = PythonResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="HTTP 404"):
        resolver.resolve("1.2.3")


def test_python_resolver_url_error():
    error = urllib.error.URLError("Connection failed")
    client = FakeHttpClient(fetch_responses=[error])
    resolver = PythonResolver(client, timeout=10, explicit_value="")

    with pytest.raises(ResolutionError, match="Unable to retrieve text"):
        resolver.resolve("1.2.3")
