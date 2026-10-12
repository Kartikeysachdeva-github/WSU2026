# COMP2029 DevOps - Website Health Monitor

## Student

**Name:** Kartikey Sachdeva  
**Student ID:** 22122045  
**Language:** Python  
**Infrastructure:** AWS Cloud Development Kit (CDK v2)  
**AWS Region:** `us-east-1`

---

## Project Overview

This project implements an automated Website Health Monitoring system using Python, AWS and Infrastructure as Code.

The system originally monitored a fixed set of websites. The Applied Project extends the application with a public REST API that allows the crawler target list to be created, read, updated and deleted without changing or redeploying the crawler code.

Website targets are stored in Amazon DynamoDB. An EventBridge rule invokes the crawler every five minutes, and the crawler reads the current target list from DynamoDB before checking each website.

For every target, the crawler publishes availability and latency metrics to Amazon CloudWatch.

The system also monitors the operational health of the crawler itself using Lambda metrics including invocations, errors, execution duration and throttles.

CloudWatch alarms publish notifications through Amazon SNS. An alarm logger Lambda stores alarm events in a separate DynamoDB table.

The complete application is deployed through an AWS CDK CodePipeline with separate Beta and Prod environments, automated tests, manual production approval, Lambda versioning, CodeDeploy canary releases and automatic rollback.

---

## Applied Project Objectives

The Applied Project extends the existing web crawler with:

- a public API Gateway REST API;
- a DynamoDB target database;
- CRUD operations for crawler targets;
- a Lambda function containing the CRUD business logic;
- DynamoDB read/write timing measurements;
- runtime target loading by the crawler;
- initial target seeding;
- additional unit and functional tests;
- a live integration test;
- Beta and Prod deployment through the existing CI/CD pipeline.

The important architectural change is that **DynamoDB is now the runtime source of truth for crawler targets**.

`websites.json` remains as infrastructure configuration for the original website-specific CloudWatch alarms, but the crawler itself retrieves its active target list from DynamoDB.

---

# Architecture

## Application Architecture

```text
                         User
                          |
                          v
                    API Gateway
                          |
                          v
                   CRUD API Lambda
                          |
                    CRUD operations
                          |
                          v
                  Targets DynamoDB
                          ^
                          |
                          |
EventBridge ------> Crawler Lambda
 every 5 min        live alias
                     |
                     +------> Target Websites
                     |
                     +------> CloudWatch Metrics
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

### Runtime Monitoring Flow

1. EventBridge invokes the crawler through its `live` Lambda alias every five minutes.
2. The crawler scans the environment-specific target DynamoDB table.
3. The current website targets are loaded at runtime.
4. The crawler sends an HTTP request to each target.
5. Availability and latency are calculated.
6. Custom metrics are published to CloudWatch.
7. CloudWatch dashboards display website and crawler health.
8. CloudWatch alarms evaluate the monitoring data.
9. Alarm notifications are sent to SNS.
10. SNS invokes the alarm logger Lambda.
11. Alarm information is stored in the alarm-log DynamoDB table.

Because the crawler reads DynamoDB during each invocation, CRUD changes can affect subsequent crawler runs without modifying the crawler source code.

---

# Target Management REST API

The Applied Project provides a public REST interface through Amazon API Gateway.

## Target Record

A crawler target uses the following structure:

```json
{
  "target_id": "github",
  "name": "GitHub",
  "url": "https://github.com/"
}
```

`target_id` is the DynamoDB partition key.

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/targets` | Create a target |
| `GET` | `/targets` | List all targets |
| `GET` | `/targets/{id}` | Retrieve one target |
| `PUT` | `/targets/{id}` | Update a target |
| `DELETE` | `/targets/{id}` | Delete a target |

API Gateway uses Lambda proxy integration to forward requests to `targetApi.py`.

---

## Create Target

### Request

```http
POST /targets
Content-Type: application/json
```

```json
{
  "target_id": "example",
  "name": "Example",
  "url": "https://example.com"
}
```

### Example Response

```json
{
  "message": "Target created.",
  "target": {
    "target_id": "example",
    "name": "Example",
    "url": "https://example.com"
  },
  "operation_time_ms": 58.922
}
```

A duplicate `target_id` is rejected rather than silently replacing an existing target.

---

## List Targets

```http
GET /targets
```

Example response:

