import json
import os
import time
from decimal import Decimal

import boto3


# AWS SDK clients/resources are created outside the handler so Lambda can
# reuse them between warm invocations.
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

TARGET_TABLE_NAME = os.environ.get(
    "TARGET_TABLE_NAME",
    "",
)

METRIC_NAMESPACE = os.environ.get(
    "METRIC_NAMESPACE",
    "Kartikey/WebsiteMonitoring",
)


def get_table():
    """
    Return the DynamoDB table used by the CRUD API.

    Beta and Prod receive different table names through Lambda
    environment variables.
    """
    if not TARGET_TABLE_NAME:
        raise ValueError(
            "TARGET_TABLE_NAME environment variable is not configured."
        )

    return dynamodb.Table(
        TARGET_TABLE_NAME
    )


def decimal_default(value):
    """
    Convert DynamoDB Decimal values into JSON-compatible numbers.
    """
    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable."
    )


def response(status_code, body):
    """
    Build the Lambda proxy response returned through API Gateway.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(
            body,
            default=decimal_default,
        ),
    }


def publish_timing_metric(
    operation,
    elapsed_ms,
):
    """
    Publish DynamoDB read/write duration as a custom CloudWatch metric.

    Measuring database time separately from the total Lambda duration
    provides evidence for the Applied Project's DynamoDB read/write
    performance requirement.
    """
    metric_name = (
        "DynamoDBReadTime"
        if operation == "Read"
        else "DynamoDBWriteTime"
    )

    # Official AWS Boto3 CloudWatch PutMetricData documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
    cloudwatch.put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=[
            {
                "MetricName": metric_name,
                "Dimensions": [
                    {
                        "Name": "Operation",
                        "Value": operation,
                    }
                ],
                "Value": elapsed_ms,
                "Unit": "Milliseconds",
            }
        ],
    )


def timed_operation(
    operation,
    function,
    **kwargs,
):
    """
    Execute one DynamoDB operation and measure only its elapsed time.
    """
    start_time = time.perf_counter()

    result = function(
        **kwargs
    )

    elapsed_ms = (
        time.perf_counter() - start_time
    ) * 1000

    publish_timing_metric(
        operation,
        elapsed_ms,
    )

    return (
        result,
        round(elapsed_ms, 3),
    )


def parse_body(event):
    """
    Parse the JSON request body supplied by API Gateway.
    """
    body = event.get("body")

    if not body:
        raise ValueError(
            "Request body is required."
        )

    if isinstance(body, dict):
        return body

    try:
        return json.loads(body)

    except json.JSONDecodeError as error:
        raise ValueError(
            "Request body must contain valid JSON."
        ) from error


def validate_target(
    data,
    require_id=True,
):
    """
    Validate the fields required to create or update a crawler target.
    """
    required_fields = [
        "name",
        "url",
    ]

    if require_id:
        required_fields.insert(
            0,
            "target_id",
        )

    missing_fields = [
        field
        for field in required_fields
        if not data.get(field)
    ]

    if missing_fields:
        raise ValueError(
            "Missing required field(s): "
            + ", ".join(missing_fields)
        )

    url = data["url"]

    # Restrict crawler targets to HTTP/HTTPS URLs.
    if not (
        url.startswith("https://")
        or url.startswith("http://")
    ):
        raise ValueError(
            "URL must start with http:// or https://."
        )


def create_target(event):
    """
    POST /targets

    Create a new website target.
    """
    data = parse_body(event)

    validate_target(
        data
    )

    target = {
        "target_id": data["target_id"],
        "name": data["name"],
        "url": data["url"],
    }

    table = get_table()

    try:
        # attribute_not_exists prevents POST from silently overwriting
        # an existing target with the same target_id.
        #
        # Official AWS Boto3 DynamoDB PutItem documentation:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/put_item.html
        _, elapsed_ms = timed_operation(
            "Write",
            table.put_item,
            Item=target,
            ConditionExpression=(
                "attribute_not_exists(target_id)"
            ),
        )

    except (
        dynamodb.meta.client.exceptions
        .ConditionalCheckFailedException
    ):
        return response(
            409,
            {
                "message": "Target already exists.",
                "target_id": target["target_id"],
            },
        )

    return response(
        201,
        {
            "message": "Target created.",
            "target": target,
            "operation_time_ms": elapsed_ms,
        },
    )


def list_targets():
    """
    GET /targets

    Return all configured crawler targets.
    """
    table = get_table()

    # The coursework target list is small, so Scan provides a simple
    # way to return the complete collection.
    #
    # Official AWS Boto3 DynamoDB Scan documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/scan.html
    result, elapsed_ms = timed_operation(
        "Read",
        table.scan,
    )

    targets = result.get(
        "Items",
        [],
    )

    return response(
        200,
        {
            "targets": targets,
            "count": len(targets),
            "operation_time_ms": elapsed_ms,
        },
    )


def get_target(target_id):
    """
    GET /targets/{id}

    Return one target using its DynamoDB partition key.
    """
    table = get_table()

    # Official AWS Boto3 DynamoDB GetItem documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/get_item.html
    result, elapsed_ms = timed_operation(
        "Read",
        table.get_item,
        Key={
            "target_id": target_id,
        },
    )

    target = result.get(
        "Item"
    )

    if not target:
        return response(
            404,
            {
                "message": "Target not found.",
                "target_id": target_id,
                "operation_time_ms": elapsed_ms,
            },
        )

    return response(
        200,
        {
            "target": target,
            "operation_time_ms": elapsed_ms,
        },
    )


def update_target(
    event,
    target_id,
):
    """
    PUT /targets/{id}

    Update the name and URL of an existing target.
    """
    data = parse_body(event)

    validate_target(
        data,
        require_id=False,
    )

    table = get_table()

    try:
        # ConditionExpression prevents PUT from accidentally creating a
        # new target when the requested target_id does not exist.
        #
        # Official AWS Boto3 DynamoDB UpdateItem documentation:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/update_item.html
        result, elapsed_ms = timed_operation(
            "Write",
            table.update_item,
            Key={
                "target_id": target_id,
            },
            UpdateExpression=(
                "SET #target_name = :name, "
                "#target_url = :url"
            ),
            ExpressionAttributeNames={
                "#target_name": "name",
                "#target_url": "url",
            },
            ExpressionAttributeValues={
                ":name": data["name"],
                ":url": data["url"],
            },
            ConditionExpression=(
                "attribute_exists(target_id)"
            ),
            ReturnValues="ALL_NEW",
        )

    except (
        dynamodb.meta.client.exceptions
        .ConditionalCheckFailedException
    ):
        return response(
            404,
            {
                "message": "Target not found.",
                "target_id": target_id,
            },
        )

    return response(
        200,
        {
            "message": "Target updated.",
            "target": result.get(
                "Attributes",
                {},
            ),
            "operation_time_ms": elapsed_ms,
        },
    )


def delete_target(target_id):
    """
    DELETE /targets/{id}

    Delete a target and return the item that was removed.
    """
    table = get_table()

    # ALL_OLD lets the API determine whether an item actually existed
    # before the delete request.
    #
    # Official AWS Boto3 DynamoDB DeleteItem documentation:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/delete_item.html
    result, elapsed_ms = timed_operation(
        "Write",
        table.delete_item,
        Key={
            "target_id": target_id,
        },
        ReturnValues="ALL_OLD",
    )

    deleted_target = result.get(
        "Attributes"
    )

    if not deleted_target:
        return response(
            404,
            {
                "message": "Target not found.",
                "target_id": target_id,
                "operation_time_ms": elapsed_ms,
            },
        )

    return response(
        200,
        {
            "message": "Target deleted.",
            "target": deleted_target,
            "operation_time_ms": elapsed_ms,
        },
    )


def handler(event, context):
    """
    Lambda entry point for the API Gateway REST API.

    API Gateway Lambda proxy integration supplies the HTTP method,
    path parameters and request body in the event object.

    Official AWS API Gateway Lambda proxy integration documentation:
    https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    method = event.get(
        "httpMethod",
        "",
    )

    path_parameters = (
        event.get("pathParameters")
        or {}
    )

    target_id = path_parameters.get(
        "id"
    )

    try:
        if method == "POST":
            return create_target(
                event
            )

        if (
            method == "GET"
            and target_id
        ):
            return get_target(
                target_id
            )

        if method == "GET":
            return list_targets()

        if (
            method == "PUT"
            and target_id
        ):
            return update_target(
                event,
                target_id,
            )

        if (
            method == "DELETE"
            and target_id
        ):
            return delete_target(
                target_id
            )

        return response(
            405,
            {
                "message": "Method not allowed.",
            },
        )

    except ValueError as error:
        return response(
            400,
            {
                "message": str(error),
            },
        )

    except Exception as error:
        # Log the real exception to CloudWatch Logs while avoiding
        # exposing internal implementation details to API clients.
        print(
            "Target API error: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return response(
            500,
            {
                "message": "Internal server error.",
            },
        )