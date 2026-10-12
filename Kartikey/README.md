# COMP2029 DevOps — Website Health Monitor

## Student

**Name:** Kartikey Sachdeva  
**Student ID:** 22122045  
**Language:** Python  
**Infrastructure:** AWS Cloud Development Kit (CDK v2)  
**AWS Account:** `715054189400`  
**AWS Region:** `us-east-1`

## Project Overview

This project uses AWS CDK with Python to deploy an automated website
health monitor for Western Sydney University, AWS and GitHub.

The monitor checks website availability and response time, publishes
CloudWatch metrics, displays a dashboard and generates alarms.
Alarm notifications pass through SNS to a logging Lambda, which
stores the events in DynamoDB.

A CDK pipeline deploys separate Beta and Prod copies of the application.
Beta is deployed first. Manual approval is required before Prod.

## Architecture

### Monitoring

1. EventBridge invokes the monitoring Lambda every five minutes.
2. The Lambda reads the websites from `websites.json`.
3. It checks each website and publishes Availability and Latency metrics.
4. CloudWatch displays the metrics and evaluates website alarms.
5. When an alarm enters ALARM, CloudWatch publishes a notification to SNS.
6. SNS invokes the alarm logger.
7. The logger stores the alarm details in DynamoDB.

### Deployment

1. Source retrieves the GitHub repository's `main` branch.
2. Synth installs dependencies, checks Python syntax and synthesises CDK.
3. SelfMutate updates the pipeline definition when required.
4. Assets publishes the Lambda code packages.
5. Beta deploys the test environment.
6. ApproveProd pauses execution for review.
7. Prod deploys after manual approval.

## Project Files

| File | Purpose |
|---|---|
| `app.py` | Creates the original monitoring stack and pipeline stack |
| `kartikey/kartikey_stack.py` | Defines monitoring infrastructure and environment-specific names |
| `kartikey/pipeline_stack.py` | Defines application stages, pipeline and Prod approval |
| `kartikey/resources/webHealth.py` | Checks websites and publishes metrics |
| `kartikey/resources/alarmLogger.py` | Processes SNS alarm messages and writes DynamoDB records |
| `kartikey/resources/constants.py` | Stores shared configuration |
| `kartikey/resources/websites.json` | Lists monitored websites |
| `kartikey/resources/CWPutData.py` | Existing CloudWatch metric helper file |
| `cdk.json` | Configures the CDK application |
| `requirements.txt` | Lists runtime CDK dependencies |
| `requirements-dev.txt` | Lists development dependencies |
| `README.md` | Explains functionality, setup and verification |
| `RUNBOOK.md` | Provides operational and troubleshooting instructions |

## Monitored Websites

| Website | URL |
|---|---|
| Western Sydney University | https://www.westernsydney.edu.au/ |
| AWS | https://aws.amazon.com/ |
| GitHub | https://github.com/ |

## Monitoring Configuration

| Setting | Value |
|---|---|
| Schedule | Every five minutes |
| Lambda runtime | Python 3.13 |
| Monitoring Lambda timeout | 60 seconds |
| Website request timeout | 10 seconds |
| Logger Lambda timeout | 30 seconds |
| Metric period | Five minutes |
| Availability alarm | Minimum availability below 1 |
| Latency alarm | Average latency above 3000 ms |
| Evaluation periods | 1 |
| Missing data | Treated as breaching |
| DynamoDB billing | PAY_PER_REQUEST |

Successful checks record availability as `1`; failed checks record `0`.
Latency is measured in milliseconds.

Each deployment has six alarms: one availability alarm and one latency
alarm for each website.

## Beta and Prod Separation

Both environments use the same account and region. They have separate
resources and metric namespaces, although they share the same AWS
account permissions and billing boundary.

| Resource | Beta | Prod |
|---|---|---|
| Monitoring Lambda | `kartikey-web-health-beta` | `kartikey-web-health-prod` |
| Logger Lambda | `kartikey-alarm-logger-beta` | `kartikey-alarm-logger-prod` |
| Metric namespace | `Kartikey/WebsiteMonitoring/Beta` | `Kartikey/WebsiteMonitoring/Prod` |
| Dashboard | `Kartikey-Website-Health-Dashboard-beta` | `Kartikey-Website-Health-Dashboard-prod` |
| SNS topic | `kartikey-website-alarm-notifications-beta` | `kartikey-website-alarm-notifications-prod` |
| DynamoDB table | `Kartikey-Website-Alarm-Logs-beta` | `Kartikey-Website-Alarm-Logs-prod` |
| Alarm suffix | `-beta` | `-prod` |

`KartikeyStack` remains the original deployment with its original names
and namespace `Kartikey/WebsiteMonitoring`.

The monitoring Lambda reads its namespace from the `METRIC_NAMESPACE`
environment variable. The stack uses the same namespace for its
dashboard and alarms.

## DynamoDB Alarm Records

| Attribute | Purpose |
|---|---|
| `alarm_id` | Unique event identifier and partition key |
| `timestamp` | Event timestamp and sort key |
| `alarm_name` | CloudWatch alarm name |
| `new_state` | Reported alarm state |
| `reason` | Explanation of the state change |

The logger receives write permissions for its environment's table.

## Setup

### Prerequisites

Install Python, Node.js, Git, AWS CLI and the AWS CDK CLI.
Configure AWS credentials for the project account.

```powershell
npm install -g aws-cdk
```

The pipeline expects an existing Secrets Manager secret named
`github-token` in `us-east-1`, containing the GitHub authentication token.
Do not commit tokens or AWS credentials.

### Clone and Install

