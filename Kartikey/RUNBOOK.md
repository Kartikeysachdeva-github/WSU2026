# Website Health Monitor Runbook

## Purpose

This runbook explains how to operate, verify and troubleshoot the Website
Health Monitor in the Beta and Prod environments.

The project uses:

- AWS CDK for Infrastructure as Code
- AWS Lambda for website monitoring and alarm logging
- EventBridge for scheduled execution
- CloudWatch for metrics, dashboards and alarms
- SNS for alarm notifications
- DynamoDB for alarm history
- CodePipeline for CI/CD
- CodeDeploy for canary deployment and automatic rollback

---

## Account and Region

- Region: `us-east-1`
- Pipeline: `Kartikey-Website-Health-Pipeline`

Before working with AWS:

```powershell
aws sts get-caller-identity
```

Confirm that the correct project account is being used.

---

## Select Environment

Run commands from the `Kartikey` project folder.

Choose `beta` or `prod`:

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

    default {
        throw "Choose beta or prod."
    }
}

$monitorFunction = "kartikey-web-health$monitorSuffix"
$monitorLogger = "kartikey-alarm-logger$monitorSuffix"
$monitorTable = "Kartikey-Website-Alarm-Logs$monitorSuffix"
$monitorDashboard = "Kartikey-Website-Health-Dashboard$monitorSuffix"

$monitorAvailabilityAlarm = "GitHub-Availability-Alarm$monitorSuffix"
$monitorErrorAlarm = "Kartikey-Crawler-Errors$monitorSuffix"
$monitorDurationAlarm = "Kartikey-Crawler-Duration$monitorSuffix"
$monitorThrottleAlarm = "Kartikey-Crawler-Throttles$monitorSuffix"

$monitorDeploymentGroup = "Kartikey-Crawler-Deployment$monitorSuffix"
```

Rerun this block whenever switching between Beta and Prod.

---

# 1. Local Verification

Activate the Python environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the automated tests:

```powershell
python -m pytest tests/unit tests/functional -v
```

Expected:

```text
25 passed
```

Then run:

```powershell
cdk synth
```

Both tests and synthesis should pass before committing code.

Check repository state:

```powershell
git status
```

Do not commit temporary files such as:

```text
beta-response.json
prod-response.json
```

---

# 2. CI/CD Pipeline

The release process is:

```text
GitHub main
     |
     v
CodePipeline
     |
     v
Build / Synth
     |
     +--> Install dependencies
     +--> Compile Python
     +--> Run unit + functional tests
     +--> CDK synth
     |
     v
Beta
     |
     v
Manual Approval
     |
     v
Prod
```

Week 11 makes the automated tests pipeline-blocking.

If a test fails, the pipeline stops before deployment.

Check pipeline state:

```powershell
aws codepipeline get-pipeline-state `
    --name Kartikey-Website-Health-Pipeline `
    --region us-east-1 `
    --query "stageStates[].{Stage:stageName,Actions:actionStates[].{Action:actionName,Status:latestExecution.status}}" `
    --output json `
    --no-cli-pager
```

---

# 3. Check Monitoring Lambda

Run:

```powershell
aws lambda get-function-configuration `
    --function-name $monitorFunction `
    --region us-east-1 `
    --query "{State:State,LastUpdateStatus:LastUpdateStatus,Namespace:Environment.Variables.METRIC_NAMESPACE}" `
    --output json `
    --no-cli-pager
```

Expected:

- `State` = `Active`
- `LastUpdateStatus` = `Successful`
- Correct Beta or Prod metric namespace

Beta:

```text
Kartikey/WebsiteMonitoring/Beta
```

Prod:

```text
Kartikey/WebsiteMonitoring/Prod
```

---

# 4. Lambda Version and Live Alias

Week 11 uses immutable Lambda versions and a `live` alias.

Check published versions:

```powershell
aws lambda list-versions-by-function `
    --function-name $monitorFunction `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

Check the alias:

```powershell
aws lambda get-alias `
    --function-name $monitorFunction `
    --name live `
    --region us-east-1 `
    --output json `
    --no-cli-pager
```

The alias should point to a numbered Lambda version.

The normal execution path is:

```text
EventBridge
     |
     v
live Alias
     |
     v
