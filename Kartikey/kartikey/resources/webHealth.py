import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import boto3

from constants import (
    AVAILABILITY_METRIC_NAME,
    LATENCY_METRIC_NAME,
    METRIC_NAMESPACE as DEFAULT_METRIC_NAMESPACE,
    REQUEST_TIMEOUT_SECONDS,
    WEBSITE_DIMENSION_NAME,
)


# AWS SDK clients/resources are created outside the handler so Lambda can
# reuse them between warm invocations.
cloudwatch = boto3.client("cloudwatch")
dynamodb = boto3.resource("dynamodb")

metric_namespace = os.environ.get(
    "METRIC_NAMESPACE",
    DEFAULT_METRIC_NAMESPACE,
)

target_table_name = os.environ.get(
    "TARGET_TABLE_NAME",
    "",
)


def get_target_table():
    """
    Return the DynamoDB table containing the crawler target list.

    The table name is supplied through a Lambda environment variable so
    Beta and Prod can use separate DynamoDB tables.
    """
    if not target_table_name:
        raise ValueError(
            "TARGET_TABLE_NAME environment variable is not configured."
        )

    return dynamodb.Table(target_table_name)


def load_websites():
    """
    Load the current crawler target list from DynamoDB.

    The original project loaded targets from websites.json. The Applied
    Project moves the runtime target list into DynamoDB so targets can be
    changed through the REST API without redeploying the crawler.
    """
    table = get_target_table()

    # Official AWS Boto3 DynamoDB Scan documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/scan.html
    response = table.scan()
    websites = response.get("Items", [])

    # A DynamoDB Scan can be paginated. LastEvaluatedKey means more
    # targets remain, so continue until the complete list is loaded.
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )

        websites.extend(
            response.get("Items", [])
        )

    # The crawler only needs the name and URL. target_id remains the
    # database/API identifier and is not required for an HTTP check.
    return [
        {
            "name": website["name"],
            "url": website["url"],
        }
        for website in websites
    ]


def check_website(website):
    """
    Check one website and publish availability and latency metrics.
    """
    website_name = website["name"]
    website_url = website["url"]

    start_time = time.perf_counter()

    status_code = 0
    availability = 0

    try:
        request = urllib.request.Request(
            website_url,
            headers={
                "User-Agent": "AWS-Lambda-Website-Crawler"
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            status_code = response.getcode()

            # HTTP 2xx and 3xx responses are considered available.
            availability = (
                1
                if 200 <= status_code < 400
                else 0
            )

    except Exception as error:
        # A failed request is recorded as unavailable, but the Lambda
        # continues so the remaining targets can still be checked.
        print(
            f"{website_name} check failed: {error}"
        )

    latency_ms = (
        time.perf_counter() - start_time
    ) * 1000

    timestamp = datetime.now(timezone.utc)

    # Publish both website health measurements in one CloudWatch call.
    #
    # Official AWS Boto3 CloudWatch PutMetricData documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
    cloudwatch.put_metric_data(
        Namespace=metric_namespace,
        MetricData=[
            {
                "MetricName": AVAILABILITY_METRIC_NAME,
                "Dimensions": [
                    {
                        "Name": WEBSITE_DIMENSION_NAME,
                        "Value": website_name,
                    }
                ],
                "Timestamp": timestamp,
                "Value": availability,
                "Unit": "Count",
            },
            {
                "MetricName": LATENCY_METRIC_NAME,
                "Dimensions": [
                    {
                        "Name": WEBSITE_DIMENSION_NAME,
                        "Value": website_name,
                    }
                ],
                "Timestamp": timestamp,
                "Value": latency_ms,
                "Unit": "Milliseconds",
            },
        ],
    )

    return {
        "name": website_name,
        "url": website_url,
        "status_code": status_code,
        "availability": availability,
        "latency_ms": round(
            latency_ms,
            2,
        ),
    }


def handler(event, context):
    """
    Lambda entry point used by the EventBridge schedule.

    Every invocation reads the latest target list from DynamoDB. This
    means CRUD API changes are automatically reflected in future crawls.
    """
    websites = load_websites()
    results = []

    for website in websites:
        result = check_website(website)

        results.append(result)

        # CloudWatch Logs receives one structured result per target.
        print(
            json.dumps(result)
        )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "results": results,
            }
        ),
    }