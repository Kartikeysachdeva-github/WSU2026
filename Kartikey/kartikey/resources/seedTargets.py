import json
import os
import urllib.request

import boto3


dynamodb = boto3.resource("dynamodb")

TARGET_TABLE_NAME = os.environ["TARGET_TABLE_NAME"]


def send_response(event, context, status, reason=None):
    """
    Send the required response back to the CloudFormation
    custom-resource response URL.

    AWS custom-resource response reference:
    https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-responses.html
    """
    response_body = {
        "Status": status,
        "Reason": reason or (
            f"See CloudWatch Logs: {context.log_stream_name}"
        ),
        "PhysicalResourceId": (
            event.get("PhysicalResourceId")
            or f"{TARGET_TABLE_NAME}-initial-targets"
        ),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": False,
        "Data": {},
    }

    body = json.dumps(response_body).encode("utf-8")

    request = urllib.request.Request(
        event["ResponseURL"],
        data=body,
        method="PUT",
        headers={
            "Content-Type": "",
            "Content-Length": str(len(body)),
        },
    )

    with urllib.request.urlopen(request) as response:
        response.read()


def handler(event, context):
    """
    Seed the initial crawler targets when CloudFormation creates
    the custom resource.

    Existing targets are never overwritten. After creation, the
    public CRUD API remains responsible for managing the target list.
    """
    try:
        print(
            json.dumps(
                {
                    "RequestType": event.get("RequestType"),
                    "Table": TARGET_TABLE_NAME,
                }
            )
        )

        # Delete should remove the CloudFormation custom resource,
        # not manually delete target records from DynamoDB.
        if event["RequestType"] == "Delete":
            send_response(
                event,
                context,
                "SUCCESS",
            )
            return

        table = dynamodb.Table(
            TARGET_TABLE_NAME
        )

        targets = event["ResourceProperties"].get(
            "Targets",
            [],
        )

        for target in targets:
            try:
                # Only create a target when its target_id does not
                # already exist. This prevents later deployments from
                # overwriting changes made through the CRUD API.
                #
                # AWS DynamoDB PutItem reference:
                # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb/table/put_item.html
                table.put_item(
                    Item={
                        "target_id": target["target_id"],
                        "name": target["name"],
                        "url": target["url"],
                    },
                    ConditionExpression=(
                        "attribute_not_exists(target_id)"
                    ),
                )

                print(
                    f"Seeded target: {target['target_id']}"
                )

            except (
                dynamodb.meta.client.exceptions
                .ConditionalCheckFailedException
            ):
                # The target already exists. Preserve the current
                # DynamoDB value instead of overwriting it.
                print(
                    "Target already exists, preserving: "
                    f"{target['target_id']}"
                )

        send_response(
            event,
            context,
            "SUCCESS",
        )

    except Exception as error:
        print(
            "Target seeding failed: "
            f"{type(error).__name__}: {error}"
        )

        send_response(
            event,
            context,
            "FAILED",
            reason=str(error),
        )