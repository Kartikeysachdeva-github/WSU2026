from aws_cdk import (
    Environment,
    SecretValue,
    Stack,
    Stage,
    aws_codepipeline_actions as pipeline_actions,
    pipelines,
)
from constructs import Construct

from .kartikey_stack import KartikeyStack


# Official AWS CDK Python API v2 reference:
# https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/Stage.html
class WebsiteHealthStage(Stage):
    """Deploy a separate copy of the website health monitor."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        KartikeyStack(
            self,
            "WebsiteHealth",
            environment_name=environment_name,
        )


# Official AWS CDK Python API v2 reference:
# https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipeline.html
class KartikeyPipelineStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        deployment_environment = Environment(
            account=self.account,
            region=self.region,
        )

        # Read the GitHub token from Secrets Manager.
        # Polling checks for changes without creating a webhook.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/CodePipelineSource.html
        source = pipelines.CodePipelineSource.git_hub(
            "Kartikeysachdeva-github/WSU2026",
            "main",
            authentication=SecretValue.secrets_manager(
                "github-token"
            ),
            trigger=pipeline_actions.GitHubTrigger.POLL,
        )

        # CodeBuild starts at the repository root.
        # The CDK application is inside the Kartikey folder.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/ShellStep.html
        pipeline = pipelines.CodePipeline(
            self,
            "WebsiteHealthPipeline",
            pipeline_name="Kartikey-Website-Health-Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "cd Kartikey",
                    "npm install -g aws-cdk",
                    "python -m pip install -r requirements.txt",
                    "python -m compileall -q app.py kartikey",
                    "cdk synth",
                ],
                primary_output_directory="Kartikey/cdk.out",
            ),
        )

        # Deploy the test environment first.
        pipeline.add_stage(
            WebsiteHealthStage(
                self,
                "Beta",
                environment_name="Beta",
                env=deployment_environment,
            )
        )

        # Pause before production so Beta can be checked.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.pipelines/ManualApprovalStep.html
        pipeline.add_stage(
            WebsiteHealthStage(
                self,
                "Prod",
                environment_name="Prod",
                env=deployment_environment,
            ),
            pre=[
                pipelines.ManualApprovalStep(
                    "ApproveProd",
                    comment=(
                        "Check Beta metrics, alarms and DynamoDB "
                        "logging before approving Prod."
                    ),
                )
            ],
        )