# COMP2029 DevOps — Website Health Monitor

## Student

**Name:** Kartikey Sachdeva  
**Student ID:** 22122045  
**Language:** Python  
**Infrastructure:** AWS Cloud Development Kit (CDK v2)  
**AWS Region:** `us-east-1`

---

## Project Overview

This project implements an automated Website Health Monitoring system using
Python, AWS and Infrastructure as Code (IaC).

The system monitors:

- Western Sydney University
- Amazon Web Services (AWS)
- GitHub

Every five minutes, an AWS Lambda crawler checks the configured websites and
publishes health information to Amazon CloudWatch.

The system monitors both website health and the operational health of the
crawler itself. CloudWatch dashboards and alarms provide visibility into
availability, latency, Lambda invocations, errors, execution duration and
throttling.

Alarm notifications are published through Amazon SNS. An alarm logger Lambda
processes these notifications and stores alarm events in Amazon DynamoDB.

A CDK-based CI/CD pipeline automatically builds, tests and deploys the
application through separate Beta and Prod environments. Production deployment
requires manual approval.

The release process also uses Lambda versions, a `live` alias and AWS CodeDeploy
to perform a canary deployment. A new Lambda version initially receives 10% of
traffic. If the monitored deployment remains healthy for five minutes,
CodeDeploy completes the deployment. If the deployment fails or the configured
CloudWatch error alarm enters ALARM, CodeDeploy can automatically roll the
alias back to the previous Lambda version.

---

## Main DevOps Features

The project demonstrates the following DevOps practices:

- Infrastructure as Code using AWS CDK
- Source control using Git and GitHub
- Automated CI/CD using AWS CodePipeline
- Automated unit and functional testing
- Pipeline-blocking automated tests
- Separate Beta and Prod environments
- Manual approval before production
- Continuous operational monitoring
- CloudWatch dashboards and alarms
- SNS-based alarm notifications
- DynamoDB alarm history
- Lambda versioning and aliases
- Canary deployment using AWS CodeDeploy
- Automated rollback based on deployment health
- Repeatable infrastructure deployment from source code

---

## Architecture

### Monitoring Flow

```text
EventBridge
     |
     v
Lambda live Alias
     |
     v
Website Health Crawler
     |
     +-------------------------+
     |                         |
     v                         v
Website Requests          CloudWatch
                               |
                    +----------+----------+
                    |                     |
                    v                     v
                 Metrics                Alarms
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

### Monitoring Process

1. EventBridge invokes the monitoring Lambda through the `live` alias every
   five minutes.
2. The Lambda reads the monitored websites from `websites.json`.
3. Each website is requested using the configured request timeout.
4. The crawler calculates website availability and response latency.
5. Custom Availability and Latency metrics are published to CloudWatch.
6. AWS Lambda operational metrics are also monitored.
7. CloudWatch dashboards display website and crawler health.
8. CloudWatch alarms evaluate the metrics.
9. Alarm state changes are published to SNS.
10. SNS invokes the alarm logger Lambda.
11. The alarm logger stores the event in DynamoDB.

---

## CI/CD Release Flow

```text
Developer
    |
    v
GitHub main
    |
    v
AWS CodePipeline
    |
    v
Source
    |
    v
Build / Synth
    |
    +--> Install dependencies
    +--> Check Python code
    +--> Run automated tests
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

The pipeline retrieves the `main` branch from GitHub.

During the build/synthesis stage, the pipeline installs both application and
development dependencies and runs the unit and functional test suites.

If an automated test fails, the build fails and the release does not continue.

Beta is deployed before Prod. Production deployment is protected by the
`ApproveProd` manual approval step so that Beta can be reviewed before the
production release continues.

---

## Canary Deployment and Automatic Rollback

Week 11 adds a safer release mechanism for the website crawler.

Instead of EventBridge directly invoking the mutable Lambda function, it invokes
a Lambda alias named:

`live`

The alias references an immutable published Lambda version.

AWS CodeDeploy manages changes to this alias.

### Canary Process

```text
Previous Lambda Version
          |
          |
      live Alias
          |
          v
   CodeDeploy starts
          |
          v
10% traffic -> New Version
90% traffic -> Previous Version
          |
          v
     5 minute canary
          |
      +---+---+
      |       |
   Healthy   Alarm /
      |      Failure
      v       |
Remaining     v
90% moves   Automatic
to new      Rollback
version       |
      |       v
      v     Previous
100% new    Version
```