```json
{
  "targets": [
    {
      "target_id": "aws",
      "name": "AWS",
      "url": "https://aws.amazon.com/"
    },
    {
      "target_id": "github",
      "name": "GitHub",
      "url": "https://github.com/"
    }
  ],
  "count": 2,
  "operation_time_ms": 301.149
}
```

---

## Get Target

```http
GET /targets/{id}
```

Example:

```http
GET /targets/github
```

A missing target returns HTTP `404`.

---

## Update Target

```http
PUT /targets/{id}
Content-Type: application/json
```

Example request:

```json
{
  "name": "Updated Example",
  "url": "https://example.org"
}
```

The update is persisted in DynamoDB and becomes available to subsequent crawler executions.

---

## Delete Target

```http
DELETE /targets/{id}
```

The target is removed from DynamoDB.

A subsequent GET for the deleted ID returns HTTP `404`.

---

## API Status Codes

| Status | Meaning |
|---|---|
| `200` | Successful read, update or delete |
| `201` | Target successfully created |
| `400` | Invalid request or target data |
| `404` | Target does not exist |
| `409` | Target already exists |
| `500` | Unexpected server-side error |

---

# DynamoDB Operation Timing

The CRUD Lambda records the duration of DynamoDB operations using `time.perf_counter()`.

API responses include:

```json
"operation_time_ms": 58.922
```

The Lambda also publishes operation timing to CloudWatch using:

- `DynamoDBReadTime`
- `DynamoDBWriteTime`

This allows database behaviour to be measured rather than only checking whether an operation succeeded.

During live Beta testing, successful CRUD requests returned real read/write timing values.

---

# Initial Target Seeding

A CloudFormation custom-resource Lambda seeds the original target list when a new environment is deployed.

The initial targets are:

| Target | URL |
|---|---|
| AWS | `https://aws.amazon.com/` |
| WesternSydneyUniversity | `https://www.westernsydney.edu.au/` |
| GitHub | `https://github.com/` |

The seeder uses a conditional DynamoDB write so an existing target is not overwritten.

This gives a newly deployed Beta or Prod environment an immediately usable target list while still allowing the list to be managed through the CRUD API afterward.

---

# Beta and Prod Environments

Beta and Prod use separate application resources.

| Resource | Beta | Prod |
|---|---|---|
| Crawler Lambda | `kartikey-web-health-beta` | `kartikey-web-health-prod` |
| Target API Lambda | `kartikey-target-api-beta` | `kartikey-target-api-prod` |
| Target table | `Kartikey-Website-Targets-beta` | `Kartikey-Website-Targets-prod` |
| Alarm log table | `Kartikey-Website-Alarm-Logs-beta` | `Kartikey-Website-Alarm-Logs-prod` |
| Metric namespace | `Kartikey/WebsiteMonitoring/Beta` | `Kartikey/WebsiteMonitoring/Prod` |
| Dashboard | `Kartikey-Website-Health-Dashboard-beta` | `Kartikey-Website-Health-Dashboard-prod` |
| CodeDeploy group | `Kartikey-Crawler-Deployment-beta` | `Kartikey-Crawler-Deployment-prod` |
| Lambda alias | `live` | `live` |

Separate resource names prevent Beta data from being mixed with production data.

---

# CI/CD Pipeline

The deployment pipeline is:

```text
GitHub main
     |
     v
Source
     |
     v
Build / Synth
     |
     +--> Install dependencies
     +--> Compile/check Python
     +--> Run unit tests
     +--> Run functional tests
     +--> CDK synth
     |
     v
Self-Mutate / Assets
     |
     v
Beta
     |
     v
Manual Production Approval
     |
     v
Prod
```

Pipeline name:

`Kartikey-Website-Health-Pipeline`

Repository:

`Kartikeysachdeva-github/WSU2026`

Branch:

`main`

A failed unit or functional test causes the CodeBuild stage to fail, preventing deployment.

Production cannot proceed until the `ApproveProd` manual approval action is completed.

---

# Testing Strategy

Testing is divided into three levels.

## Unit Tests

Unit tests verify isolated application logic and synthesized infrastructure.

Coverage includes:

- crawler configuration;
- EventBridge scheduling;
- DynamoDB schemas;
- target-table infrastructure;
- alarm logger configuration;
- SNS integration;
- CloudWatch alarms;
- Beta/Prod separation;
- DynamoDB target loading;
- target pagination;
- CRUD API behaviour.

