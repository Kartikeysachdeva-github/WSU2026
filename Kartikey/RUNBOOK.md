# Website Health Monitor - Operational Runbook

## Student

**Name:** Kartikey Sachdeva
**Student ID:** 22122045
**Unit:** COMP2029 DevOps
**Region:** `us-east-1`

---

# 1. Purpose

This runbook explains how to operate, verify and troubleshoot the Website Health Monitor and Applied Project in the Beta and Prod environments.

The deployed system uses:

- AWS CDK for Infrastructure as Code
- AWS CodePipeline for CI/CD
- AWS Lambda for website monitoring, CRUD operations and alarm logging
- Amazon API Gateway for the public target-management REST API
- Amazon DynamoDB for crawler targets and alarm history
- Amazon EventBridge for scheduled crawler execution
- Amazon CloudWatch for metrics, dashboards, logs and alarms
- Amazon SNS for alarm notifications
- AWS CodeDeploy for canary deployment and automatic rollback

The crawler target list is stored in DynamoDB and can be managed using the REST API.

---

# 2. Architecture

```text
                         User
                          |
                          v
                    API Gateway
                          |
                          v
                   CRUD API Lambda
                          |
                          v
                  Targets DynamoDB
                          ^
                          |
                          |
EventBridge ------> Crawler Lambda
 every 5 min        live alias
                     |
                     +------> Websites
                     |
                     +------> CloudWatch
                                  |
                           +------+------+
                           |             |
                       Dashboard       Alarms
                                         |
                                         v
                                        SNS
                                         |
                                         v
                                Alarm Logger Lambda
                                         |
                                         v
                                Alarm Log DynamoDB
```

The main runtime change introduced by the Applied Project is:

```text
Before:
websites.json -> Crawler

Now:
API Gateway -> CRUD Lambda -> DynamoDB <- Crawler
```

`websites.json` remains as baseline infrastructure configuration, while DynamoDB is the crawler's runtime target source.

---

# 3. Verify AWS Identity

Before performing AWS operations:

```powershell
aws sts get-caller-identity
```

Confirm that the expected AWS account is being used.

Region:

```text
us-east-1
```

Pipeline:

```text
Kartikey-Website-Health-Pipeline
```

---

# 4. Select Beta or Prod

Run commands from the `Kartikey` project directory.

Choose the environment:

```powershell
$monitorDeployment = "beta"
```

or:

```powershell
$monitorDeployment = "prod"
```

Then run:

```powershell
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
$monitorApiFunction = "kartikey-target-api$monitorSuffix"
$monitorSeeder = "kartikey-target-seeder$monitorSuffix"

$monitorTargetTable = "Kartikey-Website-Targets$monitorSuffix"
$monitorAlarmTable = "Kartikey-Website-Alarm-Logs$monitorSuffix"

$monitorLogger = "kartikey-alarm-logger$monitorSuffix"

$monitorDashboard = "Kartikey-Website-Health-Dashboard$monitorSuffix"

$monitorErrorAlarm = "Kartikey-Crawler-Errors$monitorSuffix"
$monitorDurationAlarm = "Kartikey-Crawler-Duration$monitorSuffix"
$monitorThrottleAlarm = "Kartikey-Crawler-Throttles$monitorSuffix"

$monitorDeploymentGroup = "Kartikey-Crawler-Deployment$monitorSuffix"
```

Rerun this block when switching between environments.

---

# 5. Local Verification

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the unit and functional tests:

```powershell
python -m pytest tests/unit tests/functional -v
```

Current expected result:

```text
29 passed
```

Check Python:

```powershell
python -m compileall -q app.py kartikey
```

Synthesize the CDK application:

```powershell
cdk synth
```

All checks should pass before pushing a release.

---

# 6. Live CRUD Integration Test

The Applied Project includes a live integration test:

```text
tests/integration/test_target_api_integration.py
```

It tests:

```text
API Gateway
     |
     v
CRUD Lambda
     |
     v
Real DynamoDB
```

The lifecycle is:

```text
CREATE
  ↓
READ
  ↓
UPDATE
  ↓
READ UPDATED VALUE
  ↓
DELETE
  ↓
GET -> 404
```

Configure the environment:

```powershell
$env:RUN_LIVE_TESTS = "1"
$env:TARGET_API_URL = "YOUR-DEPLOYED-API-URL"
```