```powershell
git clone https://github.com/Kartikeysachdeva-github/WSU2026.git
cd WSU2026\Kartikey
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Verify the Account

```powershell
aws sts get-caller-identity
```

Confirm the account is `715054189400`.

### Bootstrap

The project account and region have already been bootstrapped.
For a fresh setup:

```powershell
cdk bootstrap aws://715054189400/us-east-1
```

### Check and Deploy the Pipeline

Commit and push the application code before initial deployment so the
pipeline can retrieve it from GitHub.

```powershell
python -m py_compile .\app.py .\kartikey\pipeline_stack.py .\kartikey\kartikey_stack.py
cdk synth KartikeyPipelineStack --quiet
cdk diff KartikeyPipelineStack
cdk deploy KartikeyPipelineStack
```

Pipeline name: `Kartikey-Website-Health-Pipeline`.

The source polls `Kartikeysachdeva-github/WSU2026` on branch `main`.
The build enters the repository's `Kartikey/` folder and publishes
`Kartikey/cdk.out` as its cloud assembly.

Check Beta before approving Prod in the CodePipeline console.

### Deploy the Original Monitor Separately

```powershell
cdk synth KartikeyStack --quiet
cdk diff KartikeyStack
cdk deploy KartikeyStack
```

## Development Progress

| Week | Work completed |
|---|---|
| 1 | Development environment, repository, Python CDK app and synthesis |
| 2 | Lambda website checks and CloudWatch metrics |
| 3 | Multi-website checks, EventBridge schedule, dashboard and alarms |
| 4–5 | Monitoring review, documentation and backlog work |
| 6 | SNS notifications, logger Lambda and DynamoDB alarm storage |
| 7 | Consolidation and checklist review |
| 8 | No additional practical implementation |
| 9 | CDK pipeline, separate Beta/Prod deployments and manual approval |

## Testing and Verification

### Week 6

The original GitHub availability alarm was temporarily changed from
OK to ALARM with the reason
`Week 6 end-to-end SNS and DynamoDB test`.

The resulting DynamoDB record verified the alarm notification path
through SNS and the logger Lambda.

### Week 9 — 12 October 2026

| Check | Observed result |
|---|---|
| Python syntax and local synthesis | Passed |
| Pipeline stack deployment | Successful |
| Source, Synth, SelfMutate and Assets | All succeeded |
| Beta deployment | Succeeded |
| Beta Lambda invocation | All three websites returned HTTP 200 and availability 1 |
| Beta metric publication | GitHub Availability datapoint was 1 |
| Beta alarm recovery | GitHub availability alarm returned to OK |
| Beta alarm logging | Five startup alarm records found |
| Approval gate | Paused before Prod and continued after approval |
| Prod deployment | Succeeded |
| Prod Lambda invocation | All three websites returned HTTP 200 and availability 1 |
| Prod alarm logging | Three startup alarm records found |

Observed response times from the manual Prod invocation:

| Website | Latency |
|---|---:|
| Western Sydney University | 573.22 ms |
| AWS | 105.19 ms |
| GitHub | 54.53 ms |

These are individual measurements, not long-term performance guarantees.

See `RUNBOOK.md` for repeatable verification commands.

## Quality and Known Limitations

- One reusable infrastructure definition supports Beta and Prod.
- Separate names and namespaces prevent their monitoring data from mixing.
- GitHub provides version history for code and infrastructure changes.
- Manual approval provides a review point before Prod deployment.
- The pipeline checks Python syntax and CDK synthesis. Runtime checks
  were performed manually; they are not automated pipeline tests.
- Missing data is treated as breaching. Startup alarms occurred before
  metrics arrived, and their logged reasons identified missing data.
- The new SNS topics subscribe the logger Lambda. Original email
  subscriptions do not automatically carry over to Beta and Prod.
- Dependency ranges and the build's CDK CLI installation are not pinned
  to exact versions.
- The original, Beta and Prod monitors remain separate active deployments.
- Removing the pipeline does not automatically remove application stacks.
  Retained tables and log groups may also remain after stack deletion.

## Useful Commands

| Command | Purpose |
|---|---|
| `cdk list` | Lists application stacks |
| `cdk synth KartikeyPipelineStack --quiet` | Checks pipeline synthesis |
| `cdk diff KartikeyPipelineStack` | Reviews pipeline changes |
| `cdk deploy KartikeyPipelineStack` | Creates or updates the pipeline stack |
| `cdk deploy KartikeyStack` | Deploys the original monitor |

## Official AWS CDK References

| Construct | Reference |
|---|---|
| Lambda Function | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html |
| Lambda Code | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Code.html |
| IAM PolicyStatement | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html |
| EventBridge Rule | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Rule.html |
| EventBridge Schedule | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Schedule.html |
| Lambda Event Target | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/LambdaFunction.html |
| CloudWatch Metric | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Metric.html |
| CloudWatch Dashboard | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Dashboard.html |
| CloudWatch GraphWidget | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/GraphWidget.html |
| CloudWatch Alarm | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html |
| SNS Topic | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns/Topic.html |
| Lambda Subscription | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns_subscriptions/LambdaSubscription.html |
| SNS Alarm Action | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch_actions/SnsAction.html |
| DynamoDB Table | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html |
| CDK Stage | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/Stage.html |
| CDK CodePipeline | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipeline.html |
| CodePipelineSource | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipelineSource.html |
| ShellStep | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/ShellStep.html |
| ManualApprovalStep | https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/ManualApprovalStep.html |

## Generative AI Acknowledgement

ChatGPT assisted with explanations, CDK code drafts, troubleshooting
and documentation. I applied the changes, ran the commands and reviewed
the deployment and runtime results. Official AWS CDK references are
included alongside the implementation.