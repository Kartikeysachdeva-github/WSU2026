import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ALARM_TABLE_NAME"])


def handler(event, context):
    logged_alarms = []

    for record in event.get("Records", []):
        sns_message = record.get("Sns", {}).get("Message", "{}")

        try:
            alarm_data = json.loads(sns_message)
        except json.JSONDecodeError:
            alarm_data = {"message": sns_message}

        alarm_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        item = {
            "alarm_id": alarm_id,
            "timestamp": timestamp,
            "alarm_name": alarm_data.get("AlarmName", "Unknown"),
            "new_state": alarm_data.get("NewStateValue", "Unknown"),
            "reason": alarm_data.get(
                "NewStateReason",
                alarm_data.get("message", "No reason supplied"),
            ),
        }

        table.put_item(Item=item)
        logged_alarms.append(item)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Alarm notifications logged successfully",
                "alarms_logged": len(logged_alarms),
            }
        ),
    }