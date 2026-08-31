from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct


class KartikeyStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Source:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        web_health_function = lambda_.Function(
            self,
            "WebHealthFunction",
            function_name="kartikey-web-health",
            description="Checks a website and publishes health metrics",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="webHealth.handler",
            code=lambda_.Code.from_asset("kartikey/resources"),
            timeout=Duration.seconds(15),
            environment={
                "WEBSITE_URL": "https://www.westernsydney.edu.au/",
                "METRIC_NAMESPACE": "Kartikey/WebsiteMonitoring",
            },
        )

        # Source:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html
        web_health_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )