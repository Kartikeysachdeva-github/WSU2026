import json
import os
import time
import urllib.request

import boto3


cloudwatch = boto3.client("cloudwatch")


def handler(event, context):
    website_url = os.environ["WEBSITE_URL"]
    metric_namespace = os.environ["METRIC_NAMESPACE"]

    start_time = time.time()
    status_code = 0
    availability = 0

    try:
        request = urllib.request.Request(
            website_url,
            headers={"User-Agent": "AWS-Lambda-Website-Monitor"},
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = response.getcode()
            availability = 1 if 200 <= status_code < 400 else 0

    except Exception as error:
        print(f"Website check failed: {error}")

    response_time_ms = (time.time() - start_time) * 1000

    # Official AWS SDK reference:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
    cloudwatch.put_metric_data(
        Namespace=metric_namespace,
        MetricData=[
            {
                "MetricName": "Availability",
                "Value": availability,
                "Unit": "Count",
            },
            {
                "MetricName": "ResponseTime",
                "Value": response_time_ms,
                "Unit": "Milliseconds",
            },
        ],
    )

    result = {
        "website": website_url,
        "status_code": status_code,
        "availability": availability,
        "response_time_ms": round(response_time_ms, 2),
    }

    print(json.dumps(result))

    return {
        "statusCode": 200,
        "body": json.dumps(result),
    }