Run:

```powershell
python -m pytest tests/integration/test_target_api_integration.py -v
```

Expected:

```text
1 passed
```

Remove the variables afterward if required:

```powershell
Remove-Item Env:RUN_LIVE_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:TARGET_API_URL -ErrorAction SilentlyContinue
```

The live integration test is separate from the pipeline's unit and functional test gate because it requires an already deployed API.

---

# 7. CI/CD Pipeline

Release flow:

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
     +--> Run 29 unit + functional tests
     +--> CDK synth
     |
     v
Assets / Self-Mutate
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

Check pipeline state:

```powershell
aws codepipeline get-pipeline-state `
    --name Kartikey-Website-Health-Pipeline `
    --region us-east-1 `
    --query "stageStates[].{Stage:stageName,Actions:actionStates[].{Action:actionName,Status:latestExecution.status}}" `
    --output json `
    --no-cli-pager
```

A failing unit or functional test should stop the release before application deployment.

---

# 8. Verify Target DynamoDB Table

The crawler's runtime targets are stored in:

Beta:

```text
Kartikey-Website-Targets-beta
```

Prod:

```text
Kartikey-Website-Targets-prod
```

Scan the selected table:

```powershell
aws dynamodb scan `
    --table-name $monitorTargetTable `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

A newly deployed environment should initially contain:

```text
AWS
WesternSydneyUniversity
GitHub
```

The partition key is:

```text
target_id
```

---

# 9. Initial Target Seeder

The Lambda:

```text
kartikey-target-seeder-beta
```

or:

```text
kartikey-target-seeder-prod
```

initializes the target table during deployment.

The seeder only creates missing records and does not intentionally overwrite an existing target.

Check its configuration:

```powershell
aws lambda get-function-configuration `
    --function-name $monitorSeeder `
    --region us-east-1 `
    --query "{State:State,Table:Environment.Variables.TARGET_TABLE_NAME}" `
    --output json `
    --no-cli-pager
```

Expected:

- Lambda state is `Active`
- `TARGET_TABLE_NAME` points to the correct Beta or Prod target table

---

# 10. Target CRUD API

The public REST API provides:

| Method | Endpoint | Operation |
|---|---|---|
| `POST` | `/targets` | Create |
| `GET` | `/targets` | List |
| `GET` | `/targets/{id}` | Read |
| `PUT` | `/targets/{id}` | Update |
| `DELETE` | `/targets/{id}` | Delete |

Set the appropriate API URL:

```powershell
$ApiUrl = "YOUR-API-URL".TrimEnd("/")
```

---

## List Targets

```powershell
Invoke-RestMethod `
    -Uri "$ApiUrl/targets" `
    -Method GET | ConvertTo-Json -Depth 10
