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
def target_store(monkeypatch):
    store = {}
    table = MagicMock()

    def put_item(Item, **kwargs):
        store[Item["target_id"]] = Item.copy()
        return {}

    def scan(**kwargs):
        return {
            "Items": list(store.values())
        }

    def get_item(Key, **kwargs):
        item = store.get(Key["target_id"])

        if item is None:
            return {}

        return {
            "Item": item.copy()
        }

    def update_item(
        Key,
        ExpressionAttributeValues,
        **kwargs,
    ):
        target_id = Key["target_id"]

        item = store[target_id]

        item["name"] = (
            ExpressionAttributeValues[":name"]
        )
        item["url"] = (
            ExpressionAttributeValues[":url"]
        )

        return {
            "Attributes": item.copy()
        }

    def delete_item(Key, **kwargs):
        item = store.pop(
            Key["target_id"],
            None,
        )

        if item is None:
            return {}

        return {
            "Attributes": item
        }

    table.put_item.side_effect = put_item
    table.scan.side_effect = scan
    table.get_item.side_effect = get_item
    table.update_item.side_effect = update_item
    table.delete_item.side_effect = delete_item

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

    return store


def test_complete_crud_lifecycle(target_store):
    create_event = {
        "httpMethod": "POST",
        "body": json.dumps(
            {
                "target_id": "github",
                "name": "GitHub",
                "url": "https://github.com",
            }
        ),
    }

    create_result = target_api.handler(
        create_event,
        None,
    )

    assert create_result["statusCode"] == 201

    create_body = json.loads(
        create_result["body"]
    )

    assert create_body["operation_time_ms"] >= 0

    read_event = {
        "httpMethod": "GET",
        "pathParameters": {
            "id": "github",
        },
    }

    read_result = target_api.handler(
        read_event,
        None,
    )

    assert read_result["statusCode"] == 200

    read_body = json.loads(
        read_result["body"]
    )

    assert read_body["target"]["name"] == "GitHub"
    assert read_body["operation_time_ms"] >= 0

    update_event = {
        "httpMethod": "PUT",
        "pathParameters": {
            "id": "github",
        },
        "body": json.dumps(
            {
                "name": "GitHub Updated",
                "url": "https://github.com",
            }
        ),
    }

    update_result = target_api.handler(
        update_event,
        None,
    )

    assert update_result["statusCode"] == 200

    update_body = json.loads(
        update_result["body"]
    )

    assert (
        update_body["target"]["name"]
        == "GitHub Updated"
    )

    assert update_body["operation_time_ms"] >= 0

    delete_event = {
        "httpMethod": "DELETE",
        "pathParameters": {
            "id": "github",
        },
    }

    delete_result = target_api.handler(
        delete_event,
        None,
    )

    assert delete_result["statusCode"] == 200

    delete_body = json.loads(
        delete_result["body"]
    )

    assert delete_body["operation_time_ms"] >= 0
    assert "github" not in target_store