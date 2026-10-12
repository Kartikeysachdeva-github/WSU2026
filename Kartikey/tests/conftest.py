import importlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import boto3
import pytest


RESOURCES = (
    Path(__file__).resolve().parents[1]
    / "kartikey"
    / "resources"
)


class FakeResponse:
    """Small replacement for a urllib HTTP response."""

    def __init__(self, status):
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def crawler(monkeypatch):
    # Lambda imports constants from its deployment directory.
    monkeypatch.syspath_prepend(str(RESOURCES))

    # Replace AWS client creation before importing the crawler.
    fake_cloudwatch = Mock()
    monkeypatch.setattr(
        boto3,
        "client",
        lambda *args, **kwargs: fake_cloudwatch,
    )
    monkeypatch.setenv(
        "METRIC_NAMESPACE",
        "Kartikey/WebsiteMonitoring/Test",
    )

    sys.modules.pop("webHealth", None)
    module = importlib.import_module("webHealth")

    yield module

    sys.modules.pop("webHealth", None)


@pytest.fixture
def website():
    return {
        "name": "Example",
        "url": "https://example.com/",
    }


@pytest.fixture
def http_response(crawler, monkeypatch):
    def configure(status=200, error=None):
        request_mock = Mock()

        if error is None:
            request_mock.return_value = FakeResponse(status)
        else:
            request_mock.side_effect = error

        monkeypatch.setattr(
            crawler.urllib.request,
            "urlopen",
            request_mock,
        )
        return request_mock

    return configure


@pytest.fixture
def website_file(crawler, monkeypatch):
    def configure(websites):
        contents = json.dumps({"websites": websites})

        def open_file(*args, **kwargs):
            return io.StringIO(contents)

        monkeypatch.setattr(
            crawler,
            "open",
            open_file,
            raising=False,
        )

    return configure