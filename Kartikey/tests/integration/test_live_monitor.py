import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Attr
import pytest


# Official Boto3 references:
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda/client/invoke.html
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/get_metric_statistics.html
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/scan.html


@pytest.fixture
def live_aws():
    # Live tests are opt-in so ordinary local test runs stay offline.
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live AWS tests")

    stage = os.environ.get("TEST_STAGE")
    if stage not in {"Beta", "Prod"}:
        pytest.fail("TEST_STAGE must be Beta or Prod")

    config = Config(
        connect_timeout=10,
        read_timeout=90,
        retries={"max_attempts": 3},
    )
    session = boto3.Session(region_name="us-east-1")
    account = session.client(
        "sts", config=config
    ).get_caller_identity()["Account"]

    # Prevent accidental testing against another configured account.
    assert account == "715054189400"

    return {
        "stage": stage,
        "suffix": stage.lower(),
        "account": account,
        "lambda": session.client("lambda", config=config),
        "cloudwatch": session.client("cloudwatch", config=config),
        "sns": session.client("sns", config=config),
        "dynamodb": session.resource("dynamodb", config=config),
    }


def wait_until(check, timeout=240):
    # AWS delivery is asynchronous; retry for a bounded period.
    deadline = time.monotonic() + timeout

    while True:
        if check():
            return

        if time.monotonic() >= deadline:
            pytest.fail("Expected AWS result did not arrive within 240 seconds")

        time.sleep(10)


def test_deployed_crawler_publishes_metrics(live_aws):
    # Verify deployed code returns results and publishes recent data.
    function_name = f"kartikey-web-health-{live_aws['suffix']}"
    namespace = f"Kartikey/WebsiteMonitoring/{live_aws['stage']}"

    configuration = live_aws["lambda"].get_function_configuration(
        FunctionName=function_name
    )
    assert configuration["State"] == "Active"
    assert (
        configuration["Environment"]["Variables"]["METRIC_NAMESPACE"]
        == namespace
    )

    started = datetime.now(timezone.utc)
    invocation = live_aws["lambda"].invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=b"{}",
    )

    assert "FunctionError" not in invocation, invocation
    response = json.loads(invocation["Payload"].read())
    assert response["statusCode"] == 200

    results = json.loads(response["body"])["results"]
    assert {result["name"] for result in results} == {
        "WesternSydneyUniversity", "AWS", "GitHub"
    }

    for result in results:
        assert result["availability"] in {0, 1}
        assert math.isfinite(result["latency_ms"])
        assert result["latency_ms"] >= 0

    # Check both metrics for every configured website.
    # External website downtime is a valid crawler result, not
    # automatically a defect in the monitoring application.
    def metrics_arrived():
        for result in results:
            for metric_name in ("Availability", "Latency"):
                data = live_aws["cloudwatch"].get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=[
                        {"Name": "Website", "Value": result["name"]}
                    ],
                    StartTime=started - timedelta(seconds=60),
                    EndTime=datetime.now(timezone.utc) + timedelta(seconds=60),
                    Period=60,
                    Statistics=["SampleCount"],
                )
                if not data["Datapoints"]:
                    return False

        return True

    wait_until(metrics_arrived)


def test_sns_notification_reaches_alarm_table(live_aws):
    # Check alarm wiring, then send a unique message through SNS
    # and the real logger. This does not simulate an actual outage.
    suffix = live_aws["suffix"]
    alarm_name = f"GitHub-Availability-Alarm-{suffix}"
    topic_arn = (
        f"arn:aws:sns:us-east-1:{live_aws['account']}:"
        f"kartikey-website-alarm-notifications-{suffix}"
    )
    table = live_aws["dynamodb"].Table(
        f"Kartikey-Website-Alarm-Logs-{suffix}"
    )

    alarms = live_aws["cloudwatch"].describe_alarms(
        AlarmNames=[alarm_name]
    )["MetricAlarms"]
    assert len(alarms) == 1
    assert alarms[0]["ActionsEnabled"]
    assert topic_arn in alarms[0]["AlarmActions"]

    reason = f"Week 10 integration test {uuid4()}"
    live_aws["sns"].publish(
        TopicArn=topic_arn,
        Message=json.dumps({
            "AlarmName": alarm_name,
            "NewStateValue": "ALARM",
            "NewStateReason": reason,
        }),
    )

    def record_arrived():
        # Paginate so the test still works after the table grows.
        arguments = {
            "FilterExpression": Attr("reason").eq(reason),
            "ConsistentRead": True,
        }

        while True:
            page = table.scan(**arguments)

            for item in page["Items"]:
                assert item["alarm_name"] == alarm_name
                assert item["new_state"] == "ALARM"
                assert item["alarm_id"]
                assert item["timestamp"]
                return True

            if "LastEvaluatedKey" not in page:
                return False

            arguments["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    wait_until(record_arrived)