import importlib
import io
from urllib.error import URLError

import pytest


def test_load_websites_reads_configured_list(
    crawler, website_file, website
):
    website_file([website])

    assert crawler.load_websites() == [website]


def test_load_websites_rejects_invalid_json(
    crawler, monkeypatch
):
    monkeypatch.setattr(
        crawler,
        "open",
        lambda *args, **kwargs: io.StringIO("{broken"),
        raising=False,
    )

    with pytest.raises(crawler.json.JSONDecodeError):
        crawler.load_websites()


def test_load_websites_requires_websites_key(
    crawler, monkeypatch
):
    monkeypatch.setattr(
        crawler,
        "open",
        lambda *args, **kwargs: io.StringIO("{}"),
        raising=False,
    )

    with pytest.raises(KeyError, match="websites"):
        crawler.load_websites()


def test_http_200_is_available(
    crawler, website, http_response
):
    http_response(status=200)

    result = crawler.check_website(website)

    assert result["availability"] == 1
    assert result["status_code"] == 200


def test_http_399_is_available(
    crawler, website, http_response
):
    http_response(status=399)

    result = crawler.check_website(website)

    assert result["availability"] == 1


def test_http_400_is_unavailable(
    crawler, website, http_response
):
    http_response(status=400)

    result = crawler.check_website(website)

    assert result["availability"] == 0
    assert result["status_code"] == 400


def test_connection_error_is_unavailable(
    crawler, website, http_response
):
    http_response(error=URLError("Connection failed"))

    result = crawler.check_website(website)

    assert result["availability"] == 0
    assert result["status_code"] == 0


def test_timeout_still_publishes_failure_metrics(
    crawler, website, http_response
):
    http_response(error=TimeoutError("Request timed out"))

    result = crawler.check_website(website)
    metric_data = (
        crawler.cloudwatch.put_metric_data
        .call_args.kwargs["MetricData"]
    )

    assert result["availability"] == 0
    assert metric_data[0]["Value"] == 0
    assert metric_data[1]["Value"] >= 0


def test_latency_is_converted_to_milliseconds(
    crawler, website, http_response, monkeypatch
):
    http_response()
    clock_values = iter([10.0, 10.125])

    monkeypatch.setattr(
        crawler.time,
        "perf_counter",
        lambda: next(clock_values),
    )

    result = crawler.check_website(website)
    metric_data = (
        crawler.cloudwatch.put_metric_data
        .call_args.kwargs["MetricData"]
    )

    assert result["latency_ms"] == 125.0
    assert metric_data[1]["Value"] == 125.0
    assert metric_data[1]["Unit"] == "Milliseconds"


def test_namespace_override_and_default(
    crawler, monkeypatch
):
    assert (
        crawler.metric_namespace
        == "Kartikey/WebsiteMonitoring/Test"
    )

    monkeypatch.delenv("METRIC_NAMESPACE")
    importlib.reload(crawler)

    assert (
        crawler.metric_namespace
        == crawler.DEFAULT_METRIC_NAMESPACE
    )