---

## Functional Tests

Functional tests exercise application behaviour with mocked AWS resources.

The CRUD functional test verifies a complete lifecycle:

```text
CREATE
   |
   v
READ
   |
   v
UPDATE
   |
   v
DELETE
```

Crawler functional tests verify behaviour such as:

- checking every configured target;
- continuing after connection failures;
- publishing the expected CloudWatch metrics;
- HTTP failure handling;
- configured request timeout;
- empty target lists;
- CloudWatch publication failures;
- correct website metric dimensions.

---

## Automated CI Test Gate

The pipeline runs:

```powershell
python -m pytest tests/unit tests/functional -v
```

The current unit and functional suite contains:

**29 passing tests**

These tests are pipeline-blocking.

---

## Live Integration Test

The project also contains:

`tests/integration/test_target_api_integration.py`

This test calls the deployed API rather than mocking AWS services.

It verifies:

```text
API Gateway
     |
     v
Target API Lambda
     |
     v
Real DynamoDB Table
```

The integration lifecycle is:

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

The test also checks that DynamoDB operation timing is returned.

The live Beta integration test completed successfully:

```text
1 passed
```

The integration test is deliberately separate from the normal pipeline build because it requires an already deployed API endpoint.

---

# Live Applied Project Verification

## Beta

The Beta environment was verified before production approval.

Testing confirmed:

- the target DynamoDB table contained the three seeded websites;
- `GET /targets` returned the target list;
- `POST /targets` created a temporary target;
- `GET /targets/{id}` retrieved it;
- `PUT /targets/{id}` updated it;
- the updated data persisted;
- `DELETE /targets/{id}` removed it;
- a subsequent GET returned `404`;
- DynamoDB read/write timing was returned;
- the automated live integration test passed;
- the scheduled crawler successfully processed the DynamoDB targets;
- CloudWatch logs showed successful crawler executions.

Only after Beta verification was production manually approved.

---

## Production

The complete CodePipeline execution successfully deployed Prod.

A production `GET /targets` returned:

- AWS;
- WesternSydneyUniversity;
- GitHub;
- `count = 3`;
- DynamoDB operation timing.

The production crawler CloudWatch logs also confirmed successful processing of all three targets.

This demonstrated that the Applied Project worked in both deployment environments.

---

# Website Monitoring

For each active target, the crawler publishes two custom metrics.

## Availability

Metric:

`Availability`

Successful request:

`1`

Failed request:

`0`

The original website availability alarms trigger when availability falls below `1`.

## Latency

Metric:

`Latency`

Latency is measured in milliseconds.

The original latency alarms trigger when average latency exceeds:

`3000 ms`

---

# Crawler Operational Monitoring

The project monitors the Lambda crawler using standard Lambda metrics:

| Metric | Purpose |
|---|---|
| Invocations | Number of crawler executions |
| Errors | Failed executions |
| Duration | Average execution duration |
| Throttles | Throttled executions |

Three crawler alarms are configured:

| Alarm | Trigger |
|---|---|
| Crawler Errors | Errors >= 1 |
| Crawler Duration | Average duration > 30 seconds |
| Crawler Throttles | Throttles >= 1 |

Operational alarms treat missing data as non-breaching.

---

# Dashboard

The CloudWatch dashboard displays:

- Website Availability
- Website Latency
- Crawler Invocations and Errors
- Crawler Execution Duration
- Crawler Throttles

This provides visibility into both the monitored websites and the monitoring application itself.

---

# Alarm Notification Flow

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

Alarm records provide persistent history instead of relying only on the current CloudWatch alarm state.

---

# Canary Deployment and Automatic Rollback

The crawler uses an immutable Lambda version and a stable alias named:

`live`

EventBridge invokes the alias rather than `$LATEST`.

AWS CodeDeploy uses:

`CANARY_10_PERCENT_5_MINUTES`

The deployment process is:

```text
New Lambda Version
        |
        v
10% traffic to new version
90% traffic to previous version
        |
        v
5 minute canary period
        |
   +----+----+
   |         |
Healthy    Failure / Alarm
   |         |
   v         v
100% new   Automatic rollback
version    to previous version
```

Automatic rollback is configured when:

- the crawler error alarm enters ALARM;
- deployment fails; or
- deployment is stopped.

This reduces the impact of an unhealthy crawler release.

---

# Security

Security considerations include:

