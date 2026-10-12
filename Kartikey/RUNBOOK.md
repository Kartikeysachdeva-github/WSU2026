# Website Health Monitor Runbook

## Purpose

This runbook explains how to operate and troubleshoot the original
monitor and the separate Beta and Prod deployments.

## Account and Region

- Account: `715054189400`
- Region: `us-east-1`
- Pipeline: `Kartikey-Website-Health-Pipeline`

Before running commands:

```powershell
aws sts get-caller-identity
```

Confirm the account matches the project account.

## Select a Deployment

Run commands from the repository's `Kartikey` project folder.

Set the deployment to `beta`, `prod` or `original`:

```powershell
$monitorDeployment = "beta"

switch ($monitorDeployment) {
    "beta" {
        $monitorSuffix = "-beta"
        $monitorNamespace = "Kartikey/WebsiteMonitoring/Beta"
    }
    "prod" {
        $monitorSuffix = "-prod"
        $monitorNamespace = "Kartikey/WebsiteMonitoring/Prod"
    }
    "original" {
        $monitorSuffix = ""
        $monitorNamespace = "Kartikey/WebsiteMonitoring"
    }
    default {
        throw "Choose beta, prod or original."
    }
}

$monitorFunction = "kartikey-web-health$monitorSuffix"
$monitorLogger = "kartikey-alarm-logger$monitorSuffix"
$monitorTable = "Kartikey-Website-Alarm-Logs$monitorSuffix"
$monitorDashboard = "Kartikey-Website-Health-Dashboard$monitorSuffix"
$monitorTopic = "arn:aws:sns:us-east-1:715054189400:kartikey-website-alarm-notifications$monitorSuffix"
$monitorAlarm = "GitHub-Availability-Alarm$monitorSuffix"
```

Rerun this block when switching deployments.

## Check the Monitoring Lambda

```powershell
aws lambda get-function-configuration --function-name $monitorFunction --region us-east-1 --query "{State:State,LastUpdateStatus:LastUpdateStatus,Namespace:Environment.Variables.METRIC_NAMESPACE}" --output json --no-cli-pager
```

Expect State `Active`, LastUpdateStatus `Successful` and the selected
namespace. The older original deployment may use the namespace fallback
in code until its updated stack is deployed.

## Invoke the Monitor

```powershell
aws lambda invoke --function-name $monitorFunction --region us-east-1 --cli-binary-format raw-in-base64-out --payload '{}' "$env:TEMP\kartikey-$monitorDeployment-response.json" --no-cli-pager

Get-Content "$env:TEMP\kartikey-$monitorDeployment-response.json"
```

Check both the invocation metadata and response body.
An invocation StatusCode of 200 alone does not prove successful
application execution; inspect FunctionError and the website results.

For the verified healthy checks, each website returned HTTP 200,
availability 1 and a latency measurement.

## Check the Schedule

```powershell
aws events list-rules --region us-east-1 --query "Rules[?contains(Name, 'WebHealthSchedule')].[Name,State,ScheduleExpression]" --output table --no-cli-pager
```

The application rules should be ENABLED with `rate(5 minutes)`.

Use the EventBridge console to inspect the selected rule's target.
Confirm it points to the monitoring Lambda for the selected deployment.

## Check Metrics

Discover metrics:

```powershell
aws cloudwatch list-metrics --namespace $monitorNamespace --region us-east-1 --output json --no-cli-pager
```

Expect Availability and Latency metrics with a Website dimension.

New metrics may take up to 15 minutes to appear in list-metrics.
Query datapoints directly when discovery has not caught up:

```powershell
$monitorEnd = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$monitorStart = (Get-Date).ToUniversalTime().AddMinutes(-30).ToString("yyyy-MM-ddTHH:mm:ssZ")

aws cloudwatch get-metric-statistics --namespace $monitorNamespace --metric-name Availability --dimensions Name=Website,Value=GitHub --start-time $monitorStart --end-time $monitorEnd --period 300 --statistics Minimum --region us-east-1 --output json --no-cli-pager

aws cloudwatch get-metric-statistics --namespace $monitorNamespace --metric-name Latency --dimensions Name=Website,Value=GitHub --start-time $monitorStart --end-time $monitorEnd --period 300 --statistics Average --region us-east-1 --output json --no-cli-pager
```

For other websites, replace GitHub with AWS or WesternSydneyUniversity.
Refresh the start and end variables when repeating the checks later.

## Check the Dashboard

In CloudWatch, select Dashboards and open the name stored in
`$monitorDashboard`.

Verify recent Availability and Latency data for all three websites.
Check the region and graph time range if data appears missing.

## Check Alarms

```powershell
aws cloudwatch describe-alarms --alarm-names $monitorAlarm --region us-east-1 --query "MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason,ActionsEnabled:ActionsEnabled,Actions:AlarmActions,Metrics:Metrics}" --output json --no-cli-pager
```

| State | Meaning |
|---|---|
| OK | Evaluated data is within the configured threshold |
| ALARM | The alarm condition is met, including missing data treated as breaching |
| INSUFFICIENT_DATA | The alarm cannot currently determine its state |

Read StateReason before concluding that a website is unavailable.
The current configuration treats missing data as breaching, which
caused startup alarms before metrics arrived.

## Check SNS and the Logger

```powershell
aws sns list-subscriptions-by-topic --topic-arn $monitorTopic --region us-east-1 --output json --no-cli-pager

aws lambda get-function-configuration --function-name $monitorLogger --region us-east-1 --query "{State:State,Table:Environment.Variables.ALARM_TABLE_NAME}" --output json --no-cli-pager
```