The deployment configuration is:

`CANARY_10_PERCENT_5_MINUTES`

This means the new version initially receives 10% of traffic.

If the canary remains healthy for five minutes, CodeDeploy completes the
traffic shift.

The crawler error alarm is connected to the CodeDeploy deployment group. The
deployment is configured for automatic rollback when:

- the deployment enters an alarm state;
- the deployment fails; or
- the deployment is stopped.

This reduces the risk of a faulty crawler release remaining active in the
environment.

---

## Project Files

| File | Purpose |
|---|---|
| `app.py` | Creates the monitoring and pipeline stacks |
| `kartikey/kartikey_stack.py` | Defines monitoring, alarms, Lambda versioning, alias and CodeDeploy rollback infrastructure |
| `kartikey/pipeline_stack.py` | Defines Beta/Prod stages, automated build/test process and Prod approval |
| `kartikey/resources/webHealth.py` | Checks websites and publishes health metrics |
| `kartikey/resources/alarmLogger.py` | Processes SNS alarm events and writes records to DynamoDB |
| `kartikey/resources/constants.py` | Stores shared application configuration |
| `kartikey/resources/websites.json` | Defines the websites monitored by the crawler |
| `kartikey/resources/CWPutData.py` | CloudWatch metric helper file |
| `tests/unit/test_kartikey_stack.py` | Tests the synthesized infrastructure |
| `tests/functional/` | Tests application behaviour without requiring the live AWS deployment |
| `tests/integration/` | Contains tests used to verify deployed AWS environments |
| `requirements.txt` | Runtime/CDK Python dependencies |
| `requirements-dev.txt` | Development and testing dependencies |
| `cdk.json` | Configures the AWS CDK application |
| `RUNBOOK.md` | Operational verification and troubleshooting guide |
| `README.md` | Project architecture, setup, testing and implementation documentation |

---

## Monitored Websites

| Website | URL |
|---|---|
| Western Sydney University | `https://www.westernsydney.edu.au/` |
| AWS | `https://aws.amazon.com/` |
| GitHub | `https://github.com/` |

---

## Website Health Metrics

The crawler publishes two custom metrics for every monitored website.

### Availability

Metric:

`Availability`

A successful request records:

`1`

A failed request records:

`0`

The availability alarm is triggered when minimum availability falls below `1`.

### Latency

Metric:

`Latency`

Latency is measured in milliseconds.

The latency alarm is triggered when average latency exceeds:

`3000 ms`

The metrics use the website name as the CloudWatch dimension so each monitored
website can be evaluated separately.

---

## Crawler Operational Metrics

Week 11 extends monitoring beyond website availability.

The project also monitors the operational health of the Lambda crawler using
standard AWS Lambda CloudWatch metrics.

| Metric | Purpose |
|---|---|
| Invocations | Number of crawler executions |
| Errors | Number of failed Lambda executions |
| Duration | Average crawler execution time |
| Throttles | Number of throttled executions |

These metrics provide operational feedback about whether the crawler itself is
working correctly.

---

## Operational Alarms

Each environment contains the original website alarms plus crawler operational
alarms.

### Website Alarms

For each of the three monitored websites:

- one Availability alarm;
- one Latency alarm.

This produces six website health alarms per environment.

### Crawler Alarms

Three additional alarms monitor the crawler:

| Alarm | Trigger |
|---|---|
| Crawler Errors | Errors greater than or equal to 1 |
| Crawler Duration | Average execution duration greater than 30 seconds |
| Crawler Throttles | Throttles greater than or equal to 1 |

Therefore, each Beta/Prod monitoring stack contains nine CloudWatch alarms.

Crawler operational alarms treat missing data as not breaching.

The crawler error alarm is also used by CodeDeploy to protect the canary
deployment.

---

## CloudWatch Dashboard

The CloudWatch dashboard contains graphs for:

- Website Availability
- Website Latency
- Crawler Invocations and Errors
- Crawler Execution Duration
- Crawler Throttles

This provides one location for observing both application-level health and
infrastructure/runtime health.

---

## Alarm Notification and Logging

CloudWatch alarms publish notifications to an SNS topic.

The SNS topic invokes the alarm logger Lambda.

The logger stores alarm information in DynamoDB.

### DynamoDB Alarm Record