Lambda Version
```

CodeDeploy controls the `live` alias during a release.

---

# 5. Invoke the Monitor

Invoke through the `live` alias:

```powershell
aws lambda invoke `
    --function-name $monitorFunction `
    --qualifier live `
    --region us-east-1 `
    --cli-binary-format raw-in-base64-out `
    --payload '{}' `
    "$env:TEMP\kartikey-$monitorDeployment-response.json" `
    --no-cli-pager

Get-Content "$env:TEMP\kartikey-$monitorDeployment-response.json"
```

Check:

- no `FunctionError`
- HTTP response from each website
- Availability value
- Latency value

A successful AWS invocation alone does not prove that all website checks
succeeded.

---

# 6. Check EventBridge Schedule

Run:

```powershell
aws events list-rules `
    --region us-east-1 `
    --query "Rules[?contains(Name, 'WebHealthSchedule')].[Name,State,ScheduleExpression]" `
    --output table `
    --no-cli-pager
```

Expected:

```text
ENABLED
rate(5 minutes)
```

For Beta and Prod, EventBridge should invoke the `live` Lambda alias.

---

# 7. Website Metrics

The crawler publishes two custom metrics:

```text
Availability
Latency
```

Check available metrics:

```powershell
aws cloudwatch list-metrics `
    --namespace $monitorNamespace `
    --region us-east-1 `
    --output json `
    --no-cli-pager
```

The project monitors:

- Western Sydney University
- AWS
- GitHub

Availability normally reports:

```text
1 = available
0 = unavailable
```

Latency records the response time.

---

# 8. Operational Metrics

Week 11 adds operational monitoring for the crawler Lambda.

The metrics are:

| Metric | Purpose |
|---|---|
| Invocations | Number of crawler executions |
| Errors | Failed executions |
| Duration | Execution time |
| Throttles | Throttled executions |

These are standard `AWS/Lambda` CloudWatch metrics.

This means the project monitors both:

```text
Website health
+
Crawler health
```

---

# 9. Dashboard

Open:

```text
AWS Console
→ CloudWatch
→ Dashboards
```

Beta:

```text
Kartikey-Website-Health-Dashboard-beta
```

Prod:

```text
Kartikey-Website-Health-Dashboard-prod
```

The dashboard contains:

- Website Availability
- Website Latency
- Crawler Invocations and Errors
- Crawler Execution Duration
- Crawler Throttles

---

# 10. CloudWatch Alarms

Each environment contains six website alarms:

```text
3 Availability alarms
3 Latency alarms
```

Week 11 adds three crawler alarms:

```text
Crawler Errors
Crawler Duration
Crawler Throttles
```

Total:

```text
6 website alarms
+
3 crawler alarms
=
9 alarms per environment
```

Check the operational alarms:

```powershell
aws cloudwatch describe-alarms `
    --alarm-names `
        $monitorErrorAlarm `
        $monitorDurationAlarm `
        $monitorThrottleAlarm `
    --region us-east-1 `
    --query "MetricAlarms[].{Name:AlarmName,Metric:MetricName,State:StateValue,Threshold:Threshold}" `
    --output table `
    --no-cli-pager
```

Operational thresholds:

| Alarm | Threshold |
|---|---|
| Errors | >= 1 |
| Duration | > 30,000 ms |
| Throttles | >= 1 |

Missing operational data is treated as not breaching.

---

# 11. SNS and DynamoDB Alarm Logging

Alarm flow:

```text
CloudWatch Alarm
       |
       v
      SNS
       |
       v
Alarm Logger Lambda
       |
       v
    DynamoDB
```

Check the logger:

```powershell
aws lambda get-function-configuration `
    --function-name $monitorLogger `
    --region us-east-1 `
    --query "{State:State,Table:Environment.Variables.ALARM_TABLE_NAME}" `
    --output json `
    --no-cli-pager
```

Check DynamoDB:

```powershell
aws dynamodb scan `
    --table-name $monitorTable `
    --region us-east-1 `
    --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" `
    --output table `
    --no-cli-pager
```

Alarm records contain information such as:

```text
alarm_name
new_state
reason
timestamp
```

---

# 12. CodeDeploy Canary Deployment

Week 11 adds AWS CodeDeploy.

The deployment strategy is:

```text
CANARY_10_PERCENT_5_MINUTES
```

Release flow:

```text
New Lambda Version
        |
        v
    CodeDeploy
        |
        v
     live Alias
      /     \
     /       \
Previous     New
Version     Version
  90%        10%
     \       /
      \     /
      5 minutes
          |
       Healthy?
       /     \
     Yes      No
      |        |
      v        v
  Complete   Rollback
```

