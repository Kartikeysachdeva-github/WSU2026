# COMP2029 DevOps Project

## Student

**Name:** Kartikey Sachdeva  
**Project:** AWS infrastructure using the AWS Cloud Development Kit (CDK)  
**Language:** Python  
**AWS Region:** `us-east-1`

## Project Overview

This repository contains my practical work for COMP2029 DevOps. The project uses AWS CDK with Python to define and deploy an automated website-health monitoring system.

The solution monitors Western Sydney University, AWS and GitHub. It publishes availability and latency metrics to Amazon CloudWatch, displays the results on a dashboard, generates alarms, publishes alarm notifications through Amazon SNS and stores alarm events in Amazon DynamoDB.

## Project Architecture

```text
EventBridge schedule
        |
        v
Website-monitoring Lambda
        |
        v
CloudWatch metrics
        |
        +----> CloudWatch dashboard
        |
        +----> CloudWatch alarms
                       |
                       v
                   SNS topic
                       |
                       v
              Alarm-logger Lambda
                       |
                       v
                DynamoDB table
```

## Project Structure

```text
Kartikey/
|-- kartikey/
|   |-- resources/
|   |   |-- alarmLogger.py
|   |   |-- constants.py
|   |   |-- CWPutData.py
|   |   |-- webHealth.py
|   |   `-- websites.json
|   |-- __init__.py
|   `-- kartikey_stack.py
|-- tests/
|   `-- unit/
|-- .gitignore
|-- app.py
|-- cdk.json
|-- README.md
|-- RUNBOOK.md
|-- requirements.txt
`-- requirements-dev.txt
```

- `app.py` creates the CDK application and loads the stack.
- `kartikey/kartikey_stack.py` defines the AWS infrastructure.
- `webHealth.py` checks the configured websites and publishes metrics.
- `alarmLogger.py` receives SNS messages and stores alarm events.
- `constants.py` stores reusable project configuration.
- `websites.json` contains the monitored website list.
- `RUNBOOK.md` provides operational and troubleshooting instructions.

## Setup Instructions

### 1. Clone the repository

```powershell
git clone https://github.com/Kartikeysachdeva-github/WSU2026.git
cd WSU2026\Kartikey
```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install the dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Verify the AWS identity

```powershell
aws sts get-caller-identity
```

### 5. Synthesise the CloudFormation template

```powershell
cdk synth
```

### 6. Review infrastructure changes

```powershell
cdk diff
```

### 7. Deploy the project

```powershell
cdk deploy
```

## Useful CDK Commands

| Command | Purpose |
|---|---|
| `cdk ls` | Lists the stacks in the application |
| `cdk synth` | Generates the CloudFormation template |
| `cdk diff` | Previews infrastructure changes |
| `cdk deploy` | Deploys the stack to AWS |
| `cdk destroy` | Removes non-retained stack resources |

## Week 1: Development Environment and Project Setup

The following tasks were completed:

- Installed Python, Visual Studio Code and Node.js.
- Installed and configured the AWS CLI.
- Installed the AWS CDK CLI.
- Forked and cloned the course repository.
- Created the `Kartikey` project directory.
- Initialised a Python CDK application.
- Created and activated a Python virtual environment.
- Installed the project dependencies.
- Verified the application using `cdk synth`.
- Configured `.gitignore` to exclude generated files.

## Week 2: Lambda Website Monitoring

An AWS Lambda function named `kartikey-web-health` was created using AWS CDK.

The function:

- Sends an HTTP request to the configured website.
- Determines whether the website is available.
- Measures latency in milliseconds.
- Publishes `Availability` and `Latency` metrics.
- Uses the `Kartikey/WebsiteMonitoring` namespace.

A successful website check records availability as `1`. A failed check records availability as `0`.

## Week 3: Automated Multi-Website Monitoring

The Lambda function was extended into an automated multi-site crawler.

The system now:

- Reads website information from `websites.json`.
- Checks Western Sydney University, AWS and GitHub.
- Publishes separate metrics using the `Website` dimension.
- Runs every five minutes through Amazon EventBridge.
- Displays website health on a CloudWatch dashboard.
- Creates availability and latency alarms for every website.

### Monitored Websites

| Website | URL |
|---|---|
| Western Sydney University | `https://www.westernsydney.edu.au/` |
| AWS | `https://aws.amazon.com/` |
| GitHub | `https://github.com/` |

### Monitoring Configuration

| Setting | Value |
|---|---|
| AWS Region | `us-east-1` |
| Schedule | Every five minutes |
| Metric namespace | `Kartikey/WebsiteMonitoring` |
| Availability threshold | Below `1` |
| Latency threshold | Above `3000 ms` |
| Evaluation periods | `1` |
| Dashboard | `Kartikey-Website-Health-Dashboard` |

Six CloudWatch alarms were created:

- Three availability alarms
- Three latency alarms

## Week 4 and Week 5: Dashboard, Alarms and Documentation