Confirm the SNS topic has a Lambda subscription for the selected logger.
Confirm ALARM_TABLE_NAME matches the selected DynamoDB table.

Email subscriptions must be configured and confirmed separately for
each topic if email notifications are required.

## Check DynamoDB Records

```powershell
aws dynamodb scan --table-name $monitorTable --region us-east-1 --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" --output table --no-cli-pager
```

Records should contain the alarm name, new state, reason and timestamp.
A scan is suitable for this small practical dataset; it is not a
recommended access pattern for a large production table.

## Controlled Alarm Delivery Test

Use Beta for routine testing. Select Beta using the deployment block.

First confirm the chosen alarm is OK. Then temporarily set it to ALARM:

```powershell
aws cloudwatch set-alarm-state --alarm-name $monitorAlarm --state-value ALARM --state-reason "Controlled Beta alarm delivery test" --region us-east-1
```

Check DynamoDB for a new record with that reason:

```powershell
aws dynamodb scan --table-name $monitorTable --region us-east-1 --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" --output table --no-cli-pager
```

Delivery is asynchronous; repeat the read if the record has not arrived.

CloudWatch recalculates the alarm state on subsequent evaluation.
Confirm that it returns to its expected calculated state.

This test verifies notification delivery and logging. It does not
simulate a real website outage or test threshold evaluation.

## Check the Pipeline

```powershell
aws codepipeline get-pipeline-state --name Kartikey-Website-Health-Pipeline --region us-east-1 --query "stageStates[].{Stage:stageName,Actions:actionStates[].{Action:actionName,Status:latestExecution.status,Error:latestExecution.errorDetails.message}}" --output json --no-cli-pager
```

Expected order:

1. Source
2. Build
3. UpdatePipeline
4. Assets
5. Beta
6. Prod, beginning with ApproveProd

Before approving Prod, inspect Beta's Lambda results, metric datapoints,
alarm reasons and DynamoDB records.

## Deploy Changes

Activate the environment and check the application:

```powershell
.\.venv\Scripts\Activate.ps1
python -m py_compile .\app.py .\kartikey\pipeline_stack.py .\kartikey\kartikey_stack.py .\kartikey\resources\webHealth.py .\kartikey\resources\alarmLogger.py
cdk synth KartikeyPipelineStack --quiet
git status --short
```

Commit only the intended files and push to main.
The pipeline polls GitHub for new revisions and requires a fresh
Prod approval for each execution that reaches the approval step.

For initial creation or a deliberate local pipeline update:

```powershell
cdk diff KartikeyPipelineStack
cdk deploy KartikeyPipelineStack
```

For the original monitor:

```powershell
cdk diff KartikeyStack
cdk deploy KartikeyStack
```

## Troubleshooting

### Source fails

- Inspect the Source action's error.
- Check repository access and the token's validity.
- Confirm `github-token` exists in the correct account and region.
- Never paste or commit the secret value.

### Synth fails

- Open the Synth CodeBuild logs.
- Find the first failing command and its error.
- Confirm the application is under `Kartikey/`.
- Confirm dependencies install and local synthesis succeeds.
- Confirm `Kartikey/cdk.out` is produced.

### Application deployment fails

- Open the failed action's CloudFormation events.
- Identify the resource and its failure reason.
- Check permissions, resource naming conflicts and bootstrap resources.
- Correct the CDK code and push the change.

### Website availability is 0

- Check the URL in websites.json.
- Review the monitoring Lambda logs.
- Check timeouts, HTTP errors and blocked automated requests.
- Compare multiple checks before concluding there is an outage.

### Metrics are missing

- Confirm the Lambda executed successfully.
- Check its namespace and Website dimension.
- Review logs and cloudwatch:PutMetricData permissions.
- Query datapoints directly and allow for discovery delay.

### Schedule does not invoke Lambda

- Confirm the rule is enabled.
- Inspect its target and Lambda invocation permission.
- Invoke Lambda manually to distinguish code issues from schedule issues.

### Alarm is active despite a healthy response

- Read StateReason and inspect the evaluated metric period.
- Check for missing data and allow evaluation to catch up.
- Compare the actual datapoints against the threshold.

### DynamoDB has no new record

- Confirm an ALARM state transition occurred.
- Check the alarm's SNS action and ActionsEnabled.
- Check the topic's logger subscription.
- Review logger logs, table configuration and write permissions.

### Record contains Unknown

A manually published message may not match CloudWatch's alarm JSON.
Use the controlled CloudWatch alarm test to check the expected format.

## Verified Results — 12 October 2026

- Every action in the first pipeline execution succeeded.
- Beta and Prod monitoring Lambdas were Active.
- Both returned HTTP 200 and availability 1 for all three websites.
- A GitHub Availability datapoint of 1 was verified in Beta.
- Beta's GitHub availability alarm recovered to OK.
- Startup alarm records were found in both environment tables.
- Manual approval paused the pipeline before Prod deployment.

## Resource Removal

The original stack can be removed with:

```powershell
cdk destroy KartikeyStack
```

The pipeline stack can be removed with:

```powershell
cdk destroy KartikeyPipelineStack
```

Run removal commands only when those resources are no longer needed.

Removing the pipeline does not automatically remove Beta and Prod
application stacks. Inspect their actual stack names in CloudFormation
before planning separate cleanup.

DynamoDB tables and Lambda log groups may remain because of retention
policies. Check retained resources after stack removal.

## References

- https://docs.aws.amazon.com/cdk/api/v2/python/
- https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipeline.html
- https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipelineSource.html
- https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/ManualApprovalStep.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_ListMetrics.html