```

Expected response includes:

```text
targets
count
operation_time_ms
```

---

## Create Temporary Target

```powershell
$Body = @{
    target_id = "runbook-test"
    name      = "Runbook Test"
    url       = "https://example.com"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "$ApiUrl/targets" `
    -Method POST `
    -ContentType "application/json" `
    -Body $Body | ConvertTo-Json -Depth 10
```

Expected status:

```text
201 Created
```

---

## Read Target

```powershell
Invoke-RestMethod `
    -Uri "$ApiUrl/targets/runbook-test" `
    -Method GET | ConvertTo-Json -Depth 10
```

---

## Update Target

```powershell
$UpdateBody = @{
    name = "Updated Runbook Test"
    url  = "https://example.org"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "$ApiUrl/targets/runbook-test" `
    -Method PUT `
    -ContentType "application/json" `
    -Body $UpdateBody | ConvertTo-Json -Depth 10
```

---

## Delete Target

```powershell
Invoke-RestMethod `
    -Uri "$ApiUrl/targets/runbook-test" `
    -Method DELETE | ConvertTo-Json -Depth 10
```

Verify deletion:

```powershell
Invoke-RestMethod `
    -Uri "$ApiUrl/targets/runbook-test" `
    -Method GET
```

Expected:

```text
404 Target not found
```

---

# 11. DynamoDB Read/Write Timing

CRUD responses include:

```json
{
  "operation_time_ms": 58.922
}
```

The API also publishes CloudWatch timing metrics:

```text
DynamoDBReadTime
DynamoDBWriteTime
```

These allow database performance to be observed in addition to CRUD correctness.

---

# 12. Check CRUD Lambda

Run:

```powershell
aws lambda get-function-configuration `
    --function-name $monitorApiFunction `
    --region us-east-1 `
    --query "{State:State,Table:Environment.Variables.TARGET_TABLE_NAME,Namespace:Environment.Variables.METRIC_NAMESPACE}" `
    --output json `
    --no-cli-pager
```

Check:

- `State = Active`
- target table matches the selected environment
- metric namespace matches Beta or Prod

---

# 13. Check Crawler Lambda

Run:

```powershell
aws lambda get-function-configuration `
    --function-name $monitorFunction `
    --region us-east-1 `
    --query "{State:State,LastUpdateStatus:LastUpdateStatus,Namespace:Environment.Variables.METRIC_NAMESPACE,TargetTable:Environment.Variables.TARGET_TABLE_NAME}" `
    --output json `
    --no-cli-pager
```

Expected:

```text
State = Active
LastUpdateStatus = Successful
```

The target table must match:

```text
Kartikey-Website-Targets-beta
```

or:

```text
Kartikey-Website-Targets-prod
```

This proves the crawler is configured to use DynamoDB.

---

# 14. Lambda Version and Live Alias

Check published crawler versions:

```powershell
aws lambda list-versions-by-function `
    --function-name $monitorFunction `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

Check the `live` alias:

```powershell
aws lambda get-alias `
    --function-name $monitorFunction `
    --name live `
    --region us-east-1 `
    --output json `
    --no-cli-pager
```

The alias should point to a numbered Lambda version.

Runtime path:

```text
EventBridge
     |
     v
live Alias
     |
     v
Published Lambda Version
```

---

# 15. Invoke the Crawler Manually

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
```

View the result:

```powershell
Get-Content "$env:TEMP\kartikey-$monitorDeployment-response.json"
```

Check that:

- there is no `FunctionError`;
- targets were loaded;
- websites were requested;
- availability values were generated;
- latency values were generated.

---

# 16. Verify Crawler Logs

Open:

```text
AWS Console
→ Lambda
→ kartikey-web-health-beta/prod
→ Monitor
→ View CloudWatch logs
→ Latest log stream
```

A healthy execution should show the configured DynamoDB targets being processed and finish with:

```text
END
REPORT
```

The Applied Project was verified with:

```text
AWS
WesternSydneyUniversity
GitHub
```

being processed successfully in both Beta and Prod.

---

# 17. EventBridge Schedule

Check the schedule:

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

EventBridge should invoke the crawler's `live` alias.

---

# 18. Website Metrics

The crawler publishes:

```text
Availability
Latency
```

List the selected environment's metrics:

```powershell
aws cloudwatch list-metrics `
    --namespace $monitorNamespace `
    --region us-east-1 `
    --output json `
    --no-cli-pager
```

Availability:

```text
1 = available
0 = unavailable
```

Latency is measured in milliseconds.

Because targets are now loaded dynamically, a target created through the API can be checked by a later crawler execution without redeploying the crawler.

---

# 19. Crawler Operational Metrics

The crawler is also monitored using standard Lambda metrics:

| Metric | Purpose |
|---|---|
| Invocations | Number of executions |
| Errors | Failed executions |
| Duration | Execution duration |
| Throttles | Throttled executions |

This provides monitoring for both:

```text
Website health
+
Crawler health
```

---

# 20. CloudWatch Dashboard

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

The dashboard includes:

- Website Availability
- Website Latency
- Crawler Invocations and Errors
- Crawler Execution Duration
- Crawler Throttles

---

# 21. CloudWatch Alarms

Each environment contains the original website alarms plus crawler operational alarms.

Crawler alarms:

```text
Kartikey-Crawler-Errors-beta/prod
Kartikey-Crawler-Duration-beta/prod
Kartikey-Crawler-Throttles-beta/prod
```

Check:

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

Thresholds:

| Alarm | Threshold |
|---|---|
| Errors | >= 1 |
| Duration | > 30,000 ms |
| Throttles | >= 1 |

Operational missing data is treated as not breaching.

---

# 22. SNS and Alarm History

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
Alarm Log DynamoDB
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

Check alarm history:

```powershell
aws dynamodb scan `
    --table-name $monitorAlarmTable `
    --region us-east-1 `
    --query "Items[].{Alarm:alarm_name.S,State:new_state.S,Reason:reason.S,Time:timestamp.S}" `
    --output table `
    --no-cli-pager
```

---

# 23. CodeDeploy Canary

Deployment strategy:

```text
CANARY_10_PERCENT_5_MINUTES
```

Flow:

```text
Previous Version
       |
       +------------------+
       |                  |
       v                  v
      90%                10%
                         New Version
                             |
                       5 minute canary
                             |
                      +------+------+
                      |             |
                   Healthy       Failure
                      |             |
                      v             v
                  100% New       Rollback
```

The canary reduces the impact of a faulty release.

---

# 24. Automatic Rollback

CodeDeploy uses the crawler error alarm:

Beta:

```text
Kartikey-Crawler-Errors-beta
```

Prod:

```text
Kartikey-Crawler-Errors-prod
```

Rollback is configured when:

- the monitored deployment enters ALARM;
- deployment fails;
- deployment is stopped.

Check the alarm:

```powershell
aws cloudwatch describe-alarms `
    --alarm-names $monitorErrorAlarm `
    --region us-east-1 `
    --query "MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason}" `
    --output table `
    --no-cli-pager
```

A healthy deployment normally reports:

```text
State = OK
```

---

# 25. Production Approval Checklist

Before approving Prod, verify Beta:

- [x] Unit and functional tests passed
- [x] CDK synth passed
- [x] Beta deployment succeeded
- [x] Target DynamoDB table contains initial records
- [x] Public CRUD API responds
- [x] CREATE works
- [x] READ works
- [x] UPDATE works
- [x] DELETE works
- [x] Deleted target returns 404
- [x] DynamoDB operation timing is returned
- [x] Live CRUD integration test passed
- [x] Crawler reads DynamoDB targets
- [x] Crawler logs show successful executions
- [x] `live` alias exists
- [x] Crawler error alarm is healthy

Production can then be approved through:

```text
CodePipeline
→ Kartikey-Website-Health-Pipeline
→ ApproveProd
→ Review
→ Approve
```

The Applied Project production deployment has been successfully completed and verified.

---

# 26. Applied Project Verified Status

The final implementation includes:

- [x] Public API Gateway
- [x] CRUD Lambda
- [x] Target DynamoDB table
- [x] Initial target seeding
- [x] `POST /targets`
- [x] `GET /targets`
- [x] `GET /targets/{id}`
- [x] `PUT /targets/{id}`
- [x] `DELETE /targets/{id}`
- [x] DynamoDB read timing
- [x] DynamoDB write timing
- [x] Crawler reads DynamoDB targets
- [x] DynamoDB pagination support in crawler
- [x] 29 unit/functional tests passing
- [x] Unit/functional tests pipeline-blocking
- [x] Live CRUD integration test passing
- [x] CDK synthesis passing
- [x] Beta deployed and verified
- [x] Manual production approval
- [x] Prod deployed and verified
- [x] Prod API returns three seeded targets
- [x] Prod crawler processes DynamoDB targets
- [x] CloudWatch monitoring
- [x] SNS alarm flow
- [x] Alarm history DynamoDB
- [x] Lambda versions and `live` alias
- [x] CodeDeploy canary
- [x] Automatic rollback

---

# 27. Troubleshooting

## API Returns 500

Check:

- Target API Lambda logs
- `TARGET_TABLE_NAME`
- DynamoDB permissions
- CloudWatch metric permission
- request body

Lambda:

```text
kartikey-target-api-beta/prod
```

---

## API Returns 400

Check:

- JSON body is valid
- `target_id` is supplied when creating
- `name` is supplied
- `url` is supplied
- URL begins with `http://` or `https://`

---

## API Returns 404

For:

```text
GET /targets/{id}
PUT /targets/{id}
DELETE /targets/{id}
```

confirm that the requested `target_id` exists.

---

## API Returns 409

A target with that `target_id` already exists.

Use another ID or update the existing record with PUT.

---

## Target Table Is Empty

Check:

- target seeder Lambda;
- seeder CloudWatch logs;
- target table environment variable;
- DynamoDB write permission;
- CloudFormation deployment status.

---

## Crawler Processes No Targets

Check:

```text
TARGET_TABLE_NAME
```

on the crawler Lambda.

Then scan:

```powershell
aws dynamodb scan `
    --table-name $monitorTargetTable `
    --region us-east-1 `
    --output table `
    --no-cli-pager
```

Also inspect the crawler CloudWatch logs.

---

## Website Availability Is 0

Check:

- URL stored in DynamoDB;
- crawler logs;
- HTTP status;
- website availability;
- request timeout.

Do not edit `websites.json` to fix a runtime CRUD target. Runtime target management should be performed through the API/DynamoDB.

---

## Pipeline Test Failure

Run locally:

```powershell
python -m pytest tests/unit tests/functional -v
```

Fix the first failure before pushing again.

---

## CDK Synth Failure

Run:

```powershell
cdk synth
```

Resolve the first CDK/Python error.

---

## Metrics Missing

Check:

- EventBridge enabled;
- crawler execution logs;
- correct CloudWatch namespace;
- `METRIC_NAMESPACE`;
- Lambda `cloudwatch:PutMetricData` permission;
- CloudWatch time range.

---

## Crawler Error Alarm

Check:

- crawler logs;
- CodeDeploy deployment;
- `live` alias;
- Lambda version;
- DynamoDB target configuration.

A deployment-time error may cause automatic rollback.

---

## DynamoDB Alarm History Missing

Check:

- CloudWatch alarm action;
- SNS topic;
- logger Lambda subscription;
- logger Lambda logs;
- `ALARM_TABLE_NAME`;
- DynamoDB permissions.

---

# 28. Deploying Changes

Before pushing:

```powershell
python -m pytest tests/unit tests/functional -v
python -m compileall -q app.py kartikey
cdk synth
git status
```

Then stage only intended files:

```powershell
git add <intended-files>
git commit -m "Describe the change"
git push origin main
```

Never commit:

- AWS credentials
- GitHub tokens
- secret values
- temporary API response files

---

# 29. Quick Presentation Explanation

## What does the project do?

> The project is an AWS-based website health monitoring system. EventBridge invokes a Lambda crawler every five minutes. The crawler reads its current website targets from DynamoDB and checks each target for availability and latency. The results are published to CloudWatch for dashboards and alarms.

## What did the Applied Project add?

> The Applied Project changed the target list from a static runtime configuration into a DynamoDB-backed system. I added a public API Gateway interface and a CRUD Lambda so targets can be created, read, updated and deleted without changing the crawler code.

## How does CRUD connect to the crawler?

> API Gateway sends CRUD requests to the target API Lambda. The Lambda changes records in the target DynamoDB table. Every time the scheduled crawler runs, it reads that same table, so the API and crawler share the same runtime source of truth.

## How did you test it?

> I used unit tests for isolated logic and infrastructure, functional tests with mocked AWS resources, and a live integration test against the deployed Beta API. The live test performs create, read, update, delete and verifies a 404 after deletion.

## How does CI/CD work?

> GitHub changes trigger CodePipeline. The build installs dependencies, compiles the Python code, runs 29 unit and functional tests and performs CDK synthesis. Successful changes deploy to Beta first. Production requires manual approval.

## Why Beta and Prod?

> Beta provides a safe environment to verify a release before production. The environments use separate Lambda functions, DynamoDB tables, monitoring namespaces and other resources.

## Why use a canary?

> CodeDeploy initially sends only 10% of crawler traffic to a new Lambda version. If the deployment remains healthy for five minutes, the release completes. If it fails or the crawler error alarm enters ALARM, automatic rollback protects the active version.

## What measures DynamoDB performance?

> Each CRUD operation measures its DynamoDB execution time. The value is returned as `operation_time_ms` and read/write timing metrics are also published to CloudWatch.

---

# 30. Complete DevOps Flow

```text
Develop
   |
   v
GitHub
   |
   v
Unit + Functional Tests
   |
   v
CDK Synth
   |
   v
Beta
   |
   +--> CRUD API Verification
   |
   +--> Live Integration Test
   |
   +--> Crawler Verification
   |
   v
Manual Approval
   |
   v
Prod
   |
   v
CodeDeploy Canary
   |
   v
CloudWatch
   |
   +-------- Healthy --------> Continue
   |
   +-------- Failure --------> Rollback
                                 |
                                 v
                             Investigate
                                 |
                                 v
                                Fix
```

This workflow demonstrates source control, Infrastructure as Code, automated testing, CI/CD, runtime configuration, monitoring, controlled releases and automated recovery.
