#!/usr/bin/env python3

import aws_cdk as cdk

from kartikey.kartikey_stack import KartikeyStack
from kartikey.pipeline_stack import KartikeyPipelineStack


app = cdk.App()

deployment_environment = cdk.Environment(
    account="715054189400",
    region="us-east-1",
)

# Keep the existing monitor available as its original stack.
KartikeyStack(
    app,
    "KartikeyStack",
    env=deployment_environment,
)

# The pipeline manages the separate Beta and Prod deployments.
KartikeyPipelineStack(
    app,
    "KartikeyPipelineStack",
    env=deployment_environment,
)

app.synth()