This reduces deployment risk because the new version receives only a portion
of traffic before the release completes.

---

# 13. Automatic Rollback

CodeDeploy monitors:

```text
Kartikey-Crawler-Errors-beta
```

or:

```text
Kartikey-Crawler-Errors-prod
```

Automatic rollback is configured when:

- the deployment enters the configured alarm state;
- the deployment fails; or
- the deployment is stopped.

Check the rollback alarm:

```powershell
aws cloudwatch describe-alarms `
    --alarm-names $monitorErrorAlarm `
    --region us-east-1 `
    --query "MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason}" `
    --output table `
    --no-cli-pager
```

A healthy deployment should normally show:

```text
State = OK
```

If rollback occurs, check which version the alias points to:

```powershell
aws lambda get-alias `
    --function-name $monitorFunction `
    --name live `
    --region us-east-1 `
    --output json `
    --no-cli-pager
```

---

# 14. Check CodeDeploy

List CodeDeploy applications:

```powershell
aws deploy list-applications `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

CDK may generate the application name.

After identifying it:

```powershell
$codeDeployApplication = "<APPLICATION-NAME>"
```

Check deployment groups:

```powershell
aws deploy list-deployment-groups `
    --application-name $codeDeployApplication `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

Expected deployment group:

Beta:

```text
Kartikey-Crawler-Deployment-beta
```

Prod:

```text
Kartikey-Crawler-Deployment-prod
```

Check recent deployments:

```powershell
aws deploy list-deployments `
    --application-name $codeDeployApplication `
    --deployment-group-name $monitorDeploymentGroup `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

---

# 15. Production Approval

The pipeline intentionally pauses before Prod.

Before approving production, verify Beta:

- [x] Automated tests passed
- [x] Build/Synth passed
- [x] Beta deployment succeeded
- [x] Beta `live` alias exists
- [x] Beta alias points to a numbered Lambda version
- [x] Beta crawler error alarm is `OK`
- [x] Beta reached the production approval gate

Then approve:

```text
CodePipeline
→ Kartikey-Website-Health-Pipeline
→ ApproveProd
→ Review
→ Approve
```

After approval, verify Prod using the same checks.

---

# 16. Live Integration Tests

For Beta:

```powershell
$env:RUN_LIVE_TESTS = "1"
$env:TEST_STAGE = "Beta"

python -m pytest tests/integration -v
```

For Prod:

```powershell
$env:RUN_LIVE_TESTS = "1"
$env:TEST_STAGE = "Prod"

