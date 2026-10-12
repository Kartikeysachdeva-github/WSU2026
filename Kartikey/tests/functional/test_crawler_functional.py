import json
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError, URLError

import pytest


class FakeResponse:
    """Controlled HTTP response for functional tests."""

    def __init__(self, status):
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def results_from(response):
    """Return crawler results from the Lambda proxy response."""
    assert response["statusCode"] == 200
    return json.loads(response["body"])["results"]


def configure_targets(
    crawler,
    monkeypatch,
    websites,
):
    """
    Configure a mocked DynamoDB target table for a functional test.

    The production crawler reads its target list from DynamoDB. These
    tests replace the real table with a controlled mock so no AWS
    resources or credentials are required during local testing.

    AWS Boto3 DynamoDB Scan reference:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/scan.html
    """
    mock_table = MagicMock()

    # DynamoDB records include target_id in addition to the name and URL
    # used by the crawler.
    items = [
        {
            "target_id": f"target-{index}",
            "name": website["name"],
            "url": website["url"],
        }
        for index, website in enumerate(
            websites,
            start=1,
        )
    ]

    mock_table.scan.return_value = {
        "Items": items,
    }

    # Replace the real DynamoDB table lookup so the functional tests
    # remain isolated from AWS while exercising the real load_websites
    # and handler logic.
    monkeypatch.setattr(
        crawler,
        "get_target_table",
        lambda: mock_table,
    )

    return mock_table


def test_handler_checks_every_configured_website(
    crawler,
    monkeypatch,
    http_response,
):
    """
    The handler should load every target from DynamoDB and check each
    configured website.
    """
    websites = [
        {
            "name": "One",
            "url": "https://one.example/",
        },
        {
            "name": "Two",
            "url": "https://two.example/",
        },
        {
            "name": "Three",
            "url": "https://three.example/",
        },
    ]

    target_table = configure_targets(
        crawler,
        monkeypatch,
        websites,
    )

    request_mock = http_response()

    results = results_from(
        crawler.handler({}, None)
    )

    assert [
        result["name"]
        for result in results
    ] == [
        "One",
        "Two",
        "Three",
    ]

    assert all(
        result["availability"] == 1
        for result in results
    )

    assert request_mock.call_count == 3

    assert (
        crawler.cloudwatch
        .put_metric_data
        .call_count
        == 3
    )

    target_table.scan.assert_called_once_with()


def test_handler_continues_after_connection_failure(
    crawler,
    monkeypatch,
):
    """
    A failed website should not prevent the crawler from checking the
    remaining DynamoDB targets.
    """
    websites = [
        {
            "name": "Offline",
            "url": "https://offline.example/",
        },
        {
            "name": "Online",
            "url": "https://online.example/",
        },
    ]

    configure_targets(
        crawler,
        monkeypatch,
        websites,
    )

    def open_url(request, timeout):
        if (
            request.full_url
            == websites[0]["url"]
        ):
            raise URLError(
                "Connection failed"
            )

        return FakeResponse(200)

    monkeypatch.setattr(
        crawler.urllib.request,
        "urlopen",
        open_url,
    )

    results = results_from(
        crawler.handler({}, None)
    )

    assert [
        result["availability"]
        for result in results
    ] == [
        0,
        1,
    ]

    assert (
        crawler.cloudwatch
        .put_metric_data
        .call_count
        == 2
    )


def test_handler_records_http_error_and_metrics(
    crawler,
    monkeypatch,
    website,
    http_response,
):
    """
    HTTP failures should be represented as unavailable and still produce
    CloudWatch availability and latency metrics.
    """
    configure_targets(
        crawler,
        monkeypatch,
        [website],
    )

    http_response(
        error=HTTPError(
            website["url"],
            503,
            "Service unavailable",
            None,
            None,
        )
    )

    results = results_from(
        crawler.handler({}, None)
    )

    metric_data = (
        crawler.cloudwatch
        .put_metric_data
        .call_args
        .kwargs["MetricData"]
    )

    assert results[0]["availability"] == 0

    # The crawler currently records status code 0 whenever urlopen
    # raises an exception.
    assert results[0]["status_code"] == 0

    assert metric_data[0]["Value"] == 0