| Attribute | Purpose |
|---|---|
| `alarm_id` | Unique alarm event identifier and partition key |
| `timestamp` | Event timestamp and sort key |
| `alarm_name` | CloudWatch alarm name |
| `new_state` | New CloudWatch alarm state |
| `reason` | Explanation for the state change |

This provides a persistent record of alarm activity rather than relying only on
the current CloudWatch alarm state.

---

## Beta and Prod Separation

Beta and Prod use the same AWS account and region but have separate application
resources and monitoring namespaces.

| Resource | Beta | Prod |
|---|---|---|
| Monitoring Lambda | `kartikey-web-health-beta` | `kartikey-web-health-prod` |
| Lambda alias | `live` | `live` |
| Logger Lambda | `kartikey-alarm-logger-beta` | `kartikey-alarm-logger-prod` |
| Metric namespace | `Kartikey/WebsiteMonitoring/Beta` | `Kartikey/WebsiteMonitoring/Prod` |
| Dashboard | `Kartikey-Website-Health-Dashboard-beta` | `Kartikey-Website-Health-Dashboard-prod` |
| SNS topic | `kartikey-website-alarm-notifications-beta` | `kartikey-website-alarm-notifications-prod` |
| DynamoDB table | `Kartikey-Website-Alarm-Logs-beta` | `Kartikey-Website-Alarm-Logs-prod` |
| CodeDeploy group | `Kartikey-Crawler-Deployment-beta` | `Kartikey-Crawler-Deployment-prod` |
| Alarm suffix | `-beta` | `-prod` |

Environment-specific names prevent Beta and Prod resources from overlapping.

The monitoring Lambda receives its custom metric namespace through the
`METRIC_NAMESPACE` environment variable.

---

## Testing Strategy

Testing is divided into multiple levels.

### Unit Tests

Unit tests validate the CDK infrastructure definition.

They check infrastructure such as:

- Lambda configuration
- EventBridge scheduling
- DynamoDB table schema
- alarm logger configuration
- SNS subscription
- CloudWatch alarms
- Beta and Prod resource separation

### Functional Tests

Functional tests verify application behaviour without depending on the live AWS
environment.

### Integration Tests

Integration tests are used to validate deployed AWS resources and behaviour.

Beta and Prod have previously been tested against the live AWS environment to
confirm that the crawler executes and publishes monitoring information.

### Automated Pipeline Gate

Week 11 moves the local unit and functional test suites into the CI/CD build
process.

The pipeline executes:

```powershell
python -m pytest tests/unit tests/functional -v
```

If any test fails, CodeBuild returns a failure and CodePipeline stops before
deploying the change.

This creates an automated quality gate in the release process.

At the latest local verification, all automated unit and functional tests
passed successfully.

---

## Monitoring Configuration

| Setting | Value |
|---|---|
| Schedule | Every five minutes |
| Lambda runtime | Python 3.13 |
| Monitoring Lambda timeout | 60 seconds |
| Website request timeout | 10 seconds |
| Logger Lambda timeout | 30 seconds |
| Website metric period | Five minutes |
| Availability threshold | Minimum below 1 |
| Latency threshold | Average above 3000 ms |
| Crawler error threshold | Greater than or equal to 1 |
| Crawler duration threshold | Greater than 30,000 ms |
| Crawler throttle threshold | Greater than or equal to 1 |
| Website alarm evaluation periods | 1 |
| DynamoDB billing | PAY_PER_REQUEST |
| Lambda alias | `live` |
| CodeDeploy strategy | 10% canary for five minutes |
| Automatic rollback | Enabled |

---

## Setup

### Prerequisites

Install:

- Python
- Node.js
- Git
- AWS CLI
- AWS CDK CLI

Install the CDK CLI:

```powershell
npm install -g aws-cdk
```

AWS credentials must be configured for the AWS account used by the project.

The pipeline expects an AWS Secrets Manager secret named:

`github-token`

The secret is used by the pipeline to access the GitHub repository.

Tokens and AWS credentials must never be committed to GitHub.

---

## Clone and Install

```powershell
git clone https://github.com/Kartikeysachdeva-github/WSU2026.git
cd WSU2026\Kartikey

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

---

## Verify AWS Identity

Before deploying, verify the currently configured AWS identity:

```powershell
aws sts get-caller-identity
```

This helps prevent resources from being deployed to the wrong AWS account.

---

## Bootstrap CDK

The AWS environment must be bootstrapped before CDK Pipelines can deploy
assets.

For the configured account and region:

```powershell
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