python -m pytest tests/integration -v
```

Remove the variables afterwards:

```powershell
Remove-Item Env:RUN_LIVE_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:TEST_STAGE -ErrorAction SilentlyContinue
```

These live tests are separate from the unit and functional tests that run
inside CodePipeline.

---

# 17. Deploying Changes

Before pushing:

```powershell
python -m pytest tests/unit tests/functional -v
cdk synth
git status
```

Then:

```powershell
git add <intended-files>
git commit -m "Describe the change"
git push origin main
```

Do not commit:

- AWS credentials
- GitHub tokens
- secret values
- temporary response JSON files

---

# 18. Troubleshooting

## Pipeline Test Failure

Run locally:

```powershell
python -m pytest tests/unit tests/functional -v
```

Fix the first failing test before pushing again.

## CDK Synth Failure

Run:

```powershell
cdk synth
```

Check the first CDK/Python error.

## Website Availability Is 0

Check:

- URL in `websites.json`
- crawler Lambda logs
- HTTP response
- request timeout
- whether the website is actually unavailable

## Metrics Missing

Check:

- EventBridge is enabled
- Lambda executed
- correct namespace is selected
- `METRIC_NAMESPACE` is correct
- Lambda has `cloudwatch:PutMetricData`
- CloudWatch time range is correct

## Crawler Error Alarm

Check:

- crawler Lambda logs
- CodeDeploy deployment status
- `live` alias
- current Lambda version

An error during deployment may cause automatic rollback.

## High Duration

Check:

- Lambda Duration metric
- website response times
- crawler logs
- HTTP timeouts

The alarm threshold is 30 seconds.

## Throttling

Check:

- Lambda concurrency
- unexpected invocations
- EventBridge schedule
- Lambda account limits

## DynamoDB Has No Alarm Record

Check:

- CloudWatch alarm action
- SNS topic
- logger Lambda subscription
- logger Lambda logs
- table environment variable
- DynamoDB permissions

---

# 19. Week 11 Implementation Status

The Week 11 implementation now includes:

- [x] Crawler invocation monitoring
- [x] Crawler error monitoring
- [x] Crawler duration monitoring
- [x] Crawler throttle monitoring
- [x] Operational CloudWatch alarms
- [x] Operational dashboard widgets
- [x] Automated tests added to CodePipeline
- [x] 25 local unit/functional tests passing
- [x] CDK synthesis passing
- [x] Lambda immutable version
- [x] Lambda `live` alias
- [x] EventBridge uses the alias
- [x] CodeDeploy deployment group
- [x] 10% / five-minute canary
- [x] Crawler error alarm connected to CodeDeploy
- [x] Automatic rollback configured
- [x] Final Week 11 Beta deployment verified
- [ ] Final Week 11 Prod deployment verified

### Current Beta Verification

Beta has successfully reached the production approval stage.

The `live` alias was verified:

```text
Name: live
FunctionVersion: 1
Description: Live version of the website health crawler.
```

The Beta crawler error alarm was also verified:

```text
Kartikey-Crawler-Errors-beta
State: OK
Latest Errors datapoint: 0
Threshold: 1
```

This confirms that Beta is healthy enough to proceed through the manual
production approval gate.

Prod should only be marked complete after its deployment finishes and the
production alias/alarm are checked.

---

# 20. Previous Verified Functionality

Earlier project testing already verified:

- EventBridge executes the crawler every five minutes.
- The crawler checks Western Sydney University, AWS and GitHub.
- Website Availability and Latency are published to CloudWatch.
- CloudWatch alarms trigger SNS.
- SNS invokes the alarm logger Lambda.
- Alarm information is stored in DynamoDB.
- Beta and Prod use separate resources and namespaces.
- Manual approval prevents automatic promotion into Prod.
- Live Beta and Prod integration tests passed before the Week 11 changes.

Week 11 builds on this foundation by adding automated pipeline testing,
operational monitoring, canary deployment and rollback.

---

# 21. Quick Presentation Explanation

If asked **what the project does**:

> The project is an automated website health monitoring system built using
> Python and AWS CDK. EventBridge runs a Lambda crawler every five minutes. It
> checks Western Sydney University, AWS and GitHub and publishes Availability
> and Latency metrics to CloudWatch. CloudWatch also monitors the operational
> health of the crawler. Alarms are sent through SNS to another Lambda, which
> stores alarm history in DynamoDB.

If asked **how CI/CD works**:

> Changes are pushed to GitHub and picked up by CodePipeline. The pipeline
> installs the dependencies, runs the automated unit and functional tests and
> performs CDK synthesis. A failing test blocks the release. A successful build
> deploys to Beta first, and production requires manual approval.

If asked **what Week 11 added**:

> Week 11 added operational Lambda metrics, pipeline-blocking automated tests,
> Lambda versioning, a live alias, CodeDeploy canary deployment and automatic
> rollback.

If asked **why use a canary**:

> A canary reduces deployment risk because only 10% of traffic is initially
> directed to the new Lambda version. The release completes after the canary
> period if it remains healthy.

If asked **how rollback works**:

> CodeDeploy monitors the crawler error alarm. If the deployment becomes
> unhealthy, fails or is stopped, it is configured to roll the live alias back
> to the previous Lambda version.

If asked **why use Beta and Prod**:

> Beta provides a safe environment to validate a release before production.
> Separate resources and CloudWatch namespaces also prevent Beta monitoring
> data from mixing with production.

---

# 22. DevOps Flow

The complete workflow is:

```text
Develop
   |
   v
GitHub
   |
   v
Automated Tests
   |
   v
CDK Synth
   |
   v
Beta
   |
   v
Monitor
   |
   v
Manual Approval
   |
   v
Prod
   |
   v
Canary
   |
   v
CloudWatch
   |
   v
Healthy?
 /      \
Yes      No
 |        |
 v        v
Run    Rollback
          |
          v
      Investigate
          |
          v
         Fix
```

This demonstrates source control, Infrastructure as Code, automated testing,
CI/CD, continuous monitoring, controlled releases and automated recovery.