def test_handler_publishes_correct_metric_contract(
    crawler,
    monkeypatch,
    website,
    http_response,
):
    """
    Verify the CloudWatch namespace, metric names, dimensions, timestamp
    and units produced by a complete crawler invocation.

    AWS Boto3 CloudWatch PutMetricData reference:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
    """
    configure_targets(
        crawler,
        monkeypatch,
        [website],
    )

    http_response()

    crawler.handler(
        {},
        None,
    )

    published = (
        crawler.cloudwatch
        .put_metric_data
        .call_args
        .kwargs
    )

    availability, latency = (
        published["MetricData"]
    )

    assert (
        published["Namespace"]
        == "Kartikey/WebsiteMonitoring/Test"
    )

    assert (
        availability["MetricName"]
        == "Availability"
    )

    assert (
        latency["MetricName"]
        == "Latency"
    )

    for metric in published["MetricData"]:
        assert metric["Dimensions"] == [
            {
                "Name": "Website",
                "Value": "Example",
            }
        ]

        assert (
            metric["Timestamp"]
            .utcoffset()
            .total_seconds()
            == 0
        )

    assert (
        availability["Unit"]
        == "Count"
    )

    assert (
        availability["Value"]
        == 1
    )

    assert (
        latency["Unit"]
        == "Milliseconds"
    )

    assert latency["Value"] >= 0


def test_handler_uses_configured_timeout_and_user_agent(
    crawler,
    monkeypatch,
    website,
    http_response,
):
    """
    Verify the crawler keeps the configured HTTP timeout and user-agent
    when targets are loaded from DynamoDB.
    """
    configure_targets(
        crawler,
        monkeypatch,
        [website],
    )

    request_mock = http_response()

    crawler.handler(
        {},
        None,
    )

    request = (
        request_mock
        .call_args
        .args[0]
    )

    assert (
        request.full_url
        == website["url"]
    )

    assert (
        request.get_header(
            "User-agent"
        )
        == "AWS-Lambda-Website-Crawler"
    )

    assert (
        request_mock
        .call_args
        .kwargs["timeout"]
        == crawler.REQUEST_TIMEOUT_SECONDS
    )


def test_handler_returns_empty_results_for_empty_list(
    crawler,
    monkeypatch,
    http_response,
):
    """
    An empty DynamoDB target table should produce a successful response
    containing no crawler results.
    """
    target_table = configure_targets(
        crawler,
        monkeypatch,
        [],
    )

    request_mock = http_response()

    results = results_from(
        crawler.handler({}, None)
    )

    assert results == []

    request_mock.assert_not_called()

    crawler.cloudwatch.put_metric_data.assert_not_called()

    target_table.scan.assert_called_once_with()


def test_handler_fails_when_metric_publication_fails(
    crawler,
    monkeypatch,
    website,
    http_response,
):
    """
    Preserve the existing failure behaviour when CloudWatch metric
    publication raises an exception.
    """
    configure_targets(
        crawler,
        monkeypatch,
        [website],
    )

    http_response()

    crawler.cloudwatch.put_metric_data.side_effect = (
        RuntimeError(
            "Metric publication failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Metric publication failed",
    ):
        crawler.handler(
            {},
            None,
        )


def test_handler_preserves_website_metric_dimensions(
    crawler,
    monkeypatch,
):
    """
    Each DynamoDB target must keep its own Website dimension when
    CloudWatch metrics are published.
    """
    websites = [
        {
            "name": "First",
            "url": "https://first.example/",
        },
        {
            "name": "Second",
            "url": "https://second.example/",
        },
    ]

    configure_targets(
        crawler,
        monkeypatch,
        websites,
    )

    request_mock = Mock(
        side_effect=[
            FakeResponse(200),
            FakeResponse(500),
        ]
    )

    monkeypatch.setattr(
        crawler.urllib.request,
        "urlopen",
        request_mock,
    )

    results = results_from(
        crawler.handler({}, None)
    )

    calls = (
        crawler.cloudwatch
        .put_metric_data
        .call_args_list
    )

    assert [
        result["availability"]
        for result in results
    ] == [
        1,
        0,
    ]

    for (
        call,
        expected_name,
        expected_value,
    ) in zip(
        calls,
        [
            "First",
            "Second",
        ],
        [
            1,
            0,
        ],
    ):
        metrics = (
            call.kwargs["MetricData"]
        )

        assert (
            metrics[0]["Value"]
            == expected_value
        )

        assert all(
            metric["Dimensions"]
            == [
                {
                    "Name": "Website",
                    "Value": expected_name,
                }
            ]
            for metric in metrics
        )