The project dashboard, alarms, README, runbook and GitHub Project board were completed and reviewed.

The CloudWatch dashboard displays:

- Availability data for all three websites
- Latency data for all three websites

Week 5 introduced no additional project task and was used to complete the existing backlog.

## Week 6: SNS Notifications and DynamoDB Alarm Logging

During Week 6, the monitoring system was extended so CloudWatch alarms can publish notifications and store alarm events.

The following resources were added:

- SNS topic: `kartikey-website-alarm-notifications`
- Logging Lambda: `kartikey-alarm-logger`
- DynamoDB table: `Kartikey-Website-Alarm-Logs`
- SNS alarm actions for all six CloudWatch alarms
- SNS subscription connecting the topic to the logging Lambda
- IAM permission allowing the logging Lambda to write to DynamoDB

### Alarm-Logging Process

When a website alarm enters the `ALARM` state:

1. CloudWatch publishes the alarm notification to SNS.
2. SNS invokes `kartikey-alarm-logger`.
3. The Lambda reads the alarm notification.
4. The Lambda writes the alarm name, state, reason and timestamp to DynamoDB.

### DynamoDB Schema

| Attribute | Purpose |
|---|---|
| `alarm_id` | Unique partition key generated for each event |
| `timestamp` | Sort key containing the event time |
| `alarm_name` | Name of the CloudWatch alarm |
| `new_state` | New state reported by CloudWatch |
| `reason` | Reason for the state change |

The table uses on-demand billing through `PAY_PER_REQUEST`.

### Week 6 Deployment Verification

The updated stack completed successfully:

```text
KartikeyStack: UPDATE_COMPLETE
```

The synthesised template contained:

- DynamoDB table
- SNS topic
- Alarm-logger Lambda
- SNS Lambda subscription
- DynamoDB write permissions
- SNS actions on all six alarms

### Week 6 End-to-End Test

`GitHub-Availability-Alarm` was temporarily changed from `OK` to `ALARM`.

The resulting DynamoDB record contained:

| Field | Result |
|---|---|
| Alarm | `GitHub-Availability-Alarm` |
| State | `ALARM` |
| Reason | `Week 6 end-to-end SNS and DynamoDB test` |
| DynamoDB write | Successful |

This verified the complete workflow:

```text
CloudWatch alarm -> SNS -> alarm-logger Lambda -> DynamoDB
```

## AWS CDK Code Source Map

| Project code | Purpose | Official AWS CDK Python API v2 source |
|---|---|---|
| `lambda_.Function` | Creates both Lambda functions | [Lambda Function](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html) |
| `lambda_.Code.from_asset` | Packages the Lambda source files | [Lambda Code](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Code.html) |
| `lambda_.Runtime.PYTHON_3_13` | Selects the Python runtime | [Lambda Runtime](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Runtime.html) |
| `Duration.seconds` | Configures Lambda timeouts | [CDK Duration](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/Duration.html) |
| `iam.PolicyStatement` | Grants permission to publish metrics | [IAM PolicyStatement](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html) |
| `events.Rule` | Creates the EventBridge schedule | [EventBridge Rule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Rule.html) |
| `events.Schedule.rate` | Runs the crawler every five minutes | [EventBridge Schedule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Schedule.html) |
| `targets.LambdaFunction` | Connects EventBridge to Lambda | [Lambda Event Target](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/LambdaFunction.html) |
| `cloudwatch.Metric` | Represents each website metric | [CloudWatch Metric](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Metric.html) |
| `cloudwatch.Dashboard` | Creates the health dashboard | [CloudWatch Dashboard](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Dashboard.html) |
| `cloudwatch.GraphWidget` | Displays metrics on the dashboard | [CloudWatch GraphWidget](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/GraphWidget.html) |
| `cloudwatch.Alarm` | Creates website-health alarms | [CloudWatch Alarm](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html) |
| `sns.Topic` | Creates the alarm notification topic | [SNS Topic](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns/Topic.html) |
| `sns_subscriptions.LambdaSubscription` | Subscribes the logger Lambda to SNS | [Lambda Subscription](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns_subscriptions/LambdaSubscription.html) |
| `cloudwatch_actions.SnsAction` | Connects each alarm to SNS | [SNS Alarm Action](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch_actions/SnsAction.html) |
| `dynamodb.Table` | Creates the alarm-log table | [DynamoDB Table](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html) |
| `dynamodb.Attribute` | Defines the table keys | [DynamoDB Attribute](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Attribute.html) |
| `dynamodb.BillingMode` | Configures on-demand billing | [DynamoDB BillingMode](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/BillingMode.html) |

## References

- [AWS CDK Python API v2](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [AWS CDK Python Guide](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html)
- [AWS CDK Getting Started](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)

## Generative AI Acknowledgement

ChatGPT was used to explain concepts, troubleshoot the development environment and improve documentation. All commands and CDK constructs were reviewed against the official AWS CDK documentation.