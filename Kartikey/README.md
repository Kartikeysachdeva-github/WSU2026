# COMP2029 DevOps Project

## Student

**Name:** Kartikey Sachdeva  
**Project:** AWS Infrastructure using the AWS Cloud Development Kit (CDK)  
**Language:** Python

## Project Overview

This repository contains my practical work for COMP2029 DevOps. The project uses AWS CDK with Python to define AWS infrastructure as code. CDK synthesises the infrastructure into an AWS CloudFormation template.

## Week 1: Development Environment and Project Setup

The following tasks were completed during Week 1:

- Installed Python and Visual Studio Code.
- Installed Node.js.
- Installed and configured the AWS CLI.
- Installed the AWS CDK CLI.
- Forked the course repository on GitHub.
- Cloned the forked repository to the local machine.
- Created the `Kartikey` project directory.
- Initialised a Python CDK application.
- Created and activated a Python virtual environment.
- Installed the dependencies from `requirements.txt`.
- Verified the project using `cdk synth`.
- Configured `.gitignore` to exclude the virtual environment, Python cache files and CDK output.

## Project Structure

```text
Kartikey/
├── kartikey/
│   ├── resources/
│   ├── __init__.py
│   └── kartikey_stack.py
├── tests/
│   └── unit/
├── .gitignore
├── app.py
├── cdk.json
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

- `app.py` creates the CDK application and loads the stack.
- `kartikey/kartikey_stack.py` defines the AWS CDK stack.
- `kartikey/resources/` contains the Lambda handler and supporting resource modules.
- `tests/unit/` contains the project’s unit tests.
- `cdk.json` tells the CDK Toolkit how to run the application.
- `requirements.txt` contains the required Python packages.

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

### 4. Verify the AWS configuration

```powershell
aws sts get-caller-identity
```

### 5. Synthesise the CloudFormation template

```powershell
cdk synth
```

The `cdk synth` command completed successfully and generated the project’s AWS CloudFormation template.

## Useful CDK Commands

| Command | Purpose |
|---|---|
| `cdk ls` | Lists the stacks in the application |
| `cdk synth` | Generates the CloudFormation template |
| `cdk diff` | Shows infrastructure changes |
| `cdk deploy` | Deploys the stack to AWS |
| `cdk destroy` | Removes the deployed stack |

## Week 2: Lambda Website Monitoring

During Week 2, I created and deployed an AWS Lambda function using AWS CDK and Python.

The Lambda function monitors the Western Sydney University website and:

- Sends an HTTP request to the website.
- Records whether the website is available.
- Measures the website response time.
- Publishes `Availability` and `ResponseTime` as custom CloudWatch metrics.
- Runs in the `us-east-1` AWS Region.

### Deployment Verification

The CDK application was synthesised and deployed successfully.

The deployed Lambda function is:

```text
kartikey-web-health
```

The custom metrics were confirmed in the following CloudWatch namespace:

```text
Kartikey/WebsiteMonitoring
```

The namespace contains:

- `Availability`
- `ResponseTime`

### Test Result

A manual invocation of the deployed Lambda returned:

- HTTP status: `200`
- Availability: `1`
- Response time: approximately `2228 ms`

This confirmed that the Lambda successfully reached the monitored website and published its health metrics.

## Week 2 Code Source Map

| Project code | Purpose | Official AWS source |
|---|---|---|
| `lambda_.Function` | Creates the Lambda function | [Lambda Function](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html) |
| `lambda_.Code.from_asset` | Packages the local Lambda code | [Lambda Code](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Code.html) |
| `lambda_.Runtime.PYTHON_3_13` | Selects the Python runtime | [Lambda Runtime](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Runtime.html) |
| `Duration.seconds` | Configures the Lambda timeout | [CDK Duration](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/Duration.html) |
| `iam.PolicyStatement` | Grants permission to publish metrics | [IAM PolicyStatement](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html) |
| `put_metric_data` | Publishes custom CloudWatch metrics | [Boto3 PutMetricData](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html) |

## Week 3: Automated Multi-Website Monitoring

During Week 3, I extended the Week 2 Lambda function into an automated multi-website crawler.

The system now:

- Reads a custom list of websites from `websites.json`.
- Checks Western Sydney University, AWS and GitHub.
- Records availability as `1` or `0`.
- Measures latency in milliseconds.
- Publishes separate CloudWatch metrics using the `Website` dimension.
- Runs automatically every five minutes using Amazon EventBridge.
- Displays website health through a CloudWatch dashboard.
- Uses availability and latency alarms to detect problems.

### Monitoring Architecture

```text
EventBridge schedule
        |
        v
Lambda web crawler
        |
        v
Read websites.json
        |
        v
Check each website
        |
        v
Publish availability and latency
        |
        +----> CloudWatch dashboard
        |
        +----> CloudWatch alarms
```

### Monitored Websites

| Website | URL |
|---|---|
| Western Sydney University | https://www.westernsydney.edu.au/ |
| AWS | https://aws.amazon.com/ |
| GitHub | https://github.com/ |

### Monitoring Configuration

| Setting | Value |
|---|---|
| AWS Region | `us-east-1` |
| Schedule | Every 5 minutes |
| Metric namespace | `Kartikey/WebsiteMonitoring` |
| Availability threshold | Below `1` |
| Latency threshold | Above `3000 ms` |
| Evaluation periods | `1` |
| Dashboard | `Kartikey-Website-Health-Dashboard` |

### Deployment Verification

The multi-website crawler was successfully synthesised and deployed using AWS CDK.

A manual test returned:

| Website | HTTP status | Availability | Example latency |
|---|---:|---:|---:|
| Western Sydney University | 200 | 1 | 548.07 ms |
| AWS | 200 | 1 | 91.89 ms |
| GitHub | 200 | 1 | 40.20 ms |

CloudWatch confirmed separate `Availability` and `Latency` metrics for all three websites. Six CloudWatch alarms were created: one availability alarm and one latency alarm for each website.

### Week 3 Code Sources

| Project code | Purpose | Official AWS documentation |
|---|---|---|
| `events.Rule` | Creates the automatic EventBridge rule | [EventBridge Rule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Rule.html) |
| `events.Schedule.rate` | Runs the crawler every five minutes | [EventBridge Schedule](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Schedule.html) |
| `targets.LambdaFunction` | Connects EventBridge to Lambda | [Lambda event target](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/LambdaFunction.html) |
| `cloudwatch.Metric` | Represents each website metric | [CloudWatch Metric](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Metric.html) |
| `cloudwatch.Dashboard` | Creates the monitoring dashboard | [CloudWatch Dashboard](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Dashboard.html) |
| `cloudwatch.GraphWidget` | Displays metrics on the dashboard | [CloudWatch GraphWidget](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/GraphWidget.html) |
| `cloudwatch.Alarm` | Creates availability and latency alarms | [CloudWatch Alarm](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html) |
| `put_metric_data` | Publishes custom metrics from Lambda | [Boto3 PutMetricData](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html) |

## References

- [AWS CDK Python API Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [AWS CDK Python Guide](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html)
- [AWS CDK Getting Started](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)
- [AWS CLI Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS Lambda CDK Tutorial](https://docs.aws.amazon.com/lambda/latest/dg/lambda-cdk-tutorial.html)

## Generative AI Acknowledgement

ChatGPT was used to help explain concepts, troubleshoot the local development environment and improve documentation. All commands and CDK constructs were checked against official AWS documentation.