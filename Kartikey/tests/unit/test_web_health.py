import importlib
from urllib.error import URLError
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------
# DynamoDB target loading tests
# ---------------------------------------------------------


def test_load_websites_reads_targets_from_dynamodb(
    crawler,
    monkeypatch,
):
    """
    The crawler should load its runtime website targets from DynamoDB
    instead of the original websites.json configuration file.
    """
    mock_table = MagicMock()

    mock_table.scan.return_value = {
        "Items": [
            {
                "target_id": "github",
                "name": "GitHub",
                "url": "https://github.com",
            },
            {
                "target_id": "aws",
                "name": "AWS",
                "url": "https://aws.amazon.com",
            },
        ]
    }

    monkeypatch.setattr(
        crawler,
        "get_target_table",
        lambda: mock_table,
    )

    websites = crawler.load_websites()

    # target_id belongs to the CRUD/database layer. The crawler only
    # requires the display name and URL when checking website health.
    assert websites == [
        {
            "name": "GitHub",
            "url": "https://github.com",
        },
        {
            "name": "AWS",
            "url": "https://aws.amazon.com",
        },
    ]

    mock_table.scan.assert_called_once_with()


def test_load_websites_handles_dynamodb_pagination(
    crawler,
    monkeypatch,
):
    """
    DynamoDB Scan may return a LastEvaluatedKey. The crawler must read
    all pages so no configured target is skipped.

    AWS Boto3 DynamoDB Scan reference:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/scan.html
    """
    mock_table = MagicMock()

    mock_table.scan.side_effect = [
        {
            "Items": [
                {
                    "target_id": "github",
                    "name": "GitHub",
                    "url": "https://github.com",
                }
            ],
            "LastEvaluatedKey": {
                "target_id": "github"
            },
        },
        {
            "Items": [
                {
                    "target_id": "aws",
                    "name": "AWS",
                    "url": "https://aws.amazon.com",
                }
            ]
        },
    ]

    monkeypatch.setattr(
        crawler,
        "get_target_table",
        lambda: mock_table,
    )

    websites = crawler.load_websites()

    assert websites == [
        {
            "name": "GitHub",
            "url": "https://github.com",
        },
        {
            "name": "AWS",
            "url": "https://aws.amazon.com",
        },
    ]

    assert mock_table.scan.call_count == 2

    # The second scan must continue from the key returned by the first
    # page rather than starting another full table scan.
    mock_table.scan.assert_any_call(
        ExclusiveStartKey={
            "target_id": "github"
        }
    )


def test_get_target_table_requires_configuration(
    crawler,
    monkeypatch,
):
    """
    The crawler should fail clearly if the deployment did not provide
    the DynamoDB target table environment configuration.
    """
    monkeypatch.setattr(
        crawler,
        "target_table_name",
        "",
    )

    with pytest.raises(
        ValueError,
        match="TARGET_TABLE_NAME",
    ):
        crawler.get_target_table()


# ---------------------------------------------------------
# Website availability tests
# ---------------------------------------------------------


def test_http_200_is_available(
    crawler,
    website,
    http_response,
):
    http_response(status=200)

    result = crawler.check_website(
        website
    )

    assert result["availability"] == 1
    assert result["status_code"] == 200


def test_http_399_is_available(
    crawler,
    website,
    http_response,
):
    http_response(status=399)

    result = crawler.check_website(
        website
    )

    assert result["availability"] == 1


def test_http_400_is_unavailable(
    crawler,
    website,
    http_response,
):
    http_response(status=400)

    result = crawler.check_website(
        website
    )

    assert result["availability"] == 0
    assert result["status_code"] == 400


def test_connection_error_is_unavailable(
    crawler,
    website,
    http_response,
):
    http_response(
        error=URLError(
            "Connection failed"
        )
    )

    result = crawler.check_website(
        website
    )

    assert result["availability"] == 0
    assert result["status_code"] == 0


def test_timeout_still_publishes_failure_metrics(
    crawler,
    website,
    http_response,
):
    """
    Even when the HTTP request times out, the crawler should publish
    failure and latency information to CloudWatch.
    """
    http_response(
        error=TimeoutError(
            "Request timed out"
        )
    )

    result = crawler.check_website(
        website
    )

    metric_data = (
        crawler.cloudwatch
        .put_metric_data
        .call_args
        .kwargs["MetricData"]
    )

    assert result["availability"] == 0
    assert metric_data[0]["Value"] == 0
    assert metric_data[1]["Value"] >= 0


# ---------------------------------------------------------
# Performance and CloudWatch tests
# ---------------------------------------------------------


def test_latency_is_converted_to_milliseconds(
    crawler,
    website,
    http_response,
    monkeypatch,
):
    """
    Website request latency is measured with perf_counter and published
    to CloudWatch in milliseconds.
    """
    http_response()

    clock_values = iter(
        [
            10.0,
            10.125,
        ]
    )

    monkeypatch.setattr(
        crawler.time,
        "perf_counter",
        lambda: next(clock_values),
    )

    result = crawler.check_website(
        website
    )

    metric_data = (
        crawler.cloudwatch
        .put_metric_data
        .call_args
        .kwargs["MetricData"]
    )

    assert result["latency_ms"] == 125.0
    assert metric_data[1]["Value"] == 125.0
    assert (
        metric_data[1]["Unit"]
        == "Milliseconds"
    )


def test_namespace_override_and_default(
    crawler,
    monkeypatch,
):
    """
    Each pipeline environment can override the CloudWatch namespace,
    while the constants value remains the local/default fallback.
    """
    assert (
        crawler.metric_namespace
        == "Kartikey/WebsiteMonitoring/Test"
    )

    monkeypatch.delenv(
        "METRIC_NAMESPACE"
    )

    importlib.reload(
        crawler
    )

    assert (
        crawler.metric_namespace
        == crawler.DEFAULT_METRIC_NAMESPACE
    )