---

## Local Verification

Run all unit and functional tests:

```powershell
python -m pytest tests/unit tests/functional -v
```

Synthesize the CDK application:

```powershell
cdk synth
```

A successful test run followed by successful synthesis provides a local check
before committing the change.

---

## Pipeline

Pipeline name:

`Kartikey-Website-Health-Pipeline`

The source retrieves:

`Kartikeysachdeva-github/WSU2026`

Branch:

`main`

The pipeline build performs the following actions:

1. Enters the `Kartikey` project directory.
2. Installs the AWS CDK CLI.
3. Installs `requirements.txt`.
4. Installs `requirements-dev.txt`.
5. Checks Python source files.
6. Runs unit and functional tests.
7. Synthesizes the CDK cloud assembly.
8. Publishes deployment assets.
9. Deploys Beta.
10. Pauses for production approval.
11. Deploys Prod after approval.

---

## Development Roadmap

| Week | Work Completed |
|---|---|
| 1 | Configured the development environment, repository, Python CDK application and initial synthesis |
| 2 | Implemented Lambda website checks and CloudWatch metric publication |
| 3 | Added multi-website monitoring, EventBridge scheduling, dashboard and website alarms |
| 4–5 | Refactored monitoring infrastructure, reviewed DevOps workflow and maintained backlog/documentation |
| 6 | Added SNS alarm notifications, alarm logger Lambda and DynamoDB alarm history |
| 7 | Consolidated the monitoring solution and completed checklist verification |
| 8 | No additional practical implementation |
| 9 | Implemented AWS CDK Pipeline, Beta/Prod stages and manual production approval |
| 10 | Continued deployment/testing work and AWS operational/security practical activities |
| 11 | Added automated pipeline test gate, crawler operational metrics, operational alarms, Lambda versioning, `live` alias, CodeDeploy canary release and automatic rollback |

---

## Verification Evidence

The project has been tested at multiple stages of development.

### Alarm Notification Flow

A CloudWatch alarm state change was used to verify the path:

```text
CloudWatch Alarm
      ↓
SNS
      ↓
Alarm Logger Lambda
      ↓
DynamoDB
```

The resulting DynamoDB record confirmed that the alarm notification and
persistent logging path worked.

### Beta and Prod Verification

The deployment pipeline has previously completed:

```text
Source
  ↓
Synth
  ↓
Self-Mutate
  ↓
Assets
  ↓
Beta
  ↓
ApproveProd
  ↓
Prod
```

Live Beta and Prod integration testing confirmed that the deployed monitoring
functions could execute and monitor the configured websites.

### Week 11 Local Verification

After adding operational monitoring and the canary/rollback infrastructure:

- all unit and functional tests passed;
- CDK synthesis completed successfully;
- the CodeDeploy resources synthesized successfully;
- the EventBridge target was changed to the versioned `live` alias;
- automatic rollback was configured against the crawler error alarm.

Final cloud deployment should also be checked in CodePipeline and CodeDeploy
after the Week 11 commit is processed.

---

## DevOps Concepts Demonstrated

### Infrastructure as Code

AWS resources are defined in Python using AWS CDK instead of being created
manually.

This makes the infrastructure repeatable, version controlled and easier to
review.

### Continuous Integration

Every release executes automated tests and CDK synthesis in the pipeline.

A failing automated test prevents the release from progressing.

### Continuous Delivery

Successful changes can move automatically through the build and Beta stages.

Production remains protected by a manual approval gate.

### Continuous Monitoring

CloudWatch continuously collects website and Lambda operational metrics.

Alarms provide feedback when the system becomes unhealthy.

### Feedback

Monitoring, alarms, SNS notifications and DynamoDB records provide feedback
about the behaviour of the deployed system.

### Safer Releases

Lambda versions are immutable release points.

The `live` alias provides a stable target for EventBridge while CodeDeploy
controls which Lambda version receives production traffic.

### Canary Deployment

Only a percentage of traffic is initially exposed to a new crawler version,
reducing the impact of a faulty release.

### Automated Rollback

CodeDeploy can return the `live` alias to the previous Lambda version if the
deployment becomes unhealthy.

Together, these features create a feedback loop:

```text
Code
 ↓
Test
 ↓
Build
 ↓
Deploy
 ↓
Monitor
 ↓
Feedback
 ↓
Rollback or Continue
```

---

## Quality and Limitations

### Strengths

- Infrastructure is defined as code.
- Beta and Prod use separate physical resources.
- Git provides version history.
- Automated tests run before deployment.
- Production requires manual approval.
- Monitoring covers both website health and crawler operational health.
- Alarm events are stored in DynamoDB.
- Canary releases reduce deployment risk.
- Automatic rollback protects the active Lambda alias.
- The architecture is reproducible through CDK.

### Current Limitations

- The project monitors standard Lambda operational metrics such as invocations,
  errors, duration and throttles. It does not currently publish a custom
  Lambda memory-usage metric.
- The crawler runs every five minutes, so a short canary period may receive a
  limited number of scheduled invocations.
- Live integration tests have been used for deployed-environment verification,
  while the current pipeline build gate runs the unit and functional suites.
- GitHub authentication depends on the configured Secrets Manager secret.
- Beta and Prod are isolated by resource naming and namespaces but remain in
  the same AWS account and region.
- Dependency versions should be reviewed and pinned where stronger build
  reproducibility is required.
- Removing the pipeline does not necessarily remove all application resources,
  retained data or CloudWatch logs.

---

## Useful Commands

Run automated tests:

```powershell
python -m pytest tests/unit tests/functional -v
```

Run live integration tests when the required environment is configured:

```powershell
python -m pytest tests/integration -v
```

Check Python source:

```powershell
python -m compileall -q app.py kartikey
```

Synthesize the application:

```powershell
cdk synth
```

List stacks:

```powershell
cdk list
```

Review pipeline changes:

```powershell
cdk diff KartikeyPipelineStack
```

Deploy/update the pipeline:

```powershell
cdk deploy KartikeyPipelineStack
```

Check AWS identity:

```powershell
aws sts get-caller-identity
```

Check Git changes:

```powershell
git status
```

Run all local verification before a release:

```powershell
python -m pytest tests/unit tests/functional -v
cdk synth
git status
```

---

## Troubleshooting

### Pipeline Stops During Synth

Check the CodeBuild logs.

Because automated tests are now part of the build, a failed test intentionally
prevents deployment.

Reproduce the check locally with:

```powershell
python -m pytest tests/unit tests/functional -v
cdk synth
```

### No Website Metrics

Check:

1. EventBridge rule status.
2. Lambda `live` alias.
3. Lambda CloudWatch logs.
4. `METRIC_NAMESPACE` environment variable.
5. CloudWatch namespace for the correct environment.

### Alarm Triggered

Check:

1. CloudWatch alarm reason.
2. SNS topic.
3. alarm logger Lambda logs.
4. DynamoDB alarm record.

### Canary Deployment Fails

Check:

1. AWS CodeDeploy deployment status.
2. `Kartikey-Crawler-Errors-beta` or Prod equivalent.
3. crawler Lambda logs.
4. Lambda versions.
5. `live` alias.
6. CodeDeploy rollback status.

If the monitored deployment enters the configured failure condition,
CodeDeploy should move the alias back to the previous healthy version.

---

## Presentation Summary

The project can be explained as four connected stages:

### 1. Monitor

EventBridge runs a Lambda crawler every five minutes.

The crawler checks three websites and publishes availability and latency
metrics.

### 2. Observe

CloudWatch dashboards display website and Lambda operational health.

CloudWatch alarms detect failures, slow responses, crawler errors, long
execution times and throttling.

### 3. Notify and Record

CloudWatch sends alarm events to SNS.

SNS invokes a logger Lambda that stores the alarm event in DynamoDB.

### 4. Release Safely

GitHub changes enter CodePipeline.

Automated tests must pass before deployment.

Beta is deployed before Prod.

Prod requires manual approval.

Lambda versions and the `live` alias allow CodeDeploy to perform a 10% canary
release.

If the release becomes unhealthy, automatic rollback protects the active
environment.

---

## Generative AI Acknowledgement

ChatGPT assisted with explanations, AWS CDK code drafts, troubleshooting and
documentation.

I reviewed and applied the changes, executed the commands, tested the 
implementation and verified deployment behaviour.

Generative AI assistance should be acknowledged in accordance with the
assessment requirements and Western Sydney University academic integrity
requirements.