- AWS credentials are not stored in source code.
- GitHub credentials are stored in AWS Secrets Manager.
- IAM permissions are granted to specific Lambda functions.
- The crawler receives read access to the target table.
- The target API receives read/write access because it performs CRUD operations.
- The alarm logger only requires access to its alarm table.
- Beta and Prod use separate resources.
- Production deployment requires manual approval.
- CodeDeploy rollback protects the active crawler version.
- URLs are validated before being accepted by the API.

The REST API is intentionally public to satisfy the Applied Project requirement. In a production commercial system, authentication and authorization should be added using a mechanism such as IAM, Cognito or another API authorization layer.

---

# Performance

Performance is considered through:

- DynamoDB `PAY_PER_REQUEST` billing;
- DynamoDB operation timing;
- Lambda execution-duration monitoring;
- website latency metrics;
- a 10-second HTTP request timeout;
- a five-minute monitoring schedule;
- CloudWatch duration alarms.

The API reports DynamoDB operation duration directly in each CRUD response and publishes timing metrics to CloudWatch.

---

# Reliability

Reliability features include:

- automated unit and functional testing;
- Beta verification before production;
- manual production approval;
- separate Beta and Prod resources;
- Lambda immutable versions;
- stable `live` alias;
- CodeDeploy canary releases;
- automatic rollback;
- CloudWatch alarms;
- SNS notifications;
- persistent alarm logging;
- runtime target retrieval from DynamoDB;
- initial target seeding.

---

# Usability

The REST interface allows targets to be managed without editing crawler source code.

The five CRUD endpoints use standard HTTP methods and JSON payloads.

Meaningful HTTP status codes are returned for successful operations, validation errors, missing records and duplicate records.

The CloudFormation `TargetApiUrl` output also makes the deployed endpoint easy to locate after deployment.

---

# Project Files

| File | Purpose |
|---|---|
| `app.py` | Creates the application and pipeline stacks |
| `kartikey/kartikey_stack.py` | Defines application infrastructure |
| `kartikey/pipeline_stack.py` | Defines CI/CD, Beta, Prod and approval |
| `kartikey/resources/webHealth.py` | Loads DynamoDB targets, checks websites and publishes metrics |
| `kartikey/resources/targetApi.py` | Implements CRUD target management |
| `kartikey/resources/seedTargets.py` | Seeds initial DynamoDB targets |
| `kartikey/resources/alarmLogger.py` | Stores alarm events in DynamoDB |
| `kartikey/resources/constants.py` | Shared application configuration |
| `kartikey/resources/websites.json` | Baseline infrastructure configuration and initial target definitions |
| `tests/unit/test_target_api.py` | CRUD API unit tests |
| `tests/unit/test_web_health.py` | Crawler unit tests |
| `tests/unit/test_kartikey_stack.py` | CDK infrastructure tests |
| `tests/functional/test_target_api_functional.py` | CRUD functional lifecycle test |
| `tests/functional/test_crawler_functional.py` | Crawler functional tests |
| `tests/integration/test_target_api_integration.py` | Live deployed CRUD integration test |
| `RUNBOOK.md` | Operational verification and troubleshooting |
| `README.md` | Main project and API documentation |

---

# Setup

## Prerequisites

Install:

- Python
- Node.js
- Git
- AWS CLI
- AWS CDK CLI

Install CDK:

```powershell
npm install -g aws-cdk
```

Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Verify the AWS identity before deployment:

```powershell
aws sts get-caller-identity
```

---

# Local Verification

Run the pipeline-blocking test suites:

```powershell
python -m pytest tests/unit tests/functional -v
```

Expected current result:

```text
29 passed
```

Check Python source:

```powershell
python -m compileall -q app.py kartikey
```

Synthesize the CDK application:

```powershell
cdk synth
```

---

# Running the Live Integration Test

Set the deployed API endpoint:

```powershell
$env:RUN_LIVE_TESTS = "1"
$env:TARGET_API_URL = "YOUR-DEPLOYED-API-URL"
```

Run:

```powershell
python -m pytest tests/integration/test_target_api_integration.py -v
```

The test creates its own temporary target and cleans it up after testing.

---

# Development Roadmap

