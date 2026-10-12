import json
from unittest.mock import Mock
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
    assert response["statusCode"] == 200
    return json.loads(response["body"])["results"]


def test_handler_checks_every_configured_website(
    crawler, website_file, http_response
):
    websites = [
        {"name": "One", "url": "https://one.example/"},
        {"name": "Two", "url": "https://two.example/"},
        {"name": "Three", "url": "https://three.example/"},
    ]
    website_file(websites)
    request_mock = http_response()

    results = results_from(crawler.handler({}, None))

    assert [result["name"] for result in results] == [
        "One", "Two", "Three"
    ]
    assert all(
        result["availability"] == 1
        for result in results
    )
    assert request_mock.call_count == 3
    assert (
        crawler.cloudwatch.put_metric_data.call_count
        == 3
    )


def test_handler_continues_after_connection_failure(
    crawler, website_file, monkeypatch
):
    websites = [
        {"name": "Offline", "url": "https://offline.example/"},
        {"name": "Online", "url": "https://online.example/"},
    ]
    website_file(websites)

    def open_url(request, timeout):
        if request.full_url == websites[0]["url"]:
            raise URLError("Connection failed")


        return FakeResponse(200)

    monkeypatch.setattr(
        crawler.urllib.request, "urlopen", open_url
    )

    results = results_from(crawler.handler({}, None))

    assert [
        result["availability"] for result in results
    ] == [0, 1]
    assert (
        crawler.cloudwatch.put_metric_data.call_count
        == 2
    )


def test_handler_records_http_error_and_metrics(
    crawler, website_file, website, http_response
):
    website_file([website])
    http_response(
        error=HTTPError(
            website["url"],
            503,
            "Service unavailable",
            None,
            None,
        )
    )

    results = results_from(crawler.handler({}, None))
    metric_data = (
        crawler.cloudwatch.put_metric_data
        .call_args.kwargs["MetricData"]
    )

    assert results[0]["availability"] == 0
    # Current crawler uses 0 when urlopen raises an exception.
    assert results[0]["status_code"] == 0
    assert metric_data[0]["Value"] == 0


def test_handler_publishes_correct_metric_contract(
    crawler, website_file, website, http_response
):
    website_file([website])
    http_response()

    crawler.handler({}, None)

    published = (
        crawler.cloudwatch.put_metric_data
        .call_args.kwargs
    )
    availability, latency = published["MetricData"]

    assert (
        published["Namespace"]
        == "Kartikey/WebsiteMonitoring/Test"
    )
    assert availability["MetricName"] == "Availability"
    assert latency["MetricName"] == "Latency"

    for metric in published["MetricData"]:
        assert metric["Dimensions"] == [
            {"Name": "Website", "Value": "Example"}
        ]
        assert metric["Timestamp"].utcoffset().total_seconds() == 0

    assert availability["Unit"] == "Count"
    assert availability["Value"] == 1
    assert latency["Unit"] == "Milliseconds"
    assert latency["Value"] >= 0


def test_handler_uses_configured_timeout_and_user_agent(
    crawler, website_file, website, http_response
):
    website_file([website])
    request_mock = http_response()

    crawler.handler({}, None)

    request = request_mock.call_args.args[0]

    assert request.full_url == website["url"]
    assert (
        request.get_header("User-agent")
        == "AWS-Lambda-Website-Crawler"
    )
    assert (
        request_mock.call_args.kwargs["timeout"]
        == crawler.REQUEST_TIMEOUT_SECONDS
    )


def test_handler_returns_empty_results_for_empty_list(
    crawler, website_file, http_response
):
    website_file([])
    request_mock = http_response()

    results = results_from(crawler.handler({}, None))

    assert results == []
    request_mock.assert_not_called()
    crawler.cloudwatch.put_metric_data.assert_not_called()


def test_handler_fails_when_metric_publication_fails(
    crawler, website_file, website, http_response
):
    website_file([website])
    http_response()

    crawler.cloudwatch.put_metric_data.side_effect = (
        RuntimeError("Metric publication failed")
    )

    with pytest.raises(
        RuntimeError, match="Metric publication failed"
    ):
        crawler.handler({}, None)


def test_handler_preserves_website_metric_dimensions(
    crawler, website_file, monkeypatch
):
    websites = [
        {"name": "First", "url": "https://first.example/"},
        {"name": "Second", "url": "https://second.example/"},
    ]
    website_file(websites)



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

    results = results_from(crawler.handler({}, None))
    calls = (
        crawler.cloudwatch.put_metric_data.call_args_list
    )

    assert [
        result["availability"] for result in results
    ] == [1, 0]

    for call, expected_name, expected_value in zip(
        calls, ["First", "Second"], [1, 0]
    ):
        metrics = call.kwargs["MetricData"]

        assert metrics[0]["Value"] == expected_value
        assert all(
            metric["Dimensions"] == [
                {
                    "Name": "Website",
                    "Value": expected_name,
                }
            ]
            for metric in metrics
        )