# Website Monitoring Runbook

## Purpose

This runbook explains how to verify and troubleshoot the automated website-monitoring and alarm-logging system.

## System Components

| Component | Name |
|---|---|
| Website-monitoring Lambda | `kartikey-web-health` |
| Alarm-logging Lambda | `kartikey-alarm-logger` |
| AWS Region | `us-east-1` |
| CloudWatch namespace | `Kartikey/WebsiteMonitoring` |
| CloudWatch dashboard | `Kartikey-Website-Health-Dashboard` |
| EventBridge schedule | Every five minutes |
| SNS topic | `kartikey-website-alarm-notifications` |
| DynamoDB table | `Kartikey-Website-Alarm-Logs` |
| Monitored websites | Western Sydney University, AWS and GitHub |

## Verify the AWS Account

```powershell
aws sts get-caller-identity
```

The deployed project currently belongs to AWS account:

```text
715054189400
```

Confirm this account before checking resources or deploying changes.

## Check the Website-Monitoring Lambda

```powershell
aws lambda get-function --function-name kartikey-web-health --region us-east-1
```

## Manually Invoke the Website Crawler

```powershell
aws lambda invoke --function-name kartikey-web-health --region us-east-1 "$env:TEMP\kartikey-test.json"
```

View the result:

```powershell
Get-Content "$env:TEMP\kartikey-test.json"
```

A healthy website should report:

- HTTP status `200`
- Availability `1`
- Latency below the configured threshold

## Check the EventBridge Schedule

```powershell
aws events list-rules --region us-east-1 --query "Rules[?contains(Name, 'WebHealthSchedule')].[Name,State,ScheduleExpression]" --output table
```

The rule should be `ENABLED` and use `rate(5 minutes)`.

## Check CloudWatch Metrics

```powershell
aws cloudwatch list-metrics --namespace "Kartikey/WebsiteMonitoring" --region us-east-1 --output table
```

Each website should have:

- `Availability`
- `Latency`
- A `Website` dimension

## Check the Dashboard

Open Amazon CloudWatch in `us-east-1`, select **Dashboards**, and then open:

```text
Kartikey-Website-Health-Dashboard
```

Verify that the availability and latency graphs contain recent data for all three websites.

## Check the CloudWatch Alarms

```powershell
aws cloudwatch describe-alarms --region us-east-1 --query "MetricAlarms[].{Name:AlarmName,State:StateValue}" --output table
```

Alarm states:

- `OK`: The metric is within the threshold.
- `ALARM`: The metric has breached the threshold.
- `INSUFFICIENT_DATA`: CloudWatch does not have enough recent data.

## Check the SNS Topic

```powershell
aws sns list-topics --region us-east-1
```

Confirm that the output contains:

```text
kartikey-website-alarm-notifications
```

## Check the Alarm-Logging Lambda

```powershell
aws lambda get-function --function-name kartikey-alarm-logger --region us-east-1
```

## Check DynamoDB Alarm Records

```powershell
aws dynamodb scan --region us-east-1 --table-name "Kartikey-Website-Alarm-Logs" --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" --output table --no-cli-pager
```

A correctly processed alarm should contain:

- Alarm name
- State
- State-change reason
- Timestamp

## End-to-End Alarm Test

Check that the selected alarm is currently `OK`:

```powershell
aws cloudwatch describe-alarms --region us-east-1 --query "MetricAlarms[].{Name:AlarmName,State:StateValue}" --output table
```

Temporarily change the GitHub availability alarm to `ALARM`:

```powershell
aws cloudwatch set-alarm-state --region us-east-1 --alarm-name "GitHub-Availability-Alarm" --state-value ALARM --state-reason "Week 6 end-to-end SNS and DynamoDB test"
```

Then check DynamoDB:

```powershell
aws dynamodb scan --region us-east-1 --table-name "Kartikey-Website-Alarm-Logs" --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" --output table --no-cli-pager
```

The alarm should return to its normal calculated state after CloudWatch evaluates the next metric.

## Troubleshooting

### Website availability is `0`

1. Confirm the URL in `websites.json`.
2. Open the website manually.
3. Review the website-monitoring Lambda logs.
4. Check whether the request timed out.
5. Determine whether the website blocks automated requests.

### A latency alarm is active

1. Check the latest latency metric.
2. Invoke the crawler again.
3. Compare the results across multiple checks.
4. Determine whether one website or every website is affected.
5. Do not change the threshold until the cause is understood.

### Metrics are missing

1. Confirm that `kartikey-web-health` executed.
2. Review its CloudWatch logs.
3. Confirm that its role permits `cloudwatch:PutMetricData`.
4. Verify the metric namespace and `Website` dimension.
5. Allow several minutes for new metrics to appear.

### The schedule is not running

1. Confirm that the EventBridge rule is enabled.
2. Confirm that its target is `kartikey-web-health`.
3. Confirm that EventBridge can invoke the Lambda.
4. Invoke the Lambda manually to separate code problems from scheduling problems.

### SNS does not invoke the logger

1. Confirm that the SNS topic exists in `us-east-1`.
2. Confirm the topic has a Lambda subscription.
3. Confirm that the endpoint is `kartikey-alarm-logger`.
4. Check the logger Lambda’s CloudWatch logs.
5. Confirm the CloudWatch alarm contains an SNS alarm action.

### DynamoDB has no new record

1. Confirm that the alarm entered `ALARM`.
2. Check the SNS topic and Lambda subscription.
3. Review the `kartikey-alarm-logger` logs.
4. Confirm the Lambda environment contains `ALARM_TABLE_NAME`.
5. Confirm the Lambda role has `dynamodb:PutItem` permission.
6. Confirm the table name is `Kartikey-Website-Alarm-Logs`.

### DynamoDB displays `Unknown`

This can happen when a manually published SNS test message is not valid JSON. Real CloudWatch alarm messages use valid JSON and are parsed into the expected fields.

Use the end-to-end CloudWatch alarm test to verify the correct format.

## Deployment Commands

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Check Python syntax:

```powershell
python -m py_compile .\kartikey\kartikey_stack.py
python -m py_compile .\kartikey\resources\alarmLogger.py
```

Synthesise, review and deploy:

```powershell
cdk synth
cdk diff
cdk deploy
```

## Resource Removal

To remove the stack-managed resources:

```powershell
cdk destroy
```

Only run this command when the project is no longer required. The DynamoDB table uses a retain policy in the synthesised template and may remain after the stack is destroyed.

## AWS CDK References

- [Lambda Function](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html)
- [CloudWatch Alarm](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html)
- [SNS Topic](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns/Topic.html)
- [SNS Alarm Action](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch_actions/SnsAction.html)
- [Lambda Subscription](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns_subscriptions/LambdaSubscription.html)
- [DynamoDB Table](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html)

