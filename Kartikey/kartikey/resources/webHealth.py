import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import boto3

from constants import (
    AVAILABILITY_METRIC_NAME,
    LATENCY_METRIC_NAME,
    METRIC_NAMESPACE,
    REQUEST_TIMEOUT_SECONDS,
    WEBSITES_FILE,
    WEBSITE_DIMENSION_NAME,
)


cloudwatch = boto3.client("cloudwatch")


def load_websites():
    file_path = os.path.join(os.path.dirname(__file__), WEBSITES_FILE)

    with open(file_path, "r", encoding="utf-8") as websites_file:
        website_data = json.load(websites_file)

    return website_data["websites"]


def check_website(website):
    website_name = website["name"]
    website_url = website["url"]

    start_time = time.perf_counter()
    status_code = 0
    availability = 0

    try:
        request = urllib.request.Request(
            website_url,
            headers={"User-Agent": "AWS-Lambda-Website-Crawler"},
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            status_code = response.getcode()
            availability = 1 if 200 <= status_code < 400 else 0

    except Exception as error:
        print(f"{website_name} check failed: {error}")

    latency_ms = (time.perf_counter() - start_time) * 1000
    timestamp = datetime.now(timezone.utc)

    # Official AWS Boto3 documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
    cloudwatch.put_metric_data(
        Namespace=METRIC_NAMESPACE,
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
        "latency_ms": round(latency_ms, 2),
    }


def handler(event, context):
    websites = load_websites()
    results = []

    for website in websites:
        result = check_website(website)
        results.append(result)
        print(json.dumps(result))

    return {
        "statusCode": 200,
        "body": json.dumps({"results": results}),
    }