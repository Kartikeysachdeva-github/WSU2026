import importlib
import json
import os
from unittest.mock import MagicMock

import pytest


os.environ["TARGET_TABLE_NAME"] = "Test-Targets"
os.environ["METRIC_NAMESPACE"] = "Test/WebsiteMonitoring"

target_api = importlib.import_module(
    "kartikey.resources.targetApi"
)


@pytest.fixture
def mock_table(monkeypatch):
    table = MagicMock()

    monkeypatch.setattr(
        target_api,
        "get_table",
        lambda: table,
    )

    monkeypatch.setattr(
        target_api,
        "publish_timing_metric",
        lambda operation, elapsed_ms: None,
    )

    return table


def test_create_target(mock_table):
    mock_table.put_item.return_value = {}

    event = {
        "httpMethod": "POST",
        "body": json.dumps(
            {
                "target_id": "github",
                "name": "GitHub",
                "url": "https://github.com",
            }
        ),
    }

    result = target_api.handler(event, None)

    assert result["statusCode"] == 201

    body = json.loads(result["body"])

    assert body["message"] == "Target created."
    assert body["target"]["target_id"] == "github"
    assert body["target"]["name"] == "GitHub"
    assert body["target"]["url"] == "https://github.com"
    assert body["operation_time_ms"] >= 0

    mock_table.put_item.assert_called_once()


def test_get_target(mock_table):
    mock_table.get_item.return_value = {
        "Item": {
            "target_id": "github",
            "name": "GitHub",
            "url": "https://github.com",
        }
    }

    event = {
        "httpMethod": "GET",
        "pathParameters": {
            "id": "github",
        },
    }

    result = target_api.handler(event, None)

    assert result["statusCode"] == 200

    body = json.loads(result["body"])

    assert body["target"]["target_id"] == "github"
    assert body["target"]["name"] == "GitHub"
    assert body["operation_time_ms"] >= 0

    mock_table.get_item.assert_called_once_with(
        Key={
            "target_id": "github",
        }
    )