| Stage | Work Completed |
|---|---|
| Weeks 1-2 | Development environment, CDK application, Lambda crawler and CloudWatch metrics |
| Week 3 | Multi-site monitoring, EventBridge, dashboard and alarms |
| Weeks 4-5 | Refactoring, DevOps workflow and project documentation |
| Week 6 | SNS notifications, alarm logger and DynamoDB alarm history |
| Week 7 | Consolidation and end-to-end verification |
| Week 8 | No additional practical implementation |
| Week 9 | CDK Pipeline, Beta/Prod stages and production approval |
| Week 10 | Deployment and operational/security practical work |
| Week 11 | Automated test gate, crawler operational monitoring, Lambda alias, CodeDeploy canary and rollback |
| Applied Project | DynamoDB target database, public CRUD REST API, target seeding, crawler DynamoDB integration, timing metrics, expanded tests, Beta verification and Prod deployment |

---

# DevOps Practices Demonstrated

## Infrastructure as Code

AWS resources are defined using Python and AWS CDK. Infrastructure changes are therefore version controlled and repeatable.

## Continuous Integration

Changes pushed to GitHub enter CodePipeline. Unit and functional tests run before deployment.

## Continuous Delivery

Successful changes automatically deploy to Beta. Production remains protected by manual approval.

## Continuous Monitoring

CloudWatch monitors both website health and crawler operational health.

## Feedback

Metrics, alarms, SNS notifications, CloudWatch logs and DynamoDB alarm records provide feedback about the deployed application.

## Safer Releases

Lambda versions, the `live` alias, CodeDeploy canary deployment and automatic rollback reduce deployment risk.

---

# Quality Considerations and Limitations

## Strengths

- Infrastructure is version controlled through CDK.
- Target management no longer requires crawler code changes.
- DynamoDB provides a persistent runtime target list.
- CRUD behaviour is tested at unit, functional and live integration levels.
- CI automatically blocks releases when unit/functional tests fail.
- Beta is verified before production.
- Production requires manual approval.
- Website and crawler health are continuously monitored.
- Canary releases reduce deployment risk.
- Automatic rollback protects the active crawler version.
- Beta and Prod use separate application resources.

## Current Limitations

- The public API does not currently require authentication because public access is part of the Applied Project requirement.
- `GET /targets` uses a DynamoDB scan, which is suitable for the small coursework target list but would require further design for a large production dataset.
- The live integration test requires a deployed API and is therefore not part of the pre-deployment pipeline build gate.
- The original per-website CloudWatch alarms are created from infrastructure configuration. Dynamically created targets receive crawler metrics but do not automatically create new CDK alarm resources.
- Beta and Prod are separated by resource names and namespaces but use the same AWS account and region.
- The crawler runs every five minutes, so a short canary window can contain a limited number of scheduled invocations.

---

# Useful Commands

Run unit and functional tests:

```powershell
python -m pytest tests/unit tests/functional -v
```

Run integration test:

```powershell
python -m pytest tests/integration/test_target_api_integration.py -v
```

Check Python:

```powershell
python -m compileall -q app.py kartikey
```

Synthesize:

```powershell
cdk synth
```

Check AWS identity:

```powershell
aws sts get-caller-identity
```

Check Git:

```powershell
git status
```

---

# Presentation Summary

The project can be presented as five connected parts.

### 1. Manage

The user manages crawler targets through API Gateway using standard CRUD operations.

### 2. Store

DynamoDB stores the current runtime target list.

### 3. Monitor

EventBridge invokes the crawler every five minutes. The crawler retrieves DynamoDB targets and publishes website health metrics.

### 4. Observe and Respond

CloudWatch dashboards and alarms provide operational feedback. SNS and the alarm logger provide notification and persistent alarm history.

### 5. Release Safely

GitHub changes enter CodePipeline. Automated tests protect the deployment, Beta is deployed first, Prod requires manual approval, and CodeDeploy provides canary deployment and automatic rollback.

The resulting DevOps feedback loop is:

```text
Code
  ↓
Test
  ↓
Build
  ↓
Deploy Beta
  ↓
Verify
  ↓
Approve
  ↓
Deploy Prod
  ↓
Monitor
  ↓
Feedback / Rollback
```

---

# Generative AI Acknowledgement

ChatGPT assisted with explanations, AWS CDK and Python code drafts, troubleshooting and documentation.

I reviewed and applied the changes, executed the commands, tested the implementation and verified the deployed behaviour.

Generative AI assistance should be acknowledged in accordance with the assessment requirements and Western Sydney University academic integrity requirements.