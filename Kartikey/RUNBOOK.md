# Website Monitoring Runbook

## Purpose

This runbook explains how to verify and troubleshoot the automated website-monitoring system.

## System Components

- Lambda function: `kartikey-web-health`
- AWS Region: `us-east-1`
- CloudWatch namespace: `Kartikey/WebsiteMonitoring`
- Dashboard: `Kartikey-Website-Health-Dashboard`
- EventBridge schedule: Every five minutes
- Monitored websites: WSU, AWS and GitHub

## Check the Lambda

Confirm that the Lambda exists:

```powershell
aws lambda get-function --function-name kartikey-web-health --region Brittany us-east-1
```

Remove the word `Brittany` from that command. The correct command is:

```powershell
aws lambda get-function --function-name kartikey-web-health --region us-east-1
```

## Manually Invoke the Crawler

```powershell
aws lambda invoke --function-name kartikey-web-health --region us-east-1 "$env:TEMP\kartikey-test.json"
```

View the result:

```powershell
Get-Content "$env:TEMP\kartikey-test.json"
```

A healthy website should return:

- HTTP status `200`
- Availability `1`
- Latency below the configured threshold

## Check the EventBridge Schedule

```powershell
aws events list-rules --region us-east-1 --query "Rules[?contains(Name, 'WebHealthSchedule')].[Name,State,ScheduleExpression]" --output table
```

The rule should be `ENABLED` with `rate(5 minutes)`.

## Check CloudWatch Metrics

```powershell
aws cloudwatch list-metrics --namespace "Kartikey/WebsiteMonitoring" --region us-east-1 --output table
```

Each website should have:

- `Availability`
- `Latency`
- A `Website` dimension

## Check the Dashboard

Open CloudWatch in `us-east-1` and select:

```text
Dashboards → Kartikey-Website-Health-Dashboard
```

Verify that the availability and latency graphs contain recent data.

## Check the Alarms

```powershell
aws cloudwatch describe-alarms --region us-east-1 --query "MetricAlarms[].[AlarmName,StateValue,Threshold]" --output table
```

Alarm states:

- `OK`: The metric is within the configured threshold.
- `ALARM`: The metric breached the configured threshold.
- `INSUFFICIENT_DATA`: CloudWatch does not yet have enough data.

## Troubleshooting

### Availability is 0

1. Check whether the URL in `websites.json` is correct.
2. Open the website manually.
3. Review the Lambda logs.
4. Check whether the request timed out.
5. Check whether the website blocks automated requests.

### Latency alarm is active

1. Check the latest latency metric.
2. Invoke the Lambda again.
3. Compare results across multiple runs.
4. Determine whether the problem affects one website or all websites.
5. Avoid changing the threshold until the actual cause is understood.

### Metrics are missing

1. Confirm that the Lambda executed.
2. Check its CloudWatch logs.
3. Confirm the IAM role allows `cloudwatch:PutMetricData`.
4. Verify the metric namespace and website dimension.
5. Allow several minutes for new metrics to appear.

### Schedule is not running

1. Confirm that the EventBridge rule is enabled.
2. Confirm its target is the Lambda function.
3. Confirm EventBridge has `lambda:InvokeFunction` permission.
4. Manually invoke the Lambda to separate scheduling problems from code problems.

## Deployment Commands

```powershell
cdk synth
cdk diff
cdk deploy
```

## Safe Removal

To remove the deployed project resources:

```powershell
cdk destroy
```

Only run this when the deployed monitoring system is no longer required.