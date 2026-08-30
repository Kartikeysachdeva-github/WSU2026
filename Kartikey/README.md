# COMP2029 DevOps Project

## Student

**Name:** Kartikey Sachdeva  
**Project:** AWS Infrastructure using the AWS Cloud Development Kit (CDK)  
**Language:** Python

## Project Overview

This repository contains my practical work for COMP2029 DevOps. The project uses AWS CDK with Python to define AWS infrastructure as code. The infrastructure created through CDK is synthesised into an AWS CloudFormation template.

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
- `kartikey/resources/` contains separate modules for project resources.
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

## References

- [AWS CDK Python API Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [AWS CDK Python Guide](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html)
- [AWS CDK Getting Started](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)
- [AWS CLI Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS Lambda CDK Tutorial](https://docs.aws.amazon.com/lambda/latest/dg/lambda-cdk-tutorial.html)

## Generative AI Acknowledgement

ChatGPT was used to help explain concepts, troubleshoot the local development environment and improve documentation. All commands and CDK constructs were checked against the official AWS documentation.